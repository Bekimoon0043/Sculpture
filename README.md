# LuxuryForm Studio v1 — Phases 1-4 of 7 CLOSED

**What this is:** an internal design platform for LuxuryCon (Addis Ababa). It
turns a client brief for a sculpture or fountain into a design that is
defensible in numbers — real wall thickness, real weight, real water flow —
using a council of AI models (Claude, GPT, Kimi) whose every call is logged
and spend-capped, plus a real CAD engine.

**Current phase status:** This platform has 7 phases. Phases 1, 2, 3 and 4
are built and CLOSED (operator gates PASS, 2026-08-01 / 2026-08-04 /
2026-08-07 / 2026-08-17). Phases 5, 6 and 7 are not started.

What works today: everything from Phase 1 (provider layer, spend caps, audit
logging, gates), PLUS the geometry kernel — one fully parametric
tiered-cascade fountain built as a single watertight CAD solid, hard design
constraints with real numbers in every error, trimesh validation,
deterministic STEP export (same spec + same seed = byte-identical file,
proven cross-machine by printed sha256 hashes), GLB export and a three.js
browser viewport at http://localhost:5173, PLUS the full AI Council (Phase
3) — six agents across three providers producing and cross-reviewing Design
Specs, a binding Arbiter decision, full transcript UI with per-call costs
(first live session measured $0.843842 against a $1.15 estimate), PLUS the
fabrication loop (Phase 4) — the GEOMETRIST writes the CAD program, an AST
gate refuses illegal programs, the ADR-005 sandbox (separate container,
non-root, no network, read-only filesystem) executes legal ones, a bounded
repair loop feeds every failure back, and every attempt is persisted with
full spec -> program -> artifact lineage. On 2026-08-17 the operator's own
brief produced a watertight 2.6 m basalt cascade (3,432 kg) passing the
Phase 2 validation gate on the first attempt, for $0.046777. Since
2026-08-26 (Phase 6 slice A2, ADR-052) a passing ASSEMBLY fabrication
persists as a real design — viewable in the Designer, checkable by the
layered gates, exportable as a LUXEXCHANGE package — through the same
byte-identical persistence path the operator's own builds use, and the
assembler refuses knife-edge seats with the signed tolerance arithmetic
(ADR-053). Slice B (same day, ADR-054) makes a basin a fountain part:
weir-crest, coping and pool-edge rims drawn INTO the revolved profile,
and nozzle rings bored by trusted code with the count and bore taken
verbatim from the spec's hydraulic network — never invented, refused
when the water plan and the geometry disagree. Slice C1 (ADR-055) takes
the library to TEN primitives — rectangular basins, stepped monoliths,
water walls, torus rings, and the blade-fin and lotus-petal arrays —
with a 24-blade array proven to fuse into ONE watertight body that
exports byte-identical STEP across two processes. Slice C2 (2026-08-27,
ADR-056) ends the flat refusal of anything bigger than the workshop: an
element over `fabrication.max_module_m` is CUT by the kernel into
numbered modules, and the crane and truck limits bind on the MODULES, so
a 5 m basalt basin weighing 11,346 kg as one piece — previously refused
outright — now builds as 9 pieces of at most 1,472 kg, volume conserved
to 0.0000000000%, with the seams counted once per interface and matched
to hand arithmetic. The crane line on the BOM prices the heaviest module
instead of the whole fountain, and the seam and transport lines move from
"we cannot compute this" to "supply the rate".

Rendering and the vision-critique loop (Phase 5), the remaining primitive
library work (Phase 6), exports beyond STEP/GLB, and DesignDNA/recovery
hardening are not fully built. The missing L5-L8 work starts in
`PHASE_7_COMPLETION_PLAN.md` and is split into follow-on plans through
`PHASE_13_RECOVERY_HARDENING_PLAN.md`; see `LIMITATIONS.md` for the current
truth table.

## One-command start (with Docker)

