# VENV REAPER — AI Product Upgrade Plan
**Version:** 1.0 · **Author:** Senior AI Systems Architecture Review · **Status:** Proposed

> ☠ HUNT · INSPECT · DESTROY · REPEAT — now with a brain.

This document specifies a complete, production-ready evolution of `Venv-Reaper` from its current single-directory Streamlit scanner into a system-wide, AI-augmented virtual environment manager. **The signature Hacker UI is preserved end-to-end — every new surface (CLI, daemon status views, REST/IDE clients, Copilot chat, dashboards) renders in the same neon-green/Matrix-rain/scanline aesthetic established in [v2.py](v2.py).**

---

## Part 1 — Codebase Audit

### 1.1 What exists today

The entire product is a single 1,080-line file: [v2.py](v2.py). It is a **Streamlit web app** (not a true CLI, despite the original mental model).

#### High-level architecture

```
v2.py
├── Page config + Matrix-rain canvas (HTML/JS injected via st.html)            [v2.py:19-67]
├── Global hacker CSS theme (Share Tech Mono, Orbitron, neon palette)          [v2.py:72-407]
├── Session state defaults                                                     [v2.py:412-425]
├── Filesystem helpers
│   ├── is_venv() — checks pyvenv.cfg / bin/python / Scripts/python.exe        [v2.py:434-435]
│   ├── dir_size() — recursive os.scandir size sum                             [v2.py:438-451]
│   ├── fmt_size() / size_color() — human formatting + severity color         [v2.py:454-467]
│   ├── find_req() — requirements.txt search in parent + grandparent          [v2.py:470-480]
│   ├── scan_directory() — synchronous recursive walk with SKIP_DIRS          [v2.py:483-515]
│   ├── list_subdirs() / get_drives() — directory browser support             [v2.py:518-533]
├── Logging (in-session)                                                       [v2.py:539-551]
├── UI sections
│   ├── Stats panel                                                            [v2.py:557-581]
│   ├── Breadcrumb + directory browser (folder grid)                           [v2.py:587-704]
│   ├── Header / Target acquisition card                                       [v2.py:710-777]
│   ├── Scan handler with hacker-loader animation                              [v2.py:786-821]
│   ├── Hacker-table results (HTML grid + Streamlit checkboxes)                [v2.py:828-902]
│   ├── Strike Package summary + delete confirm flow                           [v2.py:906-1026]
│   ├── Session totals + terminal log + footer                                 [v2.py:1043-1080]
```

#### Strengths (must be preserved)

- **The Hacker UI is the product's soul.** The Matrix canvas (`#matrix-canvas`), the scanlines (`body::after`), the Orbitron + Share Tech Mono pairing, the four-tier severity palette (`sz-ok` / `sz-med` / `sz-high` / `sz-crit`), the hacker-loader splash with staggered `hl-l1..hl-l6` animations, the CRT-glow `--green-glow` boxes — these are tightly coordinated through CSS variables (`:root` at [v2.py:76-88]) and **must be lifted into a reusable theme package**, not rewritten.
- **Tasteful UX flow:** locked-target pill → browser overlay → scan → confirm-then-delete is hard to improve and should be carried into every new surface.
- **Cross-platform awareness** in `get_drives()` and the `Scripts/python.exe` marker.
- **Session-state defaults dictionary** ([v2.py:412-422]) is a clean, copy-pasteable pattern for state hydration.

#### Limitations (the upgrade must address each)

| # | Limitation | Evidence |
|---|---|---|
| L1 | **Single user-picked directory only** — no system-wide discovery. | `scan_directory(root)` only walks the user-locked path. |
| L2 | **`requirements.txt` "check" is presence-only** — no comparison against `site-packages`. The README pitch claims more than the code does. | `find_req()` returns the path; nothing is parsed or diff-checked. |
| L3 | **No import-graph analysis.** The tool can't tell what the venv is *actually* used for. | No AST/static analysis anywhere. |
| L4 | **No vulnerability or CVE awareness.** | No security DB integration. |
| L5 | **No "should I keep this?" intelligence.** | Selection is 100% manual. |
| L6 | **No NL / Copilot.** | None. |
| L7 | **Single-threaded sync walks** — `dir_size()` is recursive Python; large trees stall. | [v2.py:438-451] |
| L8 | **No caching / incremental rescans.** Re-scanning a 1 TB home is full-cost every time. | Nothing persisted. |
| L9 | **No daemon, no FS watch.** State is stale the moment the user closes the browser. | Streamlit only. |
| L10 | **No CLI, no API, no IDE integration.** Streamlit is the only entry point. | Single file. |
| L11 | **Monolithic file** — UI, IO, business logic, theming all in one module. Untestable. | 1,080 lines, one file. |
| L12 | **No tests, no CI, no packaging.** Project is a `git clone`-and-run script. | No `tests/`, no `pyproject.toml`, no `.github/`. |
| L13 | **Permission errors silently swallowed.** | `except (OSError, PermissionError): pass` everywhere — fine for hobby, unacceptable for system-wide scans. |
| L14 | **Logging is volatile** (in-memory list). No rotation, no debug trail. | `st.session_state.log` only. |
| L15 | **Deletion has no undo / no trash-bin escape hatch.** | `shutil.rmtree` direct. |

These map 1-to-1 onto Part 2 below.

---

## Part 2 — End-to-End Product Plan

