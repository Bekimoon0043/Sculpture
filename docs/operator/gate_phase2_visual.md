# Phase 2 VISUAL gate — operator eye-check checklist [ADD-2]

This is the HUMAN half of the Phase 2 gate. The machine half
(`scripts/gate_phase2_auto.py`) must PASS first — it cannot click a browser,
so you do the final proof that the viewport rebuilds when you change a
parameter. Work top to bottom and tick every box. Do not skip a failed box:
write down exactly what you saw and tell the technical lead.

**Time:** about 15 minutes (longer the very first time — see step 2).

## 0. Before you start

- [ ] The automatic gate passed:
  ```bat
  docker compose exec backend python scripts/gate_phase2_auto.py
  ```
  You saw `PHASE 2 AUTO GATE: PASS` on the last lines.

## 1. Start the platform

```bat
docker compose up --build -d
docker compose logs -f frontend
```

- [ ] The frontend logs end with a line like
  `VITE v8.x.x ready in ... ms` and `Local: http://localhost:5173/`.
  (First run can take 5–30 minutes while `npm ci` downloads packages on a
  slow connection — leave it running. If it fails, see
  `docs/operator/02_phase2_viewport.md` § npm troubleshooting.)

Press Ctrl+C to stop following logs (the platform keeps running).

## 2. Open the viewport

Open **http://localhost:5173** in your browser.

- [ ] You see a dark 3D view on the left and two panels on the right:
      "Cascade parameters" and "Validation".
      (An empty grid in the 3D view is normal before the first build —
      there is no model file yet.)
- [ ] The top-left corner of the 3D view shows
      `Last rebuild: — (press Rebuild)`.

## 3. The rebuild proof (the whole point of Phase 2)

1. In "Cascade parameters", find **tiers** (default: 3).
2. Change it to **4** and press **Rebuild**.
3. Wait for the 3D model to reappear.

- [ ] **The 3D model appears framed to fill the view ON ITS OWN — you did
      not zoom, pan, or hunt for it.** The camera frames itself from the
      model's bounding box on every load, at any model size. If you have
      to touch the mouse to find the model, this box FAILS — write down
      exactly what you see (empty grid? tiny speck? model half off-screen?).
- [ ] The 3D model visibly changed (one more dish in the stack).
- [ ] The corner readout now shows real numbers, e.g.
      `Last rebuild: N ms (server build: M ms)`.
- [ ] **COPY THE NUMBER into the report [ADD-5]:** open `PHASE_2_REPORT.md`,
      find the line `viewport rebuild on operator hardware: ___ ms`, and
      replace `___` with the N you see. Save the file.
- [ ] The Validation panel updated: every row shows a real number and a green
      `PASS`, including `watertight: true` and a `volume_mm3` that is
      DIFFERENT from before the rebuild.

## 4. Try to break it (constraint proof)

1. Set **basin_diameter_mm** to **1000** and press **Rebuild**.

- [ ] The rebuild is REFUSED and a red box lists the violation WITH the real
      numbers, e.g. `basin_diameter_mm=1000 < required 1540 (= widest dish
      1400 + 2*wall 2x20 + clearance 100)`.
- [ ] The 3D model did NOT change (the last valid design stays on screen).

Set **basin_diameter_mm** back to **2600** and press **Rebuild** to restore
the good model.

- [ ] The model rebuilds and the validation panel is green again.

## 5. Open the GLB in a real viewer

1. Download the model: open **http://localhost:8000/api/geometry/cascade/latest.glb**
   in the browser — a file `cascade.glb` downloads.
2. Open it in **Windows 3D Viewer** (double-click the file) or **Blender**
   (File → Import → glTF 2.0).

- [ ] The model opens: a round basin, central column, stacked dishes.
- [ ] It is ONE solid object, no missing faces, no inside-out surfaces.

## 6. Determinism spot-check

Press **Rebuild** twice in a row without changing anything. Then open
**http://localhost:8000/api/geometry/cascade/latest.step** twice (download
both). In PowerShell:

```powershell
Get-FileHash .\Downloads\cascade.step -Algorithm SHA256
```

- [ ] The two downloads show the SAME hash when the seed and parameters were
      unchanged. (The automatic gate already proved this across two separate
      processes with printed hashes — this is your spot-check.)

## 7. Sign off

- [ ] Every box above is ticked.

```
Phase 2 VISUAL gate signed off by: ______________________
Date: ______________
Last rebuild measured on this machine: __________ ms  (also copied into
PHASE_2_REPORT.md)
```
