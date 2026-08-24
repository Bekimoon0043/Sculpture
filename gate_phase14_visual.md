# Phase 14 visual gate — Designer Workspace

The auto gate proves the backend (named-node scene, per-design reads, lazy
backfill, determinism) and that the frontend compiles. What only your eyes
can verify is that the workspace *behaves* like a design tool. Work through
this once; each step says exactly what you should see.

Setup (once):

```powershell
cd C:\Users\buroo\luxuryform
docker compose up --build -d
# the render step needs the render worker too:
docker compose --profile render up -d render-worker
```

Open http://localhost:5173 — the app opens on the **Designer** view.

## 1. Layout

- [ ] Left rail: **Library** (four primitive cards with line-art thumbnails)
      above **Scene** (element list). The thumbnails are schematic drawings,
      not renders — that is by design (LIMITATIONS.md §17).
- [ ] Centre: the 3D viewport.
- [ ] Right rail: **Inspector**, then **Checks** (validation), then
      **Export** — the same honest gate rows as before.
- [ ] Bottom: the history strip (empty until your first build, with a line
      saying so).
- [ ] Top bar: the pipeline stepper is unchanged; below it a toolbar with
      Undo/Redo · Duplicate · **Build & validate** · Render · Export ·
      Measure · Section · Frame · Views.

## 2. Build and select

- [ ] Press **Build & validate**. The three-element fountain appears;
      the Validate chip in the stepper shows the real verdict.
- [ ] Click the basin in the viewport → the scene row highlights and the
      Inspector shows `basin_01` with its parameters, ranges and units.
- [ ] Click empty space → selection clears.
- [ ] The selected element glows amber; the other elements do not.

## 3. Edit → dirty → rebuild

- [ ] Change `height_mm` on the basin and tab out. The toolbar shows
      **UNBUILT CHANGES** — the viewport deliberately still shows the last
      build (the kernel draws, never the browser).
- [ ] Press **Build & validate**; the geometry updates and the badge clears.
- [ ] Press Ctrl+Z twice / Ctrl+Y — the parameter value steps back and
      forward in the Inspector.

## 4. Add, duplicate, delete

- [ ] Click a Library card → the element appears in the Scene list marked
      "unbuilt — press Build", already jointed to a sensible parent.
- [ ] Select an element → **Duplicate**. A stack_on copy lands BESIDE its
      source (offset by the built width); building shows both.
- [ ] Select the copy → Delete key removes it; any child re-parents rather
      than orphaning.

## 5. Hide / solo / swatches

- [ ] The eye icon hides an element (viewport only — the document is
      untouched); solo (◎) shows only that element; pressing it again ends
      solo.
- [ ] In the Inspector, click a different material swatch: the element tints
      to the material's identification colour after the swatch is applied.
      Hover a swatch — the tooltip says the colour is identification only.

## 6. Measure and section

- [ ] Toolbar **Measure**, then click the basin rim on opposite sides: an
      amber line with a mm label appears. Sanity-check the number against
      the basin's `diameter_mm` (2000 mm default — expect within a few mm
      of it when clicking the outer rim at its widest).
- [ ] Esc exits measure mode and clears the line.
- [ ] Toolbar **Section**, axis Y, drag the slider: the model cuts open and
      the cut slides through it. Clicks through the removed half do NOT
      select hidden geometry. X and Z cut across the other axes.

## 7. Saved views

- [ ] Orbit somewhere distinctive → **+ view**, name it. Orbit away, pick
      the name in the **Views…** dropdown — the camera returns exactly.
- [ ] Reload the page: the saved view survives (it lives in this browser).

## 8. History and compare

- [ ] Every build added a card to the strip: thumbnail (a real screenshot
      of the viewport, taken when that geometry was on screen), time,
      verdict badge, mass.
- [ ] Click an older card: the document AND geometry restore to that
      variant; the Inspector shows its parameters; the stepper's design id
      changes.
- [ ] Tick **A/B** on two cards: the centre splits into two viewports, each
      orbitable, each captioned with its verdict and mass. Close compare
      returns to the working viewport.
- [ ] Reload the page: the strip still lists past builds (server truth);
      thumbnails persist for builds made on this machine.

## 9. Render (needs the render-worker container)

- [ ] With a built, unmodified design, press **Render**. The drawer reports
      progress honestly (elapsed seconds, what to check if nothing comes).
- [ ] When it finishes, four PNGs appear (front/side/top/three-quarter);
      clicking one opens it full size.
- [ ] With unbuilt changes, the Render button is disabled and its tooltip
      says to build first — it must never render something other than what
      you see.

## 10. The pipeline still stands

- [ ] Brief → confirm intake → the workspace's "site context" toggle shows
      the intake id; building with it produces real hydraulic/structural
      verdicts instead of NEEDS INPUT (as in Phase 8b).
- [ ] Export from the toolbar seals the package; the Export panel lists the
      tiers; Library accept still works from the Library view.
- [ ] The Cascade tool (top-right tab) still rebuilds and shows the legacy
      single-primitive flow.

If every box ticks, Phase 14 is visually closed. Anything that does not
match: screenshot it and report — a truthful failure beats a ticked box.
