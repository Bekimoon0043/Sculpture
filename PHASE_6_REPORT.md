# PHASE_6_REPORT.md — The Primitive Library (IN PROGRESS)

Phase 6 ships in gated slices (PHASE_6_PLAN.md §2). This report accumulates
one section per closed slice; the phase closes when the operator's gate — a
brief needing three primitives produces one watertight assembly, viewable
and exportable — passes live at slice A2.

---

## PHASE 6 GATE: PASS - slices A1 (2026-08-20), A2 and B auto (2026-08-26); C/D not built

## Slice B — rim treatments + nozzle fixture (BUILT, auto gate PASS 2026-08-26, $0)

**Scope:** `weir_edge` / `coping` / `pool_edge` as alternative rim
cross-sections of the basin's ONE revolved profile (Polyline + RadiusArc,
the ADR-010 cascade-lip pattern — never a post-hoc boolean); the
`nozzle_ring` fixture cut by trusted assembler code before placement and
fuse; hydraulic facts wired from the spec's `hydraulic_network` by the
mapper — never invented, never silently defaulted. The signed §2.2/§2.3
floors (min feature, min internal radius, incl. 316L's formula floors)
became load-bearing. Decisions: ADR-054. One approved-plan correction,
made openly (ADR-054 §2): `weir_depth_mm`-from-elevation was physically
incoherent for a 360° crest; built as elevation-consistency (±5 mm) plus
crest/drip shaping instead.

### Gate evidence (verbatim, 2026-08-26)

```
docker compose exec backend python -m pytest tests/test_slice_b.py -q
16 passed in 22.50s
(regression: tests/test_assembly.py + primitives + cascade + fabricate + slice_b
97 passed in 79.50s)

docker compose exec backend python scripts/gate_phase6b_auto.py
cascade: e1a59fa6… ok | A1 composition: 529014af… ok
default basin: 6038d26f… ok (pinned BEFORE the first profile edit)
weir_edge ⌀2010 / coping ⌀2120 h500 / pool_edge ⌀2000 — one solid each
volume removed: 59992 mm³, expected 3·π·(20.6/2)²·60 = 59992 mm³
process 74: 07dcd723e5e08a1a…  process 89: 07dcd723e5e08a1a…
PASS — Phase 6 slice B auto gate: all sections passed at $0.
(all 16 auto gates re-run: exit 0 across the roster)
```

One gate-authoring defect caught by the gate itself: the first run pinned
a hand-copied A1 plan (missing `taper_deg`, wrong seed) and failed §1;
the gate now imports the canonical plan from `_assembly_build_once.py`.
Cost: **$0.00** — no AI call anywhere in the slice. Operator's eye gate:
`gate_phase6b_visual.md` ($0). B-7 (hollow plinth cap) was not ruled at
approval; the plinth stays an open tube.

`gate_phase6a1_auto.py` and `gate_phase6a2_auto.py` both PASS at $0. Phase 6
as a whole is NOT closed: the operator's LIVE gate (`gate_phase6_visual.md`
— a brief needing three primitives, through Council → fabrication, viewable
and exportable) has not been run, and slices B (rim treatments + fixtures),
C and D are not built.

## Slice A2 — the fabrication → design bridge (BUILT, auto gate PASS 2026-08-26, $0)

**Scope (a tie-off, honestly):** the original A2 was largely consumed
piecemeal before this slice — the primitive-agnostic API and manifest
persistence by Phase 7A, the frontend by Phases 14–15, the mapper and
designer index on 2026-08-21. What A2 actually built is the piece none of
them provided: a passing assembly fabrication now becomes a real design
record. Decisions: ADR-052.

### What was built

| piece | where |
|---|---|
| shared persistence helper (one path, one identity) | `routes_assembly.persist_assembly_design` |
| fabrication bridge (trusted rebuild from the manifest) | `fabricate._persist_fabricated_assembly` |
| lineage columns (additive, ADR-023 patches) | `designs.generated_program_id`, `generated_programs.manifest_json` |
| two-tier prompt surface (index always, detail per spec) | `prompts.registry_surface(used_primitives)` |
| honest bridge failure (`design_bridge_error`, never a fake) | `fabricate.py` step 5 |
| tests (6, real geometry, scripted sandbox per ADR-005) | `tests/test_fabricate_assembly.py` |

### Gate evidence (verbatim, 2026-08-26)

