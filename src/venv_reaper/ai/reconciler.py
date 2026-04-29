"""Reconcile imports vs installed packages vs requirements.txt.

This is the headline "AI showed me what I install but never use" feature.
It is purely deterministic right now; the ML import-mapper (Phase 2) will
plug into `imports_to_packages.map_one` via the curated table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from venv_reaper.ai.import_sweep import ImportSweepResult, sweep_project
from venv_reaper.ai.imports_to_packages import map_imports_to_packages
from venv_reaper.ai.installed import InstalledPackage, installed_packages, installed_registry


@dataclass(slots=True)
class DependencyReport:
    venv: Path
    project_dir: Path | None
    sweep: ImportSweepResult
    installed: list[InstalledPackage]
    needed: dict[str, str] = field(default_factory=dict)         # module → dist
    missing: list[str] = field(default_factory=list)             # imported, not installed
    unused: list[str] = field(default_factory=list)              # installed, never imported
    requirements_path: Path | None = None
    declared_in_req: set[str] = field(default_factory=set)
    declared_but_not_used: list[str] = field(default_factory=list)
    used_but_not_declared: list[str] = field(default_factory=list)


_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def _parse_requirements(req: Path) -> set[str]:
    out: set[str] = set()
    try:
        for line in req.read_text(errors="replace").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            m = _REQ_LINE.match(line)
            if m:
                out.add(m.group(1).lower())
    except OSError:
        pass
    return out


_TRANSITIVE_NOISE = frozenset({
    # Base tooling — installed even when nobody imports them.
    "pip", "setuptools", "wheel", "pkg_resources",
})


def reconcile(
    venv: Path,
    *,
    project_dir: Path | None = None,
    requirements: Path | None = None,
) -> DependencyReport:
    """Build a full dependency report for one venv."""
    project_dir = project_dir if project_dir is not None else _infer_project(venv)
    sweep = sweep_project(project_dir) if project_dir else ImportSweepResult(project_dir=Path("."))
    installed = installed_packages(venv)
    registry = installed_registry(venv)

    # Map imports → distribution names using the venv's own registry first.
    needed = map_imports_to_packages(sweep.modules, registry=registry)

    installed_names = {p.name.lower() for p in installed}
    needed_dists = {d.lower() for d in needed.values()}

    missing = sorted(
        {mod for mod, dist in needed.items() if dist.lower() not in installed_names}
    )

    # "Unused" = installed dist whose top-level modules never appear in imports.
    used_modules = set(sweep.modules)
    unused: list[str] = []
    for pkg in installed:
        if pkg.name.lower() in _TRANSITIVE_NOISE:
            continue
        # If any of its top-level modules is imported, it's used.
        if pkg.top_level and any(tl in used_modules for tl in pkg.top_level):
            continue
        # Or if its dist name itself is in needed (covers no-top-level edge cases).
        if pkg.name.lower() in needed_dists:
            continue
        unused.append(pkg.name)
    unused.sort(key=str.lower)

    report = DependencyReport(
        venv=venv,
        project_dir=project_dir,
        sweep=sweep,
        installed=installed,
        needed=needed,
        missing=missing,
        unused=unused,
    )

    # Requirements.txt diff (best-effort).
    if requirements is None and project_dir:
        guess = project_dir / "requirements.txt"
        if guess.exists():
            requirements = guess
    if requirements and requirements.exists():
        declared = _parse_requirements(requirements)
        report.requirements_path = requirements
        report.declared_in_req = declared
        used_dists = {d.lower() for d in needed.values()}
        report.declared_but_not_used = sorted(declared - used_dists)
        report.used_but_not_declared = sorted(used_dists - declared)

    return report


def _infer_project(venv: Path) -> Path | None:
    """Climb upward from the venv looking for a project marker."""
    cur = venv.parent
    markers = ("pyproject.toml", "setup.py", "setup.cfg", "package.json", ".git")
    seen = 0
    while seen < 10:
        if any((cur / m).exists() for m in markers):
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
        seen += 1
    return None
