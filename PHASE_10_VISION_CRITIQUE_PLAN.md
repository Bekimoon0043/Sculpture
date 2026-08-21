# PHASE_10_VISION_CRITIQUE_PLAN.md - L6 Vision Critique Loop (2026-08-21)

Phase 10 adds the closed render-to-critique-to-delta-to-resolve loop.

## Current State

- Provider vision capability was proven in Phase 1.
- `max_vision_iterations` is configured and validated.
- No render-to-vision critique loop exists yet.
- No bounded parameter delta schema exists yet.

## Build Scope

- Generate critique render set from the current assembly: front, side, plan,
  and perspective.
- Send the render set to the configured two-provider vision pair.
- Use Kimi only as the configured tiebreaker path when needed.
- Strict critique JSON schema:
  - visual issues.
  - severity.
  - confidence.
  - proposed parameter deltas.
  - stop reason.
  - provider metadata and cost.
- Delta clamp against primitive parameter ranges and fabrication limits.
- Re-solve geometry from accepted deltas.
- Re-run validation after every accepted delta.
- Persist every round: images, prompts, responses, deltas, validation report,
  and cost.

## Gate

Phase 10 closes when:

- A design completes one full critique round.
- Accepted deltas re-solve the assembly and trigger validation again.
- Invalid vision deltas are rejected before geometry execution.
- The loop stops at `max_vision_iterations` or earlier with a clear reason.
- The UI shows critique history and accepted/rejected deltas.

---

## Design corrections — review 2026-08-21

### R1 — The loop is only as good as the framing, and framing is a Phase 9 dependency

Critique renders must be a **pure function of geometry** (Phase 9B.3). If the
camera drifts between rounds, round N+1 is a different photograph of a
different framing, and every reported "improvement" is noise. Phase 10 must
not start before 9B.3 lands deterministic framing.

Consequence: the loop compares **round N vs round N+1 images**, and the
critique prompt is given both. Judging a single image in isolation cannot tell
the model whether the last delta helped.

### R2 — Vision cannot judge proportion without a scale reference

A model shown an untextured grey fountain has no way to know whether a basin
is 400 mm or 4 m deep, so "the basin looks shallow" is a guess. Every critique
render carries a ground grid at a known module and the overall height printed
in-frame (Phase 9B.3). Without this, Phase 10 produces confident nonsense —
which is worse than producing nothing.

### R3 — The delta schema must name the parameter path, not describe it

Deltas are `{element_id, parameter, from, to}` resolved against the **live
registry** `PARAMETERS` ranges and the material envelope, not free text. A
delta naming an unknown element or parameter is rejected before clamping, with
the rejection persisted. Vision output never reaches a code path that can
execute; it only ever proposes numbers that the registry then validates. This
is the ADR-005 boundary restated for L6.

### R4 — Clamping must be visible, not silent

Three outcomes per delta, all persisted and all shown in the UI:
`accepted` / `clamped` (with the original and the clamped value) /
`rejected` (with the reason). A silently clamped delta makes the next round's
critique incoherent, because the model is told its change was applied when it
was not.

### R5 — Every round must re-run Phase 8 gates, and a gate regression aborts

A delta that improves appearance and breaks the overturning or fabrication
gate is not an improvement. The loop's stop conditions become:
`max_vision_iterations` reached, both providers report no issues above
threshold, providers disagree past the tiebreaker, no delta survives clamping,
or **a validation gate regressed** — that last one reverts to the previous
accepted geometry.

### R6 — Cost ceiling belongs in the loop, not in a report afterwards

Each round is two vision calls plus renders. The loop takes a per-run cost
ceiling and stops on it with `stop_reason: budget`, before the call, not after.
Rule 8 already requires every call be logged; this makes the budget binding.

### R7 — Consensus needs a defined rule, not "two providers"

Define it explicitly: an issue counts only if both providers raise it above a
confidence threshold; a delta is applied only if both propose the same
parameter in the same direction; disagreement escalates to the configured
tiebreaker exactly once, and its cost is logged as part of the round.

### Revised gate additions

- Two consecutive rounds produce byte-identical camera framing metadata.
- A delta outside registry range is recorded `clamped` with both values shown.
- A delta naming an unknown parameter is recorded `rejected` and never reaches
  geometry.
- A round that regresses a Phase 8 gate reverts and stops with the gate named.
- A run that hits the cost ceiling stops with `stop_reason: budget` and the
  logged spend matches `ai_calls`.
