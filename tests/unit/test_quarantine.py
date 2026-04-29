"""Tests for Reaper Crypt — quarantine, restore, purge."""

from __future__ import annotations

from pathlib import Path

import pytest

from venv_reaper.core import quarantine


@pytest.fixture(autouse=True)
def _isolate_crypt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect crypt_dir() to a tmp folder for each test."""
    monkeypatch.setattr(quarantine, "_crypt_root", lambda: tmp_path / "crypt")


def _fake_venv(root: Path, name: str = "venv") -> Path:
    venv = root / name
    venv.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home=/usr\n")
    (venv / "bin").mkdir()
    (venv / "bin" / "python").write_text("#!/bin/sh")
    return venv


def test_inter_moves_path_atomic(tmp_path: Path) -> None:
    v = _fake_venv(tmp_path)
    entry = quarantine.inter(v, size_bytes=42)
    assert not v.exists()
    assert Path(entry.crypt_path).exists()
    assert entry.original_path == str(v)
    assert entry.size_bytes == 42


def test_list_returns_what_was_interred(tmp_path: Path) -> None:
    v1 = _fake_venv(tmp_path, "a")
    v2 = _fake_venv(tmp_path, "b")
    quarantine.inter(v1)
    quarantine.inter(v2)

    entries = quarantine.list_entries()
    paths = {e.original_path for e in entries}
    assert paths == {str(v1), str(v2)}


def test_restore_brings_it_back(tmp_path: Path) -> None:
    v = _fake_venv(tmp_path)
    entry = quarantine.inter(v)
    assert not v.exists()

    restored = quarantine.restore(entry.id)
    assert restored == v
    assert v.exists()
    assert (v / "pyvenv.cfg").exists()


def test_restore_refuses_to_overwrite(tmp_path: Path) -> None:
    v = _fake_venv(tmp_path)
    entry = quarantine.inter(v)
    # Recreate something at the original path
    v.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        quarantine.restore(entry.id)


def test_purge_expired_removes_old_only(tmp_path: Path) -> None:
    v = _fake_venv(tmp_path)
    entry = quarantine.inter(v, ttl_days=1)

    # Pretend it's 30 days from now.
    future = entry.interred_at + 30 * 86400
    n = quarantine.purge_expired(now=future)
    assert n == 1
    assert quarantine.list_entries() == []


def test_purge_expired_keeps_fresh(tmp_path: Path) -> None:
    v = _fake_venv(tmp_path)
    entry = quarantine.inter(v, ttl_days=7)
    n = quarantine.purge_expired(now=entry.interred_at + 60)
    assert n == 0
    assert len(quarantine.list_entries()) == 1
