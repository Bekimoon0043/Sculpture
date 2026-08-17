# PHASE_4_REPORT.md — The Fabrication Loop (CLOSED 2026-08-17)

Phase 4 built the loop that turns an Arbiter-chosen Design Spec into real
geometry with no human writing code: the GEOMETRIST writes a parametric
build123d program, an AST gate refuses illegal programs, the ADR-005
sandbox executes legal ones, the Phase 2 validation gate measures the
result, and a bounded repair loop feeds every failure back. Every attempt —
including rejected and failed ones — is persisted against its spec.

## Gate result

**GATE (verbatim, as approved):** the brief from the operator's Phase 3
session (32e1c68f) produces real geometry with no human writing code, and it
passes the Phase 2 validation gate.

**PASS — operator's machine, 2026-08-17.** Verbatim from
`gate_phase4_auto.py --live 32e1c68f`:

```
"success": true,
"attempts": 1,
"final_status": "passed",
"artifacts": {
  "glb": ".../70716728-e895-4da2-baef-54ea1967aa1c/artifact.glb",
  "glb_sha256": "71d55d8663142e854cb9b52232a5db03aa1a23b98fa81f5d47e4bfcc91a55a9a",
  "step": ".../70716728-e895-4da2-baef-54ea1967aa1c/artifact.step",
  "step_sha256": "b58a4e039058551cad9d580962bc5d17c605880d9cf664a7b57d05d03cf1860b"
},
"validation": {
  "watertight": true,          "winding_consistent": true,
  "volume_mm3": 1271287346.316879,
  "surface_area_mm2": 42954224.45121378,
  "euler_number": 0,           "degenerate_face_count": 0,
  "face_count": 30240,         "mass_kg": 3432.4758350555735,
  "bounds_mm": [-1300.0, -1299.6, 0.0, 1300.0, 1299.6, 1710.0],
  "volume_crosscheck": { "trimesh_volume_mm3": 1271287346.316879,
                         "build123d_volume_mm3": 1271814019.4899116,
                         "delta_pct": 0.0414, "within_tolerance": true },
  "passed": true
}
```

A 2.6 m basalt cascade, 1.71 m tall, 3,432 kg, watertight, B-rep and mesh
volumes agreeing to 0.041% against a 2% tolerance.

- **Auto gate** (`scripts/gate_phase4_auto.py`, fixture mode, $0): PASS —
  schema v4, the six AST-gate proofs, the eleven static ADR-005 sandbox
  assertions, the cross-container round trip, the scripted repair loop,
  rate computation and rollup separation.
- **Cross-container round trip** (ADR-028, the defect that was open at the
  start of this session), verbatim: `probe answered by worker 458e65358b1a
  (pid 1); this backend is 53c06fb080c4` — the backend read a file a
  DIFFERENT container wrote. Closed.
- **Artifacts verified on the operator's disk**, not just claimed by the
  API: `artifact.step` 56,182 bytes opening `ISO-10303-21;`, `artifact.glb`
  640,172 bytes with `glTF` magic, both sha256 matching the values above.
- **No regression:** Phase 2 auto gate PASS; the canonical STEP sha256
  `e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13` is
  unchanged, so Amendment 1 determinism survived every change in this phase.
  178 tests pass.

## Lineage — spec to program to artifact

Queryable forever, from `generated_programs` joined to `design_specs`:

```
session   32e1c68f-e94a-4727-a501-fdc2611d2394
spec      8f3c2a1d-6b47-4e89-9c3a-7d5e8f2b1c4e
spec_hash c5fafffa6fa25dd2fcf035df7b9b09a0c261071de625b5486784de75da0b8456
program   70716728-e895-4da2-baef-54ea1967aa1c
prog_sha  274183ab78b44da735069fc7c4ace6830f4e1f19071c3812f585ef7ea4a11331
artifact  artifact.step b58a4e03…  /  artifact.glb 71d55d86…
```

## Measured success rates (operator order, 2026-08-09)

First-attempt and per-repair-round rates, computed SEPARATELY. A unit is one
RUN of the repair loop (see ADR-029 fix 3 — it used to be one spec, which
made these numbers wrong).

**All four live runs of spec 8f3c2a1d, honestly:**

| metric | reached | passed | rate |
|---|---|---|---|
| first attempt | 4 | 1 | **0.25** |
| round 1 | 4 | 1 | 0.25 |
| round 2 | 2 | 0 | 0.00 |
| round 3 | 2 | 0 | 0.00 |

Three of those four runs predate the ADR-027/028/029 fixes. Split at the
fix boundary, which is the number that describes the platform as it now
stands:

| period | runs | first-attempt passes | rate |
|---|---|---|---|
| before ADR-029 (2026-08-09) | 3 | 0 | 0.00 |
| after ADR-029 (2026-08-17) | 1 | 1 | **1.00** |

One post-fix run is one data point, not a rate — stated as such deliberately
rather than dressed up. What it does establish: the spec that failed 3 runs
and 7 attempts passed on the first attempt once the prompt carried the
solving order. The next live fabrications extend this table.

**Rounds 2 and 3 never produced a pass in any run.** Every success came at
attempt 1. On this evidence the repair loop's value so far has been
diagnostic — it produced the failure digests that found the defects — not
corrective. Worth watching: if that holds across more specs, the budget is
better spent on the prompt surface than on a fourth attempt.

