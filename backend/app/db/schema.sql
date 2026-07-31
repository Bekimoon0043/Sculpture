-- schema.sql — LuxuryForm Studio v1 (Phase 1)
-- SQLite, WAL mode. All timestamps are UTC ISO-8601 text.
-- The FULL table set is created now (approved plan §D3) so no table is ever
-- retrofitted; later-phase tables carry minimal-but-real columns and are
-- documented in DECISIONS.md (ADR-001).

-- ---------------------------------------------------------------------------
-- Phase 1 tables (in active use now)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,           -- UTC ISO-8601
    ended_at        TEXT,                    -- NULL while running
    status          TEXT NOT NULL,           -- active | ended | halted
    total_cost_usd  REAL NOT NULL DEFAULT 0  -- aggregate; ai_calls stays source of truth
);

CREATE TABLE IF NOT EXISTS ai_calls (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    ts              TEXT NOT NULL,           -- UTC ISO-8601
    provider        TEXT NOT NULL,           -- anthropic | openai | kimi
    model           TEXT NOT NULL,
    purpose         TEXT NOT NULL,           -- e.g. gate_phase1_text, researcher, designer
    prompt          TEXT NOT NULL,           -- full prompt, always (Rule 8)
    response        TEXT NOT NULL,           -- full response, always (Rule 8); '' on error
    tokens_in       INTEGER NOT NULL,
    tokens_out      INTEGER NOT NULL,
    latency_ms      REAL NOT NULL,
    cost_usd        REAL NOT NULL,
    pricing_version TEXT NOT NULL,           -- which pricing.yaml version computed cost_usd
    status          TEXT NOT NULL,           -- ok | error
    error           TEXT                     -- raw error text when status='error'
);

CREATE TABLE IF NOT EXISTS budget_events (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    ts              TEXT NOT NULL,           -- UTC ISO-8601
    event_type      TEXT NOT NULL,           -- cap_breach | cap_warning
    detail          TEXT NOT NULL            -- JSON: spent, cap, attempted estimate, kind
);

CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    ts              TEXT NOT NULL,           -- UTC ISO-8601
    job_type        TEXT NOT NULL,           -- e.g. ai_dispatch, council_run (later phases)
    status          TEXT NOT NULL,           -- halted_budget | queued | running | done | failed
    state_json      TEXT NOT NULL,           -- persisted state for kill-and-resume (Amendment 2)
    halt_reason     TEXT                     -- why it halted, when status='halted_budget'
);

-- ---------------------------------------------------------------------------
-- Later-phase tables (created now, populated by their phase — approved plan
-- section D3: "full schema now so no table is ever retrofitted")
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,        -- uuid
    created_at      TEXT NOT NULL,
    name            TEXT NOT NULL,
    brief_text      TEXT NOT NULL,           -- raw client brief (L1 intake)
    status          TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS council_sessions (
    id              TEXT PRIMARY KEY,        -- == sessions.id of the council run
    created_at      TEXT NOT NULL,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    transcript_json TEXT NOT NULL,           -- full role-by-role transcript
    degraded        INTEGER NOT NULL DEFAULT 0,  -- 1 = ran without parallel comparison
    verdict_json    TEXT                     -- Arbiter decision record
);

CREATE TABLE IF NOT EXISTS design_specs (
    id              TEXT PRIMARY KEY,        -- == meta.spec_id (uuid)
    created_at      TEXT NOT NULL,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    spec_json       TEXT NOT NULL,           -- validated against schemas/design_spec_v1.json
    spec_hash       TEXT NOT NULL,           -- Amendment 1: the reproducible unit of record
    seed            INTEGER NOT NULL,
    provider        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS designs (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    spec_id         TEXT NOT NULL REFERENCES design_specs(id),
    geometry_hash   TEXT,                    -- hash of canonical STEP (Phase 2 determinism gate)
    parameter_json  TEXT NOT NULL,           -- canonical parameter set
    status          TEXT NOT NULL DEFAULT 'built'
);

CREATE TABLE IF NOT EXISTS validation_reports (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    design_id       TEXT NOT NULL REFERENCES designs(id),
    gate_name       TEXT NOT NULL,           -- mesh | hydraulics | structure | fabrication
    passed          INTEGER NOT NULL,        -- 0/1 — never a report without a verdict
    numbers_json    TEXT NOT NULL            -- every check's real measured numbers
);

CREATE TABLE IF NOT EXISTS critique_rounds (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    design_id       TEXT NOT NULL REFERENCES designs(id),
    round_no        INTEGER NOT NULL,        -- 1..max_vision_iterations (budget.yaml)
    critiques_json  TEXT NOT NULL,           -- per-provider vision critiques
    deltas_json     TEXT NOT NULL,           -- bounded parameter deltas only (ruling 5e)
    consensus       INTEGER NOT NULL         -- 1 = two-provider consensus reached
);

CREATE TABLE IF NOT EXISTS designdna (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    design_id       TEXT NOT NULL REFERENCES designs(id),
    embedding_ref   TEXT,                    -- local vector-store reference (Phase 6)
    summary_json    TEXT NOT NULL            -- what was reused / what is new (house style memory)
);

CREATE TABLE IF NOT EXISTS exports (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    design_id       TEXT NOT NULL REFERENCES designs(id),
    format          TEXT NOT NULL,           -- STEP | STL | DXF | OBJ | GLB | ...
    path            TEXT NOT NULL,           -- file location in the local store
    tool_versions_json TEXT NOT NULL         -- OCCT/Blender versions that produced it (5b)
);
