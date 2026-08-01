# DECISIONS.md — Architecture Decision Records, LuxuryForm Studio v1

One entry per significant technical choice. Newest decisions are appended;
decisions are never silently edited (a superseded ADR says so in place).

---

## ADR-001 — SQLite in WAL mode as the platform database

**Status: accepted (Phase 1).**

SQLite with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`, one file
at `data/luxuryform.db` (override with `LUXURYFORM_DB`).

**Why:** the platform is local-first and operated by a non-programmer. SQLite
is crash-safe in WAL mode, needs no server, no admin, and backups are "copy
one file". A single writer at a time is sufficient: the job runner serializes
heavy work by design.

**Full schema created up front.** Per the approved plan (§D3), every table —
including later-phase tables (`projects`, `council_sessions`, `design_specs`,
`designs`, `validation_reports`, `critique_rounds`, `designdna`, `exports`) —
is created in `db/schema.sql` NOW, with minimal-but-real columns, so no table
is ever retrofitted mid-flight. Phase 1 code only reads/writes the Phase 1
tables (`sessions`, `ai_calls`, `budget_events`, `jobs`); ORM models for
later tables arrive with the phase that populates them.

---

## ADR-002 — Official provider SDKs; Kimi via Moonshot's OpenAI-compatible endpoint

**Status: accepted (Phase 1).**

Anthropic and OpenAI are called through their official Python SDKs
(`anthropic`, `openai`), each with a 60-second timeout. Kimi (Moonshot AI) is
called through the official `openai` SDK pointed at
`base_url=https://api.moonshot.cn/v1` with `MOONSHOT_API_KEY`, because
Moonshot's API is OpenAI-compatible. One provider interface
(`app/ai/provider.py`) covers all three; every call routes through
`app/ai/call_log.py`. Token counts are always read from the API response's
`usage` object — real numbers, never estimates. If Kimi's vision endpoint
rejects a call, the raw error is surfaced verbatim (Amendment 5) rather than
hidden or silently retried elsewhere.

---

## ADR-003 — Spend caps live in the provider layer (Amendment 2)

**Status: accepted (Phase 1).**

Hard ceilings — `session_cap_usd: $5.00`, `day_cap_usd: $25.00`,
`max_vision_iterations: 6` — are enforced by `core/budget.py` BEFORE any API
call is dispatched, inside the single logged dispatch path
(`ai/call_log.py`). Spend is derived from the `ai_calls` table (single source
of truth), money math is rounded to 6 decimal places, and the day boundary is
the UTC calendar day. On breach (`on_breach: halt_and_report`): the run
halts, a `budget_events` row and a `jobs` row (`status='halted_budget'` with
persisted state JSON) are written, and the reason is reported. The system
never silently continues. `max_vision_iterations` is validated from
`config/budget.yaml` now and enforced when the critique loop is built in
Phase 5. The Phase 1 gate PROVES a cap stops a run, offline, in its section 4.

---

## ADR-004 — The determinism boundary is the Design Spec (Amendment 1)

**Status: accepted (Phase 1).**

Restated verbatim, this is the platform's guarantee:

"Identical Design Spec + identical seed + pinned Docker image = byte-identical
canonical geometry (STEP + parameter set). Brief → Spec is non-deterministic
by nature; every Spec is therefore persisted permanently as the reproducible
unit of record."

Consequences: seeds are centralized (`core/seeds.py`), the Design Spec schema
carries `meta.seed` and an optional `meta.spec_hash`, and no gate ever tests
brief-level reproducibility. (This supersedes objection 5b in the First
Action document; renders remain reproducible within visual tolerance, never
byte-identical — see LIMITATIONS.md.)

---

## ADR-005 — Sandbox isolation level for AI-written geometry code (Amendment 6)

**Status: accepted (Phase 1) — recorded now, built in Phase 4.**

In Phase 4 the GEOMETRIST's generated build123d/CadQuery code will execute
only inside a sandbox with ALL of the following:

- a **separate container** (not the backend container),
- running as a **non-root user**,
- with **no network access**,
- a **read-only filesystem except one scratch mount** for build artifacts,
- explicit **CPU and memory limits**, and
- a **hard wall-clock timeout** after which the sandbox is killed.

Recording the level now fixes the security posture before any AI-written code
ever runs; the Phase 4 gate must demonstrate each property.

---

## ADR-006 — Versioned pricing with effective dates

**Status: accepted (Phase 1).**

`config/pricing.yaml` carries `pricing_version` (currently `2026-07-v1`) and
an `effective_date` per model. Every logged AI call records which pricing
version computed its cost, so a price change never silently rewrites history:
when a provider changes prices the operator updates the file and bumps the
version. A model with no price entry is a hard error — the platform refuses
to guess a price. The file's header instructs the operator to verify prices
against the providers' live price pages before trusting cost figures.

---

## ADR-007 — Bounded vision deltas + two-provider consensus (Phase 5)

**Status: accepted (Phase 1) — recorded now, built in Phase 5.**

The vision critique loop will convert model feedback into parameter deltas,
never prose: each delta must reference a registered primitive parameter path
(e.g. `cascade_01.tier_height_m`), carry a magnitude limit, and require
**two-provider vision consensus** (Anthropic + OpenAI in parallel, Kimi as
fallback) before it is accepted; the Arbiter validates every delta before
re-solve. Anything the vision model says that cannot be expressed as a
bounded delta is recorded as an observation for the operator — not executed.
Loop rounds are hard-capped by `max_vision_iterations` (ADR-003).

