"""Read packages installed in a venv directly from `*.dist-info/METADATA`.

We do NOT activate or run the target venv (that would be slow and risky).
Instead we walk site-packages and parse the metadata files in place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_NAME = re.compile(r"^Name:\s*(.+?)\s*$", re.MULTILINE)
_VERSION = re.compile(r"^Version:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(slots=True)
class InstalledPackage:
    name: str
    version: str
    top_level: list[str]   # importable top-level modules from this dist


def _site_packages_dirs(venv: Path) -> list[Path]:
    """Find every site-packages dir inside a venv (handles posix + windows)."""
    out: list[Path] = []
    # Linux/macOS: lib/pythonX.Y/site-packages
    for lib in (venv / "lib").glob("python*"):
        sp = lib / "site-packages"
        if sp.is_dir():
            out.append(sp)
    # Windows: Lib/site-packages
    win_sp = venv / "Lib" / "site-packages"
    if win_sp.is_dir():
        out.append(win_sp)
    return out


def _parse_metadata(meta_file: Path) -> tuple[str, str] | None:
    try:
        text = meta_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    name_m = _NAME.search(text)
    ver_m = _VERSION.search(text)
    if not name_m or not ver_m:
        return None
    return name_m.group(1), ver_m.group(1)


def _read_top_level(dist_info: Path) -> list[str]:
    """Read top_level.txt if present; else infer from RECORD."""
    tl = dist_info / "top_level.txt"
    if tl.exists():
        try:
            return [
                line.strip() for line in tl.read_text(errors="replace").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        except OSError:
            pass

    record = dist_info / "RECORD"
    if not record.exists():
        return []
    tops: set[str] = set()
    try:
        for line in record.read_text(errors="replace").splitlines():
            entry = line.split(",", 1)[0]
            if not entry or entry.endswith(".dist-info") or entry.startswith(".."):
                continue
            head = entry.split("/", 1)[0]
            if head.endswith(".py"):
                head = head[:-3]
            if head and not head.endswith(".dist-info"):
                tops.add(head)
    except OSError:
        return []
    return sorted(tops)


def installed_packages(venv: Path) -> list[InstalledPackage]:
    """Return every installed distribution in `venv`. Empty if no site-packages."""
    pkgs: dict[str, InstalledPackage] = {}
    for sp in _site_packages_dirs(venv):
        for dist_info in sp.glob("*.dist-info"):
            meta = _parse_metadata(dist_info / "METADATA")
            if not meta:
                continue
            name, version = meta
            tops = _read_top_level(dist_info)
            pkgs[name.lower()] = InstalledPackage(name=name, version=version, top_level=tops)
    return sorted(pkgs.values(), key=lambda p: p.name.lower())


def installed_registry(venv: Path) -> dict[str, str]:
    """Build a {top_level_module → dist_name} registry for this venv.

    Used as the highest-confidence source by `imports_to_packages.map_one`.
    """
    out: dict[str, str] = {}
    for pkg in installed_packages(venv):
        for tl in pkg.top_level:
            out[tl] = pkg.name
    return out
