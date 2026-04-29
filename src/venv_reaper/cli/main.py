"""`reaper` — hacker-themed CLI driving the venv-reaper index."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.box import HEAVY
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from venv_reaper.config import index_db_path
from venv_reaper.core import default_roots, fmt_size, system_scan
from venv_reaper.core.quarantine import (
    inter as crypt_inter,
    list_entries as crypt_list,
    purge as crypt_purge,
    purge_expired,
    restore as crypt_restore,
)
from venv_reaper.index import Repository
from venv_reaper.theme import REAPER_BANNER, TAGLINE, make_console

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="☠ VENV REAPER — system-wide AI venv manager. HUNT · INSPECT · DESTROY · REPEAT.",
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = make_console()


# ──────────────────────────────────────────────────────────────────────────────
# Shared output helpers (every CLI surface uses these — keep style consistent)
# ──────────────────────────────────────────────────────────────────────────────
def banner() -> None:
    console.print(Text(REAPER_BANNER, style="reaper.green"))
    console.print(Text(TAGLINE, style="reaper.text_dim"), justify="center")
    console.print()


def _severity_style(size_bytes: int) -> str:
    mb = size_bytes / (1024**2)
    if mb < 50:
        return "sz.ok"
    if mb < 200:
        return "sz.med"
    if mb < 500:
        return "sz.high"
    return "sz.crit"


def _fmt_size_str(b: int) -> str:
    v, u = fmt_size(b)
    return f"{v} {u}"


def _path_short(p: str, max_len: int = 60) -> str:
    home = str(Path.home())
    if p.startswith(home):
        p = "~" + p[len(home):]
    if len(p) <= max_len:
        return p
    return "…" + p[-(max_len - 1):]


def _envs_table(rows: list, *, title: str) -> Table:
    t = Table(
        title=Text(title, style="h2"),
        title_justify="left",
        box=HEAVY,
        border_style="reaper.green_dark",
        header_style="reaper.text_dim",
        show_lines=False,
        expand=True,
    )
    t.add_column("ID", style="reaper.text_dim", no_wrap=True, width=4)
    t.add_column("NAME", style="primary", no_wrap=True)
    t.add_column("PATH", style="reaper.text_dim", overflow="ellipsis")
    t.add_column("SIZE", justify="right", no_wrap=True)
    t.add_column("PY", style="reaper.cyan", no_wrap=True)
    t.add_column("KEEP", justify="right", style="value", no_wrap=True)
    for env in rows:
        t.add_row(
            str(env.id),
            env.name or Path(env.path).name,
            _path_short(env.path),
            Text(_fmt_size_str(env.size_bytes), style=_severity_style(env.size_bytes)),
            env.python_version or "?",
            f"{env.keep_probability:.2f}" if env.keep_probability is not None else "—",
        )
    return t


# ──────────────────────────────────────────────────────────────────────────────
# scan
# ──────────────────────────────────────────────────────────────────────────────
@app.command()
def scan(
    full: bool = typer.Option(False, "--full", "-f", help="Re-scan everything (ignore hash_quick)."),
    root: list[Path] = typer.Option(
        None, "--root", "-r",
        help="Override scan roots. Repeat for multiple. Default: platform-sensible roots.",
    ),
    workers: int | None = typer.Option(None, "--workers", "-w", help="Thread pool size."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Skip the banner."),
) -> None:
    """Walk the system, find every Python venv, write to the index."""
    if not quiet:
        banner()

    repo = Repository()
    roots = root or default_roots()
    incremental = not full

    console.print(
        Panel.fit(
            Text.from_markup(
                "[label]MODE[/]  [value]"
                f"{'incremental' if incremental else 'full'}[/]\n"
                f"[label]ROOTS[/] [value]{', '.join(_path_short(str(r)) for r in roots)}[/]"
            ),
            title=Text("// SCAN INITIATED", style="h2"),
            border_style="reaper.green_dark",
            padding=(0, 2),
        )
    )

    found: list[Path] = []

    def _on_venv(p: Path) -> None:
        found.append(p)

    progress = Progress(
        SpinnerColumn(style="reaper.green"),
        TextColumn("[reaper.text_dim]hunting[/]"),
        BarColumn(complete_style="reaper.green", finished_style="reaper.green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("[value]{task.fields[count]}[/] envs"),
        console=console,
        transient=True,
    )

    with progress:
        task = progress.add_task("scanning", total=None, count=0)

        # Wrap the user's progress callback to keep counts updating.
        def _progress(p: Path) -> None:
            _on_venv(p)
            progress.update(task, count=len(found), advance=1)

        stats = system_scan(
            roots=roots,
            repo=repo,
            incremental=incremental,
            max_workers=workers,
            progress=_progress,
        )

    summary = Table.grid(padding=(0, 2))
    summary.add_row("[label]Indexed[/]",  f"[primary]{stats.envs_found}[/]")
    summary.add_row("[label]Skipped (unchanged)[/]", f"[reaper.cyan]{stats.envs_skipped_unchanged}[/]")
    summary.add_row("[label]Permission errors[/]",   f"[log.warn]{stats.permission_errors}[/]")
    summary.add_row("[label]Duration[/]",            f"[value]{stats.duration_ms} ms[/]")
    summary.add_row("[label]Index[/]",               f"[reaper.text_dim]{index_db_path()}[/]")
    console.print(Panel(summary, title=Text("// RECON SUMMARY", style="h2"),
                        border_style="reaper.green_dark"))

    if stats.permission_errors:
        console.print(
            f"[log.warn]⚠[/] [reaper.text_dim]{stats.permission_errors} directories were unreadable. "
            f"Run with sudo to include them.[/]"
        )


# ──────────────────────────────────────────────────────────────────────────────
# list
# ──────────────────────────────────────────────────────────────────────────────
@app.command("list")
def list_cmd(
    keep_below: float | None = typer.Option(
        None, "--keep-below", "-k",
        help="Show only envs with keep_probability below this threshold (cruft).",
    ),
    project: str | None = typer.Option(None, "--project", "-p", help="Filter by project_dir."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to print."),
    order: str = typer.Option("size_bytes DESC", "--order", "-o",
                              help="ORDER BY (allowlisted in repository)."),
) -> None:
    """List indexed venvs sorted by size (default) or keep-probability."""
    repo = Repository()
    rows = repo.list_envs(keep_prob_lt=keep_below, project_dir=project, order_by=order)
    if not rows:
        console.print("[log.warn]⚠ Index is empty.[/] [reaper.text_dim]Run [primary]reaper scan[/] first.[/]")
        raise typer.Exit(code=1)

    rows = rows[:limit]
    total_b = sum(r.size_bytes for r in rows)
    console.print(_envs_table(rows, title=f"// {len(rows)} VENV(S) · {_fmt_size_str(total_b)}"))


# ──────────────────────────────────────────────────────────────────────────────
# inspect
# ──────────────────────────────────────────────────────────────────────────────
@app.command()
def inspect(
    target: str = typer.Argument(..., help="Env id (number) or absolute path."),
    analyze: bool = typer.Option(
        False, "--analyze", "-a",
        help="Also run the AI dependency analysis (imports vs installed vs requirements).",
    ),
) -> None:
    """Show full detail for a single venv."""
    repo = Repository()
    env = _resolve(repo, target)
    if env is None:
        console.print(f"[log.err]✘ No env matches[/] [value]{target}[/]")
        raise typer.Exit(code=1)

    table = Table.grid(padding=(0, 2))
    fields = [
        ("ID", env.id), ("Name", env.name), ("Path", env.path),
        ("Python", env.python_version), ("Python exe", env.python_exe),
        ("Size", _fmt_size_str(env.size_bytes)),
        ("Created", _ts(env.created_at)), ("Modified", _ts(env.modified_at)),
        ("Last activated", _ts(env.last_activated)),
        ("Project dir", env.project_dir), ("User tag", env.user_tag),
        ("Keep prob", f"{env.keep_probability:.2f}" if env.keep_probability is not None else "—"),
        ("Last indexed", _ts(env.last_indexed)),
        ("Hash", env.hash_quick),
    ]
    for k, v in fields:
        table.add_row(f"[label]{k}[/]", f"[value]{v if v not in (None, '') else '—'}[/]")
    console.print(Panel(table, title=Text(f"// ENV #{env.id}", style="h2"),
                        border_style="reaper.green_dark"))

    if analyze:
        _print_analysis(Path(env.path), Path(env.project_dir) if env.project_dir else None)


# ──────────────────────────────────────────────────────────────────────────────
# analyze — AI dependency report
# ──────────────────────────────────────────────────────────────────────────────
@app.command()
def analyze(
    target: str = typer.Argument(..., help="Env id (number) or absolute path."),
    project: Path | None = typer.Option(
        None, "--project", "-p",
        help="Override the project directory (default: linked project_dir).",
    ),
    requirements: Path | None = typer.Option(
        None, "--requirements", "-r", help="Override path to requirements.txt.",
    ),
) -> None:
    """AI dependency analysis: what's imported, what's installed, what's cruft."""
    repo = Repository()
    env = _resolve(repo, target)
    if env is None:
        console.print(f"[log.err]✘ No env matches[/] [value]{target}[/]")
        raise typer.Exit(code=1)

    proj = project if project else (Path(env.project_dir) if env.project_dir else None)
    _print_analysis(Path(env.path), proj, requirements=requirements)


