# PHASE_6_REPORT.md — The Primitive Library (IN PROGRESS)

Phase 6 ships in gated slices (PHASE_6_PLAN.md §2). This report accumulates
one section per closed slice; the phase closes when the operator's gate — a
brief needing three primitives produces one watertight assembly, viewable
and exportable — passes live at slice A2.

---

## PHASE 6 GATE: PASS - slice A1 only (auto, 2026-08-20); A2/B/C/D not built

This verdict covers `gate_phase6a1_auto.py`, the only Phase 6 gate that
exists. Phase 6 as a whole is NOT closed: slices A2 (AI + surfaces),
B (rim treatments + fixtures), C and D are not built.

## Slice A1 — the assembly core (CLOSED, auto gate PASS 2026-08-20, $0)

**Scope:** registry restructure, three new revolved primitives, per-member
walls, `registry.assemble()` with typed joints, assembly validation,
assembly determinism, AST narrowing (ADR-030). No AI calls, no API/frontend
change, no DB change — those are slice A2. Decisions: ADR-030, ADR-032.
Envelope basis: PHASE_6_SLICE_A_ENVELOPES.md, signed as drafted 2026-08-20.

### What was built

| piece | where |
|---|---|
| primitive module protocol | `backend/app/geometry/primitives/base.py` |
| cascade (moved, + `column_wall_mm`) | `primitives/cascade.py` |
| `basin_round` (floor split from wall, constraint 8) | `primitives/basin_round.py` |
| `plinth` (solid/hollow frustum — the mass lever) | `primitives/plinth.py` |
| `sculptural_column` (wall XOR bore, taper, constraint 4 generalised) | `primitives/sculptural_column.py` |
| the assembler (joints, floors, interference proofs) | `geometry/assembly.py` |
| registry facade (`PRIMITIVES` + `assemble` + compat) | `geometry/registry.py` |
| `validate_assembly` + mesh `body_count` | `geometry/validate.py` |
| signed envelope values | `config/materials.yaml`, `core/config.py` |
| AST whitelist `{registry, math}` | `geometry/ast_gate.py` (ADR-030) |
| gate | `scripts/gate_phase6a1_auto.py` (+ `_assembly_build_once.py`) |

### Gate evidence (verbatim key lines, container run 2026-08-20)

```
[3/7] canonical STEP sha256: e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
      expected  (Phase 2) : e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
      PASS — per-member walls, zero geometry drift
[5/7] primitives composed: b1(basin_round), c1(sculptural_column), p1(plinth)
      body_count (B-rep): 1
      joint b1 -stack_on-> p1: overlap 10 mm (floor 10), intersection 2827433.4 mm3
      joint c1 -concentric_insert-> b1: overlap 10 mm (floor 10), intersection 78539.8 mm3
      volume conservation: members 155272529.8 - intersections 2905973.2
        vs fused 152366556.6 mm3 (delta 0.0000% of 0.2%)
      watertight True | body_count 1 | volume_crosscheck delta 0.1158% of 2%
      PASS — one watertight assembly from three primitives
[6/7] run A sha256=529014af672a282b6626cece8eebc777f5d839a34be02c9a031b5813cf22ddbd
      run B sha256=529014af672a282b6626cece8eebc777f5d839a34be02c9a031b5813cf22ddbd
      byte-identical: True
[7/7] PASS — Phase 6 slice A1 auto gate: all sections passed at $0.
```

The constraint battery (§4) proved eight refusals with real numbers,
including the signed sheet's own worked example run live: the 1.0 × 1.0 m
solid basalt plinth (2,120.6 kg) refused by a 2,000 kg crane with the
message naming HOLLOWING as the lever, and the same plinth at a 180 mm wall
(1,252.0 kg) passing — `fabrication.max_lift_kg` and `max_module_m` are now
binding constraints computed per spec, not documentation.

### The find of the slice: joints that meet THROUGH an element

Writing the canonical test composition exposed a failure class no per-joint
check can see: in a coaxial plinth → basin → column stack, the column
inserted into the basin floor reaches the PLINTH whenever
`floor_mm < stack_overlap + insert_overlap`. One millimetre decides between
undeclared interference and EXACT TANGENCY — the ADR-029 knife edge,
reproduced at assembly scale before any live run could hit it. The
assembler now proves every NON-joined pair keeps a real gap (intersection
volume + `distance_to`, API verified against the installed build123d), and
the refusal tells the designer the actual fix: thicken the middle element's
floor or reduce the overlaps. Details in ADR-032 §5.

### Honesty items

- **An incident during verification (ADR-033):** the full-suite run from a
  mounted repo checkout leaked the operator's real `.env` keys past the
  "hermetic" test fixture, and the council no-keys test may have dispatched
  a real Council session (bounded ~$0.84, possibly a partial second). The
  local audit rows died with the test's temp database; the operator has
  been asked to check the three provider consoles for the truth. Fixed as
  a standing rule: key vars are forced EMPTY in tests, never deleted.
- The operator's visual gate is deliberately deferred to slice A2 — A1 has
  no viewport surface to eye-check; its guarantees are exactly the kind a
  $0 auto gate proves better than an eye.
- `min_feature_mm` / `min_internal_radius_mm` are signed, stored and
  config-validated, but no parameter consumes them until slices B/C
  (LIMITATIONS §11).
- The `spec_hash` of a cascade parameter set CHANGES (canonical dict now
  carries `column_wall_mm`); the Amendment-1 guarantee is about STEP bytes
  from a given (spec, seed), which the gate proves unchanged.
- Full scope limits of the slice: LIMITATIONS.md §11.

### Cost

$0.00 — no AI call in the slice; all geometry proven offline.
