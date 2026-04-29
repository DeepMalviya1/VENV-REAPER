"""Tests for the parallel system_scan + Repository integration."""

from __future__ import annotations

from pathlib import Path

import pytest

import importlib

ss_module = importlib.import_module("venv_reaper.core.system_scan")
from venv_reaper.core.system_scan import (
    find_project_dir,
    parse_python_version,
    quick_hash,
    system_scan,
)
from venv_reaper.index.repository import Repository


@pytest.fixture(autouse=True)
def _allow_tmp(monkeypatch: pytest.MonkeyPatch) -> None:
    """pytest's tmp_path lives under /tmp which is in the prod skip list."""
    monkeypatch.setattr(ss_module, "_is_blocked_root", lambda p: False)


def _make_venv(root: Path, name: str = "venv", *, py_version: str = "3.11.5") -> Path:
    venv = root / name
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text(f"home = /usr/bin\nversion = {py_version}\n")
    (venv / "bin" / "python").write_text("#!/bin/sh\n")
    (venv / "lib" / "site-packages").mkdir(parents=True)
    (venv / "lib" / "site-packages" / "fake.py").write_text("x" * 1000)
    return venv


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(db_path=tmp_path / "index.db")


def test_parse_python_version(tmp_path: Path) -> None:
    venv = _make_venv(tmp_path, py_version="3.12.1")
    assert parse_python_version(venv) == "3.12.1"


def test_quick_hash_changes_with_mtime(tmp_path: Path) -> None:
    venv = _make_venv(tmp_path)
    h1 = quick_hash(venv)
    # touch python with new mtime
    py = venv / "bin" / "python"
    py.write_text("#!/bin/sh\n# changed\n")
    h2 = quick_hash(venv)
    assert h1 != h2


def test_find_project_dir_detects_pyproject(tmp_path: Path) -> None:
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='x'\n")
    venv = _make_venv(project, ".venv")

    assert find_project_dir(venv) == project


def test_find_project_dir_returns_none(tmp_path: Path) -> None:
    venv = _make_venv(tmp_path)
    # tmp_path has no project markers
    assert find_project_dir(venv) is None


def test_system_scan_indexes_venvs(tmp_path: Path, repo: Repository) -> None:
    project = tmp_path / "code" / "alpha"
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='alpha'\n")
    _make_venv(project, ".venv")

    other = tmp_path / "scratch"
    other.mkdir()
    _make_venv(other, "venv")

    stats = system_scan(roots=[tmp_path], repo=repo, incremental=False, max_workers=4)

    assert stats.envs_found == 2
    envs = repo.list_envs()
    assert len(envs) == 2
    paths = {Path(e.path).name for e in envs}
    assert paths == {".venv", "venv"}
    # project_dir linkage worked for the one with pyproject.toml
    alpha = next(e for e in envs if e.path.endswith(".venv"))
    assert alpha.project_dir == str(project)


def test_system_scan_incremental_skips_unchanged(
    tmp_path: Path, repo: Repository
) -> None:
    _make_venv(tmp_path, "venv")

    s1 = system_scan(roots=[tmp_path], repo=repo, incremental=False)
    assert s1.envs_found == 1

    s2 = system_scan(roots=[tmp_path], repo=repo, incremental=True)
    assert s2.envs_skipped_unchanged == 1
    assert s2.envs_found == 0


def test_system_scan_prunes_deleted(tmp_path: Path, repo: Repository) -> None:
    venv = _make_venv(tmp_path, "venv")
    system_scan(roots=[tmp_path], repo=repo, incremental=False)
    assert len(repo.list_envs()) == 1

    # remove venv from disk
    import shutil
    shutil.rmtree(venv)

    system_scan(roots=[tmp_path], repo=repo, incremental=False)
    assert repo.list_envs() == []


def test_system_scan_records_scan_history(tmp_path: Path, repo: Repository) -> None:
    _make_venv(tmp_path, "venv")
    system_scan(roots=[tmp_path], repo=repo, incremental=False)

    last = repo.last_scan(str(tmp_path))
    assert last is not None
    assert last.envs_found == 1
    assert last.duration_ms is not None and last.duration_ms >= 0