### 2.0 Guiding principles

1. **Hacker UI is non-negotiable.** Every surface — CLI, TUI, web dashboard, IDE webview, Copilot chat — uses the same theme tokens lifted from [v2.py:76-88]. Themed via `rich` (TUI/CLI) and a shared CSS package (`reaper-theme.css`) for web/IDE/dashboard.
2. **On-device by default.** All AI runs locally. Telemetry is opt-in. SQLite (optionally SQLCipher) for persistence.
3. **One source of truth.** A single SQLite index serves CLI, daemon, web UI, REST API, and IDE plugins. No duplicated state.
4. **Modular monorepo.** Replace `v2.py` with a proper `src/venv_reaper/` package; old file is kept as a thin Streamlit shim that imports the new package, then deprecated in Phase 2.
5. **Reversible by default.** `shutil.rmtree` is replaced with a quarantine ("Reaper Crypt") that allows N-day undo before true deletion.

### 2.1 Proposed Repository Layout

```
venv-reaper/
├── pyproject.toml                       # PEP 621, hatchling
├── README.md
├── CHANGELOG.md
├── VENV_REAPER_AI_PRODUCT_PLAN.md       # ← this doc
├── src/venv_reaper/
│   ├── __init__.py
│   ├── __main__.py                      # `python -m venv_reaper`
│   ├── core/
│   │   ├── discovery.py                 # System-wide scanner (replaces scan_directory)
│   │   ├── walker.py                    # Parallel, cancellable os.walk wrapper
│   │   ├── markers.py                   # is_venv() + extended marker rules
│   │   ├── sizing.py                    # dir_size with batching + ionice/IO_PRIORITY
│   │   ├── requirements.py              # parse + diff against site-packages
│   │   └── quarantine.py                # Reaper Crypt: trash + restore
│   ├── index/
│   │   ├── db.py                        # SQLite (+ SQLCipher) connection pool
│   │   ├── schema.sql                   # tables defined in §2.2
│   │   ├── repository.py                # CRUD + query helpers
│   │   └── migrations/                  # alembic-style migration files
│   ├── ai/
│   │   ├── imports_to_packages.py       # ONNX CodeBERT → PyPI mapping
│   │   ├── valuation.py                 # XGBoost keep-probability
│   │   ├── advisor.py                   # OSV vulnerability matcher + LLM summarizer
│   │   ├── copilot.py                   # llama-cpp-python chat agent + tools
│   │   ├── embeddings.py                # sentence-transformers (MiniLM) wrapper
│   │   └── models/                      # downloaded weights (gitignored)
│   ├── daemon/
│   │   ├── service.py                   # main loop
│   │   ├── watch.py                     # watchdog (inotify/FSEvents/ReadDirectoryChangesW)
│   │   ├── ipc.py                       # Unix socket / Windows named pipe
│   │   └── platform/
│   │       ├── systemd.service
│   │       ├── launchd.plist
│   │       └── windows_service.py
│   ├── api/
│   │   ├── server.py                    # FastAPI app
│   │   ├── routers/
│   │   │   ├── envs.py
│   │   │   ├── scan.py
│   │   │   ├── advisor.py
│   │   │   └── copilot.py
│   │   ├── schemas.py                   # Pydantic models
│   │   └── auth.py                      # local-loopback token
│   ├── cli/
│   │   ├── main.py                      # Typer app: `reaper` entrypoint
│   │   ├── commands/                    # scan, list, kill, ask, watch, daemon
│   │   └── interactive.py               # Textual-based hacker TUI
│   ├── web/                             # Streamlit shim (legacy) + new dashboard
│   │   ├── streamlit_app.py             # current v2.py refactored to thin views
│   │   └── dashboard/                   # optional Tauri/PyWebView desktop wrapper
│   ├── theme/
│   │   ├── reaper_theme.css             # extracted from v2.py:72-407
│   │   ├── matrix_rain.js               # extracted from v2.py:29-67
│   │   ├── rich_theme.py                # rich Theme + Console for CLI/TUI
│   │   └── ascii_art.py                 # ☠ banners, headers
│   ├── config.py                        # XDG-aware TOML loader
│   └── logging.py                       # rotating file logs + rich console
├── tests/
│   ├── unit/
│   ├── integration/
│   └── system/
├── extensions/
│   ├── vscode/                          # TypeScript extension
│   └── jetbrains/                       # Kotlin plugin
├── packaging/
│   ├── homebrew/reaper.rb
│   ├── windows/reaper.wxs               # WiX MSI
│   ├── appimage/AppImageBuilder.yml
│   └── pypi/                            # PEP 517 build config
└── .github/workflows/
    ├── ci.yml
    ├── release.yml
    └── model-refresh.yml
```

### 2.2 The Index — One Schema to Rule Them All

SQLite at `${XDG_DATA_HOME}/venv-reaper/index.db` (encrypted optional). The daemon owns writes; everything else reads.

