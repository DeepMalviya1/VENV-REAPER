-- venv-reaper index schema v1
-- See VENV_REAPER_AI_PRODUCT_PLAN.md §2.2 for design.

CREATE TABLE IF NOT EXISTS envs (
    id               INTEGER PRIMARY KEY,
    path             TEXT UNIQUE NOT NULL,
    name             TEXT,
    python_version   TEXT,
    python_exe       TEXT,
    size_bytes       INTEGER,
    created_at       INTEGER,
    modified_at      INTEGER,
    last_activated   INTEGER,
    project_dir      TEXT,
    user_tag         TEXT,
    keep_probability REAL,
    last_indexed     INTEGER NOT NULL,
    hash_quick       TEXT
);

CREATE INDEX IF NOT EXISTS idx_envs_project  ON envs(project_dir);
CREATE INDEX IF NOT EXISTS idx_envs_keep     ON envs(keep_probability);
CREATE INDEX IF NOT EXISTS idx_envs_indexed  ON envs(last_indexed);

CREATE TABLE IF NOT EXISTS packages (
    env_id   INTEGER NOT NULL REFERENCES envs(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    version  TEXT,
    PRIMARY KEY (env_id, name)
);

CREATE TABLE IF NOT EXISTS imports (
    project_dir TEXT NOT NULL,
    module      TEXT NOT NULL,
    count       INTEGER DEFAULT 1,
    PRIMARY KEY (project_dir, module)
);

CREATE TABLE IF NOT EXISTS vulns (
    env_id      INTEGER NOT NULL REFERENCES envs(id) ON DELETE CASCADE,
    package     TEXT NOT NULL,
    version     TEXT,
    osv_id      TEXT NOT NULL,
    severity    TEXT,
    summary     TEXT,
    fixed_in    TEXT,
    detected_at INTEGER,
    PRIMARY KEY (env_id, package, osv_id)
);

CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY,
    started_at  INTEGER NOT NULL,
    finished_at INTEGER,
    root        TEXT,
    mode        TEXT,             -- 'full' | 'incremental' | 'targeted'
    envs_found  INTEGER,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (1, strftime('%s','now'));