def _print_analysis(
    venv: Path,
    project: Path | None,
    *,
    requirements: Path | None = None,
) -> None:
    from venv_reaper.ai.reconciler import reconcile

    report = reconcile(venv, project_dir=project, requirements=requirements)

    # Summary header
    summary = Table.grid(padding=(0, 2))
    summary.add_row("[label]Project[/]",
                    f"[value]{report.project_dir or '— (no project linked)'}[/]")
    summary.add_row("[label]Files scanned[/]",  f"[value]{report.sweep.files_scanned}[/]")
    summary.add_row("[label]Files unparsable[/]", f"[log.warn]{report.sweep.files_failed}[/]")
    summary.add_row("[label]Distinct imports[/]", f"[value]{len(report.sweep.modules)}[/]")
    summary.add_row("[label]Installed dists[/]", f"[value]{len(report.installed)}[/]")
    summary.add_row("[label]Missing (imported, not installed)[/]",
                    f"[log.err]{len(report.missing)}[/]")
    summary.add_row("[label]Unused (installed, never imported)[/]",
                    f"[log.warn]{len(report.unused)}[/]")
    if report.requirements_path:
        summary.add_row("[label]requirements.txt[/]",
                        f"[reaper.text_dim]{report.requirements_path}[/]")
        summary.add_row("[label]Declared but unused[/]",
                        f"[log.warn]{len(report.declared_but_not_used)}[/]")
        summary.add_row("[label]Used but undeclared[/]",
                        f"[log.err]{len(report.used_but_not_declared)}[/]")

    console.print(Panel(
        summary, title=Text("// DEPENDENCY ANALYSIS", style="h2"),
        border_style="reaper.green_dark",
    ))

    if report.missing:
        _list_panel(
            "// IMPORTED BUT NOT INSTALLED",
            "log.err",
            [f"{m}  →  [reaper.text_dim]{report.needed[m]}[/]" for m in report.missing],
        )
    if report.unused:
        _list_panel(
            "// INSTALLED BUT NEVER IMPORTED",
            "log.warn",
            report.unused,
        )
    if report.used_but_not_declared:
        _list_panel(
            "// USED BUT NOT IN requirements.txt",
            "log.err",
            report.used_but_not_declared,
        )
    if report.declared_but_not_used:
        _list_panel(
            "// IN requirements.txt BUT NEVER IMPORTED",
            "log.warn",
            report.declared_but_not_used,
        )

    if not (report.missing or report.unused
            or report.used_but_not_declared or report.declared_but_not_used):
        console.print("[log.ok]✔ Environment looks clean — nothing to report.[/]")


