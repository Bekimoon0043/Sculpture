# Phase 14b visual gate — window audit + Blender-familiar controls

Follows `gate_phase14_visual.md` (do that one first if you haven't). This
gate checks the Blender-style layer added on top. Open the Designer view
with at least one built design.

## 1. Discoverability

- [ ] Press `?` (or click **⌨ Keys** top right of the toolbar): a keymap
      card opens listing views, mouse, edit, show and panel keys. `Esc` or
      clicking outside closes it.
- [ ] Hover any toolbar button: the tooltip names its shortcut
      (e.g. Duplicate — "Shift+D").
- [ ] Bottom-left of the viewport shows a quiet mouse-hint line; entering
      Measure mode changes it to the measure instructions.

## 2. Viewport navigation, Blender hands

- [ ] Middle-mouse drag orbits; Shift+middle-drag pans; right-drag pans;
      wheel zooms. Left-drag still orbits (browser habit kept).
- [ ] `1` front, `3` right, `7` top; with `Shift` back / left / bottom.
      The model stays the same apparent size when snapping.
- [ ] `5` toggles orthographic — the toolbar button flips to "Ortho", the
      model keeps its size, and parallel edges stop converging (check
      against the column). `5` again returns to perspective.
- [ ] Top-right axis gizmo: coloured dots orbit as you orbit; clicking the
      X / Y / Z dots snaps to right / top / front; the small hollow dots
      snap to the opposites.
- [ ] Select the basin, press `.` — the camera frames just the basin
      WITHOUT changing your viewing angle. `Home` frames everything.

## 3. Outliner-style editing

- [ ] Double-click an element name in the Scene list (or select it and
      press `F2`): an inline rename field opens. Rename `basin_01` to
      `main_basin`, Enter. The list, the inspector header, and the child
      column's joint line ("into main_basin") all update; the renamed
      element shows "unbuilt — press Build" (its geometry node still
      carries the old name until rebuilt) — build and selection works
      against the new name.
- [ ] Renaming to an already-taken or empty name does nothing (no
      corruption, no error dialog — the edit simply doesn't apply).
- [ ] With an element selected: `Shift+D` duplicates beside it, `H` hides
      it, `Alt+H` unhides everything, `/` solos it and `/` again ends the
      solo, `X` deletes it.

## 4. Panels

- [ ] `T` collapses the left rail (library + scene); the viewport takes
      the space. `T` restores it. `N` does the same for the right rail.
- [ ] Reload the page: the rails come back the way you left them.
- [ ] Keys do nothing while you are typing in a parameter field, and
      nothing while you are on the Brief / Council / Ops views.

If every box ticks, 14b is visually closed. Mismatches: screenshot and
report.