```bat
copy .env.example .env
REM  open .env in Notepad and paste your three API keys
docker compose up --build -d
```

- The **viewport** is at http://localhost:5173. Node packages are baked
  into the image at BUILD time (ADR-013), so container start is fast; it is
  the first `--build` that downloads. See
  `docs/operator/02_phase2_viewport.md`.
- The **API** is at http://localhost:8000 — try
  http://localhost:8000/api/health in your browser.

## Prove it works (the gates)

```bat
docker compose exec backend python scripts/gate_phase1.py
docker compose exec backend python scripts/gate_phase2_auto.py
docker compose exec backend python scripts/gate_phase3_auto.py
docker compose exec backend python scripts/gate_phase4_auto.py
```

Each gate prints a numbered transcript and ends in PASS or FAIL with exact
reasons. The Phase 1 gate costs about **$0.01–0.05** in API calls per run;
the Phase 2, 3 and 4 auto gates are fully offline (no API calls, $0). The
Phase 3 and 4 gates take `--live` to re-run their real-money halves on
demand. After the auto gate,
do the 15-minute visual check: `docs/operator/gate_phase2_visual.md`.
Full walkthroughs: `docs/operator/01_starting_the_platform.md` (Phase 1) and
`docs/operator/02_phase2_viewport.md` (Phase 2).

## Where the audit log lives

Every AI call — provider, model, full prompt, full response, token counts,
latency, cost, and which pricing version computed that cost — is written to
the `ai_calls` table in the SQLite database at `data/luxuryform.db`. You can
browse it without any tools:

- `http://localhost:8000/api/logs/calls` — every AI call, newest first
- `http://localhost:8000/api/logs/budget` — today's spend, the caps, and any
  cap-breach events

Every cascade build is persisted too: the `designs` table holds the parameter
set, seed, spec hash, STEP sha256 and file paths; `validation_reports` holds
the measured mesh numbers. Nothing leaves your machine except the explicit
AI API calls, and every one of those is in the `ai_calls` table.

## Hard spend caps (always on)

`config/budget.yaml` sets a **$5 per-logical-run** and **$25 per-UTC-day**
ceiling. Since PR-2 (ADR-061) nothing may call a provider without first
writing an atomic reservation into the database — the caps cannot be
jointly exceeded by concurrent calls, a crash can never lose money
invisibly, and an uncertain attempt stays counted at its full bound until
the operator reconciles it with `scripts/spend_admin.py`. On breach the
platform halts, saves its state, and reports — it never quietly keeps
spending.

## Repository map

- `config/` — council roles, model names, token prices, budget caps, materials
- `schemas/design_spec_v1.json` — the AI-to-CAD contract (units everywhere)
- `backend/app/` — the FastAPI backend (`core`, `db`, `ai`, `api`, `geometry`)
- `backend/app/geometry/` — the Phase 2 kernel: parameter registry + hard
  constraints, cascade builder, exporters, trimesh validation — plus the
  Phase 4 sandbox: `ast_gate.py`, `worker.py`, `job_runner.py`
- `backend/app/council/` — the Phase 3 Council (orchestrator, prompts,
  dispatch, replay) and the Phase 4 fabrication loop (`fabricate.py`)
- `frontend/` — the three.js viewport (React + Vite + TypeScript, pinned)
- `scripts/` — one gate per phase (`gate_phase1.py` … `gate_phase4_auto.py`),
  `_cascade_build_once.py`, `generate_hub_status.py`
- `tests/` — the offline test suite (`pytest`)
- `docs/operator/` — plain-language operator guides + the visual gate
- `NEXT.md` — what is left, in order, with its blockers (the loop state file)
- `.claude/commands/` — the `/lf-*` slash commands that drive the build loop;
  the operator's guide to it is `docs/operator/06_the_loop.md`
- `DECISIONS.md` / `LIMITATIONS.md` / `PHASE_1..4_REPORT.md` — read these
