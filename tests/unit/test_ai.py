"""Tests for the AI layer: import sweep, mapping, installed parser, reconciler."""

from __future__ import annotations

from pathlib import Path

import pytest

from venv_reaper.ai.import_sweep import sweep_file, sweep_project
from venv_reaper.ai.imports_to_packages import map_imports_to_packages, map_one
from venv_reaper.ai.installed import installed_packages, installed_registry
from venv_reaper.ai.reconciler import reconcile


# ──────────────────────────────────────────────────────────────────────────────
# Helpers to build a fake project + venv on disk
# ──────────────────────────────────────────────────────────────────────────────
def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _fake_dist(sp: Path, *, name: str, version: str, top: list[str]) -> None:
    info = sp / f"{name}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )
    (info / "top_level.txt").write_text("\n".join(top) + "\n")


def _fake_venv_with_packages(root: Path, packages: dict[str, list[str]]) -> Path:
    """Build a venv whose site-packages contains the given dists.

    `packages` maps dist-name → top-level module list.
    """
    venv = root / ".venv"
    sp = venv / "lib" / "python3.11" / "site-packages"
    sp.mkdir(parents=True)
    (venv / "bin").mkdir()
    (venv / "bin" / "python").write_text("#!/bin/sh")
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.11.5\n")
    for name, top in packages.items():
        _fake_dist(sp, name=name, version="1.0.0", top=top)
    return venv


# ──────────────────────────────────────────────────────────────────────────────
# Import sweep
# ──────────────────────────────────────────────────────────────────────────────
def test_sweep_file_extracts_top_level(tmp_path: Path) -> None:
    f = tmp_path / "a.py"
    _write(f, "import numpy\nimport os\nfrom requests.auth import HTTPBasicAuth\n")
    mods = sweep_file(f)
    assert "numpy" in mods
    assert "requests" in mods
    assert "os" not in mods           # stdlib filtered


def test_sweep_file_skips_relative_imports(tmp_path: Path) -> None:
    f = tmp_path / "b.py"
    _write(f, "from . import sibling\nfrom ..pkg import x\nimport pandas\n")
    assert sweep_file(f) == ["pandas"]


def test_sweep_project_handles_syntax_errors(tmp_path: Path) -> None:
    _write(tmp_path / "good.py", "import requests\n")
    _write(tmp_path / "bad.py",  "def broken(:::\n")
    res = sweep_project(tmp_path)
    assert "requests" in res.modules
    assert res.files_failed == 1
    assert res.files_scanned == 1


def test_sweep_project_skips_venv_dirs(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "main.py", "import requests\n")
    _write(tmp_path / ".venv" / "lib" / "site-packages" / "x.py", "import django\n")
    res = sweep_project(tmp_path)
    assert "requests" in res.modules
    assert "django" not in res.modules


# ──────────────────────────────────────────────────────────────────────────────
# Import-to-package mapping
# ──────────────────────────────────────────────────────────────────────────────
def test_map_curated_overrides() -> None:
    # Live registry on the host can override curated mappings (intended:
    # the venv's own metadata is more accurate). We only assert the result
    # case-insensitively where casing varies between sources.
    assert map_one("cv2") == "opencv-python"
    assert map_one("PIL").lower() == "pillow"
    assert map_one("yaml").lower() in {"pyyaml", "pyyaml-include"}


def test_map_fallback_dash_replacement() -> None:
    # A module guaranteed not to be in any registry — exercise the fallback.
    assert map_one("definitely_not_real_xyz_42") == "definitely-not-real-xyz-42"


def test_map_uses_supplied_registry_first() -> None:
    out = map_imports_to_packages(["numpy"], registry={"numpy": "custom-numpy"})
    assert out["numpy"] == "custom-numpy"


# ──────────────────────────────────────────────────────────────────────────────
# Installed packages parser
# ──────────────────────────────────────────────────────────────────────────────
def test_installed_packages_reads_metadata(tmp_path: Path) -> None:
    venv = _fake_venv_with_packages(tmp_path, {
        "requests": ["requests"],
        "numpy":    ["numpy"],
    })
    pkgs = installed_packages(venv)
    names = {p.name for p in pkgs}
    assert names == {"requests", "numpy"}
    assert all(p.version == "1.0.0" for p in pkgs)


def test_installed_registry_maps_top_levels(tmp_path: Path) -> None:
    venv = _fake_venv_with_packages(tmp_path, {
        "opencv-python": ["cv2"],
        "pillow":        ["PIL"],
    })
    reg = installed_registry(venv)
    assert reg["cv2"] == "opencv-python"
    assert reg["PIL"] == "pillow"


# ──────────────────────────────────────────────────────────────────────────────
# Reconciler
# ──────────────────────────────────────────────────────────────────────────────
def test_reconcile_finds_missing_and_unused(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='x'\n")
    _write(project / "main.py", "import requests\nimport pandas\n")

    venv = _fake_venv_with_packages(project, {
        "requests": ["requests"],
        "django":   ["django"],   # installed but never imported
    })

    report = reconcile(venv)
    assert "pandas" in report.missing                       # imported, not installed
    assert "django" in report.unused                        # installed, not imported
    assert "requests" not in report.missing
    assert report.project_dir == project


def test_reconcile_requirements_diff(tmp_path: Path) -> None:
    project = tmp_path / "p2"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='y'\n")
    _write(project / "app.py", "import requests\nimport numpy\n")
    (project / "requirements.txt").write_text(
        "requests==2.31.0\n"
        "django==4.2\n"          # declared but unused
    )
    venv = _fake_venv_with_packages(project, {
        "requests": ["requests"],
    })

    report = reconcile(venv)
    assert report.requirements_path is not None
    assert "django" in report.declared_but_not_used
    assert "numpy" in report.used_but_not_declared


def test_reconcile_ignores_pip_setuptools(tmp_path: Path) -> None:
    project = tmp_path / "p3"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='z'\n")
    _write(project / "main.py", "import requests\n")
    venv = _fake_venv_with_packages(project, {
        "requests":   ["requests"],
        "pip":        ["pip"],
        "setuptools": ["setuptools"],
    })
    report = reconcile(venv)
    assert "pip" not in report.unused
    assert "setuptools" not in report.unused
