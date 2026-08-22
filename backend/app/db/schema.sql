-- schema.sql — LuxuryForm Studio v1 (schema version 4: + generated_programs)
-- SQLite, WAL mode. All timestamps are UTC ISO-8601 text.
-- Phase 2 evolution (ADR-010): the designs table gained the cascade build
-- columns (seed, spec_hash, build_ms, glb_path, step_path) and spec_id became
-- nullable (a Phase 2 cascade build has no council Design Spec yet).
-- ADR-022 (2026-08-07): ai_calls and council_calls gained
-- cached_input_tokens / cache_write_input_tokens — providers normalise
-- tokens_in to the UNCACHED count so cache classes price separately.
-- Phase 3 evolution (PHASE_3_PLAN.md §3, operator-approved 2026-08-04):
-- council_sessions/design_specs re-shaped for the real Council (v2 versions
-- were NEVER populated — replacement is lossless), and the normalized
-- Council tables arrive: council_calls (per-role cost measurement),
-- engineering_reviews, defect_lists, arbiter_decisions.
-- Migrations rename, never delete: Phase 1 files -> <name>.phase1-backup.db,
-- Phase 2 files -> <name>.phase2-backup.db (SPEC_PHASE2 §2 pattern).

-- ---------------------------------------------------------------------------
-- Schema version bookkeeping (Phase 2)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,           -- UTC ISO-8601
    note        TEXT NOT NULL
);

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
    tokens_in       INTEGER NOT NULL,          -- UNCACHED input tokens (normalised, ADR-022)
    tokens_out      INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL DEFAULT 0,  -- cache-READ class (ADR-022)
    cache_write_input_tokens INTEGER NOT NULL DEFAULT 0, -- cache-WRITE class (anthropic only)
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
    id                 TEXT PRIMARY KEY,     -- == sessions.id of the council run
    created_at         TEXT NOT NULL,
    brief_text         TEXT NOT NULL,        -- the plain-language brief (L1 intake)
    status             TEXT NOT NULL,        -- running | completed | halted_budget | failed
    started_at         TEXT NOT NULL,
    ended_at           TEXT,                 -- NULL while running
    total_cost_usd     REAL NOT NULL DEFAULT 0,  -- aggregate; council_calls is source of truth
    pricing_version    TEXT NOT NULL,        -- pricing.yaml version that computed costs
    arbiter_confidence REAL,                 -- copied from the binding decision (NULL pre-Arbiter)
    degraded           INTEGER NOT NULL DEFAULT 0, -- 1 = provider failure left a seat empty/reduced
    corrected          INTEGER NOT NULL DEFAULT 0  -- ADR-025: 1 = a bounded re-ask succeeded (self-correction)
);

-- Per-call record of a Council session (Phase 3). Mirrors ai_calls and adds
-- role + side so the per-role x provider cost table (operator requirement:
-- measure, then reassign from data) is a GROUP BY away. ai_calls stays the
-- generic dispatch log; council_calls is the Council's own transcript index.
CREATE TABLE IF NOT EXISTS council_calls (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES council_sessions(id),
    ts              TEXT NOT NULL,           -- UTC ISO-8601
    role            TEXT NOT NULL,           -- researcher|designer|geometrist|engineer|critic|arbiter
    side            TEXT NOT NULL,           -- primary | parallel | tiebreaker
    provider        TEXT NOT NULL,           -- anthropic | openai | kimi
    model           TEXT NOT NULL,
    prompt          TEXT NOT NULL,           -- full prompt, always (Rule 8)
    response        TEXT NOT NULL,           -- full response, always (Rule 8); '' on error
    tokens_in       INTEGER NOT NULL,          -- UNCACHED input tokens (normalised, ADR-022)
    tokens_out      INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL DEFAULT 0,  -- cache-READ class (ADR-022)
    cache_write_input_tokens INTEGER NOT NULL DEFAULT 0, -- cache-WRITE class (anthropic only)
    latency_ms      REAL NOT NULL,
    cost_usd        REAL NOT NULL,
    pricing_version TEXT NOT NULL,
    status          TEXT NOT NULL,           -- ok | error
    error           TEXT
);

