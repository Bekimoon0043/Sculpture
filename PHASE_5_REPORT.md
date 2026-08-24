# PHASE_5_REPORT.md — Vision Critique Loop (Phase 5)

**Status:** auto gate PASS 2026-08-24. The render dependency is CLOSED
(Phase 9B built, ADR-043). Awaiting the operator's visual gate
(`gate_phase5_visual.md`), which requires live API spend.

**Date:** 2026-08-22, revised 2026-08-24.

**Scope:** Phase 5 builds the render → vision-critique → bounded-delta loop
(ADR-007). It produces four canonical renders of a design, asks two vision
providers for bounded parameter deltas, enforces two-provider consensus,
anneals the permitted step each round, and scores improvement with an
objective composite derived from geometry facts.

---

## What was built

### Backend render orchestration

- `backend/app/render/__init__.py` — `RenderStatus`, `RenderCamera`,
  `RenderView`, `RenderJob`, `DEFAULT_VIEWS`.
- `backend/app/render/queue.py` — `ScratchRenderRunner`, `submit_render_job`,
  `poll_render_job`. Mirrors the geo-worker handoff from ADR-028.
- `backend/app/render/scene.py` — camera rig documentation and framing helper.
- `backend/app/api/routes_render.py` — FastAPI routes:
  - `POST /api/render/jobs`
  - `GET /api/render/jobs/{id}`
  - `GET /api/render/jobs/{id}/views/{name}`
- `backend/app/main.py` — routes_render mounted.

### Vision critique loop

- `backend/app/council/critique.py` — the loop, consensus, annealing,
  delta application, and objective scoring.
- `backend/app/council/prompts.py` — `vision_critique_prompt()` with strict
  JSON delta schema.

### Gate + fixtures

- `scripts/gate_phase5_auto.py` — offline, $0 gate, five checks.
- `tests/fixtures/critique_round_v1.json`
- `tests/test_critique.py` — 7 tests, all passing.
- `gate_phase5_visual.md` — operator visual gate checklist.

---

## Corrections made on 2026-08-24

The 2026-08-22 version of this report described the phase as complete apart
from the render container. Running it showed otherwise — three defects that
each made the gate or the loop non-functional:

1. **The gate and the test suite did not import.** Both did
   `from app.render import RenderResult`, but `RenderResult` is defined in
   `app.render.queue`; re-exporting it from the package `__init__` would make
   the two modules import each other. Both imports now name `queue` directly.
   The 2026-08-22 report claimed this gate passed; it could not have.

2. **Consensus rejected everything.** `compute_consensus` carried its own
   `tolerance=0.05` default, so two providers proposing +0.030 m and +0.032 m
   on a tier height — 2 mm apart, 6.25% relative — were scored as disagreeing
   and the round produced nothing. The tolerance is now 0.20, as a named
   constant used by both call sites, on the reasoning recorded in ADR-043 §7:
   consensus asks whether two models found the same problem and the same
   direction, not whether they agree to two significant figures, and the
   magnitude is clamped to the annealed engineering limit regardless.

3. **`_annealing_limit` was tested with the wrong shape.** The test passed the
   whole ranges dict where the function takes a single `(lo, hi)` tuple, and
   died on `KeyError: 1`. Fixed, with an added assertion that round 1 really
   is 10% of the span.

One further change, not a defect but a real fragility: consensus took the
magnitude from provider `a`, so swapping the provider order silently changed
the resulting design. It now takes the smaller of the two proposals, which is
both conservative and order-independent.

The render contract also changed — `input_step` became `input_mesh`, and the
API renders `design.glb_path` — because Blender cannot import STEP. That is
recorded in ADR-043 §2.

---

## Gate evidence

```
$ docker compose exec backend python scripts/gate_phase5_auto.py
============================================================
Phase 5 auto gate — vision critique loop (offline, $0)
============================================================
[1] PASS render handoff produced 4 views
[2] PASS two-provider critique + consensus
[3] PASS objective score before=0.64 after=0.96
[4] PASS applied delta: tier_height_m 0.25 -> 0.28
[5] PASS annealing: r1 limit=0.045000 r2 limit=0.022500
============================================================
Phase 5 auto gate PASS
============================================================

$ docker compose exec backend python -m pytest tests/test_critique.py -q
7 passed
```

---

## How to run

```bat
docker compose up --build -d
docker compose exec backend python scripts\gate_phase5_auto.py
```

For the live loop, the render worker must also be up:

```bat
docker compose --profile render up -d render-worker
```

---

## Cost

The auto gate is fixture-replayed and costs $0. A full live 6-iteration loop is
estimated at ≈ $0.47 per `PHASE_5_PLAN.md` §1.1, well under the $5 session cap.

---

## Honest blockers

1. **No live iteration run yet.** The auto gate proves the orchestration with
   scripted providers; it does not prove that two real vision models, looking
   at two real renders, will converge. That is the operator's visual gate and
   it costs money.
2. **`scripts/measure_render.py` does not exist.** The 2026-08-22 report and
   `gate_phase5_visual.md` both reference it. It was never written. The visual
   gate's render step is served by `gate_phase9b_auto.py` and the API instead —
   `gate_phase5_visual.md` should be re-read against that before the operator
   runs it.
3. **The loop can only move parameters already in the Design Spec**, and it
   cannot judge engineering — only proportion, silhouette and composition.

---

## Files touched

- `backend/app/render/{__init__,queue,scene}.py`
- `backend/app/api/routes_render.py`
- `backend/app/main.py`
- `backend/app/council/{critique,prompts}.py`
- `scripts/gate_phase5_auto.py`
- `tests/test_critique.py`, `tests/fixtures/critique_round_v1.json`
- `gate_phase5_visual.md`
- `LIMITATIONS.md`, `DECISIONS.md` (ADR-042, corrected; ADR-043)