```sql
-- envs: one row per detected virtual environment
CREATE TABLE envs (
  id              INTEGER PRIMARY KEY,
  path            TEXT UNIQUE NOT NULL,
  name            TEXT,
  python_version  TEXT,            -- parsed from pyvenv.cfg
  python_exe      TEXT,
  size_bytes      INTEGER,
  created_at      INTEGER,         -- ctime
  modified_at     INTEGER,         -- mtime
  last_activated  INTEGER,         -- best-effort: shell history scan
  project_dir     TEXT,            -- linked project (see §2.3)
  user_tag        TEXT,            -- "keep" / "archive" / "?" — manual override
  keep_probability REAL,           -- §2.4.B output [0..1]
  last_indexed    INTEGER,
  hash_quick      TEXT             -- mtime+size hash for incremental rescan
);
CREATE INDEX idx_envs_project ON envs(project_dir);
CREATE INDEX idx_envs_keep    ON envs(keep_probability);

-- packages: installed packages per env (parsed from site-packages metadata)
CREATE TABLE packages (
  env_id    INTEGER REFERENCES envs(id) ON DELETE CASCADE,
  name      TEXT,
  version   TEXT,
  PRIMARY KEY(env_id, name)
);

-- imports: distinct top-level imports detected across the linked project
CREATE TABLE imports (
  project_dir TEXT,
  module      TEXT,
  count       INTEGER,
  PRIMARY KEY(project_dir, module)
);

-- vulns: matched CVE/OSV records for installed package versions
CREATE TABLE vulns (
  env_id     INTEGER REFERENCES envs(id) ON DELETE CASCADE,
  package    TEXT, version TEXT,
  osv_id     TEXT, severity TEXT,
  summary    TEXT, fixed_in TEXT,
  detected_at INTEGER
);

-- scans: history of scan runs (for incremental & telemetry)
CREATE TABLE scans (
  id INTEGER PRIMARY KEY, started_at INTEGER, finished_at INTEGER,
  root TEXT, mode TEXT, envs_found INTEGER
);
```

### 2.3 System-Wide Discovery (addresses L1, L7, L8)

Replaces the single-tree walker at [v2.py:483-515].

#### Scan roots

