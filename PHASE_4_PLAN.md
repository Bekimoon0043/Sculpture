# PHASE_4_PLAN.md — The Fabrication Loop (2026-08-09)

**STATUS (2026-08-09):** plan reported to the operator before coding and
APPROVED verbatim with three additions (below). Built same-day; gate
pending operator-side (`scripts/gate_phase4_auto.py` PASS in fixture mode,
$0; the live half needs the operator's stack and keys).

Scope per the master build order: the GEOMETRIST agent writes parametric
build123d code from a Design Spec, executed in a sandbox, with automatic
repair on failure.

**GATE (verbatim):** the brief from the operator's Phase 3 session
(32e1c68f) produces real geometry with no human writing code, and it
passes the Phase 2 validation gate.

## Operator-approved additions (2026-08-09)

1. **Success rates reported SEPARATELY**: first attempt AND after each
   repair round (`fabricate.success_rates()` → per-round table; exposed at
   GET /api/council/fabrication-rates and printed by the gate). Rationale
   (operator): if first-attempt success is low, the registry surface in
   the prompt needs enriching before Phase 6 adds more primitives.
2. **Every REJECTED program persisted WITH its AST rejection reason**
   (`generated_programs.rejection_reason`) — the catalogue of what the
   model tried that it was not allowed to do; informs the Phase 6
   vocabulary widening. `success_rates()` aggregates the catalogue.
3. **Generated-program token cost separated in the rollup**: fabrication
   calls are audited under their own role `geometrist_code`, so every
   by_role rollup shows what a repair loop costs before Phase 5 stacks a
   critique loop on top.

## Architecture (as built)

```
Arbiter decision (Phase 3) — chosen spec, ranked best-first
  └─ POST /api/council/sessions/{id}/fabricate
       loop, max 3 attempts:
         1. GEOMETRIST code call (role geometrist_code, audited + priced)
            prompt = registry surface (generated from LIVE registry.py)
                     + program contract | CACHE_BREAK | spec + repair digest
         2. AST GATE (app/geometry/ast_gate.py)
            imports: registry / build123d / math only; no open/eval/exec/
            getattr/…; no dunder attribute access; no self-export;
            must define build(spec). Rejection reason persisted + fed back.
         3. SANDBOX (ADR-005 realized — docker-compose service geo-worker):
            separate container · user 1000:1000 · network_mode: none ·
            read-only fs + tmpfs /tmp · one scratch bind mount ·
            cpus 1.0 · mem_limit 2g · hard timeout 120s per job
            (worker watcher enforces via subprocess timeout)
            AI-written code executes NOWHERE else — tests use a scripted
            runner that executes nothing.
         4. Phase 2 validation gate on the exported GLB (trusted backend
            code, real numbers — same checks as the Phase 2 gate)
         5. Persist generated_programs row — EVERY attempt, EVERY status.
            spec -> program -> artifact lineage is queryable forever.
```

**Program contract:** `def build(spec):` → `(solid, params_dict, seed)`.
The only geometry vocabulary is `registry.cascade_fountain(params, seed)`
— one primitive today (the cascade); Phase 6 widens registry.py and the
prompt surface follows automatically (it is generated from the live
registry). The runner owns STEP/GLB export (deterministic STEP timestamp
from the seed — Amendment 1 carries forward).

**Provider:** the geometrist primary (anthropic per council.yaml) writes
code; the parallel seat is unused in Phase 4 (one program at a time; the
repair loop iterates on the same provider).

**Bounded repair:** `max_attempts=3` (route parameter). Any failure —
provider call, AST rejection, sandbox error, validation failure — is
appended to the failure history; every repair prompt carries the FULL
history (oldest first) with an explicit no-repeat instruction (ADR-027,
fixed after the first live run repeated attempt 1's value on attempt 3).
Exhaustion is reported honestly (`success=false`, all rows persisted).

## Costing

Phase 3 machinery carries forward unchanged: every code call is a
council_calls row (role `geometrist_code`) priced by pricing.yaml
2026-08-v3, session/day caps enforced by the same BudgetEnforcer, cache
classes split per ADR-022. Operator rate data for costing.yaml still
outstanding (unchanged from Phase 3).

## Build steps

1. Schema v4 (generated_programs) + AST gate + registry primitive. DONE.
2. Sandbox worker + job runner + compose service (ADR-005). DONE.
3. Fabrication stage + prompt + bounded repair + persistence. DONE.
4. Rates (first attempt / per round) + rollup separation + transcript UI
   lineage section. DONE.
5. Split gate: scripts/gate_phase4_auto.py + docs/operator/
   gate_phase4_visual.md. DONE — live half pending operator.

## What Phase 4 is NOT

No new primitives (Phase 6), no vision critique loop (Phase 5), no
Blender workers. One primitive, one loop, proven end to end.