---

## ADR-008 — DXF native; ODA File Converter for DWG; no SKP writer

**Status: accepted (Phase 1 ruling 5a).**

- **DXF** is written natively (open-source `ezdxf` covers it fully).
- **DWG** is Autodesk's closed format. We do not write it directly; the
  operator converts DXF → DWG with the free ODA File Converter (one-time
  install, documented in LIMITATIONS.md with exact steps).
- **SKP** (SketchUp) has no working open-source writer, so we do not export
  it. The import path is documented instead: fabricators open our
  STEP/DXF/OBJ directly in SketchUp Pro.

Everything else on the export list (STEP, STL, OBJ, GLB, FBX, USD/USDZ, DAE,
Alembic) is genuinely achievable and arrives with the export phase.

## ADR-009 — No platform fact from training-data recall; live docs only, fetch date recorded

**Status: accepted (Phase 1 correction, operator directive).**

No third-party endpoint, model string, SDK shape, parameter name, or price is
ever written into this codebase from the model's training-data recall. Each is
fetched from the live provider documentation (or verified against the live
API) at the time it is written, and the fetch date and source URL are recorded
next to the value (config comments, docstrings, pricing.yaml sources).

**Why:** this has now caused two real defects in Phase 1 alone:

1. The offline test transports mirrored an *assumed* SDK response shape
   (LIMITATIONS.md §7) — retired only by the live gate run.
2. `kimi_provider.py` hardcoded `https://api.moonshot.cn/v1` from recall; the
   operator's account lives on the global endpoint and the gate returned a
   live 401. The operator verified against the live API:
   `https://api.moonshot.ai/v1` authenticates, and `models.list()` returns
   exactly `kimi-k3, kimi-k2.6, kimi-k2.7-code, kimi-k2.7-code-highspeed` —
   no vision-specific model.

**Applied immediately (2026-08-01):** endpoints moved to
`config/council.yaml`; kimi text+vision model = `kimi-k3` (native image
input); `max_completion_tokens` replaces the deprecated `max_tokens`; kimi-k3
pricing ($3.00 cache-miss input / $15.00 output per 1M) fetched from
`platform.kimi.ai/docs/pricing/chat-k3.md`. Every value carries its source
URL and fetch date.

---

## ADR-010 — Phase 2 geometry stack: build123d kernel, native GLB, trimesh validation, STEP timestamp injection

**Status: accepted (Phase 2, all API facts live-doc sourced 2026-08-01 per ADR-009).**

- **Kernel: build123d 0.11.1** (OpenCASCADE). The tiered-cascade primitive is
  built from solids of revolution (BuildSketch profile in the XZ plane →
  `revolve(..., Axis.Z)`), fused into ONE solid, plumbing bore cut through
  the stack. Watertight BY CONSTRUCTION (Rule 6): no mesh repair anywhere.
- **Lip fillets are drawn INTO the dish profile** as true circular arcs
  (`RadiusArc`), so the revolved lip is an exact toroidal surface — no
  post-hoc 3D `fillet()` call that could fail at parameter extremes. The
  validated ranges in `registry.py` plus hard constraints 3 and 5
  (`lip_fillet_mm < dish_depth_mm/2`, `lip_fillet_mm < basin_wall_mm`)
  guarantee the profile is always drawable.
- **GLB export is build123d's NATIVE `export_gltf(binary=True)`** (live-doc
  signature confirmed 2026-08-01). No trimesh conversion on the export path.
  `linear_deflection` is set to 1.0 mm explicitly: the live-doc default
  0.001 mm would tessellate a 2.6 m fountain into tens of millions of
  triangles and blow the <1M-triangle viewport budget (PHASE2_PLAN §7). STEP
  is the canonical artifact; the GLB is a preview/validation mesh.
- **trimesh (5.0.0) is used for VALIDATION only** — watertight, winding,
  volume, surface area, Euler number, bounds, degenerate faces — with a 2%
  volume cross-check against the exact B-rep volume.
- **STEP determinism (Amendment 1):** the STEP header normally embeds a
  wall-clock timestamp. `export_step(..., *, timestamp=)` (live-doc confirmed
  2026-08-01) lets us inject `datetime(2026,1,1) + timedelta(seconds=seed)`,
  so (spec, seed) → byte-identical STEP. The gate proves this across TWO
  separate processes with both sha256 hashes printed.
- **Schema evolution is honest (SPEC_PHASE2 §2):** a `schema_migrations`
  table records the version; a Phase 1 database file is RENAMED to
  `<name>.phase1-backup.db` on startup (never deleted) and a fresh v2 schema
  is created, because SQLite cannot alter the `designs.spec_id` foreign key
  in place and Phase 2 builds have no council Design Spec yet.
- **[ADD-1] `.gitattributes`** pins LF for text and marks STEP/GLB/etc.
  binary — Windows CRLF conversion at checkout would corrupt the STEP sha256
  determinism proof.
- **[ADD-2] The Phase 2 gate is split:** `scripts/gate_phase2_auto.py`
  (non-interactive, exit 0/1) + `docs/operator/gate_phase2_visual.md`
  (operator eye-check including the [ADD-5] rebuild-time measurement).
