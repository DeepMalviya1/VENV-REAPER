"""Typed CRUD over the index DB. No ORM — predictable SQL, easy to debug."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from venv_reaper.index.db import init_db, transaction


@dataclass(slots=True)
class EnvRow:
    path: str
    name: str = ""
    python_version: str | None = None
    python_exe: str | None = None
    size_bytes: int = 0
    created_at: int | None = None
    modified_at: int | None = None
    last_activated: int | None = None
    project_dir: str | None = None
    user_tag: str | None = None
    keep_probability: float | None = None
    hash_quick: str | None = None
    id: int | None = None
    last_indexed: int = field(default_factory=lambda: int(time.time()))


@dataclass(slots=True)
class ScanRow:
    started_at: int
    root: str
    mode: str
    finished_at: int | None = None
    envs_found: int | None = None
    duration_ms: int | None = None
    id: int | None = None


class Repository:
    """Thin wrapper around a sqlite3 connection."""

    def __init__(self, conn: sqlite3.Connection | None = None, db_path: Path | None = None) -> None:
        self.conn = conn or init_db(db_path)

    # ── envs ────────────────────────────────────────────────────────────────
    def upsert_env(self, env: EnvRow) -> int:
        """Insert or update by `path`. Returns row id."""
        env.last_indexed = int(time.time())
        cur = self.conn.execute(
            """
            INSERT INTO envs (
                path, name, python_version, python_exe, size_bytes,
                created_at, modified_at, last_activated, project_dir,
                user_tag, keep_probability, last_indexed, hash_quick
            ) VALUES (
                :path, :name, :python_version, :python_exe, :size_bytes,
                :created_at, :modified_at, :last_activated, :project_dir,
                :user_tag, :keep_probability, :last_indexed, :hash_quick
            )
            ON CONFLICT(path) DO UPDATE SET
                name=excluded.name,
                python_version=excluded.python_version,
                python_exe=excluded.python_exe,
                size_bytes=excluded.size_bytes,
                created_at=excluded.created_at,
                modified_at=excluded.modified_at,
                last_activated=COALESCE(excluded.last_activated, envs.last_activated),
                project_dir=excluded.project_dir,
                user_tag=COALESCE(envs.user_tag, excluded.user_tag),
                keep_probability=COALESCE(excluded.keep_probability, envs.keep_probability),
                last_indexed=excluded.last_indexed,
                hash_quick=excluded.hash_quick
            RETURNING id
            """,
            asdict(env),
        )
        row_id = cur.fetchone()[0]
        env.id = row_id
        return row_id

    def get_env(self, path: str) -> EnvRow | None:
        row = self.conn.execute("SELECT * FROM envs WHERE path = ?", (path,)).fetchone()
        return self._row_to_env(row) if row else None

    def list_envs(
        self,
        *,
        keep_prob_lt: float | None = None,
        project_dir: str | None = None,
        order_by: str = "size_bytes DESC",
    ) -> list[EnvRow]:
        sql = "SELECT * FROM envs WHERE 1=1"
        params: list = []
        if keep_prob_lt is not None:
            sql += " AND keep_probability < ?"
            params.append(keep_prob_lt)
        if project_dir is not None:
            sql += " AND project_dir = ?"
            params.append(project_dir)
        # order_by is constrained to a small allowlist
        if order_by not in {
            "size_bytes DESC", "size_bytes ASC", "modified_at ASC", "modified_at DESC",
            "keep_probability ASC", "keep_probability DESC", "last_indexed DESC",
        }:
            order_by = "size_bytes DESC"
        sql += f" ORDER BY {order_by}"
        return [self._row_to_env(r) for r in self.conn.execute(sql, params).fetchall()]

    def delete_env(self, path: str) -> None:
        self.conn.execute("DELETE FROM envs WHERE path = ?", (path,))

    def prune_missing(self, seen_paths: Iterable[str]) -> int:
        """Remove envs whose path is no longer on disk and not in `seen_paths`."""
        seen = set(seen_paths)
        rows = self.conn.execute("SELECT path FROM envs").fetchall()
        gone = [r["path"] for r in rows if r["path"] not in seen and not Path(r["path"]).exists()]
        if not gone:
            return 0
        with transaction(self.conn):
            self.conn.executemany("DELETE FROM envs WHERE path = ?", [(p,) for p in gone])
        return len(gone)

    # ── scans ───────────────────────────────────────────────────────────────
    def start_scan(self, root: str, mode: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO scans (started_at, root, mode) VALUES (?,?,?) RETURNING id",
            (int(time.time()), root, mode),
        )
        return cur.fetchone()[0]

    def finish_scan(self, scan_id: int, envs_found: int, duration_ms: int) -> None:
        self.conn.execute(
            "UPDATE scans SET finished_at = ?, envs_found = ?, duration_ms = ? WHERE id = ?",
            (int(time.time()), envs_found, duration_ms, scan_id),
        )

    def last_scan(self, root: str) -> ScanRow | None:
        row = self.conn.execute(
            "SELECT * FROM scans WHERE root = ? AND finished_at IS NOT NULL "
            "ORDER BY finished_at DESC LIMIT 1",
            (root,),
        ).fetchone()
        if not row:
            return None
        return ScanRow(
            id=row["id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            root=row["root"],
            mode=row["mode"],
            envs_found=row["envs_found"],
            duration_ms=row["duration_ms"],
        )

    # ── helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _row_to_env(row: sqlite3.Row) -> EnvRow:
        return EnvRow(
            id=row["id"],
            path=row["path"],
            name=row["name"] or "",
            python_version=row["python_version"],
            python_exe=row["python_exe"],
            size_bytes=row["size_bytes"] or 0,
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            last_activated=row["last_activated"],
            project_dir=row["project_dir"],
            user_tag=row["user_tag"],
            keep_probability=row["keep_probability"],
            last_indexed=row["last_indexed"],
            hash_quick=row["hash_quick"],
        )

    def close(self) -> None:
        self.conn.close()