| Platform | Roots |
|---|---|
| Linux | `$HOME`, `/opt`, `/srv`, `/var/lib`, `/usr/local`, `/tmp` (opt-in) — skip `/proc`, `/sys`, `/dev`, `/snap`, network mounts |
| macOS | `$HOME`, `/Applications`, `/usr/local`, `/opt`, `/Volumes/*` (opt-in) — skip `/System`, Time Machine snapshots |
| Windows | `%USERPROFILE%`, `C:\` … `Z:\` (drives from `get_drives()` extended), `%PROGRAMDATA%` — skip `C:\Windows`, `C:\$Recycle.Bin`, `System Volume Information` |

#### Algorithm — `discovery.system_scan()`

1. **Bootstrap:** load `last_indexed` per-root from `scans`. If absent → full scan; else → incremental.
2. **Parallel BFS:** `concurrent.futures.ThreadPoolExecutor` with worker count = `min(32, os.cpu_count()*4)` (IO-bound). One task per directory; bounded queue to keep memory flat.
3. **Cancel & throttle:** all walks observe `cancel_event: threading.Event`; on laptop battery, fall back to single thread.
4. **Marker check:** rule-of-three — `pyvenv.cfg`, OR `bin/python*`, OR `Scripts/python.exe`. Extend [v2.py:430-435] with `conda-meta/`, `poetry.lock`-adjacent `.venv`, `Pipfile.lock`, `__pypackages__/` (PEP 582).
5. **Skip set:** the existing `SKIP_DIRS` ([v2.py:431]) is extended with platform-specific entries plus a configurable user list.
6. **Permission policy:** swallowed `PermissionError` is replaced with structured logging — counted per scan and surfaced in the CLI/UI ("⚠  3,221 directories not readable; run with `sudo` to include them").
7. **Project linkage:** for each found venv, walk **up** from `path.parent` looking for project markers (`.git`, `pyproject.toml`, `setup.py`, `package.json`). First hit becomes `project_dir`.
8. **Last activation:** scan `~/.bash_history`, `~/.zsh_history`, `~/.config/fish/fish_history`, PowerShell `ConsoleHost_history.txt` for `activate` lines mentioning this path. Best-effort, opt-in.
9. **Quick hash:** `hash_quick = sha1(f"{mtime}|{size_bytes}")`; if unchanged on incremental scan, skip re-walk of contents.
10. **Live updates:** the daemon (§2.5) keeps the index hot via `watchdog` so subsequent CLI/UI runs are **instant**.

#### Cross-platform IO niceness

- Linux: `os.posix_fadvise` for sequential reads, `ionice -c 3` if available.
- Windows: `SetThreadPriority(THREAD_MODE_BACKGROUND_BEGIN)` via `ctypes`.
- macOS: `setiopolicy_np` for utility class.

### 2.4 AI Layer (addresses L2–L6)

All models run locally. Models live in `~/.local/share/venv-reaper/models/` and are SHA-256 verified on download.

#### A. Code-to-Package Mapping

**Goal:** answer "what does this project actually need?" by reading `*.py` files instead of trusting `requirements.txt`.

**Pipeline:**

1. **AST sweep** of every `.py` under `project_dir`: extract `import X` and `from X import Y`. Use `ast.NodeVisitor` (handles `try/except ImportError` correctly).
2. **Stdlib filter:** `sys.stdlib_module_names` (3.10+).
3. **Heuristic mapping table** (`ai/models/import_map.json`) — bundled, ~3,000 hand-curated entries (`cv2 → opencv-python`, `PIL → pillow`, `sklearn → scikit-learn`). Covers ~85% of cases.
4. **Fallback ML model:** a quantised `microsoft/codebert-base` exported to ONNX (see `optimum.onnxruntime`). Input = top-level module name + 5 lines of context; output = top-3 PyPI candidates with confidence. Inference via `onnxruntime` (CPU, <50 ms per query, batched).
5. **Confidence-gated reconciliation:** if heuristic + model agree → green. If only model with confidence > 0.85 → yellow. Else → flag for user.

**Training data sources** (all permissive licence):
- **PyPI top-15k packages** (`packages.json` + `top-pypi-packages` dataset).
- **GitHub `pyproject.toml` corpus** sampled via the BigQuery public dataset (`bigquery-public-data.github_repos`).
- **`importlib.metadata.packages_distributions()`** harvested from a corpus of containerised installs to ground-truth `import → distribution` pairs.

**Output:** `dependencies_inferred.txt` written next to the venv on demand (`reaper recreate`), and a diff card in the UI: *"Installed but never imported: 47 pkgs · Imported but missing: 2 pkgs (`requests`, `pyyaml`)"*.

#### B. Environment Valuation (Keep-Probability Classifier)

**Goal:** rank venvs by "safe-to-delete" so the user sees pre-checked boxes for the obvious cruft.

**Model:** `xgboost.XGBClassifier`, max_depth=6, ~50k tree boosting rounds with early stopping. Trained offline; ships as `keep_clf.json` (~200 KB) loaded with `xgboost.Booster.load_model`.

**Features (engineered in `ai/valuation.py`):**

| Feature | Source |
|---|---|
| `days_since_modified` | `envs.modified_at` |
| `days_since_activated` | `envs.last_activated` |
| `days_since_project_commit` | `git log -1 --format=%ct` in `project_dir` |
| `project_has_pyproject` | bool |
| `project_in_open_editor` | VS Code workspaces JSON, JetBrains recent projects |
| `pkg_count` | from `packages` |
| `pkg_count_unique_to_this_env` | dedup vs. other envs of same project |
| `python_version_eol` | bool, from EOL list |
| `size_mb` | already computed |
| `duplicate_of_other_env` | content-hash of `packages` table |
| `user_tag` | manual override → forces 0/1 |

**Training data without compromising privacy:**

1. **Synthetic seed:** generate ~10,000 venvs across CI containers with known labels (one-shot tutorial venv = delete; 6-month active project = keep).
2. **Opt-in user telemetry:** during a closed beta, anonymised feature vectors (no paths, no package names — just numeric features and the user's final keep/delete decision) are uploaded to a S3 bucket with explicit consent. SHA-256 hash of `path` is the only identifier.
3. **Self-supervised refinement:** the daemon observes which venvs the user manually deletes vs. activates, fine-tuning the classifier locally with `xgboost.train(xgb_model=existing)` every 30 days. **All training happens on-device** after telemetry phase ends.

**UI surfacing:** keep-probability becomes a new column in the Hacker Table — `KEEP` with a green-to-red bar (reusing the existing `--green`/`--yellow`/`--red` palette from [v2.py:76-88]) and pre-checks rows with `keep_probability < 0.15`.

#### C. Vulnerability Advisor

**Local DB:**
- **OSV** — daily download of `https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip` (~30 MB compressed). Stored at `~/.local/share/venv-reaper/osv/`.
- **GitHub Advisory mirror** for cross-reference (optional, requires GitHub PAT).
- Refresh via `model-refresh.yml` cron in CI which publishes a signed bundle; clients pull the bundle (so users don't need internet at scan time).

**Matching:**
1. For each `(package, version)` in `packages`, look up matching OSV records.
2. SemVer range matching using `packaging.specifiers.SpecifierSet`.
3. Embed CVE summary with `sentence-transformers/all-MiniLM-L6-v2` (90 MB, CPU-friendly). Top-5 nearest summaries become RAG context for the LLM (§D).

**Risk report (per env):**
```
☠  CRITICAL: 2  ⚠  HIGH: 5  ⚙  MED: 11
  └─ pyyaml 3.13         CVE-2017-18342  RCE   → fixed in 5.4
  └─ urllib3 1.24.1      CVE-2021-33503  DoS   → fixed in 1.26.5
[ASK COPILOT FOR REMEDIATION] [GENERATE PATCH BRANCH]
```

The patch-branch command writes a new `requirements.txt`, runs `pip-compile --upgrade`, and produces a unified diff — never modifies the live venv without explicit confirmation.

#### D. Natural-Language Copilot

**Stack:** `llama-cpp-python` running a 4-bit quantised **Llama-3.1-8B-Instruct** GGUF (~4.8 GB, runs comfortably on 16 GB RAM laptops) or **Qwen2.5-Coder-7B** as a smaller alternative for code-savvy questions.

**Tool/function calling:** exposed via `llama-cpp-python`'s grammar-constrained generation. The LLM has structured access to the index:

| Tool | Signature |
|---|---|
| `list_envs(filter: str | None) → list[Env]` | filter is a SQL-safe predicate validated against an allow-list |
| `inspect_env(env_id) → dict` | size, packages, vulns |
| `find_outdated(package: str) → list[Env]` | answers the headline use case |
| `keep_probability_below(threshold: float) → list[Env]` | "show me the cruft" |
| `quarantine(env_ids: list[int])` | safe delete (write-only, requires user confirm token) |
| `recreate(env_id, target_path)` | runs `python -m venv` + `pip install` from inferred deps |

**Why structured tools, not free SQL?** Stops the LLM from issuing `DROP TABLE` regardless of jailbreak attempts.

**Example transcripts (rendered in hacker chat UI — see §2.5):**

> **`>` which of my environments use an outdated numpy?**
> `[COPILOT]` Calling `find_outdated('numpy')`...
> `[COPILOT]` 4 envs match. Worst offender: `~/Code/old-thesis/venv` has `numpy 1.16.4` — 4 known CVEs, latest is `2.1.0`.
> `[COPILOT]` Want me to quarantine `old-thesis` (last touched 2021-04-11, keep-prob 0.04)?

> **`>` clean up everything I haven't used in a year**
> `[COPILOT]` Found 23 envs idle ≥ 365 days, total 14.7 GB. None have uncommitted git changes upstream. Confirm to send to Crypt?

**UI rendering:** the chat interface lives in (a) the Streamlit app as a new `// COPILOT` card, (b) the Textual TUI (`reaper ask`), and (c) the IDE webview — all using the same `terminal { ... }` CSS class from [v2.py:271-281] and the existing `t-ok / t-info / t-warn / t-err / t-dim` color spans.

