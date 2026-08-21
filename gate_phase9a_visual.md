# gate_phase9a_visual.md — what the operator checks by eye

The auto gate (`scripts/gate_phase9a_auto.py`) proves reproducibility and
tamper detection at $0 with no internet. This proves the package is
something you would actually send a fabricator. Fifteen minutes.

```powershell
docker compose up --build -d
```

Open http://localhost:5173, **Assembly** tab.

---

## 1. Export is a deliberate action, not a side effect

- [ ] Before building an assembly, the **Build LUXEXCHANGE package** button
      is disabled.
- [ ] Press **Build assembly**, then the export button becomes available.
- [ ] Before exporting, the panel says no package has been built yet.

Opening a download link must never create data. If clicking a link builds
files and writes database rows, that is the defect Phase 9A fixed.

## 2. The format list is honest

Press **Build LUXEXCHANGE package**.

- [ ] STEP, BREP, STL, DXF, SVG, GLB, OBJ, PLY show **in package** with a
      size in kB.
- [ ] USD, USDZ, FBX, ABC show **unavailable**.
- [ ] DWG and SKP show **not possible**.
- [ ] DAE and 3MF show **unavailable** naming a missing Python package.
- [ ] Nothing is silently absent from the list.

## 3. The digest is shown and stable

- [ ] A **content digest** is displayed under the download links.
- [ ] Press **Build LUXEXCHANGE package** again.
- [ ] The digest is **exactly the same**.

## 4. The package verifies itself on a bare Python

Download the zip and extract it somewhere outside the repo — pretend you are
the fabricator.

```powershell
cd $env:USERPROFILE\Downloads\luxexchange
python verify_luxexchange.py
```

- [ ] It prints `LUXEXCHANGE VERIFICATION PASSED`.
- [ ] The content digest matches what the screen showed.
- [ ] It needed no pip install and no internet.

## 5. Tampering is caught

Open `exports/assembly.step` in Notepad, change one character in the middle
of the file, save. Run the verifier again.

- [ ] It prints `LUXEXCHANGE VERIFICATION FAILED`.
- [ ] It names `exports/assembly.step` as MODIFIED.

Delete `exports/assembly.stl` and run it again.

- [ ] It reports `MISSING exports/assembly.stl`.

Re-extract a clean copy before continuing.

## 6. The drawing is a real drawing

Open `exports/assembly.dxf` in any CAD viewer (LibreCAD, ODA Viewer,
AutoCAD, SketchUp Pro — all open DXF).

- [ ] There are **two views side by side**: a plan section on the left, a
      front elevation on the right.
- [ ] The layer list contains **PLAN**, **ELEVATION** and **HIDDEN**.
- [ ] Switching off HIDDEN removes the occluded lines from the elevation.
- [ ] The plan section shows wall thicknesses as closed profiles — this is a
      real cut through the piece, not an outline.
- [ ] Dimensions read in millimetres and match the design.

## 7. The CAD files open where they must

- [ ] `assembly.step` opens in your CAD program as a solid.
- [ ] `assembly.stl` opens in a slicer or mesh viewer.
- [ ] Open `README_DWG_SKP.txt` — it explains the DWG route and the
      SketchUp import route without needing this repository.

## 8. Nothing leaks

- [ ] Open `luxexchange_v1.json`. Every export `path` is relative
      (`exports/assembly.step`), never a `C:\Users\...` path.
- [ ] Open `provenance.json`. It carries tool versions — nothing private.

---

**PASS** = every box ticked. Any unticked box is a Phase 9A failure; record
it in `LIMITATIONS.md` and report it before closing the slice.
