# LuxuryForm Studio v1 — Phase 1

**What this is:** an internal design platform for LuxuryCon (Addis Ababa). It
turns a client brief for a sculpture or fountain into a design that is
defensible in numbers — real wall thickness, real weight, real water flow —
using a council of AI models (Claude, GPT, Kimi) whose every call is logged
and spend-capped, plus (in later phases) a real CAD engine.

**Current phase status:** Phase 1 of 7 is built. What works today: the
three-provider AI layer with full audit logging, hard spend caps, the Design
Spec JSON contract, the config system, the database, and the Phase 1
acceptance gate. Geometry, the council orchestrator, and the user interface
arrive in Phases 2–7 (see `LIMITATIONS.md`).

## One-command start (with Docker)

```bat
copy .env.example .env
REM  open .env in Notepad and paste your three API keys
docker compose up --build -d
```

The API is then at http://localhost:8000 — try
http://localhost:8000/api/health in your browser.

## Prove it works (the Phase 1 gate)

```bat
docker compose exec backend python scripts/gate_phase1.py
```

The gate prints a numbered transcript and ends in `PHASE 1 GATE: PASS` or
`PHASE 1 GATE: FAIL — <exact reason>`. Each run costs about **$0.01–0.05** in
API calls. Full walkthrough: `docs/operator/01_starting_the_platform.md`.

## Where the audit log lives

Every AI call — provider, model, full prompt, full response, token counts,
latency, cost, and which pricing version computed that cost — is written to
the `ai_calls` table in the SQLite database at `data/luxuryform.db`. You can
browse it without any tools:

- `http://localhost:8000/api/logs/calls` — every AI call, newest first
- `http://localhost:8000/api/logs/budget` — today's spend, the caps, and any
  cap-breach events

Nothing leaves your machine except the explicit AI API calls, and every one
of those is in that table.

## Hard spend caps (always on)

`config/budget.yaml` sets a **$5 per-session** and **$25 per-day** ceiling.
The platform checks the cap *before* every API call; on breach it halts,
saves its state to the database, and reports — it never quietly keeps
spending.

## Repository map

- `config/` — council roles, model names, token prices, budget caps, materials
- `schemas/design_spec_v1.json` — the AI-to-CAD contract (units everywhere)
- `backend/app/` — the FastAPI backend (`core`, `db`, `ai`, `api`)
- `scripts/gate_phase1.py` — the acceptance gate
- `tests/` — the offline test suite (`pytest`)
- `DECISIONS.md` / `LIMITATIONS.md` / `PHASE_1_REPORT.md` — read these
