"""XDG-compliant paths for index, models, logs, and quarantine."""

from __future__ import annotations

import os
from pathlib import Path

_APP = "venv-reaper"


def _xdg(env: str, default: Path) -> Path:
    raw = os.environ.get(env)
    return Path(raw) if raw else default


def data_dir() -> Path:
    """`$XDG_DATA_HOME/venv-reaper/` — index DB, models, quarantine."""
    p = _xdg("XDG_DATA_HOME", Path.home() / ".local" / "share") / _APP
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = _xdg("XDG_CACHE_HOME", Path.home() / ".cache") / _APP
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_dir() -> Path:
    p = _xdg("XDG_STATE_HOME", Path.home() / ".local" / "state") / _APP
    p.mkdir(parents=True, exist_ok=True)
    return p


def index_db_path() -> Path:
    return data_dir() / "index.db"


def crypt_dir() -> Path:
    """Where quarantined venvs are moved before purge."""
    p = data_dir() / "crypt"
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_path() -> Path:
    return state_dir() / "reaper.log"
