"""Reaper Crypt — atomic move-to-trash with N-day TTL and undo.

Replaces direct `shutil.rmtree`. A move on the same filesystem is atomic; the
real deletion is delayed so a slip of the finger is recoverable.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from venv_reaper.config import crypt_dir

_MANIFEST = "manifest.json"
DEFAULT_TTL_DAYS = 7


@dataclass(slots=True)
class CryptEntry:
    id: str                  # short sha8 of original path + ts
    original_path: str
    crypt_path: str
    size_bytes: int
    interred_at: int         # unix ts
    ttl_days: int = DEFAULT_TTL_DAYS

    def expires_at(self) -> int:
        return self.interred_at + self.ttl_days * 86400

    def expired(self, now: int | None = None) -> bool:
        return (now or int(time.time())) >= self.expires_at()


def _entry_id(path: Path, ts: int) -> str:
    return hashlib.sha1(f"{path}|{ts}".encode()).hexdigest()[:8]


def _crypt_root() -> Path:
    return crypt_dir()


def _read_manifest(slot: Path) -> CryptEntry | None:
    f = slot / _MANIFEST
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
        return CryptEntry(**d)
    except Exception:
        return None


def _write_manifest(slot: Path, entry: CryptEntry) -> None:
    (slot / _MANIFEST).write_text(json.dumps(asdict(entry), indent=2))


def inter(path: Path, *, size_bytes: int | None = None,
          ttl_days: int = DEFAULT_TTL_DAYS) -> CryptEntry:
    """Move `path` into the crypt. Atomic when same-filesystem."""
    if not path.exists():
        raise FileNotFoundError(path)
    ts = int(time.time())
    entry_id = _entry_id(path, ts)
    slot = _crypt_root() / f"{ts}-{entry_id}"
    slot.mkdir(parents=True, exist_ok=False)
    target = slot / path.name
    try:
        path.rename(target)              # atomic same-FS
    except OSError:
        shutil.move(str(path), target)   # cross-FS fallback
    entry = CryptEntry(
        id=entry_id,
        original_path=str(path),
        crypt_path=str(target),
        size_bytes=size_bytes if size_bytes is not None else 0,
        interred_at=ts,
        ttl_days=ttl_days,
    )
    _write_manifest(slot, entry)
    return entry


def list_entries() -> list[CryptEntry]:
    out: list[CryptEntry] = []
    if not _crypt_root().exists():
        return out
    for slot in sorted(_crypt_root().iterdir()):
        if not slot.is_dir():
            continue
        entry = _read_manifest(slot)
        if entry:
            out.append(entry)
    return out


def restore(entry_id: str) -> Path:
    """Move a crypt entry back to its original path. Errors if path is occupied."""
    for slot in _crypt_root().iterdir():
        entry = _read_manifest(slot) if slot.is_dir() else None
        if entry and entry.id == entry_id:
            target = Path(entry.original_path)
            if target.exists():
                raise FileExistsError(f"Restore target already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            Path(entry.crypt_path).rename(target)
            shutil.rmtree(slot)
            return target
    raise KeyError(entry_id)


def purge(entry_id: str) -> None:
    """Permanently delete a single entry."""
    for slot in _crypt_root().iterdir():
        entry = _read_manifest(slot) if slot.is_dir() else None
        if entry and entry.id == entry_id:
            shutil.rmtree(slot)
            return
    raise KeyError(entry_id)


def purge_expired(now: int | None = None) -> int:
    """Purge all expired entries. Returns count purged."""
    now = now or int(time.time())
    n = 0
    if not _crypt_root().exists():
        return 0
    for slot in list(_crypt_root().iterdir()):
        if not slot.is_dir():
            continue
        entry = _read_manifest(slot)
        if entry and entry.expired(now):
            shutil.rmtree(slot)
            n += 1
    return n
