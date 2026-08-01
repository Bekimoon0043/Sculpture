# PHASE_2_REPORT.md — Phase 2 build & verification report

Phase 2 scope (SPEC_PHASE2.md): geometry kernel + one parametric
tiered-cascade fountain + trimesh validation + GLB export + three.js
viewport + split gate [ADD-2], with the five operator additions [ADD-1..5].

## What was built

- `backend/app/geometry/` — kernel (seed → spec_hash + deterministic STEP
  timestamp), parameter registry (13 parameters, PHASE2_PLAN §3 +
  min_clearance_mm) with SIX hard constraints (three from the spec [ADD-4]
  plus three construction-safety constraints — see "Deviations" below),
  cascade builder (solids of revolution, fused, profile-drawn lip fillets,
  bore cut — watertight by construction), native STEP/GLB exporters, trimesh
  validation with a 2% volume cross-check against the exact B-rep volume.
- `backend/app/api/routes_geometry.py` — defaults / build / latest.glb /
  latest.step / latest/validation; builds persisted to `designs` +
  `validation_reports`; exports under `data/designs/<spec_hash>/`.
- DB upgrade (SPEC_PHASE2 §2): `schema_migrations` table; a Phase 1 database
  is RENAMED to `<name>.phase1-backup.db` on startup, never deleted.
- `frontend/` — React+Vite+TS+three.js viewport (pinned, package-lock.json
  committed): parameter panel from the live registry, rebuild button,
  validation table with real numbers, [ADD-5] rebuild timer in the viewport
  corner ("Last rebuild: N ms (server build: M ms)").
- `scripts/gate_phase2_auto.py` + `scripts/_cascade_build_once.py` — the
  non-interactive gate; `docs/operator/gate_phase2_visual.md` — the operator
  eye-check.
- `.gitattributes` [ADD-1] committed as its own first commit.

## Verification results

All verification below ran in this build sandbox (build123d 0.11.1 / trimesh 5.0.0 importable).

### Test suite

```
$ python3 -m pytest            (PYTHONPATH=<geometry deps>:backend)
...................................................................... [100%]
======================= 70 passed, 2 warnings in 14.78s ========================
(36 Phase 1 tests + 34 new Phase 2 tests; the 2 warnings are FastAPI's own
on_event deprecation notice, unchanged from Phase 1 style.)
```

### Phase 2 auto gate transcript

