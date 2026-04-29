"""SQLite-backed index — single source of truth for envs, packages, vulns, scans."""

from venv_reaper.index.db import connect, init_db
from venv_reaper.index.repository import Repository

__all__ = ["Repository", "connect", "init_db"]