## AST rejection catalogue

**Empty across every live run — zero AST rejections in 8 real attempts.**

The catalogue is not broken; the gate is exercised and proven by six cases
in the auto gate (illegal import, dunder escape, self-export, missing
`build(spec)`, syntax error, plus a clean program passing). It is empty
because the model has never once written *illegal* code. Every live failure
was a legal program carrying *infeasible numbers*:

| live failure class | count | what it was |
|---|---|---|
| range breach (pre-ADR-027) | 3 | wall 180 > old cap 100; dish 420 > old cap 300 |
| hard constraint 4 | 3 | column diameter below bore + 2×wall |
| validation (watertight) | 1 | zero-clearance tangency (ADR-029) |
| passed | 1 | 2026-08-17 |

This is the operator's stated Phase 6 signal, and it points somewhere
specific: the vocabulary needs *arithmetic guidance*, not a wider whitelist.
The one change that moved first-attempt success was teaching the prompt how
to SOLVE the binding constraint, not giving the model more to call.

## Real cost of a fabrication, including repairs

Every fabrication call is a `council_calls` row under its own role
`geometrist_code`, priced by pricing.yaml `2026-08-v3`, capped pre-dispatch
by the same BudgetEnforcer as Phase 3.

| run | calls | tokens in | tokens out | cost | outcome |
|---|---|---|---|---|---|
| 2026-08-09 (3 runs, 7 attempts) | 8 | 39,531 | 10,144 | **$0.279975** | all failed |
| 2026-08-17 (1 run, 1 attempt) | 1 | 4,320 | 1,884 | **$0.046777** | PASSED |

- **A successful single-attempt fabrication costs $0.046777** (anthropic
  claude-sonnet-4-5, 46.6 s latency, 0 cached input tokens).
- **A failed 3-attempt run costs roughly $0.10–0.12** — ~$0.035/call at the
  2026-08-09 prompt size; the prompt is now longer, so budget ~$0.047/call.
- **Session 32e1c68f total, all phases: $1.170594** across 26 logged calls
  ($0.843842 Council + $0.326752 fabrication across all attempts), against
  the $5 session cap. Every figure from the `ai_calls` audit table, which is
  the budget enforcer's single source of truth (ADR-003).

Fabrication is ~4% of the cost of the Council session that precedes it. Cost
is not the constraint on this loop; first-attempt success is.

## What was built (5 build steps, all DONE)

1. Schema v4 (`generated_programs`) + AST gate + registry primitive.
2. Sandbox worker + job runner + compose `geo-worker` service (ADR-005).
3. Fabrication stage + prompt + bounded repair + persistence.
4. Rates (first attempt / per round) + rollup separation + transcript UI
   lineage section.
5. Split gate: `scripts/gate_phase4_auto.py` +
   `docs/operator/gate_phase4_visual.md`.

## Incidents and what they changed

- **Ranges were demo envelopes, not engineering reality** (live run 1, 3/3
  failed). The Council designed a buildable 180 mm basalt wall; the registry
  capped at 100. **ADR-027**: per-material wall envelopes from materials.yaml.
- **The repair loop carried only the LAST failure** — attempt 3 repeated
  attempt 1's value, so 3 attempts gave 2. **ADR-027**: full failure history,
  oldest first, with an explicit no-repeat instruction.
- **Artifact collection crossed the container boundary wrongly** (live run 2:
  built successfully, then an unhandled 500). Worker-side absolute paths are
  meaningless in the backend. **ADR-028**: mount parity, basename artifacts
  with verified visibility, honest `collection_failed` rows, and a gate
  section that queues a real probe and proves a *different* container
  answered. Verified on the operator's machine this session.
- **Zero-clearance tangency** (live run 3: built, collected, `watertight:
  False`). **ADR-029**: per-material fall-gap floors, hard constraint 7, and
  — the change that actually fixed first-attempt success — a prompt that
  teaches the diametral convention and the constraint solving order.
- **The success-rate metric counted specs, not runs**, reporting 1.0 where
  the truth was 0.25. **ADR-029.** Found while writing this report; the
  tables above use the corrected computation.

## Known scope limits (carried in LIMITATIONS.md §9)

- **One wall parameter serves basin, dishes AND column.** In the passing
  run the model met hard constraint 4 (`column >= bore + 2*wall`) by
  thinning the wall from the Council's 180 mm to 60 mm rather than widening
  the 240 mm column — and said so in its own comments: *"basin_wall_mm is
  for basin/dish walls, not column wall... But constraint uses
  basin_wall_mm literally."* The geometry is valid, watertight and passes;
  it is simply not the wall the Council specified. Both resolutions are
  legal and the platform has no basis to prefer one. Separate per-member
  wall parameters are a Phase 6 registry change.
- One primitive (the cascade). No composition, no new primitives — Phase 6.
- Rounds 2 and 3 have never produced a pass; the repair loop is so far
  diagnostic rather than corrective (see rates above).
- `config/costing.yaml` is still all nulls — operator rate data outstanding,
  unchanged from Phase 3. No cost line is computed until it arrives.

Phase 4 is CLOSED. Next by the operator's stated order: Phase 6 (the
primitive library) before Phase 5 (the vision critique loop).
