"""End-to-end tests for the `reaper` CLI using typer.testing."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner


def _make_venv(root: Path, name: str = "venv") -> Path:
    venv = root / name
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.11.5\n")
    (venv / "bin" / "python").write_text("#!/bin/sh")
    (venv / "lib" / "site-packages").mkdir(parents=True)
    (venv / "lib" / "site-packages" / "f.py").write_text("x" * 500)
    return venv


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate XDG dirs + bypass /tmp skip filter; return (runner, app)."""
    monkeypatch.setenv("XDG_DATA_HOME",  str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    # Re-import modules so they pick up the new env.
    for mod in [
        "venv_reaper.config",
        "venv_reaper.index.db",
        "venv_reaper.index.repository",
        "venv_reaper.index",
        "venv_reaper.core.system_scan",
        "venv_reaper.core.quarantine",
        "venv_reaper.core",
        "venv_reaper.cli.main",
        "venv_reaper.cli",
    ]:
        if mod in importlib.sys.modules:
            importlib.reload(importlib.sys.modules[mod])

    ss_mod = importlib.import_module("venv_reaper.core.system_scan")
    monkeypatch.setattr(ss_mod, "_is_blocked_root", lambda p: False)

    cli_main = importlib.import_module("venv_reaper.cli.main")
    return CliRunner(), cli_main.app


def test_version(cli_env) -> None:
    runner, app = cli_env
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "venv-reaper" in result.stdout


def test_list_empty_index(cli_env) -> None:
    runner, app = cli_env
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 1
    assert "Index is empty" in result.stdout


def test_scan_then_list_then_inspect(cli_env, tmp_path: Path) -> None:
    runner, app = cli_env
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='x'\n")
    _make_venv(project, ".venv")

    r1 = runner.invoke(app, ["scan", "--root", str(tmp_path), "--full", "--quiet"])
    assert r1.exit_code == 0, r1.stdout
    assert "Indexed" in r1.stdout

    r2 = runner.invoke(app, ["list"])
    assert r2.exit_code == 0
    assert ".venv" in r2.stdout

    # parse the env id from the table — first numeric token after the header rows
    r3 = runner.invoke(app, ["inspect", "1"])
    assert r3.exit_code == 0
    assert "ENV #1" in r3.stdout
    assert "3.11.5" in r3.stdout


def test_kill_and_restore_roundtrip(cli_env, tmp_path: Path) -> None:
    runner, app = cli_env
    venv = _make_venv(tmp_path, "victim")

    runner.invoke(app, ["scan", "--root", str(tmp_path), "--full", "--quiet"])

    # Kill non-interactively
    r_kill = runner.invoke(app, ["kill", "1", "--yes"])
    assert r_kill.exit_code == 0, r_kill.stdout
    assert "INTERRED" in r_kill.stdout
    assert not venv.exists()  # actually moved

    # Crypt has the entry
    r_crypt = runner.invoke(app, ["crypt", "list"])
    assert r_crypt.exit_code == 0
    assert "REAPER CRYPT" in r_crypt.stdout

    # Pull the entry id (8 hex chars) from the original_path → crypt_dir
    from venv_reaper.core.quarantine import list_entries
    entries = list_entries()
    assert len(entries) == 1
    eid = entries[0].id

    r_restore = runner.invoke(app, ["restore", eid])
    assert r_restore.exit_code == 0, r_restore.stdout
    assert venv.exists()
    assert (venv / "pyvenv.cfg").exists()


def test_kill_dry_run_does_not_touch_disk(cli_env, tmp_path: Path) -> None:
    runner, app = cli_env
    venv = _make_venv(tmp_path, "safe")

    runner.invoke(app, ["scan", "--root", str(tmp_path), "--full", "--quiet"])
    r = runner.invoke(app, ["kill", "1", "--dry-run"])
    assert r.exit_code == 0
    assert "Dry run" in r.stdout
    assert venv.exists()


def test_kill_unknown_id(cli_env) -> None:
    runner, app = cli_env
    r = runner.invoke(app, ["kill", "9999", "--yes"])
    assert r.exit_code == 1
    assert "Unknown" in r.stdout
