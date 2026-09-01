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
    error           TEXT,                    -- raw error text when status='error'
    reservation_id  TEXT REFERENCES spend_reservations(id)  -- PR-2 (ADR-061): 1:1, NULL pre-PR-2
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
    step_path       TEXT,                    -- canonical STEP artifact
    project_id      TEXT REFERENCES projects(id), -- NULL = legacy/ungrouped
    parent_design_id TEXT REFERENCES designs(id)  -- NULL = root variant
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

-- ---------------------------------------------------------------------------
-- PR-2 (ADR-061): atomic spend caps. A provider dispatch may not exist
-- without a HELD reservation taken first inside one BEGIN IMMEDIATE
-- transaction; every physical attempt has exactly one reservation and at
-- most one ai_calls row (1:1 both ways — unique partial indexes are applied
-- by the startup index patches). Money here is INTEGER micro-USD
-- (1 µUSD = $0.000001): cap arithmetic is exact integer arithmetic, never
-- binary floats. Rows are NEVER deleted; uncertain holds keep their bound.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS spend_scopes (
    id              TEXT PRIMARY KEY,        -- full uuid4 or uuid5 — NEVER a truncated prefix
    kind            TEXT NOT NULL,           -- council | fabrication | critique | intake | gate | verify | adhoc
    created_at      TEXT NOT NULL,           -- UTC ISO-8601
    status          TEXT NOT NULL,           -- open | closed | halted (halted is STICKY)
    closed_at       TEXT,                    -- UTC ISO-8601; NULL while open/halted
    design_ref      TEXT,                    -- what the run works on (spec/intake/plan digest); audit only
    note            TEXT                     -- lifecycle audit trail (reopens, halts, resolutions)
);

CREATE TABLE IF NOT EXISTS spend_reservations (
    id              TEXT PRIMARY KEY,        -- uuid4
    created_at      TEXT NOT NULL,           -- UTC ISO-8601, hold taken (pre-dispatch)
    day_utc         TEXT NOT NULL,           -- created_at[:10]; the day BOTH caps bind against
    scope_id        TEXT NOT NULL REFERENCES spend_scopes(id),
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    attempt_no      INTEGER NOT NULL,        -- physical attempt within one logical call (1..N)
    provider        TEXT NOT NULL,           -- anthropic | openai | kimi
    model           TEXT NOT NULL,
    kind            TEXT NOT NULL,           -- text | vision
    reserved_usd_micro INTEGER NOT NULL,     -- documented cap-safe UPPER BOUND (µUSD)
    settled_usd_micro  INTEGER,              -- set when status='settled'; == its ai_call cost
    status          TEXT NOT NULL,           -- held | settled | uncertain | reconciled
                                             -- (reconciled = operator-verified amount via
                                             -- spend_admin; no 'released': no first-party
                                             -- proof of non-billing exists, ADR-061)
    settled_at      TEXT,                    -- UTC ISO-8601 of the terminal classification
    ai_call_id      TEXT REFERENCES ai_calls(id),  -- exact-id correlation; NULL only for
                                             -- recovery-classified died-mid-flight holds
    note            TEXT                     -- uncertainty/recovery/reconciliation reason
);

CREATE TABLE IF NOT EXISTS spend_safety_locks (
    id              TEXT PRIMARY KEY,        -- uuid4
    created_at      TEXT NOT NULL,           -- UTC ISO-8601
    provider        TEXT,                    -- NULL = GLOBAL lock (all paid dispatch refuses)
    model           TEXT,                    -- NULL = every model of the provider
    reason          TEXT NOT NULL,           -- bound_exceeded | pricing_failure | ledger_mismatch
    detail          TEXT NOT NULL,           -- JSON evidence (amounts, reservation/call ids)
    status          TEXT NOT NULL,           -- active | resolved
    resolved_at     TEXT,                    -- UTC ISO-8601
    resolution_note TEXT                     -- REQUIRED at resolution (audited operator action)
);