### 2.5 Architecture & Surfaces (addresses L9, L10, L11)

#### A. Daemon (`venv-reaper-daemon`)

- **Role:** sole writer of `index.db`; runs FS watch; refreshes vuln DB nightly; recomputes `keep_probability` weekly.
- **Implementation:** plain Python `asyncio` event loop in `daemon/service.py`, no Celery/Redis (overkill).
- **FS watch:** `watchdog` library — inotify (Linux), FSEvents (macOS), `ReadDirectoryChangesW` (Windows). Watches scan roots with debounce (5 s) and only reacts to creation of marker files (`pyvenv.cfg` etc.) to avoid hot churn.
- **IPC:** Unix domain socket at `${XDG_RUNTIME_DIR}/venv-reaper.sock` / Windows named pipe `\\.\pipe\venv-reaper`. JSON-RPC framing (newline-delimited).
- **Lifecycle:** systemd user service (`~/.config/systemd/user/venv-reaper.service`), `launchd` plist on macOS (`~/Library/LaunchAgents/`), Windows Service via `pywin32`. Templates in `daemon/platform/`.
- **Resource ceiling:** `resource.setrlimit(RLIMIT_AS, ...)` on POSIX; soft cap 512 MB RSS; CPU yields when `psutil.cpu_percent() > 80`.

#### B. CLI — `reaper`

Built with **Typer** (autocomplete, types) + **Rich** (themed via [v2.py:76-88] colors). Examples:

```
reaper scan [--full | --incremental] [--root PATH ...]
reaper list [--keep-prob-below 0.2] [--json]
reaper inspect <env-id-or-path>
reaper kill <env-id-or-path> [--dry-run]
reaper recreate <env-id> [--target PATH]
reaper advise [--severity high|critical]
reaper ask "<question>"             # one-shot copilot
reaper chat                          # interactive TUI chat
reaper watch                         # tail daemon events
reaper daemon {start|stop|status|logs}
reaper ui                            # launches Streamlit (legacy + new)
reaper config edit
```

The `rich.theme.Theme` in `theme/rich_theme.py` mirrors the CSS variables one-to-one, so `[venv]Hello[/venv]` in any CLI command emits #00ff41 with bold Orbitron-style spacing where the terminal supports it.

#### C. TUI — `reaper chat`, `reaper ui --tui`

