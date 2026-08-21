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
- Unknown primitives fail with HTTP 422 before artifacts are written.
