"""Disk-usage helpers: recursive size, human-formatting, severity color."""

from __future__ import annotations

import os
from pathlib import Path


def dir_size(p: Path) -> int:
    """Recursively sum file sizes under `p`. Permission errors are skipped."""
    total = 0
    try:
        for e in os.scandir(p):
            try:
                if e.is_file(follow_symlinks=False):
                    total += e.stat(follow_symlinks=False).st_size
                elif e.is_dir(follow_symlinks=False):
                    total += dir_size(Path(e.path))
            except (OSError, PermissionError):
                pass
    except (OSError, PermissionError):
        pass
    return total


def fmt_size(b: float) -> tuple[str, str]:
    """Format bytes into a (value, unit) pair, e.g. ("12.3", "MB")."""
    for u in ("B", "KB", "MB"):
        if b < 1024:
            return f"{b:.1f}", u
        b /= 1024
    return f"{b:.2f}", "GB"


def size_color(b: int) -> str:
    """Map a byte count to the hacker palette severity color."""
    mb = b / (1024**2)
    if mb < 50:
        return "#00ff41"
    if mb < 200:
        return "#f0e040"
    if mb < 500:
        return "#ff8c00"
    return "#ff2222"
