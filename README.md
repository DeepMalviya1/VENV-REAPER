<div align="center">

```
██╗   ██╗███████╗███╗   ██╗██╗   ██╗     ██████╗ ███████╗ █████╗ ██████╗ ███████╗██████╗
██║   ██║██╔════╝████╗  ██║██║   ██║     ██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗
██║   ██║█████╗  ██╔██╗ ██║██║   ██║     ██████╔╝█████╗  ███████║██████╔╝█████╗  ██████╔╝
╚██╗ ██╔╝██╔══╝  ██║╚██╗██║╚██╗ ██╔╝     ██╔══██╗██╔══╝  ██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗
 ╚████╔╝ ███████╗██║ ╚████║ ╚████╔╝      ██║  ██║███████╗██║  ██║██║     ███████╗██║  ██║
  ╚═══╝  ╚══════╝╚═╝  ╚═══╝  ╚═══╝       ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝
```

# ☠ &nbsp; **VENV REAPER** &nbsp; ☠

### *HUNT · INSPECT · DESTROY · REPEAT*

**An AI-augmented, system-wide Python virtual environment manager with a hacker-themed UI.**

[![Python](https://img.shields.io/badge/python-3.10%2B-00ff41?style=flat-square&labelColor=000)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-alpha-f0e040?style=flat-square&labelColor=000)](VENV_REAPER_AI_PRODUCT_PLAN.md)
[![Tests](https://img.shields.io/badge/tests-55%20passing-00ff41?style=flat-square&labelColor=000)](tests/)
[![License](https://img.shields.io/badge/license-MIT-00e5ff?style=flat-square&labelColor=000)](#license)
[![UI](https://img.shields.io/badge/UI-Matrix%20Rain-00ff41?style=flat-square&labelColor=000)](src/venv_reaper/theme/)

</div>

---

## ✦ &nbsp; What is this?

`venv-reaper` finds **every Python virtual environment on your machine**, tells you what's inside them, what's *actually used* by your code vs. what's just gathering dust, and lets you delete the cruft — all behind a Matrix-rain Streamlit UI **and** a fully themed terminal CLI.


> **Why this exists:** every Python developer has 10–80 GB of forgotten venvs scattered across `~/Code`, `~/Downloads`, old hackathons, that 2-year-old Coursera tutorial. Reaper finds them all, scores them, and reaps them — safely.

---

## ✦ &nbsp; Highlights

- 🟢 **Two surfaces, one identity** — a Streamlit web UI with Matrix-rain canvas, neon CSS, scanlines, and CRT glow + a `rich`-themed terminal CLI sharing the **exact same color tokens**.
- 🟢 **Name-agnostic discovery** — finds venvs by *marker* (`pyvenv.cfg`, `bin/python`, `Scripts/python.exe`), not by directory name. `WTF/`, `dl_2024_old/`, `myproject-py311/` — all detected.
- 🟢 **System-wide, parallel, incremental** — a `ThreadPoolExecutor`-backed walker scans your whole machine; an `mtime+size` quick-hash skips unchanged venvs on re-runs.
- 🟢 **SQLite-backed index** — single source of truth (WAL mode, foreign keys on) shared by the CLI, the Streamlit UI, and (soon) the daemon, REST API, and IDE plugins.
- 🟢 **Reaper Crypt** — `kill` doesn't `rm -rf`. It atomically moves the venv into a quarantine with a 7-day TTL. `restore <id>` brings it back.
- 🟢 **AI dependency analyzer** — AST-based import sweep + curated import→PyPI map + site-packages parser tells you exactly which installed packages your code never touches.
- 🟢 **Cross-platform** — Linux, macOS, Windows. Platform-specific scan roots and skip lists are baked in.

---

## ✦ &nbsp; The Hacker UI

| | |
|---|---|
| **Streamlit** | Matrix-rain canvas, scanlines, Orbitron + Share Tech Mono fonts, neon `#00ff41` palette, glow shadows, hacker-loader splash, custom hacker-table with severity-tinted size cells |
| **CLI** | `rich` console using the **same hex tokens** as the CSS, ASCII REAPER banner, neon panels, themed progress spinner, severity-colored size column |

The whole theme is decoupled into [`src/venv_reaper/theme/`](src/venv_reaper/theme/) — `reaper_theme.css`, `matrix_rain.js`, `rich_theme.py`, `ascii_art.py` — so every future surface (TUI, IDE webview, Tauri desktop) inherits the same identity.

---

## ✦ &nbsp; Quick Start

### 1. Clone and create a working venv (don't reuse an old one)

```bash
git clone https://github.com/<you>/venv-reaper.git
cd venv-reaper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install (editable)

```bash
pip install -e .
```

### 3. Pick your weapon

#### A. Terminal — the `reaper` CLI

```bash
reaper --help
reaper scan --root ~                # Index your home dir
reaper list -n 20                   # Top 20 by size
reaper inspect 1 --analyze          # Full detail + AI analysis
reaper kill 1 --yes                 # Send to the Crypt
reaper crypt list                   # See what's quarantined
reaper restore <id>                 # Undo
```

#### B. Web — the Matrix UI

```bash
reaper ui          # Equivalent to: streamlit run v2.py
```

Then open the printed `http://localhost:8501` in your browser.

---

## ✦ &nbsp; CLI Reference

| Command | What it does |
|---|---|
| `reaper scan [--full] [--root P …] [--workers N]` | Parallel system-wide walk → SQLite index. Incremental by default. |
| `reaper list [--keep-below 0.2] [--project P] [-n 50]` | Themed table of indexed venvs, sorted by size or keep-probability. |
| `reaper inspect <id\|path> [--analyze]` | Full detail panel for one env; `-a` adds the AI dependency analysis. |
| `reaper analyze <id\|path>` | AI-only mode: imports vs installed vs requirements.txt diff. |
| `reaper kill <id …> [--yes] [--dry-run]` | Sends venvs to the Reaper Crypt (recoverable for 7 days). |
| `reaper restore <crypt-id>` | Brings a quarantined venv back to its original path. |
| `reaper crypt list` | Show crypt contents + days-until-expiry. |
| `reaper crypt purge [<id>] [--yes]` | Permanent delete (single id, or all expired). |
| `reaper ui` | Launch the Streamlit Hacker UI. |
| `reaper version` | Print the package version. |

All output uses the same neon palette as the web UI.

---

## ✦ &nbsp; Architecture

```
venv-reaper/
├── v2.py                                 ← Streamlit Hacker UI (thin shim now)
├── pyproject.toml                        ← PEP 621 + ruff/mypy/pytest config
├── VENV_REAPER_AI_PRODUCT_PLAN.md        ← Full product/architecture vision
│
├── src/venv_reaper/
│   ├── __init__.py
│   ├── __main__.py                       ← `python -m venv_reaper`
│   ├── config.py                         ← XDG-aware paths
│   │
│   ├── core/                             ← Pure filesystem logic
│   │   ├── markers.py                    ← VENV_MARKERS, is_venv()
│   │   ├── sizing.py                     ← dir_size, fmt_size, severity color
│   │   ├── requirements.py               ← find_req()
│   │   ├── discovery.py                  ← single-tree scanner (legacy UI)
│   │   ├── system_scan.py                ← parallel multi-root + incremental
│   │   └── quarantine.py                 ← Reaper Crypt (atomic move + TTL)
│   │
│   ├── index/                            ← SQLite source of truth
│   │   ├── schema.sql                    ← envs · packages · imports · vulns · scans
│   │   ├── db.py                         ← WAL connect + init_db
│   │   └── repository.py                 ← typed CRUD, no ORM
│   │
│   ├── ai/                               ← Phase-2 intelligence layer
│   │   ├── import_sweep.py               ← AST walker, stdlib filter
│   │   ├── import_map.json               ← Curated import→PyPI table
│   │   ├── imports_to_packages.py        ← live registry + curated + fallback
│   │   ├── installed.py                  ← site-packages METADATA parser
│   │   └── reconciler.py                 ← imports ⨉ installed ⨉ requirements
│   │
│   ├── cli/                              ← Typer entrypoint (`reaper`)
│   │   └── main.py
│   │
│   └── theme/                            ← Shared aesthetic (web + CLI)
│       ├── reaper_theme.css              ← lifted from v2.py
│       ├── matrix_rain.js
│       ├── rich_theme.py                 ← rich Theme using same hex tokens
│       └── ascii_art.py                  ← REAPER banner
│
└── tests/unit/                           ← 55 tests, runs in <1s
    ├── test_smoke.py
    ├── test_index.py
    ├── test_system_scan.py
    ├── test_quarantine.py
    ├── test_cli.py
    └── test_ai.py
```

---

## ✦ &nbsp; AI Dependency Analyzer

The `analyze` command answers: **"Of the 80 packages in this venv, which ones does my code actually need?"**

It runs three deterministic passes (an ML import-mapper plugs in later — see plan §2.4.A):

1. **AST sweep** — walks every `.py` file in the linked project, extracts top-level imports, filters out stdlib (`sys.stdlib_module_names`), handles `try/except ImportError` and conditional imports correctly.
2. **Site-packages metadata parser** — reads each `*.dist-info/METADATA` and `top_level.txt` directly (no need to activate the venv). Builds an authoritative `top_level_module → distribution_name` map.
3. **Reconciler** — diffs imports vs installed dists vs `requirements.txt`. Surfaces:
   - 🟥 **Missing**: imported in code, not installed.
   - 🟨 **Unused**: installed, never imported (transitive deps + true cruft).
   - 🟥 **Used but undeclared**: imports missing from `requirements.txt`.
   - 🟨 **Declared but unused**: requirements.txt has packages your code doesn't use.

```bash
$ reaper analyze 1
╭─ // DEPENDENCY ANALYSIS ──────────────────────────────────────────╮
│ Project                          ~/Code/myapp                     │
│ Files scanned                    47                               │
│ Distinct imports                 23                               │
│ Installed dists                  87                               │
│ Missing                          1                                │
│ Unused                           62                               │
│ Used but undeclared              3                                │
╰───────────────────────────────────────────────────────────────────╯
╭─ // IMPORTED BUT NOT INSTALLED ──────────────────────────────────╮
│  ► pandas  →  pandas                                              │
╰───────────────────────────────────────────────────────────────────╯
```

---

## ✦ &nbsp; Reaper Crypt (Safe Delete)

`kill` never calls `shutil.rmtree`. Instead it `os.rename`s the venv (atomic on the same filesystem) into:

```
~/.local/share/venv-reaper/crypt/<timestamp>-<sha8>/
├── <original-venv>/
└── manifest.json   ← original_path · size_bytes · interred_at · ttl_days
```

A 7-day TTL gives you time to undo. `reaper restore <id>` moves it back. `reaper crypt purge` clears expired entries.

This means you can run `reaper kill 1 2 3 4 5 --yes` aggressively — nothing is permanently lost until the TTL elapses.

---

## ✦ &nbsp; Development

### Run the test suite

```bash
pip install -e ".[dev]"
pytest -q
# 55 passed in ~0.4s
```

### Lint + type check

```bash
ruff check src/ tests/
mypy src/venv_reaper
```

### Run the CLI without installing

```bash
PYTHONPATH=src python3 -m venv_reaper --help
```

---

## ✦ &nbsp; Roadmap

The full plan is in [VENV_REAPER_AI_PRODUCT_PLAN.md](VENV_REAPER_AI_PRODUCT_PLAN.md). At a glance:

| Phase | Deliverables | Status |
|---|---|---|
| **MVP (W1–W6)** | Refactor → package, SQLite index, parallel system scan, Reaper Crypt, Typer CLI, AI dependency analyzer | 🟢 **W1–W3 + AI groundwork done** |
| **Alpha (W7–W14)** | ONNX import-mapping model, OSV vulnerability advisor, XGBoost keep-probability, watchdog daemon, FS-watch live updates | ⚪ Next |
| **Beta (W15–W23)** | Local LLM Copilot (`llama-cpp-python`), FastAPI server, VS Code extension | ⚪ |
| **GA (W24–W33)** | Team aggregator, JetBrains plugin, Tauri desktop wrapper, MSI/AppImage/Homebrew | ⚪ |

---

## ✦ &nbsp; Design Principles

1. **The Hacker UI is non-negotiable.** Every new surface (CLI, daemon status, IDE webview) uses the same tokens from [reaper_theme.css](src/venv_reaper/theme/reaper_theme.css).
2. **On-device by default.** No telemetry unless explicitly opted in.
3. **Reversible by default.** Quarantine, not destroy.
4. **One source of truth.** SQLite index serves every surface — no duplicated state.
5. **Don't trust filenames.** Detect by marker, not by `name == "venv"`.

---

## ✦ &nbsp; Contributing

PRs welcome — please:

- Match the existing module layout (`core/`, `ai/`, `cli/`, `theme/` …).
- Add tests in `tests/unit/`.
- Don't change the visual identity without updating both `reaper_theme.css` *and* `rich_theme.py` together — they share tokens deliberately.

---

## ✦ &nbsp; License

MIT.

---

<div align="center">

**CRAFTED WITH ⚡ BY DEEP MALVIYA**

`☠ VENV REAPER  █`

</div>