def _list_panel(title: str, style: str, items: list[str]) -> None:
    body = "\n".join(f"  [{style}]►[/] {item}" for item in items)
    console.print(Panel(
        body, title=Text(title, style="h2"),
        border_style="reaper.green_dark", padding=(0, 1),
    ))


def _ts(t: int | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t else "—"


def _resolve(repo: Repository, target: str):
    """Resolve an id-or-path argument to an EnvRow."""
    if target.isdigit():
        rows = repo.conn.execute("SELECT * FROM envs WHERE id = ?", (int(target),)).fetchone()
        return repo._row_to_env(rows) if rows else None  # noqa: SLF001
    return repo.get_env(target) or repo.get_env(str(Path(target).resolve()))


# ──────────────────────────────────────────────────────────────────────────────
# kill
# ──────────────────────────────────────────────────────────────────────────────
@app.command()
def kill(
    targets: list[str] = typer.Argument(..., help="Env ids or paths."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done."),
) -> None:
    """Send venv(s) to the Reaper Crypt (recoverable for 7 days)."""
    repo = Repository()
    envs = [(t, _resolve(repo, t)) for t in targets]
    missing = [t for t, e in envs if e is None]
    if missing:
        console.print(f"[log.err]✘ Unknown:[/] {', '.join(missing)}")
        raise typer.Exit(code=1)

    rows = [e for _, e in envs if e is not None]
    total = sum(r.size_bytes for r in rows)
    console.print(_envs_table(rows, title=f"// STRIKE PACKAGE · {len(rows)} target(s) · {_fmt_size_str(total)}"))

    if dry_run:
        console.print("[log.warn]⚰ Dry run — nothing was moved.[/]")
        return

    if not yes:
        confirm = typer.confirm("⚠  CONFIRM INTERMENT — venvs will be moved to the Crypt", default=False)
        if not confirm:
            console.print("[log.warn]Aborted.[/]")
            raise typer.Exit(code=2)

    freed = 0
    killed = 0
    for env in rows:
        path = Path(env.path)
        try:
            crypt_inter(path, size_bytes=env.size_bytes)
            repo.delete_env(env.path)
            freed += env.size_bytes
            killed += 1
            console.print(
                f"[log.ok]⚰ INTERRED[/] [value]{path.name}[/] "
                f"[reaper.text_dim]({_fmt_size_str(env.size_bytes)})[/]"
            )
        except Exception as exc:
            console.print(f"[log.err]✘ {path.name} — {exc}[/]")

    console.print(
        f"\n[primary]Operation complete[/] · "
        f"[value]{killed}[/] interred · "
        f"[reaper.green]{_fmt_size_str(freed)}[/] reclaimable"
    )


# ──────────────────────────────────────────────────────────────────────────────
# crypt + restore
# ──────────────────────────────────────────────────────────────────────────────
crypt_app = typer.Typer(help="Manage the Reaper Crypt (quarantined venvs).")
app.add_typer(crypt_app, name="crypt")


@crypt_app.command("list")
def crypt_list_cmd() -> None:
    """List entries currently in the Crypt."""
    entries = crypt_list()
    if not entries:
        console.print("[log.dim]🪦  Crypt is empty.[/]")
        return
    t = Table(
        title=Text("// REAPER CRYPT", style="h2"),
        box=HEAVY, border_style="reaper.green_dark",
        header_style="reaper.text_dim", expand=True,
    )
    t.add_column("ID", style="primary", no_wrap=True)
    t.add_column("ORIGINAL", style="reaper.text_dim", overflow="ellipsis")
    t.add_column("SIZE", justify="right")
    t.add_column("INTERRED", style="reaper.cyan")
    t.add_column("EXPIRES IN", justify="right")
    now = int(time.time())
    for e in entries:
        remaining = max(0, e.expires_at() - now)
        days = remaining // 86400
        style = "log.warn" if days < 2 else "value"
        t.add_row(
            e.id, _path_short(e.original_path),
            Text(_fmt_size_str(e.size_bytes), style=_severity_style(e.size_bytes)),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(e.interred_at)),
            Text(f"{days}d {(remaining % 86400) // 3600}h", style=style),
        )
    console.print(t)


@app.command()
def restore(entry_id: str = typer.Argument(..., help="Crypt entry id (8-char sha).")) -> None:
    """Bring a quarantined venv back to its original path."""
    try:
        target = crypt_restore(entry_id)
    except KeyError:
        console.print(f"[log.err]✘ No crypt entry:[/] {entry_id}")
        raise typer.Exit(code=1)
    except FileExistsError as exc:
        console.print(f"[log.err]✘ {exc}[/]")
        raise typer.Exit(code=1)
    console.print(f"[log.ok]✔ Restored[/] [value]{target}[/]")


@crypt_app.command("purge")
def crypt_purge_cmd(
    entry_id: str | None = typer.Argument(None, help="Specific entry. Omit to purge all expired."),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Permanently delete crypt entries (single id, or all expired)."""
    if entry_id:
        if not yes and not typer.confirm(f"Permanently delete {entry_id}?", default=False):
            raise typer.Exit(code=2)
        try:
            crypt_purge(entry_id)
        except KeyError:
            console.print(f"[log.err]✘ No crypt entry:[/] {entry_id}")
            raise typer.Exit(code=1)
        console.print(f"[log.ok]✔ Purged[/] [value]{entry_id}[/]")
        return
    n = purge_expired()
    console.print(f"[primary]Purged {n} expired entr{'y' if n == 1 else 'ies'}.[/]")


# ──────────────────────────────────────────────────────────────────────────────
# ui — launch the existing Streamlit Hacker UI
# ──────────────────────────────────────────────────────────────────────────────
@app.command()
def ui() -> None:
    """Launch the Hacker UI (Streamlit) — the original Matrix-rain experience."""
    here = Path(__file__).resolve().parent.parent.parent.parent  # repo root
    target = here / "v2.py"
    if not target.exists():
        console.print(f"[log.err]✘ Streamlit app not found at {target}[/]")
        raise typer.Exit(code=1)
    console.print(f"[primary]☠ Launching Hacker UI[/] [reaper.text_dim]({target})[/]")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(here / "src") + os.pathsep + env.get("PYTHONPATH", "")
    raise SystemExit(subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(target)], env=env
    ))


# ──────────────────────────────────────────────────────────────────────────────
# version
# ──────────────────────────────────────────────────────────────────────────────
@app.command()
def version() -> None:
    """Print the package version."""
    from venv_reaper import __version__
    console.print(f"[primary]venv-reaper[/] [value]{__version__}[/]")


def main() -> None:  # pragma: no cover — invoked via console script
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
