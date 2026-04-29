"""Core filesystem logic: discovery, sizing, requirements, markers."""

from venv_reaper.core.discovery import scan_directory
from venv_reaper.core.markers import SKIP_DIRS, VENV_MARKERS, is_venv
from venv_reaper.core.requirements import find_req
from venv_reaper.core.sizing import dir_size, fmt_size, size_color
from venv_reaper.core.system_scan import ScanStats, default_roots, system_scan

__all__ = [
    "SKIP_DIRS",
    "VENV_MARKERS",
    "ScanStats",
    "default_roots",
    "dir_size",
    "find_req",
    "fmt_size",
    "is_venv",
    "scan_directory",
    "size_color",
    "system_scan",
]