```
docker compose exec backend python -m pytest tests/test_fabricate_assembly.py -q
6 passed in 46.10s

docker compose exec backend python scripts/gate_phase6a2_auto.py
full surface: 11267 chars (~2816 tokens)
3-primitive surface: 8144 chars (~2036 tokens)
persisted design: da77bd5e-aa95-40db-b8d4-ae918bd1c95c
bridge-path STEP sha256: 57e3bc901a71c97bdfdd767b948c9c7af4ebab0780554454f13cf653320c74b2
API-path STEP sha256:    57e3bc901a71c97bdfdd767b948c9c7af4ebab0780554454f13cf653320c74b2
ok   — byte-identical STEP across two separate processes
PASS — Phase 6 slice A2 auto gate: all sections passed at $0, no network,
no AI-written code executed.
```

The Phase 2 canonical hash `e1a59fa6…` is re-asserted by the gate's §1 and
unchanged. One defect was found by the first test run and fixed: the bridge
originally ran before the program row was committed, so the design's
`generated_program_id` FK had no target — the honest-failure path caught it
(`design_bridge_error: FOREIGN KEY constraint failed`) exactly as designed.

Full suite (verbatim, 2026-08-26, render worker RUNNING):

```
docker compose exec backend python -m pytest tests/ -q
5 failed, 364 passed, 2 warnings in 855.14s (0:14:15)
```

The 5 failures are PRE-EXISTING and environment-dependent, not a slice A2
regression: they hardcode the render worker being DOWN
(`assert 'included' == 'unavailable'`) and were reproduced identically on
pristine image code with none of this slice's files present
(`docker compose run --rm backend ... 5 failed in 74.58s`). Recorded as
debt D-9 in NEXT.md. Every test in areas this slice touched passes.

### Found live by the operator, fixed in the same slice (ADR-053)

The operator's screenshots of design `a3006a42` (2026-08-26) exposed a
constraint gap: a ⌀2,000 basin on a hollow ⌀2,200/102 plinth passed every
check while bearing 1,550 kg on a **2 mm basalt lip** (the plinth's inner
mouth is ⌀1,996; the stored intersection volume, 125,538 mm³, is exactly
that 2 mm × 10 mm rim ring). Interference proved the fuse, never the seat.

Fix: stack_on now enforces a **bearing floor** — the worst-angle radial
seat must be at least the signed §2.1 material joint floor (cross-material
MAX), computed from new per-primitive `base_annulus_mm` /
`stack_top_annulus_mm` helpers, refused with the arithmetic and the
levers. Three new tests reproduce the exact live case (2.0 mm refused,
50 mm at wall 150 passes, offset-on-solid keeps full bearing). One gate
needle changed and is recorded in ADR-053 §3: the A1 "floating body" case
is now refused earlier by the seat check (−100.0 mm) — protection
unchanged, refusal moved left. Verbatim after the fix (2026-08-26):

```
pytest tests/test_assembly.py tests/test_fabricate_assembly.py -q
29 passed in 31.40s
gate_phase6a1_auto: PASS — all sections passed at $0.   (exit 0)
gate_phase6a2_auto: PASS — … (exit 0, incl. "knife-edge stack seat
refused (ADR-053): b1: … 2.0 mm radial seat, below the 10 mm floor")
npm run build: ✓ built in 3.98s
```

Two UI defects from the same screenshots were fixed with it: the 220 px
left rail clipped its form labels to stray glyphs (rows now name +
full-width control, hints moved to tooltips), and the check table rendered
`element_masses_kg` as a truncated JSON blob (composite values now render
as readable key: value pairs and wrap).

Three navigation defects the operator then reported were fixed the same
day (`npm run build` ✓ 2.23s):

- **Clicking Validate or Export did nothing visible** — Build, Validate
  and Export all navigate to the same Designer view, and no signal said
  which right-rail surface was meant. The stepper now deep-links the tab
  (Build → Design, Validate → Checks, Export → Output), and a repeat
  click re-applies it.
- **A reload opened "another design"** — the workspace always opened the
  NEWEST design in the shared database, which with concurrent sessions
  building is often someone else's. It now remembers the design the
  operator had open (per-browser, like thumbnails) and reopens it when it
  still exists in the current project scope; otherwise it falls back to
  newest.
- **The Cascade tool looked like a wrong design** — it is the legacy
  Phase 2–4 single-primitive tool with its own separate artifact, and now
  says so in its header instead of leaving the operator to wonder.

### What A2 does NOT claim

No live multi-primitive fabrication has happened. The operator's gate is
`gate_phase6_visual.md` (projected ≈$0.90–1.10 live). Mixed-material
costing moved to the costing tie-off (W-7) — see LIMITATIONS §11 for why.
Stored pre-ADR-053 designs (including `a3006a42`) are not retro-flagged —
they are refused with instructions on their next rebuild (LIMITATIONS §11).

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
