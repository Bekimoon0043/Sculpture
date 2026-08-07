# LuxuryForm Studio v1 — Phase 2

**What this is:** an internal design platform for LuxuryCon (Addis Ababa). It
turns a client brief for a sculpture or fountain into a design that is
defensible in numbers — real wall thickness, real weight, real water flow —
using a council of AI models (Claude, GPT, Kimi) whose every call is logged
and spend-capped, plus a real CAD engine.

**Current phase status:** Phases 1 and 2 are built and CLOSED (operator
gates PASS, 2026-08-01 / 2026-08-04). **Phase 3 (the AI Council) is in
progress:** build step 1 of 5 is done — schema v3 persistence, the $0
fixture replay pipeline, and the costing rates schema. What works today:
everything from Phase 1 (provider layer, spend caps, audit logging, gates)
PLUS the geometry kernel — one fully parametric tiered-cascade fountain
built as a single watertight CAD solid, hard design constraints with real
numbers in every error, trimesh validation, deterministic STEP export (same
spec + same seed = byte-identical file, proven cross-machine by printed
sha256 hashes), GLB export, and a three.js browser viewport at
http://localhost:5173. The council orchestrator, AI-written geometry
sandbox, rendering and the remaining primitives arrive in the rest of
Phases 3–7 (see `LIMITATIONS.md`).

## One-command start (with Docker)

```bat
copy .env.example .env
REM  open .env in Notepad and paste your three API keys
docker compose up --build -d
```

- The **viewport** is at http://localhost:5173 (first start downloads npm
  packages — can take 5–30 minutes on a slow line; see
  `docs/operator/02_phase2_viewport.md`).
- The **API** is at http://localhost:8000 — try
  http://localhost:8000/api/health in your browser.

## Prove it works (the gates)

```bat
docker compose exec backend python scripts/gate_phase1.py
docker compose exec backend python scripts/gate_phase2_auto.py
```

Each gate prints a numbered transcript and ends in PASS or FAIL with exact
reasons. The Phase 1 gate costs about **$0.01–0.05** in API calls per run;
the Phase 2 auto gate is fully offline (no API calls). After the auto gate,
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

`config/budget.yaml` sets a **$5 per-session** and **$25 per-day** ceiling.
The platform checks the cap *before* every API call; on breach it halts,
saves its state to the database, and reports — it never quietly keeps
spending.

## Repository map

- `config/` — council roles, model names, token prices, budget caps, materials
- `schemas/design_spec_v1.json` — the AI-to-CAD contract (units everywhere)
- `backend/app/` — the FastAPI backend (`core`, `db`, `ai`, `api`, `geometry`)
- `backend/app/geometry/` — the Phase 2 kernel: parameter registry + hard
  constraints, cascade builder, exporters, trimesh validation
- `frontend/` — the three.js viewport (React + Vite + TypeScript, pinned)
- `scripts/` — `gate_phase1.py`, `gate_phase2_auto.py`, `_cascade_build_once.py`
- `tests/` — the offline test suite (`pytest`)
- `docs/operator/` — plain-language operator guides + the visual gate
- `DECISIONS.md` / `LIMITATIONS.md` / `PHASE_1_REPORT.md` / `PHASE_2_REPORT.md`
  — read these
