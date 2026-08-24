# Phase 5 Visual Gate — Vision Critique Loop

**Operator check:** a design measurably improves across at least three critique
iterations, with before/after renders and the parameter deltas that caused
each change.

## What to look at

1. Bring everything up, including the render worker (it sits behind a
   compose profile and does NOT start with a plain `up -d`):
   ```bat
   docker compose up --build -d
   docker compose --profile render up -d render-worker
   ```
2. Confirm the renderer itself works before spending anything on vision
   calls:
   ```bat
   docker compose exec backend python scripts\gate_phase9b_auto.py
   docker compose exec backend python scripts\gate_phase5_auto.py
   ```
   Both must print PASS. The first proves Blender renders; the second proves
   the critique orchestration, offline and at $0.
3. Then run the live loop against a completed design.

   NOTE: `scripts/measure_render.py`, referenced by an earlier draft of this
   gate, was never written — see PHASE_5_REPORT.md. Renders are produced
   through the API instead:
   ```bat
   curl.exe -s -X POST http://localhost:8000/api/render/jobs ^
     -H "Content-Type: application/json" ^
     -d "{\"design_id\": \"<a design id>\"}"
   ```
4. Open `data/critiques/<design_id>/` and inspect:
   - `round_1/` vs `round_3/` PNG folders
   - `critique_rounds.json` — per-round deltas and scores
5. Verify the renders are visually different in the direction the deltas claim.

## Pass criteria

- [ ] Four views rendered per round (front, side, top, three-quarter) at 1024².
- [ ] At least three rounds completed without error.
- [ ] Objective composite score improved from round 1 to round 3.
- [ ] Every accepted delta is logged with before/after parameter value.
- [ ] Prose observations that could not be expressed as deltas are preserved,
      not executed.
- [ ] No API spend exceeded the session cap; cost dashboard shows the real
      vision-call costs.

## Known limitations

- The loop can only move parameters already present in the Design Spec.
- It cannot judge engineering (stress, hydraulics) — only proportion,
  silhouette and composition.
- Render time is bounded per view; slower CPUs produce noisier images, not
  hung jobs.
