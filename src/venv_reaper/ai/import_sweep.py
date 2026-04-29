"""Walk a project directory and extract distinct top-level imports via AST.

We use `ast` (not regex) so `try/except ImportError`, conditional imports, and
relative imports are all handled correctly. Stdlib modules are filtered out.
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# stdlib_module_names was added in 3.10; we already require >=3.10.
_STDLIB: frozenset[str] = frozenset(sys.stdlib_module_names) | frozenset(
    {"__future__", "typing_extensions"}
)

_DEFAULT_SKIP: frozenset[str] = frozenset(
    {
        ".git", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
        "node_modules", "venv", ".venv", "env", ".env", "build", "dist",
        ".eggs", "site-packages",
    }
)


@dataclass(slots=True)
class ImportSweepResult:
    project_dir: Path
    files_scanned: int = 0
    files_failed: int = 0
    counts: Counter[str] = field(default_factory=Counter)

    @property
    def modules(self) -> list[str]:
        """Distinct top-level non-stdlib module names, sorted by frequency."""
        return [m for m, _ in self.counts.most_common()]

    @property
    def total_imports(self) -> int:
        return sum(self.counts.values())


def _top_level(name: str) -> str:
    return name.split(".", 1)[0]


def _extract(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield _top_level(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # `from . import foo` (level >= 1) is intra-package — skip.
            if (node.level or 0) > 0:
                continue
            if node.module:
                yield _top_level(node.module)


def sweep_file(path: Path) -> list[str]:
    """Return non-stdlib top-level imports declared in a single .py file."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(path))
    except (OSError, SyntaxError, ValueError):
        raise
    return [m for m in _extract(tree) if m and m not in _STDLIB]


def sweep_project(
    project_dir: Path,
    *,
    skip_dirs: frozenset[str] = _DEFAULT_SKIP,
    max_files: int | None = None,
) -> ImportSweepResult:
    """Walk `project_dir` recursively and collect imports from every .py file."""
    result = ImportSweepResult(project_dir=project_dir)
    if not project_dir.exists():
        return result

    for py in _iter_py_files(project_dir, skip_dirs):
        if max_files is not None and result.files_scanned >= max_files:
            break
        try:
            mods = sweep_file(py)
        except Exception:
            result.files_failed += 1
            continue
        result.files_scanned += 1
        result.counts.update(mods)
    return result


def _iter_py_files(root: Path, skip: frozenset[str]) -> Iterable[Path]:
    stack = [root]
    while stack:
        cur = stack.pop()
        if cur.name in skip:
            continue
        try:
            for entry in cur.iterdir():
                if entry.is_dir():
                    if entry.name not in skip:
                        stack.append(entry)
                elif entry.suffix == ".py":
                    yield entry
        except (OSError, PermissionError):
            continue
