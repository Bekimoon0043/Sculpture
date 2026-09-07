# 06 - Assembly manifest build (Phase 7A)

Phase 7A adds the primitive-agnostic assembly surface.

## Browser Path

1. Start the stack:

   ```bat
   docker compose up --build -d
   ```

2. Open http://localhost:5173.
3. Click **Assembly**.
4. Press **Build assembly**.

The viewport loads `/api/geometry/assembly/latest.glb` after the build. The
right panel shows the same validation panel used by the cascade path.

## API Path

Check the live registry:

```bat
curl http://localhost:8000/api/geometry/assembly/defaults
```

Build a three-element assembly:

```bat
curl -X POST http://localhost:8000/api/geometry/assembly/build ^
  -H "Content-Type: application/json" ^
  -d "{\"seed\":7,\"fabrication\":{\"max_lift_kg\":3000,\"max_module_m\":4.0},\"elements\":[{\"element_id\":\"plinth_01\",\"primitive\":\"plinth\",\"parameters\":{\"top_diameter_mm\":2200,\"height_mm\":300,\"wall_mm\":120}},{\"element_id\":\"basin_01\",\"primitive\":\"basin_round\",\"parameters\":{\"diameter_mm\":2000,\"height_mm\":450,\"wall_mm\":40,\"floor_mm\":160,\"min_clearance_mm\":220},\"joint\":{\"type\":\"stack_on\",\"parent\":\"plinth_01\"}},{\"element_id\":\"column_01\",\"primitive\":\"sculptural_column\",\"parameters\":{\"diameter_mm\":360,\"height_mm\":900,\"bore_mm\":80},\"joint\":{\"type\":\"concentric_insert\",\"parent\":\"basin_01\"}}]}"
```

Reload the persisted manifest:

```bat
curl http://localhost:8000/api/geometry/assembly/latest/manifest
```

Fetch the artifacts:

```bat
curl -o assembly.glb http://localhost:8000/api/geometry/assembly/latest.glb
curl -o assembly.step http://localhost:8000/api/geometry/assembly/latest.step
curl http://localhost:8000/api/geometry/assembly/latest/validation
curl http://localhost:8000/api/geometry/assembly/latest/exports
curl -o luxexchange_v1.zip http://localhost:8000/api/geometry/assembly/latest/luxexchange.zip
```

## Gate

Phase 7A passes when:

- `/api/geometry/assembly/defaults` lists the live primitive registry.
- `/api/geometry/assembly/build` returns `assembly_manifest_v1`.
- The manifest is persisted in the `designs` row as
  `assembly_design_record_v1`.
- Latest manifest, STEP, GLB, and validation endpoints return the same build.
- Latest validation includes `assembly_mesh`, `structure`, `hydraulics`, and
  `fabrication` gates.
- The Assembly panel shows STEP, GLB, and LUXEXCHANGE download links after a
  successful build.
- LUXEXCHANGE v1 includes the assembly manifest, validation reports, and
  included geometry artifacts.
- **Since LF-103A (2026-09-01) the package tells the truth about itself.**
  A design whose validation FAILED will not package at all (and its
  STEP/BREP/STL/DXF/SVG downloads refuse — the message names the failing
  check). A design that is not yet proven safe packages only as
  **PRE-FABRICATION**: the download is named
  `luxexchange_<id>_PRE-FABRICATION.zip`, every geometry file inside says
  PRE-FABRICATION in its own filename, the drawing carries a printed
  NOT-FOR-CONSTRUCTION notice, and `ENGINEERING_WARRANT.txt` lists every
  unresolved check and whose professional input it needs. **Read the
  warrant first.** Packages sealed before 2026-09-01 refuse to download
  until you re-export them (one click / one POST) — the old file on disk
  is never touched.
- Unknown primitives fail with HTTP 422 before artifacts are written.

## Fabricated assemblies (Phase 6 slice A2)

When the AI fabrication loop passes with a multi-element assembly, the
platform now persists it as a design AUTOMATICALLY — the same record shape,
the same STEP bytes, the same endpoints as a build you run yourself:

- The fabricate response (`POST /api/council/sessions/<id>/fabricate`)
  carries a `design_id`. Open the **Designer** view: the design is in the
  builds strip under **Ungrouped builds**, with each element pickable.
- The record links back to the exact generated program
  (`generated_program_id`), and the program row stores the manifest the
  sandbox returned (`manifest_json`) — the full audit trail from brief to
  geometry survives.
- The record also stores `sandbox_step_sha256` next to `step_sha256`. They
  should be IDENTICAL (same registry, same parameters, two containers). If
  they ever differ, the two Docker images have drifted — report it; the
  record exists to make that visible.
- If `design_id` is null on a successful fabrication, the response's
  `artifacts.design_bridge_error` says why. The fabrication itself still
  passed; nothing is faked to look complete.

## Free-form designs (FF-A2, ADR-066)

A `freeform_loop` design's manifest carries four keys legacy manifests
never have (legacy bytes are untouched — ADR-065):

- `mass_model` — the honest mass: `total_mass_kg` is **null** (the
  armature is undesigned), and `known_geometry_mass_kg` is every
  modeled 316L volume (lens shell + interface plate) × density. Every
  screen and check treats null as "incomplete", never as zero.
- `required_validation_gates` — the persisted applicability snapshot:
  export refuses outright if the `freeform_integrity_v1` row is
  missing, failed or indeterminate.
- `expected_topology` — the declared shape contract (one solid, one
  window, a sealed internal cavity); the integrity check FAILS any
  build that does not match it exactly.
- `wall_measurement` — the measured shell wall (`brepextrema_v1`).
  This is a measurement, **never approval**: the gate shows
  `geometric_wall_measurement` as needs-input unless the measured wall
  actually confirms the nominal gauge, and `fabrication_wall_approval`
  and `forming_radius` always wait for your fabricator. The
  `bore_to_cavity_clearance` row is the measured proof the window bore
  never touches the sealed cavity — it FAILS below wall − 0.5 mm.

Every free-form export seals **PRE-FABRICATION** at best, with the
warrant naming exactly what a professional still owes.
