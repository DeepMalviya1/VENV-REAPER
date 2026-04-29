"""Tests for the SQLite index and Repository."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from venv_reaper.index.repository import EnvRow, Repository


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(db_path=tmp_path / "index.db")


def test_schema_initialises(repo: Repository) -> None:
    rows = repo.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert {"envs", "packages", "imports", "vulns", "scans", "schema_version"} <= names

    version = repo.conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == 1


def test_upsert_and_get(repo: Repository) -> None:
    env = EnvRow(path="/x/venv", name="venv", size_bytes=123, hash_quick="abc")
    rid = repo.upsert_env(env)
    assert rid > 0

    fetched = repo.get_env("/x/venv")
    assert fetched is not None
    assert fetched.name == "venv"
    assert fetched.size_bytes == 123
    assert fetched.hash_quick == "abc"


def test_upsert_updates_existing(repo: Repository) -> None:
    repo.upsert_env(EnvRow(path="/x/venv", name="venv", size_bytes=100))
    repo.upsert_env(EnvRow(path="/x/venv", name="venv", size_bytes=200, hash_quick="new"))

    rows = repo.conn.execute("SELECT COUNT(*) FROM envs").fetchone()[0]
    assert rows == 1
    fetched = repo.get_env("/x/venv")
    assert fetched and fetched.size_bytes == 200
    assert fetched.hash_quick == "new"


def test_user_tag_preserved_on_upsert(repo: Repository) -> None:
    repo.upsert_env(EnvRow(path="/p", user_tag="keep"))
    repo.upsert_env(EnvRow(path="/p", user_tag=None))
    fetched = repo.get_env("/p")
    assert fetched and fetched.user_tag == "keep"


def test_list_envs_filters(repo: Repository) -> None:
    repo.upsert_env(EnvRow(path="/a", size_bytes=10, keep_probability=0.05))
    repo.upsert_env(EnvRow(path="/b", size_bytes=20, keep_probability=0.5))
    repo.upsert_env(EnvRow(path="/c", size_bytes=30, keep_probability=0.95))

    cruft = repo.list_envs(keep_prob_lt=0.2)
    assert [e.path for e in cruft] == ["/a"]

    by_size = repo.list_envs(order_by="size_bytes ASC")
    assert [e.size_bytes for e in by_size] == [10, 20, 30]


def test_scan_lifecycle(repo: Repository) -> None:
    sid = repo.start_scan(root="/", mode="full")
    time.sleep(0.01)
    repo.finish_scan(sid, envs_found=5, duration_ms=42)

    last = repo.last_scan("/")
    assert last is not None
    assert last.envs_found == 5
    assert last.duration_ms == 42


def test_prune_missing(repo: Repository, tmp_path: Path) -> None:
    real = tmp_path / "real_venv"
    real.mkdir()
    fake = "/nonexistent/ghost"

    repo.upsert_env(EnvRow(path=str(real)))
    repo.upsert_env(EnvRow(path=fake))

    pruned = repo.prune_missing(seen_paths={str(real)})
    assert pruned == 1
    assert repo.get_env(fake) is None
    assert repo.get_env(str(real)) is not None
