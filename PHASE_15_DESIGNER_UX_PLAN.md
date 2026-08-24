# Phase 15 - Designer UX correction

**Approved by the operator: 2026-08-24.**

Phase 14 proved the workspace functions, but its permanent library, stacked
Inspector/Validation/Export rail, crowded toolbar and unscoped "variants"
strip gave every capability equal visual weight. Phase 15 makes the design
loop primary without weakening the deterministic CAD and validation contracts.

## Slices

1. **A - workspace hierarchy:** dominant viewport, compact icon command bar,
   Scene-first rail, Add palette, tabbed Design/Checks/Output rail, collapsible
   Recent Builds tray. Frontend only.
2. **B - designer controls:** semantic parameter groups and labels, concise
   validation summary, simplified output hierarchy, full registry access under
   Advanced.
3. **C - kernel draft preview:** same assembly request and CAD kernel, no
   persistence or gate claims, debounced with stale-request cancellation.
4. **D - visual judgement:** Studio/Technical viewport modes, scale and ground
   cues, actual primitive previews, parameter-aware A/B comparison.
5. **E - project lineage:** additive projects table plus nullable project and
   parent design references; old designs remain ungrouped.

Each slice receives its own gate and commit. Canonical STEP bytes, full-build
validation and export behavior must remain unchanged.

## Risks held explicitly

- Draft generation is CPU work on an i7 laptop: debounce, one active request,
  stale-response rejection and content reuse are required.
- Preview pixels must come from the real geometry kernel. No browser-generated
  approximation is allowed.
- Project migration is additive. Existing rows and artifacts are never
  rewritten or reassigned silently.
- Material identification colors remain non-photoreal and labelled as such.