Built with **Textual**. Shipped widgets:
- `MatrixRain` (canvas via Textual's `RichLog` with periodic random-glyph render — replicates the JS effect at [v2.py:42-65]).
- `HackerTable` (extends `DataTable`, with the `ht-row.selected` selection style port).
- `HackerLoader` (recreates the staggered `hl-l1..hl-l6` lines from [v2.py:803-808]).
- `CopilotChat` (input pane + scrollable transcript, themed via `rich`).

This gives power users a **GUI-free, SSH-friendly hacker experience** that visually matches the Streamlit app.

#### D. REST API — `venv-reaper-api`

**FastAPI**, bound to `127.0.0.1` only by default. Token auth via a per-install secret in `~/.config/venv-reaper/api.token` (mode 0600).

```
GET    /v1/envs?keep_prob_lt=0.2&limit=100
GET    /v1/envs/{id}
POST   /v1/scan
POST   /v1/envs/{id}/quarantine
POST   /v1/envs/{id}/restore
GET    /v1/advisor/{env_id}
POST   /v1/copilot/ask          {"question": "..."}
GET    /v1/copilot/stream       (SSE)
GET    /v1/health
```

OpenAPI spec auto-published at `/docs` (themed via custom Swagger CSS using the same palette).

#### E. IDE Extensions

- **VS Code** (`extensions/vscode/`): TypeScript extension that consumes the local REST API. Single sidebar view (`reaper.envs`) renders the venv list as a webview using the bundled `reaper-theme.css` — **identical look to the Streamlit hacker table**. Commands: `Reaper: Scan Now`, `Reaper: Ask Copilot`, `Reaper: Open Crypt`. Status-bar item shows `☠ 23 envs · 14.7 GB recoverable` in neon green.
- **JetBrains** (`extensions/jetbrains/`): Kotlin plugin, JCEF browser hosting the same webview HTML.

The extensions are **thin clients** — all logic lives in the daemon/API, so they stay tiny and easy to ship.

#### F. Optional Desktop Dashboard

A **Tauri 2** app (Rust shell + WebView) wrapping the FastAPI + a single-page dashboard. Not Electron — Tauri keeps the binary at ~10 MB, fits the lean hacker ethos. Window chrome is overridden with a **CRT bezel** (custom titlebar with `text-shadow:0 0 15px #00ff41`). All HTML/CSS is `reaper-theme.css`; rounded corners explicitly forbidden in the design system.

#### G. Streamlit shim (legacy)

[v2.py](v2.py) is refactored into `web/streamlit_app.py` whose UI code becomes thin: it imports `venv_reaper.core` and `venv_reaper.theme` and renders the same cards/tables but reads from the index DB instead of running its own walk. Keeps existing users on the path they know.

### 2.6 Tech Stack Summary

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | matches existing code |
| Packaging | `hatchling` + `pyproject.toml` | PEP 621, simple |
| CLI | `typer` + `rich` | typed, themable |
| TUI | `textual` | hacker theme port |
| Web | `streamlit` (legacy) + `fastapi` + `uvicorn` | reuse existing UI |
| Desktop | `tauri@2` (Rust) | small, themable |
| DB | `sqlite3` + optional `pysqlcipher3` | zero-deps, encryptable |
| ORM | none — `repository.py` raw SQL | predictable, fast |
| FS watch | `watchdog` | cross-platform |
| Concurrency | `concurrent.futures.ThreadPoolExecutor` + `asyncio` (daemon) | IO-bound |
| LLM | `llama-cpp-python` + Llama-3.1-8B Q4_K_M GGUF | local, capable |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | small, fast |
| Classifier ML | `xgboost` | best on tabular |
| Code model | `microsoft/codebert-base` exported to ONNX via `optimum.onnxruntime` | CPU-fast |
| Vuln DB | `osv-scanner`-format JSON (downloaded) | upstream-maintained |
| Logging | stdlib `logging` + `RotatingFileHandler` | simple |
| Tests | `pytest`, `pytest-cov`, `hypothesis`, `tox` | standard |
| Lint/format | `ruff`, `mypy --strict` | one-stop |
| CI | GitHub Actions matrix (linux/macos/windows × py 3.11/3.12) | |
| Distribution | PyPI (`pip install venv-reaper`), Homebrew tap, MSI (WiX), AppImage | |
| Config | `tomli`/`tomllib` at `${XDG_CONFIG_HOME}/venv-reaper/config.toml` | XDG-compliant |

### 2.7 Production-Readiness (addresses L13, L14, L15)

#### Error handling

- All swallowed `except (OSError, PermissionError): pass` from [v2.py:447, 450, 489, 524] become `logger.debug` + a counter (`scan.permission_denied += 1`). The counter is surfaced in the post-scan summary card.
- Retry logic: `tenacity` decorators on transient IO (e.g., reading `pyvenv.cfg` while the file is being written by another `python -m venv`).
- `EnvironmentError` taxonomy: custom exceptions (`VenvCorruptError`, `IndexLockedError`, `ModelMissingError`) with hacker-styled error messages (`☠ FATAL` / `⚠ WARN` consistent with [v2.py:282-286]).

#### Permission escalation

- The CLI never auto-sudo-elevates. Instead it surfaces:
  - `[INFO] 12,344 dirs unreadable. Run `sudo reaper scan --root /opt --full` to include them.`
- Daemon refuses to run as root by default (refused with hacker error: `☠ DAEMON DECLINES ROOT — DROP PRIVILEGES`).

#### Quarantine ("Reaper Crypt")

- `shutil.rmtree` from [v2.py:997] is replaced with `quarantine.move_to_crypt(path)` which `os.rename`s into `${XDG_DATA_HOME}/venv-reaper/crypt/<timestamp>-<sha8>/` — same filesystem so the move is atomic.
- TTL: configurable, default 7 days. After TTL, daemon's nightly task purges.
- `reaper restore <id>` and a Streamlit "🪦 CRYPT" tab let users undo.

#### Logging

- `logging.handlers.RotatingFileHandler` at `${XDG_STATE_HOME}/venv-reaper/log/reaper.log`, 10 MB × 5 files.
- Console handler uses `RichHandler` themed to match the in-app `terminal { ... }` block.
- Structured JSON option (`--log-format json`) for IDE consumers.

#### Performance

- Discovery walk is parallelised (§2.3) — target: index a 5 TB home in < 90 s on warm cache, < 5 min cold.
- Daemon keeps it < 2 s for incremental updates via FS-watch.
- `keep_probability` recomputation is incremental: only env IDs whose features changed.
- LLM streaming: `llama-cpp-python` `stream=True` so first token < 500 ms on M2 / Ryzen 7.

#### Test strategy

| Layer | Tooling | What it covers |
|---|---|---|
| Unit | `pytest`, `hypothesis` | every helper in `core/`, `index/repository.py`, `ai/imports_to_packages.py` |
| Integration | `pytest` + `tmp_path` fixtures that build fake venvs (`pyvenv.cfg`, fake `bin/python` symlinks) | discovery + sizing + DB upserts end-to-end |
| AI | golden-file tests on a frozen `tests/fixtures/imports/` corpus; tolerance on confidence scores | model regression |
| TUI | `textual.pilot` | snapshot tests of TUI screens |
| Web | `streamlit.testing.v1.AppTest` | session-state flows |
| API | `httpx.AsyncClient` against FastAPI in-process | endpoints + auth |
| System | GitHub Actions matrix, ephemeral Linux VM scans `/` | smoke + perf budgets |
| Security | `bandit`, `pip-audit`, custom OSV self-test (run advisor on its own deps) | meta-correctness |

CI (`/.github/workflows/ci.yml`):
- Matrix: ubuntu/macos/windows × py3.11/3.12.
- Steps: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest --cov=venv_reaper --cov-fail-under=85`, `bandit -r src/`.
- Release pipeline (`release.yml`): tag-triggered, builds wheel + sdist, signs with Sigstore, uploads to PyPI, builds Homebrew bottle, packages MSI/AppImage.

#### Security

- All AI inference local. No network calls outside the explicit `reaper update-vulndb` and `reaper update-models` commands.
- Encryption-at-rest: optional `--encrypt-index` flag swaps SQLite for SQLCipher; key derived from OS keyring (Linux: Secret Service, macOS: Keychain, Windows: Credential Manager).
- Telemetry: **opt-in only**, off by default, scope strictly limited (numeric features, no paths). Documented in `PRIVACY.md`. Endpoint signed with HTTPS pinning.
- Supply-chain: lockfile (`uv.lock`), all model weights pinned by SHA-256, GitHub Actions OIDC for PyPI publish (no long-lived tokens).

### 2.8 Productisation & Monetisation

#### Personas

| Persona | Top JTBD |
|---|---|
| **Solo dev (Rohan)** | "Free up the 40 GB of dead venvs cluttering my MacBook" |
| **Data scientist (Maya)** | "Find which of my 60 ML envs have CVE-vulnerable `tensorflow` and recreate clean ones" |
| **Tech lead (Daniel)** | "Audit which venvs my team has outside `~/Projects` and enforce policy" |
| **Security engineer (Priya)** | "Continuous CVE coverage on every Python env across our developer fleet, integrated with our SIEM" |
| **Educator/Bootcamp instructor** | "Help students reset their environments without breaking their projects" |

#### Tiered offering

| Tier | Price | What's in it |
|---|---|---|
| **Free** | $0 | System-wide scan, hacker UI, manual delete with Crypt, single-machine, package list. (Roughly today's [v2.py] but indexed and system-wide.) |
| **Pro (individual)** | $5/mo or $48/yr | All AI features: Copilot, vuln advisor, keep-probability, code-to-package mapping, recreate, IDE extensions full features. |
| **Team** | $12/user/mo | Shared dashboards (self-hosted REST aggregator), policy rules ("no Python 3.7 envs", "auto-quarantine after 60 days"), Slack/Teams integration. |
| **Enterprise** | custom | Self-hosted aggregator, SSO, audit log to SIEM, signed model bundles, on-prem CVE feed, indemnity. |

#### Go-to-market

1. **Launch as free VS Code extension** with embedded webview (the existing Streamlit + Matrix-rain look ports directly via the `reaper-theme.css` package). The extension's `☠ 23 envs · 14.7 GB` status-bar item is visible to every Python developer and is itself viral.
2. **Hacker News / r/Python launch post** centred on the Hacker UI screenshots and the *"AI told me which 14 GB to delete"* moment.
3. **YouTube demo** — terminal reaper + Matrix rain + LLM dialogue. The aesthetic is the marketing.
4. **Paid upgrade prompt** triggers contextually inside the free tier — first time a CVE is matched, the free user sees: *"4 critical CVEs in 2 envs · UPGRADE TO REVEAL → [Pro Trial]"*. Themed in the existing `.btn-danger` style ([v2.py:188-198]).
5. **Conversion lever:** the "recreate clean venv" command in Pro tier is the most-shared action; making it easy to demo creates word-of-mouth.

### 2.9 Implementation Roadmap

> Effort is in **dev-weeks of one senior engineer**. Two-engineer parallelisation can roughly halve calendar time.

#### Phase 1 — MVP (foundation, 6 dev-weeks)
**Deliverables:** indexed system-wide scanner + refactored Streamlit app + CLI skeleton.

- [W1] Repo split: turn [v2.py] into `src/venv_reaper/` package; lift theme tokens into `theme/`. Streamlit app keeps working.
- [W2] SQLite index + `core/discovery.py` parallel walker + system-roots logic + cache.
- [W3] Typer CLI: `scan`, `list`, `inspect`, `kill` (Crypt-based). `rich` themed output.
- [W4] Tests + CI matrix + `pyproject.toml`/PyPI publish.
- [W5] Streamlit refactored to read from the index. New "// SYSTEM-WIDE RECON" view.
- [W6] Documentation, screenshots, **Hacker News launch**.

**Wow moment:** *"`reaper scan` finds every venv on your machine in seconds — same Matrix-rain UI, now on steroids."*

#### Phase 2 — Alpha (intelligence, 8 dev-weeks)
**Deliverables:** import-graph mapping, keep-probability, vuln advisor, daemon.

- [W7-8] AST sweeper + heuristic mapping table + ONNX CodeBERT integration. `reaper recreate`.
- [W9] OSV downloader + matcher + risk-report card (re-uses existing severity color palette).
- [W10] XGBoost keep-probability classifier (ship pretrained on synthetic data; collect opt-in beta data).
- [W11-12] Daemon + `watchdog` + IPC + systemd/launchd/Windows service templates.
- [W13] Quarantine/Crypt + restore.
- [W14] Closed beta (50 users), telemetry-opt-in, feedback loop.

**Wow moment:** *"Reaper showed me 47 packages I install but never import — and 2 CVE-critical vulns I had no idea about. All without leaving my terminal."*

#### Phase 3 — Beta (Copilot + IDE, 8 dev-weeks)
**Deliverables:** local LLM Copilot, REST API, VS Code extension.

- [W15-16] `llama-cpp-python` integration, function-calling tools, prompt safety harness.
- [W17] CopilotChat in Streamlit + Textual TUI.
- [W18-19] FastAPI server, auth, OpenAPI docs themed.
- [W20-22] VS Code extension: webview, sidebar, status bar, three commands.
- [W23] Public beta launch + Pro tier billing (Stripe) + license server.

**Wow moment:** *"In VS Code, I asked: 'which envs use outdated numpy?' — neon-green Matrix Copilot answered, then quarantined them on confirmation. The whole experience is one continuous hacker movie."*

#### Phase 4 — GA (Team + Enterprise, 10 dev-weeks)
**Deliverables:** Team dashboards, JetBrains plugin, Tauri desktop, MSI/AppImage/Homebrew.

- [W24-26] Team aggregator service (multi-machine, opt-in, encrypted at rest).
- [W27-28] JetBrains plugin (Kotlin, JCEF webview reusing the same HTML).
- [W29-30] Tauri desktop wrapper (CRT bezel, retro chrome).
- [W31] MSI/AppImage/Homebrew packaging.
- [W32] Enterprise: SSO, SIEM export, signed bundles.
- [W33] GA launch event, paid-tier rollout completes.

**Wow moment:** *"The whole engineering org runs the same hacker-themed reaper — and the Slack channel pings with `☠  3 critical CVEs detected on @maya's mac` in green-on-black."*

---

## Appendix A — Mapping each L# to the section that resolves it

| Limitation | Resolved in |
|---|---|
| L1 single-dir | §2.3 System-Wide Discovery |
| L2 req presence-only | §2.4.A imports_to_packages + diff |
| L3 no import graph | §2.4.A AST sweeper |
| L4 no CVE | §2.4.C Vulnerability Advisor |
| L5 no keep-suggestion | §2.4.B Valuation classifier |
| L6 no NL | §2.4.D Copilot |
| L7 sync walk | §2.3 ThreadPoolExecutor + niceness |
| L8 no cache | §2.2 SQLite index + `hash_quick` |
| L9 no daemon | §2.5.A Daemon |
| L10 no CLI/API/IDE | §2.5.B-E |
| L11 monolith | §2.1 modular package layout |
| L12 no tests/pkg | §2.7 test matrix + §2.6 packaging |
| L13 silent permerrors | §2.7 structured logging + counters |
| L14 volatile log | §2.7 RotatingFileHandler |
| L15 no undo | §2.7 Quarantine/Crypt |

## Appendix B — Hacker UI Continuity Checklist

Every new surface must pass this checklist before merge:

- [ ] Uses CSS variables from `theme/reaper_theme.css` (lifted from [v2.py:76-88]).
- [ ] Matrix rain (web) or `MatrixRain` widget (TUI) renders behind primary content.
- [ ] Headings in Orbitron (700/900) with `text-shadow: 0 0 20px #00ff41`.
- [ ] Body in Share Tech Mono.
- [ ] Severity colors map: green (`#00ff41`) → yellow (`#f0e040`) → orange (`#ff8c00`) → red (`#ff2222`). No deviations.
- [ ] Buttons styled with `btn-primary` / `btn-cyan` / `btn-danger` patterns from [v2.py:181-209].
- [ ] No rounded corners > 4 px.
- [ ] No emoji unless from the existing whitelist (`☠ ⚡ ✔ ✘ ⚠ █ ▋ ▊ 📂 🪦`).
- [ ] Loader animations replicate the staggered `hl-l1..hl-l6` cadence ([v2.py:341-346]).
- [ ] Footer signature: `CRAFTED WITH ⚡ BY DEEP MALVIYA` preserved.

## Appendix C — Concrete first PR (start here on Day 1)

```bash
# Day-1 PR: foundational refactor, zero behavior change
git checkout -b refactor/extract-package
mkdir -p src/venv_reaper/{core,theme,index,cli,web}
git mv v2.py src/venv_reaper/web/streamlit_app.py

# Extract:
#   v2.py:430-515  → src/venv_reaper/core/{markers.py,sizing.py,requirements.py,discovery.py}
#   v2.py:72-407   → src/venv_reaper/theme/reaper_theme.css
#   v2.py:29-67    → src/venv_reaper/theme/matrix_rain.js
#   v2.py:412-422  → src/venv_reaper/web/state.py

# Then in streamlit_app.py replace inline definitions with:
#   from venv_reaper.core.discovery import scan_directory
#   from venv_reaper.theme import inject_matrix_rain, inject_theme_css

# Add pyproject.toml, ruff, mypy, pytest with one smoke test that the
# Streamlit app launches and returns 200 on the index route via AppTest.
```

This single PR gives you a testable, packagable skeleton without changing what the user sees — the perfect launchpad for everything in Phases 2–4.

---

*☠ END OF PLAN ☠*