```
------------------------------------------------------------------------
[1/7] CONFIG & FRESH GATE DB
------------------------------------------------------------------------
materials loaded: basalt_slab, bronze_cast, cast_concrete_c35_45, stainless_316l_sheet
  basalt_slab: density=2700 kg/m3, min_wall=20 mm
  bronze_cast: density=8800 kg/m3, min_wall=6 mm
  cast_concrete_c35_45: density=2400 kg/m3, min_wall=75 mm
  stainless_316l_sheet: density=8000 kg/m3, min_wall=3 mm
gate DB: fresh /mnt/agents/output/luxuryform/data/gate_run_phase2.db (deleted first, schema v2 applied)
schema_migrations: v2 — fresh Phase 2 schema (v2) created
build123d 0.11.1 / trimesh 5.0.0
PASS — section 1

------------------------------------------------------------------------
[2/7] DETERMINISM PROOF (Amendment 1) — two separate processes
------------------------------------------------------------------------
sha256=e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
  spec_hash=ec06f9189e51331d2e9dcb3b614f64091b6e3b642d495a0f3dd8c9521d2c59cb
sha256=e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
  spec_hash=ec06f9189e51331d2e9dcb3b614f64091b6e3b642d495a0f3dd8c9521d2c59cb
STEP sha256 run A: e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
STEP sha256 run B: e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
byte-identical: True
PASS — section 2: same spec + same seed -> byte-identical STEP

------------------------------------------------------------------------
[3/7] HARD CONSTRAINTS [ADD-4] — real numbers in every error
------------------------------------------------------------------------
basin too small: ConstraintViolation with 1 violation(s):
  - basin_diameter_mm=2400 < required 2740 (= widest dish 2600 + 2*wall 2x20 + clearance 100)
wall below material minimum: ConstraintViolation with 1 violation(s):
  - basin_wall_mm=10 < material minimum 20 mm for basalt_slab (Basalt slab)
lip fillet too deep for dish: ConstraintViolation with 1 violation(s):
  - lip_fillet_mm=25 must be < dish_depth_mm/2 = 40/2 = 20
PASS — section 3

------------------------------------------------------------------------
[4/7] VALIDATION — trimesh real numbers on the default build
------------------------------------------------------------------------
default build: spec_hash=ec06f9189e51331d2e9dcb3b614f64091b6e3b642d495a0f3dd8c9521d2c59cb
canonical STEP sha256: e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
trimesh measured numbers:
  [PASS] watertight: True
  [PASS] winding_consistent: True
  [PASS] volume_mm3: 272335535.02
  [PASS] surface_area_mm2: 25084926.837
  [PASS] euler_number: 0
  [PASS] bounds_mm: [-1300.0, -1299.596, 0.0, 1300.0, 1299.596, 1240.0]
  [PASS] degenerate_face_count: 0
  [PASS] mass_kg: 735.306
  [PASS] volume_crosscheck: trimesh 272335535.020 vs brep 272448269.177 mm3 (delta 0.0414% of 2%)
  volume cross-check: trimesh 272335535.020 mm3 vs build123d 272448269.177 mm3 (delta 0.0414%, tolerance 2%)
PASS — section 4: watertight=true, every check passed

------------------------------------------------------------------------
[5/7] GLB ROUND-TRIP — trimesh bounds vs build123d bounds (1 mm)
------------------------------------------------------------------------
trimesh  bounds min: [-1300.0, -1299.596, 0.0]
trimesh  bounds max: [1300.0, 1299.596, 1240.0]
build123d bounds min: [-1300.0, -1300.0, 0.0]
build123d bounds max: [1300.0, 1300.0, 1240.0]
max bounds deviation: 0.4040 mm (tolerance 1.0 mm)
PASS — section 5

------------------------------------------------------------------------
[6/7] API ROUND-TRIP [ADD-3] — FastAPI TestClient, in-process
------------------------------------------------------------------------
GET /api/geometry/cascade/defaults -> 200
  13 parameters served
volume tiers=3: 272335535.020 mm3   step sha256: e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13
volume tiers=4: 340426916.278 mm3   step sha256: 1c0f76576e08ed1ad0e1c77879e68423f3d571ae1c161854f942da83cbd3da0d
server build_ms: 622.8 / 816.7 ms
  [PASS] volume changed
  [PASS] spec_hash changed
  [PASS] step hash changed
  [PASS] validation numbers changed
GET /api/geometry/cascade/latest.glb -> 200, 837592 bytes, glTF magic: b'glTF'
PASS — section 6: backend rebuild path works; if the browser does not update, the bug is isolated to the frontend

------------------------------------------------------------------------
[7/7] VERDICT
------------------------------------------------------------------------
PHASE 2 AUTO GATE: PASS

Next: the operator visual gate — docs/operator/gate_phase2_visual.md
```

### Frontend build

```
> luxuryform-frontend@0.2.0 build
> tsc --noEmit -p tsconfig.json && vite build

vite v8.2.0 building client environment for production...
transforming...✓ 26 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.42 kB │ gzip:   0.28 kB
dist/assets/index-D3mpmPu3.css    1.96 kB │ gzip:   0.81 kB
dist/assets/index-CSsaUwrN.js   817.15 kB │ gzip: 217.90 kB
✓ built in 418ms
```

### Viewport rebuild measurement [ADD-5]

viewport rebuild on operator hardware: ___ ms (operator fills from viewport
readout — "Last rebuild: N ms" in the top-left corner of the viewport;
instructions in docs/operator/gate_phase2_visual.md §3)

## Deviations from spec (with justification)

1. **Three additional hard constraints (4–6) in registry.py.** The spec
   mandates three [ADD-4]; Rule 6 (watertight by construction) requires:
   (4) column_diameter_mm ≥ bore_diameter_mm + 2·basin_wall_mm — otherwise a
   large bore deletes the column core and the dishes float; (5) lip_fillet_mm
   < basin_wall_mm — the fillet is drawn into the dish profile and must leave
   a real rim ledge (this is the sanctioned "tighten validated ranges /
   constraints rather than ship fragile geometry" move); (6) tier_spacing_mm
   ≥ dish_depth_mm — overlapping dishes are a design error the constraint
   system should catch, not silently fuse. All carry real numbers in their
   messages, same as the spec'd three.
2. **GLB linear_deflection = 1.0 mm instead of the live-doc default 0.001.**
   The default would tessellate a 2.6 m fountain into tens of millions of
   triangles (PHASE2_PLAN §7 budget is <1M). The canonical artifact is STEP;
   GLB is preview/validation only (LIMITATIONS.md §8). The 2% volume
   cross-check quantifies the tessellation effect with both numbers printed.
3. **Lip fillets drawn into the revolve profile (RadiusArc) instead of a
   post-hoc 3D fillet()** — the result is an exact toroidal fillet surface
   that cannot fail at parameter extremes (ADR-010).

## Known limitations

See LIMITATIONS.md §8 (single primitive, mesh preview only, no ray-based
wall-thickness check yet, STEP-only determinism scope, 1 mm tessellation).
