"""Locate a project's requirements file relative to a venv path."""

from __future__ import annotations

from pathlib import Path


def find_req(venv_path: Path) -> Path | None:
    """Return the first matching requirements file near a venv, or None."""
    parent = venv_path.parent
    candidates = [
        parent / "requirements.txt",
        parent / "requirements" / "base.txt",
        parent / "requirements" / "dev.txt",
        parent.parent / "requirements.txt",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
