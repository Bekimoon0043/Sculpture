# PHASE_12_BRIEF_INTAKE_POLISH_PLAN.md - L1 Brief Intake Product (2026-08-21)

Phase 12 turns the existing brief flow into a polished intake product for real
client projects.

## Current State

- Plain-language briefs can start Council sessions.
- The Design Spec schema captures key project data.
- The intake UI is not yet a complete guided product.
- Site, climate, culture, and budget normalization are partial.

## Build Scope

- Guided intake form for project type, site, dimensions, climate, culture,
  material preferences, water behavior, deadline, and budget.
- Plain-language brief parser that fills the form where possible.
- Missing-information prompts before Council spend begins.
- Climate normalization: city/country, outdoor/indoor, temperature band,
  dust/wind exposure, freeze risk, and water availability.
- Culture/context normalization: inspiration, local motifs, forbidden motifs,
  client brand tone, and public/private setting.
- Budget normalization: currency, range, contingency, transport/install split,
  and unknown budget handling.
- Intake summary preview before launching Council.

## Gate

Phase 12 closes when:

- A user can enter a plain-language brief and see a structured intake summary.
- Missing required fields are requested before paid provider calls.
- Site, climate, culture, and budget fields are present in the Design Spec.
- The Council receives the normalized intake, not only raw text.
- The UI remains honest when budget, climate, or site data is unknown.

---

## Design corrections — review 2026-08-21

### R1 — Phase 12 is a dependency of Phase 8, not a finishing touch

Phase 8's hydraulic gate is inert today because nothing populates water
context. Phase 8's structural gate cannot reach a real overturning check
without site wind exposure. Both are blocked on intake normalisation, which
this phase owns.

That makes the current ordering wrong in effect: Phase 12 sits last, but two
earlier gates cannot fully close without it. Resolution (mirrored in
`PHASE_8_VALIDATION_GATE_PLAN.md` Part 3): Phase 8 closes accepting
`needs_input` as a legitimate terminal status, and a short **Phase 8b re-gate**
runs after Phase 12 to prove the gates evaluate real numbers from a real brief.

The practical instruction: whenever Phase 12 is scheduled, treat it as
unblocking Phase 8b, not as cosmetic polish.

### R2 — Intake must emit typed contexts, not more free text

The three contexts the downstream gates need are schemas, not prose fields:

- `site_context_v1` — location, indoor/outdoor, exposure, wind band, freeze
  risk, ground bearing class, access constraints for delivery and craneage.
- `water_context_v1` — has_water, flow, operating depth, recirculation,
  water availability and quality, drain location. **This is the exact object
  Phase 8 C6 consumes.**
- `budget_context_v1` — currency, range, contingency, transport/install split.

Free-form dicts are what made Phase 8's hydraulic gate inert. Typed contexts
with explicit units (Rule 6) are the fix, and intake is where they are born.

### R3 — Every field carries its own provenance

Each normalised field records `source: operator | parsed | default | unknown`
and, when parsed, the brief sentence it came from. Two reasons: the operator
must be able to see what the parser inferred versus what he typed, and
`unknown` must stay distinguishable from `default` — a defaulted freeze risk
that nobody checked is not the same as a confirmed one, and Phase 8 will gate
on it.

`unknown` propagates to `needs_input` downstream. That chain is the honesty
guarantee, end to end.

### R4 — Parse before spend, and show the parse before confirming

The parser fills the form; the operator sees and corrects it; only then does
Council spend begin. The parse itself is a paid call and must be logged as
such (Rule 8), and it must be re-runnable without re-spending if the operator
edits and returns.

### R5 — Missing-field prompting must be ranked by downstream cost

Not all gaps are equal. Rank required fields by what they block:

1. blocks geometry — project type, overall dimensions, material
2. blocks a validation gate — site exposure, water context, ground class
3. blocks costing — budget, transport/install split
4. affects design only — culture cues, brand tone

The operator is asked for tier 1 and 2 before Council spend; tiers 3 and 4 may
proceed as `unknown` with the downstream consequence stated on screen
("costing will report `needs_input` for transport").

### Revised gate additions

- Intake emits `site_context_v1`, `water_context_v1`, `budget_context_v1`,
  each with per-field `source`.
- A brief that omits water produces `has_water: unknown`, and Phase 8's
  hydraulic gate reports `needs_input` naming the field — not `warn`.
- A fully specified brief drives the Phase 8 hydraulic gate to a real
  `pass`/`warn`/`fail` with derived values (this is the Phase 8b re-gate).
- Editing a parsed field and re-confirming spends no additional tokens.
- The intake summary distinguishes operator-entered, parsed, defaulted and
  unknown fields visually.
