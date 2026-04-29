"""Virtual environment detection markers."""

from __future__ import annotations

from pathlib import Path

VENV_MARKERS: frozenset[str] = frozenset(
    {"pyvenv.cfg", "Scripts/python.exe", "bin/python", "bin/python3"}
)

SKIP_DIRS: frozenset[str] = frozenset(
    {".git", "__pycache__", "node_modules", ".tox", ".mypy_cache", ".pytest_cache"}
)


def is_venv(p: Path) -> bool:
    """Return True iff `p` looks like a Python virtual environment root."""
    return any((p / m).exists() for m in VENV_MARKERS)
