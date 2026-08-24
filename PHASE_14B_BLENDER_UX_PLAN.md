# Phase 14b — window audit + Blender-familiar controls

**Directive** (operator, 2026-08-24): "check every window design, then make
them easy to use for designers, like Blender."

## The audit (code-level UX review — pixels remain the visual gate's job)

| Window | Finding | Action |
|---|---|---|
| Toolbar | Actions exist but shortcuts are undiscoverable; tooltips lack key hints | Add shortcut to every tooltip; add a keymap overlay (`?`) |
| Viewport | Orbit is LMB-only (three.js default); Blender hands expect MMB orbit + Shift+MMB pan; no view snapping; no ortho; no frame-selected; no navigation gizmo; no on-screen hint of what the mouse does | MMB orbit, Shift+MMB pan, 1/3/7 view keys (+Shift for opposites), 5 ortho/persp, `.` frame selected / Home frame all, clickable axis gizmo, persistent mouse-hint line |
| Library (left) | Fine, but cannot be dismissed on a small laptop screen | `T` toggles the left rail (Blender T-panel), persisted |
| Scene list | Selection/hide/solo good; no rename — Blender users rename in the outliner constantly | Double-click (or F2) inline rename; joints re-point automatically |
| Inspector (right) | Content good; cannot be dismissed | `N` toggles the right rail (Blender N-panel), persisted |
| History strip | Good; cards already restore/compare | Tooltip polish only |
| Compare view | Read-only panes are correct | No change |
| Render drawer | Honest progress; fine | No change |
| Other views (Brief/Council/Library/Ops/Cascade) | Pipeline forms, not modelling windows — Blender conventions do not apply | No change this phase |

## Keymap (Blender-derived, laptop-safe — top-row digits, not numpad-only)

- `1 / 3 / 7` front / right / top; `Shift+1 / 3 / 7` back / left / bottom
- `5` orthographic ⇄ perspective
- `.` frame selected, `Home` frame all
- `Shift+D` duplicate, `H` hide selected, `Alt+H` unhide all, `/` solo
- `X` or `Delete` delete selected; `Esc` deselect / exit mode
- `F2` rename selected; `T` / `N` toggle rails; `?` keymap overlay
- Mouse: LMB select, LMB-drag or MMB orbit, Shift+MMB pan, wheel zoom
- Ctrl+digit is browser-reserved (tab switching) — Shift variants instead.

## Not Blender, on purpose (goes in LIMITATIONS)

- No G/R/S transforms: the placement model is joints + translation — there
  is nothing free-form to grab or rotate (LIMITATIONS §18).
- No box/multi-select: the document model selects one element.
- No command palette (F3) yet.

## Gate

UI-only phase: `gate_phase14_auto.py --frontend-only` must pass;
`gate_phase14b_visual.md` gives the operator a keystroke-by-keystroke
check. No backend files change, so the container suite is unaffected.
