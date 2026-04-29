"""Parallel, cross-platform, incremental system-wide venv discovery.

Resolves L1, L7, L8 from the product plan:
    * walks every reasonable root on the machine
    * uses a thread pool for IO-bound parallelism
    * hash_quick (mtime+size) lets re-scans skip unchanged venvs
"""

from __future__ import annotations

import hashlib
import os
import platform
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from venv_reaper.core.markers import SKIP_DIRS, is_venv
from venv_reaper.core.requirements import find_req
from venv_reaper.core.sizing import dir_size
from venv_reaper.index.repository import EnvRow, Repository

# ──────────────────────────────────────────────────────────────────────────────
# Platform roots
# ──────────────────────────────────────────────────────────────────────────────
_LINUX_SKIP_ROOTS = {
    "/proc", "/sys", "/dev", "/run", "/snap", "/tmp",
    "/var/cache", "/var/lib/docker", "/var/lib/containers",
}
_MAC_SKIP_ROOTS = {"/System", "/private/var", "/Volumes/.timemachine"}
_WIN_SKIP_NAMES = {"$Recycle.Bin", "System Volume Information", "Windows", "WinSxS"}

# Platform-specific extra SKIP_DIRS layered on top of core SKIP_DIRS
_EXTRA_SKIP = frozenset({
    "Library", "Applications",        # macOS noise from $HOME
    "AppData",                        # Windows noise
    "$RECYCLE.BIN",
    ".cache", ".local", ".npm", ".nvm", ".rustup", ".cargo",
})


def default_roots() -> list[Path]:
    """Sensible scan roots for the current platform."""
    sys_name = platform.system()
    home = Path.home()
    if sys_name == "Windows":
        roots = [home]
        for d in string.ascii_uppercase:
            drive = Path(f"{d}:\\")
            if drive.exists():
                roots.append(drive)
        return roots
    if sys_name == "Darwin":
        return [home, Path("/usr/local"), Path("/opt")]
    # Linux / other POSIX
    return [home, Path("/opt"), Path("/srv"), Path("/usr/local")]


def _is_blocked_root(p: Path) -> bool:
    s = str(p)
    sysname = platform.system()
    if sysname == "Darwin" and any(s.startswith(b) for b in _MAC_SKIP_ROOTS):
        return True
    if sysname == "Linux" and any(s == b or s.startswith(b + os.sep) for b in _LINUX_SKIP_ROOTS):
        return True
    if sysname == "Windows" and p.name in _WIN_SKIP_NAMES:
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Project linkage + hashing
# ──────────────────────────────────────────────────────────────────────────────
_PROJECT_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "package.json", ".git")


def find_project_dir(venv: Path) -> Path | None:
    """Walk up from venv.parent looking for a project marker. None if hits FS root."""
    cur = venv.parent
    seen = 0
    while seen < 10:  # don't walk forever
        if any((cur / m).exists() for m in _PROJECT_MARKERS):
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
        seen += 1
    return None


def quick_hash(path: Path) -> str:
    """Cheap fingerprint: mtime + size of the venv root + its python exe."""
    try:
        st = path.stat()
        py = path / "bin" / "python"
        if not py.exists():
            py = path / "Scripts" / "python.exe"
        py_st = py.stat() if py.exists() else None
        seed = f"{st.st_mtime_ns}|{st.st_size}|"
        if py_st:
            seed += f"{py_st.st_mtime_ns}|{py_st.st_size}"
        return hashlib.sha1(seed.encode()).hexdigest()[:16]
    except OSError:
        return ""


def parse_python_version(venv: Path) -> str | None:
    """Read `version = X.Y.Z` from pyvenv.cfg if present."""
    cfg = venv / "pyvenv.cfg"
    if not cfg.exists():
        return None
    try:
        for line in cfg.read_text(errors="replace").splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                if k.strip().lower() == "version":
                    return v.strip()
    except OSError:
        return None
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Result type + scan
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class ScanStats:
    envs_found: int = 0
    envs_skipped_unchanged: int = 0
    permission_errors: int = 0
    duration_ms: int = 0


ProgressCb = Callable[[Path], None]


def _walk_root(
    root: Path,
    *,
    skip: frozenset[str],
    cancel: threading.Event,
    on_venv: Callable[[Path], None],
    counters: dict[str, int],
) -> None:
    stack: list[Path] = [root]
    while stack and not cancel.is_set():
        cur = stack.pop()
        if cur.name in skip or _is_blocked_root(cur):
            continue
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if cancel.is_set():
                        return
                    try:
                        if not e.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    p = Path(e.path)
                    if is_venv(p):
                        on_venv(p)
                        # Don't recurse into the venv itself.
                        continue
                    stack.append(p)
        except PermissionError:
            counters["perm"] += 1
        except OSError:
            counters["perm"] += 1


def system_scan(
    roots: Iterable[Path] | None = None,
    *,
    repo: Repository | None = None,
    incremental: bool = True,
    max_workers: int | None = None,
    progress: ProgressCb | None = None,
    cancel: threading.Event | None = None,
) -> ScanStats:
    """Walk all roots in parallel and write findings to the index.

    `incremental=True` skips re-sizing venvs whose hash_quick is unchanged.
    """
    repo = repo or Repository()
    cancel = cancel or threading.Event()
    skip = SKIP_DIRS | _EXTRA_SKIP
    roots = list(roots) if roots is not None else default_roots()
    started = time.monotonic()
    started_wall = int(time.time())
    stats = ScanStats()
    counters = {"perm": 0}
    seen_paths: set[str] = set()
    lock = threading.Lock()

    scan_id = repo.start_scan(
        root=os.pathsep.join(str(r) for r in roots),
        mode="incremental" if incremental else "full",
    )

    def handle_venv(p: Path) -> None:
        if cancel.is_set():
            return
        path_str = str(p)
        with lock:
            seen_paths.add(path_str)
        if progress:
            progress(p)
        new_hash = quick_hash(p)
        if incremental:
            existing = repo.get_env(path_str)
            if existing and existing.hash_quick == new_hash and existing.size_bytes:
                with lock:
                    stats.envs_skipped_unchanged += 1
                # Touch last_indexed so prune doesn't remove it.
                existing.hash_quick = new_hash
                repo.upsert_env(existing)
                return
        try:
            st = p.stat()
            size = dir_size(p)
            req = find_req(p)
            project = find_project_dir(p)
            row = EnvRow(
                path=path_str,
                name=p.name,
                python_version=parse_python_version(p),
                python_exe=str((p / "bin" / "python")) if (p / "bin" / "python").exists()
                           else str((p / "Scripts" / "python.exe")),
                size_bytes=size,
                created_at=int(st.st_ctime),
                modified_at=int(st.st_mtime),
                project_dir=str(project) if project else (str(p.parent) if req else None),
                hash_quick=new_hash,
            )
            repo.upsert_env(row)
            with lock:
                stats.envs_found += 1
        except OSError:
            with lock:
                counters["perm"] += 1

    workers = max_workers or min(32, (os.cpu_count() or 4) * 4)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [
            ex.submit(_walk_root, r, skip=skip, cancel=cancel,
                      on_venv=handle_venv, counters=counters)
            for r in roots if r.exists() and not _is_blocked_root(r)
        ]
        for f in futures:
            f.result()

    repo.prune_missing(seen_paths)
    duration_ms = int((time.monotonic() - started) * 1000)
    repo.finish_scan(scan_id, stats.envs_found, duration_ms)

    stats.duration_ms = duration_ms
    stats.permission_errors = counters["perm"]
    _ = started_wall  # currently unused — reserved for telemetry
    return stats
