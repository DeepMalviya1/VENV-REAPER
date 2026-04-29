"""SQLite connection + bootstrap. The daemon owns writes; readers are non-blocking via WAL."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator

from venv_reaper.config import index_db_path


def _schema() -> str:
    return files("venv_reaper.index").joinpath("schema.sql").read_text(encoding="utf-8")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with WAL + foreign keys enabled."""
    path = db_path or index_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Open + apply schema (idempotent)."""
    conn = connect(db_path)
    conn.executescript(_schema())
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
