# 02 — Phase 2: the cascade viewport (plain-language operator guide)

Phase 2 adds the geometry engine and a 3D viewport. You can now change the
tiered-cascade fountain's parameters in your browser, watch it rebuild in 3D,
and read the measured validation numbers — wall thickness and basin fit are
enforced by hard constraints that refuse impossible designs with the real
numbers in the error.

## Start everything

From the repo folder:

```bat
docker compose up --build -d
```

Two services start:

| service  | what it is                         | address                    |
|----------|------------------------------------|----------------------------|
| backend  | the API + geometry engine          | http://localhost:8000      |
| frontend | the 3D viewport (web page)         | http://localhost:5173      |

**First start is slow.** The frontend container runs `npm ci`, which
downloads every JavaScript package the viewport needs (about 150–250 MB).
On a slow connection expect **5–30 minutes** the first time; after that the
packages are cached inside the named volume of the project and it starts in
seconds. Watch progress with:

```bat
docker compose logs -f frontend
```

You are done when you see `VITE ... ready` and `Local: http://localhost:5173/`.

**If `npm ci` fails or stalls** (connection dropped, registry timeout):

```bat
docker compose restart frontend
```

`npm ci` resumes from the partial download cache; repeat the restart until it
finishes. If it fails five times in a row, copy the exact red error line and
send it to the technical lead — do not edit package.json yourself.

## What you are looking at (http://localhost:5173)

- **Left: the 3D viewport.** Drag with the left mouse button to orbit, scroll
  to zoom, right-drag to pan. The model units are millimetres.
- **Top-left corner of the viewport: the rebuild timer.** After every Rebuild
  it shows `Last rebuild: N ms (server build: M ms)` — N is the full time from
  your click until the new model is on screen, M is the server's geometry
  build time alone. The Phase 2 report asks you to copy N into it.
- **Right, top: Cascade parameters.** Every parameter of the fountain with
  its unit and allowed range, exactly as registered in the backend
  (`backend/app/geometry/registry.py`). `seed` controls determinism: same
  parameters + same seed = byte-identical STEP file.
- **Right, bottom: Validation.** The measured numbers of the current model:
  watertight, volume, surface area, mass (from the material's density in
  `config/materials.yaml`), and the volume cross-check between the mesh and
  the exact CAD solid. Every row shows its real number and PASS/FAIL.

## Using it

1. Change any parameter (try `tiers` 3 → 4) and press **Rebuild**.
2. The server rebuilds the fountain, re-exports STEP + GLB, re-validates, and
   the viewport reloads the new model automatically.
3. If a parameter set is impossible (basin too small for the dishes, wall
   thinner than the material allows, …), the rebuild is REFUSED and the red
   box shows exactly why, with the real numbers. The last valid model stays
   on screen.

## Downloads (open in the browser address bar)

- `http://localhost:8000/api/geometry/cascade/latest.glb` — the 3D preview
  (open with Windows 3D Viewer or Blender).
- `http://localhost:8000/api/geometry/cascade/latest.step` — the canonical
  CAD file for fabricators.
- `http://localhost:8000/api/geometry/cascade/latest/validation` — the
  validation numbers as text (JSON).

## Your old database is never deleted

The first time Phase 2 starts, if your `data/luxuryform.db` is a Phase 1
database, it is **renamed** to `data/luxuryform.phase1-backup.db` and a fresh
Phase 2 database is created (the designs table gained columns; SQLite cannot
alter a foreign key in place). The Phase 1 file contained only gate logs —
the backup keeps them forever. Delete the backup yourself only if you are
sure you do not want them.

## The two-part Phase 2 gate

1. Automatic (no browser):
   ```bat
   docker compose exec backend python scripts/gate_phase2_auto.py
   ```
2. Visual (you, in the browser): `docs/operator/gate_phase2_visual.md`.
