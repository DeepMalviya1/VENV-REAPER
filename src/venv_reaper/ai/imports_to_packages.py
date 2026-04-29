"""Map import-name → PyPI distribution-name.

Strategy (highest confidence first):
    1. Live registry from `importlib.metadata.packages_distributions()`
       — authoritative on the current interpreter.
    2. Curated heuristic table (`import_map.json`).
    3. Fallback: assume `pkg_name == import_name.replace("_", "-")`.

When a venv-specific RECORD is loaded later (see `installed.py`),
that data overrides #1 for cross-interpreter accuracy.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.metadata import packages_distributions
from importlib.resources import files


@lru_cache(maxsize=1)
def _curated_table() -> dict[str, str]:
    raw = json.loads(
        files("venv_reaper.ai").joinpath("import_map.json").read_text(encoding="utf-8")
    )
    return {k: v for k, v in raw.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def _live_table() -> dict[str, str]:
    out: dict[str, str] = {}
    for mod, dists in packages_distributions().items():
        if dists:
            out[mod] = dists[0]
    return out


def map_one(module: str, *, registry: dict[str, str] | None = None) -> str:
    """Return the best-effort PyPI distribution name for a top-level import."""
    if registry and module in registry:
        return registry[module]
    live = _live_table()
    if module in live:
        return live[module]
    curated = _curated_table()
    if module in curated:
        return curated[module]
    return module.replace("_", "-").lower()


def map_imports_to_packages(
    modules: list[str],
    *,
    registry: dict[str, str] | None = None,
) -> dict[str, str]:
    """Bulk version of `map_one`. Keys are imports; values are PyPI names."""
    return {m: map_one(m, registry=registry) for m in modules}
