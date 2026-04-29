"""Directory walker that finds virtual environments under a root."""

from __future__ import annotations

import platform
import string
from pathlib import Path
from typing import TypedDict

from venv_reaper.core.markers import SKIP_DIRS, is_venv
from venv_reaper.core.requirements import find_req
from venv_reaper.core.sizing import dir_size, fmt_size


class VenvRecord(TypedDict):
    Select: bool
    _path: str
    _size_bytes: int
    _req_path: str
    ENV_NAME: str
    RELATIVE_PATH: str
    SIZE: str
    DEPTH: int
    REQUIREMENTS: str


def scan_directory(root: Path) -> list[dict]:
    """Walk `root` recursively and return one record per detected venv.

    Record keys are kept identical to the legacy v2.py shape so existing UI
    code continues to render correctly.
    """
    results: list[dict] = []

    def _walk(cur: Path) -> None:
        if cur.name in SKIP_DIRS:
            return
        try:
            entries = list(cur.iterdir())
        except (OSError, PermissionError):
            return
        for e in entries:
            if not e.is_dir():
                continue
            if is_venv(e):
                req = find_req(e)
                size = dir_size(e)
                val, unit = fmt_size(size)
                rel = e.relative_to(root)
                depth = len(rel.parts) - 1
                results.append(
                    {
                        "Select": False,
                        "_path": str(e),
                        "_size_bytes": size,
                        "_req_path": str(req) if req else "",
                        "ENV NAME": e.name,
                        "RELATIVE PATH": str(rel.parent) if str(rel.parent) != "." else "./",
                        "SIZE": f"{val} {unit}",
                        "DEPTH": depth,
                        "REQUIREMENTS": "✔  FOUND" if req else "✘  MISSING",
                    }
                )
            else:
                _walk(e)

    _walk(root)
    return results


def list_subdirs(path: Path) -> list[Path]:
    """Return visible subdirectories of `path`, sorted case-insensitively."""
    try:
        return sorted(
            (e for e in path.iterdir() if e.is_dir() and not e.name.startswith(".")),
            key=lambda p: p.name.lower(),
        )
    except (OSError, PermissionError):
        return []


def get_drives() -> list[str]:
    """Return drive roots on Windows, `["/"]` elsewhere."""
    if platform.system() == "Windows":
        return [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    return ["/"]
