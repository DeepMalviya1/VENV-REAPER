"""Day-1 smoke tests: package imports cleanly and discovery finds a fake venv."""

from __future__ import annotations

from pathlib import Path

import pytest

from venv_reaper.core import (
    SKIP_DIRS,
    VENV_MARKERS,
    dir_size,
    find_req,
    fmt_size,
    is_venv,
    scan_directory,
    size_color,
)
from venv_reaper.theme import load_css, load_matrix_rain_js, matrix_rain_block, style_block


def _make_fake_venv(root: Path, name: str = "venv") -> Path:
    """Create a directory that satisfies the venv markers."""
    venv = root / name
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (venv / "bin" / "python").write_text("#!/bin/sh\n")
    (venv / "lib").mkdir()
    (venv / "lib" / "site-packages").mkdir()
    (venv / "lib" / "site-packages" / "fake.py").write_text("x = 1\n" * 100)
    return venv


# ──────────────────────────────────────────────────────────────────────────────
# Markers
# ──────────────────────────────────────────────────────────────────────────────
def test_marker_constants_are_frozen() -> None:
    assert "pyvenv.cfg" in VENV_MARKERS
    assert ".git" in SKIP_DIRS
    with pytest.raises(AttributeError):
        VENV_MARKERS.add("nope")  # type: ignore[attr-defined]


def test_is_venv_true_and_false(tmp_path: Path) -> None:
    venv = _make_fake_venv(tmp_path)
    assert is_venv(venv) is True
    assert is_venv(tmp_path / "not_a_venv") is False


# ──────────────────────────────────────────────────────────────────────────────
# Sizing
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "n, expected_unit",
    [(0, "B"), (500, "B"), (2048, "KB"), (5 * 1024**2, "MB"), (3 * 1024**3, "GB")],
)
def test_fmt_size_units(n: int, expected_unit: str) -> None:
    _, unit = fmt_size(n)
    assert unit == expected_unit


def test_size_color_thresholds() -> None:
    assert size_color(10 * 1024**2) == "#00ff41"
    assert size_color(100 * 1024**2) == "#f0e040"
    assert size_color(300 * 1024**2) == "#ff8c00"
    assert size_color(1024 * 1024**2) == "#ff2222"


def test_dir_size_counts_bytes(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"x" * 1000)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_bytes(b"y" * 500)
    assert dir_size(tmp_path) == 1500


# ──────────────────────────────────────────────────────────────────────────────
# Requirements
# ──────────────────────────────────────────────────────────────────────────────
def test_find_req_in_parent(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    venv = _make_fake_venv(project)
    req = project / "requirements.txt"
    req.write_text("requests==2.31.0\n")
    assert find_req(venv) == req


def test_find_req_returns_none_when_absent(tmp_path: Path) -> None:
    venv = _make_fake_venv(tmp_path)
    assert find_req(venv) is None


# ──────────────────────────────────────────────────────────────────────────────
# Discovery
# ──────────────────────────────────────────────────────────────────────────────
def test_scan_directory_finds_nested_venv(tmp_path: Path) -> None:
    project = tmp_path / "code" / "myapp"
    project.mkdir(parents=True)
    _make_fake_venv(project, ".venv")

    results = scan_directory(tmp_path)

    assert len(results) == 1
    r = results[0]
    assert r["ENV NAME"] == ".venv"
    assert r["_size_bytes"] > 0
    assert r["REQUIREMENTS"].endswith("MISSING")
    assert r["DEPTH"] == 2


def test_scan_directory_skips_skip_dirs(tmp_path: Path) -> None:
    skipped = tmp_path / ".git"
    skipped.mkdir()
    _make_fake_venv(skipped, "venv")

    results = scan_directory(tmp_path)
    assert results == []


def test_scan_directory_does_not_recurse_into_venv(tmp_path: Path) -> None:
    """A nested fake-venv inside a real venv must not be reported separately."""
    outer = _make_fake_venv(tmp_path, "outer")
    _make_fake_venv(outer / "lib", "inner")

    results = scan_directory(tmp_path)
    assert len(results) == 1
    assert results[0]["ENV NAME"] == "outer"


# ──────────────────────────────────────────────────────────────────────────────
# Theme assets
# ──────────────────────────────────────────────────────────────────────────────
def test_theme_assets_load() -> None:
    css = load_css()
    js = load_matrix_rain_js()
    assert ":root" in css
    assert "--green:      #00ff41" in css
    assert "matrix-canvas" in js


def test_style_and_matrix_blocks_are_wrapped() -> None:
    assert style_block().startswith("<style>")
    assert style_block().rstrip().endswith("</style>")
    assert matrix_rain_block().startswith("<script>")
    assert matrix_rain_block().rstrip().endswith("</script>")