CREATE TABLE IF NOT EXISTS design_specs (
    id              TEXT PRIMARY KEY,        -- == meta.spec_id (uuid)
    created_at      TEXT NOT NULL,
    session_id      TEXT NOT NULL REFERENCES council_sessions(id),
    provider        TEXT NOT NULL,           -- the provider that PRODUCED it (Critic rule input)
    alternative_no  INTEGER NOT NULL,        -- 1..3
    spec_json       TEXT NOT NULL,           -- validated against schemas/design_spec_v1.json
    spec_hash       TEXT NOT NULL,           -- Amendment 1: the reproducible unit of record
    seed            INTEGER NOT NULL,
    schema_valid    INTEGER NOT NULL         -- 1 = passed design_spec_v1.json validation
);

CREATE TABLE IF NOT EXISTS engineering_reviews (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    session_id      TEXT NOT NULL REFERENCES council_sessions(id),
    provider        TEXT NOT NULL,
    side            TEXT NOT NULL,           -- primary | parallel
    payload_json    TEXT NOT NULL            -- full engineering review document (JSON)
);

CREATE TABLE IF NOT EXISTS defect_lists (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    session_id      TEXT NOT NULL REFERENCES council_sessions(id),
    provider        TEXT NOT NULL,
    side            TEXT NOT NULL,           -- primary | parallel
    payload_json    TEXT NOT NULL            -- the Critic's defect list (JSON)
);

CREATE TABLE IF NOT EXISTS arbiter_decisions (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    session_id      TEXT NOT NULL REFERENCES council_sessions(id),
    chosen_spec_ids_json TEXT NOT NULL,      -- exactly 3, ranked best-first
    confidence      REAL NOT NULL,           -- 0..1, stated by the Arbiter
    rationale       TEXT NOT NULL,
    disagreement_register_json TEXT NOT NULL,-- material disagreements surfaced, never averaged
    binding         INTEGER NOT NULL DEFAULT 1  -- the Arbiter's decision is binding (always 1)
);

-- Phase 4 (schema v4, 2026-08-09): every program the GEOMETRIST writes,
-- including every REJECTED one with its AST-gate reason (operator order:
-- "a catalogue of what the model tried that it was not allowed to do").
-- Any geometry traces back to the code and the spec that made it.
CREATE TABLE IF NOT EXISTS generated_programs (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    session_id       TEXT NOT NULL REFERENCES council_sessions(id),
    spec_id          TEXT NOT NULL REFERENCES design_specs(id),
    attempt_no       INTEGER NOT NULL,       -- 1 = first try; 2..N = repair rounds
    provider         TEXT NOT NULL,          -- dispatch truth, not model claim
    model            TEXT NOT NULL,
    program_text     TEXT NOT NULL,          -- '' when the provider call itself failed
    program_hash     TEXT NOT NULL,          -- sha256 of program_text
    status           TEXT NOT NULL,          -- call_failed | ast_rejected | exec_failed
                                             -- | validation_failed | passed
    rejection_reason TEXT,                   -- AST-gate reason (status=ast_rejected)
    error_digest     TEXT,                   -- what the NEXT repair round was told
    artifacts_json   TEXT,                   -- {step, glb, step_sha256, glb_sha256} | NULL
    validation_json  TEXT                    -- Phase 2 ValidationReport JSON | NULL
);

CREATE TABLE IF NOT EXISTS designs (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    spec_id         TEXT REFERENCES design_specs(id),  -- NULL in Phase 2: no council spec yet
    geometry_hash   TEXT,                    -- sha256 of canonical STEP (Phase 2 determinism gate)
    parameter_json  TEXT NOT NULL,           -- canonical parameter set
    status          TEXT NOT NULL DEFAULT 'built',
    -- Phase 2 cascade build columns
    seed            INTEGER,                 -- run seed (Amendment 1)
    spec_hash       TEXT,                    -- sha256 of canonical {parameters, seed} JSON
    build_ms        REAL,                    -- measured server-side build time
    glb_path        TEXT,                    -- exported preview/validation mesh
    step_path       TEXT                     -- canonical STEP artifact
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

-- Phase 12 (L1): brief intake. normalized_json = intake_v1, every field
-- carrying its source (operator | parsed | default | unknown).
CREATE TABLE IF NOT EXISTS intakes (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    brief_text      TEXT NOT NULL,
    normalized_json TEXT NOT NULL,
    status          TEXT NOT NULL,           -- draft | confirmed
    council_session_id TEXT                  -- set when a Council run used it
);

CREATE TABLE IF NOT EXISTS exports (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    design_id       TEXT NOT NULL REFERENCES designs(id),
    format          TEXT NOT NULL,           -- STEP | STL | DXF | OBJ | GLB | ...
    path            TEXT NOT NULL,           -- file location in the local store
    tool_versions_json TEXT NOT NULL         -- OCCT/Blender versions that produced it (5b)
);
