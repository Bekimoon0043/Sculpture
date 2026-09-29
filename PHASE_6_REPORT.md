# PHASE_6_REPORT.md — The Primitive Library (IN PROGRESS)

Phase 6 ships in gated slices (PHASE_6_PLAN.md §2). This report accumulates
one section per closed slice; the phase closes when the operator's gate — a
brief needing three primitives produces one watertight assembly, viewable
and exportable — passes live at slice A2.

---

## PHASE 6 GATE: PASS - slices A1 (2026-08-20), A2/B/C1 (2026-08-26), C2 (2026-08-27); D not built

> **Correction 2026-09-08 (PR-5, ADR-068) — read before the heading
> above.** The heading is preserved as written, but "PHASE 6 GATE: PASS"
> overstates it: what passed are the slices' AUTO gates. This report's own
> opening paragraph says the phase closes when the OPERATOR's gate — a
> brief needing three primitives producing one watertight assembly,
> viewable and exportable — passes LIVE (`gate_phase6_visual.md`, ~$1),
> and that live gate has NOT been run (NEXT.md §0: "pending: live gate
> `gate_phase6_visual.md`, eye gates 6b + 6c + 6c2"). Phase 6 is therefore
> NOT closed. Slice D (free-form) has since become release-blocking
> (ADR-060) and its first primitive shipped as FF-A2 (ADR-066).

## Slice C2 — segmentation (BUILT, auto gate PASS 2026-08-27, $0)

`scripts/gate_phase6c2_auto.py` — 12 sections, exit 0, no network, no AI
call, no AI-written code executed. ADR-056.

### What it makes true

A fountain bigger than the crane or the truck stops being refused and
starts arriving as numbered modules.

    5 m basalt basin (d5000, wall 150, h700)
      as one piece   : 4,202,272,873 mm3 = 11,346.1 kg   -> previously REFUSED
      at max_module_m 2.4 m, max_lift_kg 2000:
                       9 modules, heaviest 1,472.2 kg    -> BUILDS
      volume delta   : 0.0000000000 %

### Gate evidence, verbatim numbers

| check | measured |
|---|---|
| canonical STEP, all four | `e1a59fa6…`, `529014af…`, `6038d26f…`, `956436c1…` unmoved |
| conservation, 9-module cut | delta `0.0000000000 %` (ceiling 1e-6 %) |
| widest / heaviest module | 1,666.7 mm of 2,400 mm; 1,472.2 kg of 2,000 kg |
| count measured, not predicted | hollow tube grid 3x3x2 predicts **18**, truly **16** |
| seam area vs hand arithmetic | 1,830,000.000000 vs 1,830,000.000000 mm2 |
| seam length vs hand arithmetic | 25,600.000000 vs 25,600.000000 mm |
| interfaces, not cut faces | 4 quarters -> **4** interfaces (not 8); 0 unmatched |
| joint seam = contact face | 12,566.371 mm (annulus), not 15,707.963 mm (child outline) |
| determinism | segmentation byte-identical across PIDs 233 / 248 |
| array refusal | `a1` refused by name; a naive grid would report **25** pieces, lightest 0.9 kg vs heaviest 2,685.7 kg (2,984x) |
| crane pick | 2,375.0 kg of a 13,721.2 kg assembly |
| seam line | `not_computable` -> `missing_rate` @ `materials.basalt_slab.seam` |
| transport line | `not_computable` -> `missing_rate` @ `install.truck_payload_kg` |
| filled-card arithmetic | seam 62.679 m x 300 ETB/m = 18,803.62 ETB; trips `max(ceil(13,721.2/12000)=2, ceil(10/4)=3) = 3`, bound by bed space |
| rate card | 33 -> **39** null entries; `costing.yaml` `2026-08-v2` |
| costing route on an assembly | HTTP **200** (was 500); mass 13,721.181 = manifest 13,721.181 |
| mixed material | HTTP **409** naming `basalt_slab`, `bronze_cast` |
| segmentation cost | 187 ms (9 modules), 324–713 ms (16 modules); ceiling 256 cells |

> **Superseded 2026-09-28 by PR-6 / ADR-074:** the rows above about the
> rate-card count and mixed-material refusal remain the verbatim C2 evidence.
> Current truth: `costing.yaml` is `2026-09-v3` with 47 required null
> entries, and a mixed-material assembly returns HTTP 200 with per-element
> costing, one-owned joints and shared install once. `gate_phase6c2_auto.py`
> now enforces that current contract.

### Three defects this slice had to fix, none of them planned

1. **`GET /api/costing/bom/{id}` returned HTTP 500 for every assembly ever
   built.** An assembly stores an `AssemblyValidationReport`, which by
   design carries no `material_id` and no single `mass_kg`; the route
   parsed every stored report as a `ValidationReport`. Costing had been
   unreachable for assemblies since Phase 7A and nothing recorded it. The
   first diagnosis (row selection) was wrong and is recorded in ADR-056.
2. **`GET /api/costing/bom/{id}.txt` returned 404 for every design** — the
   rendered document handed to a client. It was registered after
   `/bom/{design_id}` and FastAPI's greedy path parameter swallowed the
   `.txt`. Route order is now load-bearing and regression-tested.
3. **The LUXEXCHANGE package digest stopped being reproducible.** Making
   costing work meant the package finally sealed a real `costing/bom.json`
   — which stamps a wall-clock `generated_at`. The guarantee (ADR-035/037)
   had a latent hole that was masked only because assembly costing was
   broken. The sealed BOM is now stamped with the design's own creation
   time. Caught by the existing Phase 9A tests, not by a new one.

### Scope, honestly

- **Axis-aligned planar grids only.** A round basin splits into a 3x3
  waffle; a mason might cut radial pie segments. Flagged as the slice's
  weakest decision and put to the operator in `gate_phase6c2_visual.md` §2.
- **`material_purchase` is NOT unlocked**, contrary to the W-3b entry that
  scoped this slice. A slab count needs a stock THICKNESS that
  `materials.yaml` does not carry, and a sheet count needs a curved shell
  unrolled. Two of three lines, not three.
- **Arrays are refused, not decomposed.** Their real answer (hub + N
  blades) is D-12 in NEXT.md.
- **Pre-2026-08-27 designs carry no segmentation** and are asked to be
  rebuilt rather than guessed at.
- Full scope limits: LIMITATIONS.md §11 (slice C2 block) and §10.

### Gate transcript, verbatim

`docker compose exec -T backend python scripts/gate_phase6c2_auto.py` — exit code 0, 2026-08-27:

```
------------------------------------------------------------------------
[1/12] CANONICAL GUARDS — segmentation moved no bytes
------------------------------------------------------------------------
cascade        : e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
ok   — Phase 2 canonical cascade byte-identical
A1 composition : 529014af672a282b6626cece8eebc777f5d839a34be02c9a031b5813cf22ddbd
ok   — A1 gate-composition assembly byte-identical
default basin  : 6038d26f28cd61b0c01ae9fde00ff2841b34ad0d6228cc7c4bbdbdd1eeacf0f0
ok   — default basin byte-identical
C1 composition : 956436c12891d3bd471888a139d640e4e23cd764c7977d253de21cb0a0b97985
ok   — C1 24-blade composition byte-identical

------------------------------------------------------------------------
[2/12] CONSERVATION, EXACTLY — nothing is lost in the cut
------------------------------------------------------------------------
element        : 4,202,272,873 mm3 = 11,346.1 kg as ONE piece
modules        : 9 summing to 4,202,272,873.258047 mm3
delta          : 0.0000000000 % (ceiling 1e-6 %)
ok   — module volumes sum back to the element exactly: 0.0000000000%
ok   — an 11-tonne basin now yields liftable modules: 11,346.1 kg -> 9 modules
  module 0:   1,472.2 kg   bbox   1666.7 x   1666.7 x  700.0 mm
  module 1:   1,083.1 kg   bbox   1523.7 x   1523.7 x  700.0 mm
  module 2:   1,083.1 kg   bbox   1523.7 x   1523.7 x  700.0 mm
  module 3:   1,472.2 kg   bbox   1666.7 x   1666.7 x  700.0 mm
  module 4:   1,125.0 kg   bbox   1666.7 x   1666.7 x  150.0 mm
  module 5:   1,472.2 kg   bbox   1666.7 x   1666.7 x  700.0 mm
  module 6:   1,083.1 kg   bbox   1523.7 x   1523.7 x  700.0 mm
  module 7:   1,472.2 kg   bbox   1666.7 x   1666.7 x  700.0 mm
  module 8:   1,083.1 kg   bbox   1523.7 x   1523.7 x  700.0 mm

------------------------------------------------------------------------
[3/12] EVERY MODULE FITS — both declared limits, per module
------------------------------------------------------------------------
widest module  : 1,666.7 mm  (limit 2,400 mm)
heaviest module: 1,472.2 kg  (limit 2,000 kg)
ok   — every module inside max_module_m: worst 1,666.7 mm
ok   — every module inside max_lift_kg: worst 1,472.2 kg
ok   — the assembler BUILDS what it used to refuse (strict mode): 9 modules, heaviest 1,472.2 kg

------------------------------------------------------------------------
[4/12] MEASURED, NOT PREDICTED — the tube's centre cells are bore
------------------------------------------------------------------------
grid           : {'x': 3, 'y': 3, 'z': 2} predicts 18 cells
measured       : 16 connected solids
ok   — the module count is measured, not n_x*n_y*n_z: predicted 18, measured 16
ok   — and it still conserves volume exactly: 0.0000000000%

------------------------------------------------------------------------
[5/12] SEAM ARITHMETIC — hand-checkable, and counted once
------------------------------------------------------------------------
hand arithmetic: area 457,500.0 mm2, perimeter 6,400.0 mm, per interface
kernel         : 4 interfaces, 1,830,000.0 mm2, 25,600.0 mm
ok   — 4 quarters share 4 interfaces, not 8 cut faces: 4 modules, 4 interfaces
ok   — seam AREA matches hand arithmetic: 1,830,000.000000 vs 1,830,000.000000 mm2
ok   — seam LENGTH matches hand arithmetic: 25,600.000000 vs 25,600.000000 mm
ok   — no cut face went unpaired: 0 unmatched
joint seam     : 12,566.371 mm (annulus pi x (2200+1800) = 12,566.371 mm; the child's own outline would be 15,707.963 mm)
ok   — a joint seam is the contact face, not the child outline: 12,566.371 mm

------------------------------------------------------------------------
[6/12] DETERMINISM — two processes, and plane order
------------------------------------------------------------------------
process 494: 1735 chars of canonical JSON
process 509: 1735
ok   — segmentation byte-identical across two processes
plane order z-y-x vs x-y-z: 9 vs 9 modules, 50112.361663 vs 50112.361663 mm seam
ok   — plane order changes no engineering number

------------------------------------------------------------------------
[7/12] THE ARRAY REFUSAL — fragments are not modules
------------------------------------------------------------------------
refusal: a1: bounding box 2300 x 2300 x 600 mm exceeds max_module_m 0.8 m (800 mm), and blade_fin_array is discrete_array: it is already a ring of separate pieces on a hub, so saw planes through it produce fra
ok   — an oversized blade ring is refused BY NAME
a naive grid would have reported 25 'modules', lightest 0.9 kg against heaviest 2,685.7 kg (2,984x) — blade tips, not fabricable pieces
ok   — the platform did NOT report those fragments as modules: 25 fragments from a 3x3 grid, refused

------------------------------------------------------------------------
[8/12] DRIVERS AND THE BOM — whose homework is it now
------------------------------------------------------------------------
drivers: modules 10, seam 62.679 m / 4.7879 m2, crane pick 2,375.0 kg of 13,721.2 kg total
ok   — the crane picks a MODULE, not the whole fountain: 2,375.0 kg vs 13,721.2 kg
ok   — module count and seam length are real numbers
  seam_welding         missing_rate     materials.basalt_slab.seam
ok   — seam_welding is now the OPERATOR's to supply, not ours to build: missing_rate / materials.basalt_slab.seam
  install_transport    missing_rate     install.truck_payload_kg
ok   — install_transport is now the OPERATOR's to supply, not ours to build: missing_rate / install.truck_payload_kg
  material_purchase    not_computable   (still ours + his: stock thickness and nesting, NOT segmentation)
ok   — material_purchase is honestly still not computable
  seam_welding: seam run 62.679 m (50.112 m from segmentation cuts + 12.566 m at element joints) x 300 ETB/m = 18,803.62 ETB
ok   — seam_welding computes against a filled card
  install_transport: max(ceil(13,721.2 kg / 12000 kg) = 2, ceil(10 modules / 4) = 3) = 3 trip(s), bound by bed space x 8000 ETB/trip = 24,000.00 ETB
ok   — install_transport computes against a filled card
ok   — the rate card names the six new nulls: 39 entries (33 before slice C2)

------------------------------------------------------------------------
[9/12] THE ROUTE — it returned HTTP 500 for every assembly
------------------------------------------------------------------------
ok   — assembly build returns 200: 200
GET /api/costing/bom/4fee7af8... -> 200
ok   — costing an ASSEMBLY returns 200, not 500: 200
drivers.mass_kg 13,721.181 vs manifest total 13,721.181 kg
ok   — the BOM costs the SAME mass the manifest measured: 13,721.181 vs 13,721.181
ok   — the rendered document says what ships

------------------------------------------------------------------------
[10/12] MIXED MATERIAL — refused, never mispriced
------------------------------------------------------------------------
-> 409 mixed_material_assembly: design assembly_design_record_v1 uses 2 materials and the BOM prices one. Refusing rather than quoting every element at one material's rate
ok   — a mixed-material assembly is refused with 409: 409
ok   — and the refusal names both materials: ['basalt_slab', 'bronze_cast']

------------------------------------------------------------------------
[11/12] BUDGET — segmentation is cheap enough to sit on the build
------------------------------------------------------------------------
ok   — no wall-clock timing in the b1 manifest block
ok   — no wall-clock timing in the p1 manifest block
  5 m basin: 9 module(s) in 308 ms
  hollow tube: 16 module(s) in 389 ms
  the refused-grid ceiling is 256 cells
ok   — no element takes more than 10 s to segment: worst 389 ms
  refusal: segmentation refused: a 5000 x 5000 x 700 mm element at a 100 mm module limit needs a 50 x 50 x 7 grid = 17500 cells, over the 256-cell ceiling. Raise fabricati
ok   — a runaway module limit is refused with the numbers

------------------------------------------------------------------------
[12/12] VERDICT
------------------------------------------------------------------------
PASS — Phase 6 slice C2 auto gate: all sections passed at $0, no network, no AI-written code executed.
```

### Full roster and suite on the C2 code — reported as measured, not as hoped

```
17 of the 18 scripts/gate_*_auto.py: exit 0, 0 FAIL
  costing, 2, 3, 4, 5, 6a1, 6a2, 6b, 6c, 6c2, 8, 8b, 9a, 11, 13a, 14, 15
NOT RUN: gate_phase9b_auto — requires the render-worker container UP.
gate_phase14_auto was run in BOTH halves:
  container  -> "sections run: geometry"   exit 0
  host --frontend-only -> "sections run: frontend"  exit 0
```

The gate roster is robust to render-worker state: 9a reports the four
Blender formats `unavailable` with the worker down and `included` with it
up, and passes either way (ADR-045). **The pytest suite is not**, and it
did not come out clean:

```
docker compose exec backend python -m pytest -q
=========================== short test summary info ============================
FAILED tests/test_export_package.py::test_package_manifest_is_honest_about_what_is_missing
1 failed, 432 passed, 2 warnings in 796.34s (0:13:16)
```

```
        assert statuses["STEP"] == "included"
        assert statuses["DWG"] == "impossible"
>       assert statuses["USD"] == "unavailable"
E       AssertionError: assert 'included' == 'unavailable'
E         - unavailable
E         + included
tests/test_export_package.py:348: AssertionError
```

That is the pre-existing **D-9** condition — five export tests assume the
render worker is DOWN — and not a defect in this slice: the test exercises
no segmentation, costing or manifest code C2 touched. The worker was
verified down before the run (`stop` at 07:55:24) and was started
externally at **08:12:30**, about ten minutes into a run that began
~08:02:12.

Retried on the single file with the worker stopped and re-verified at both
ends. It was contaminated the same way:

```
=== worker state BEFORE the run ===
/luxuryform-render-worker-1 exited exit=137 finished=2026-08-27T12:22:30Z
1 failed, 18 passed in 236.81s (0:03:56)
=== worker state AFTER the run ===
/luxuryform-render-worker-1 running started=2026-08-27T12:25:35Z
```

The worker restarted at 12:25:35 — three minutes into a four-minute run.
Restarts are on record at irregular gaps — 33 s after one stop, 3 m 05 s
after another; `RestartPolicy=no`, `RestartCount=0`. No gate and no test
was edited to make any of this pass.

**Both debts were closed the same day by PR-0 (`0645b06`, 2026-08-27,
ADR-057), after this section was written.** The six worker-state tests now
assert the honest contract in BOTH states
(`assert result.status in ("included", "unavailable")`), and the sealed
manifest carries a constant `excluded` for every Blender-tier format plus
`omitted_non_reproducible`, so the package digest describes THE PACKAGE
rather than the runtime and no longer depends on worker state at all. That
is a better fix than the one D-9 proposed — D-9 only asked the tests to
tolerate both states; ADR-057 removed the dependency from the artifact.
Clean full-suite runs in both worker states are recorded in
`PRODUCTION_V1_REPORT.md`. **The sentence above — "this code has no clean
full-suite run" — was true when written and is no longer true.** It is
kept rather than deleted because the C2 gate evidence should read as it
stood on the day; `NEXT.md` marks D-9 and D-9b `[x]`.

### Cost

$0.00 — no AI call; every number above measured offline by the kernel.

## Slice C1 — extrusion and array masses (BUILT, auto gate PASS 2026-08-26, $0)

**Scope:** six new masses (registry 4 → 10): `basin_rect`,
`stepped_monolith`, `water_wall`, `torus_ring`, `blade_fin_array`,
`lotus_petal_array`. Extrusion joins revolution as a
watertight-by-construction path; arrays fuse in index order, engaged into
their hubs by the joint floor, with the tangency band refused
(`check_array_spacing`); non-circular footprints bear on conservative
inscribed-circle seats and the torus on its computed chord (ADR-053
extended). Segmentation was removed from scope to its own C2 slice (plan
§8.1, approved). Decisions: ADR-055. Live-verified library facts
(ADR-009): `Torus`, `PolarLocations`, `extrude`, `Rot` present in the
installed build123d 0.11.1, checked 2026-08-26.

### Gate evidence (verbatim, 2026-08-26)

```
docker compose exec backend python -m pytest tests/test_slice_c.py -q
16 passed in 32.03s
(regression: assembly + primitives + cascade + fabricate + slice_b + slice_c
113 passed in 121.56s)

docker compose exec backend python scripts/gate_phase6c_auto.py
cascade e1a59fa6… ok | A1 529014af… ok | default basin 6038d26f… ok
six masses built, volumes printed (blade array 225.9 x10⁶ mm³, …)
THE GATE C COMPOSITION: body_count 1 (B-rep AND mesh),
volume conservation delta 0.0000% of 0.2%
process 313: 956436c12891d3bd471888a139d640e4e23cd764c7977d253de21cb0a0b97985
process 323: 956436c12891d3bd471888a139d640e4e23cd764c7977d253de21cb0a0b97985
torus chord = 2·sqrt(10·190) = 87.2 mm >= 10 mm floor
2,494.8 kg monolith refused by a 2,000 kg crane (arithmetic printed)
PASS — Phase 6 slice C1 auto gate: all sections passed at $0.
```

Full roster and suite on the C1 code (verbatim, 2026-08-26):

```
17 auto gates: costing, 2, 3, 4, 5, 6a1, 6a2, 6b, 6c, 8, 8b, 9a, 9b, 11,
13a, 14, 15 — every one exit=0

docker compose exec backend python -m pytest tests/ -q
5 failed, 399 passed, 2 warnings in 523.72s (0:08:43)
```

The 5 failures are the pre-existing D-9 render-worker-state tests BY NAME
(2 in test_assembly_api, 3 in test_export_package) — the same five that
failed before slice A2, unrelated to C1.

Two OLDER gates went red when the registry widened, were reported before
any edit, and were corrected without weakening a check (ADR-055): 6a1's
exact-four registry assertion became a subset check **on the operator's
explicit ruling**, and 6a2's example "unknown primitive" moved from
`water_wall` (which C1 made real) to `basin_spline` (slice D, genuinely
unbuilt). Recorded as debt D-10: sweep the remaining gates for the same
built-in-expiry pattern before slice D.

Two defects caught during the build, both mine, both fixed before the
gate went green: the lens degeneracy bound was twice as strict as the
real arithmetic (width < length/2 vs width < length), and the gate's
surface check first matched index lines instead of parameter tables. One
A1-era test snapshot (registry == exactly four) updated to
subset-plus-protocol, with the exact-ten assertion in test_slice_c.
Cost: **$0.00** — no AI call anywhere in the slice. Eye gate:
`gate_phase6c_visual.md` ($0). B-7 and the notch-weir ruling remain
unanswered and open.

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
