# PHASE_3_PLAN.md — The AI Council (2026-08-04)

**STATUS (updated 2026-08-07):** plan APPROVED by the operator 2026-08-04.
Build steps (§9): **step 1 DONE** (schema v3 + fixture replay pipeline +
costing rates schema — commit 457e6e0); **step 2 DONE** (Council
orchestrator, offline-proven with scripted dispatcher — commit 7539788);
steps 3–5 pending. ADR-009 pre-code fetches executed 2026-08-07 (ADR-021);
account-level checks (models.list ×3, live kimi text shape) returned by the
operator 2026-08-07 — LIMITATIONS §7 RETIRED. Cache-aware pricing landed
2026-08-07 (ADR-022): kimi/anthropic cache token classes split and priced
at first-party rates, `pricing_version` bumped to 2026-08-v3, offline
transports updated to the live-verified usage shapes. First live
session spend (~$1–2.50) PRE-APPROVED by the operator; measured cost will
be reported against the §7 estimate (≈$1.15, likely lower with cache hits).

Scope per the master build order: all six Council agents, multi-provider,
Design Spec JSON schema, Arbiter decision record, full transcript UI.

**GATE (verbatim):** a plain-language brief produces three distinct Design
Specs, an engineering review, a defect list, and a binding Arbiter decision
with a confidence score — all persisted and viewable.

Standing constraints acknowledged: single operator — NO auth, roles, or
multi-user hooks anywhere. ADR-009: no provider API detail from training
recall — every provider surface is re-verified against live docs before
implementation (fetch list in §8). Cost control: $5/session, $25/day hard
caps (config/budget.yaml, enforced pre-dispatch by the Phase 1
BudgetEnforcer — proven to halt and persist in the Phase 1 gate).

---

## 1. Session flow

```
plain-language brief
  └─ RESEARCHER   (kimi ‖ openai)        → context brief (site, precedent,
  └─ DESIGNER     (anthropic ‖ openai)     materials, hydraulics basics)
       3 alternatives per provider       → 6 raw Design Spec candidates
  └─ GEOMETRIST   (anthropic ‖ kimi)     → feasibility pass per candidate
  └─ ENGINEER     (openai ‖ anthropic)   → engineering review (structure,
  └─ CRITIC       (openai ‖ kimi)          hydraulics, fabrication)
       dynamic rule: NEVER the provider  → defect list with real numbers
       that produced the design under
       review (resolved per session)
  └─ ARBITER      (openai ‖ anthropic)   → BINDING decision: winning 3
                                           distinct specs, ranked, with
                                           confidence + disagreement register
```

Provider pairs are the static defaults from config/council.yaml (approved
First Action §4) — changeable in one line by the operator. Decision-critical
roles run on two providers in parallel; material disagreement is surfaced
in the Arbiter record, never averaged away.

**Why 6 candidates → 3 outputs:** each designer provider produces
alternatives 1–3 (the schema's `meta.alternative_no` exists for exactly
this). The Arbiter selects the final three DISTINCT specs (distinctness =
pairwise spec_hash inequality + a stated-differences summary, not near-
duplicates), ranks them, and binds rank 1. Downstream phases consume only
the Arbiter record.

## 2. What already exists (Phase 3 builds ON it, not beside it)

- `schemas/design_spec_v1.json` — the Council→Geometry contract, already
  amended (Amendments 1/3/4): `meta.spec_hash`, `meta.provider` enum,
  `alternative_no` 1–3, hydraulic_network, currency-aware budget,
  confidence + assumptions required. Phase 3 makes the Council PRODUCE and
  VALIDATE against this schema (jsonschema, already a pinned dep).
- `backend/app/ai/` — provider layer (anthropic/openai/kimi), call_log
  (every call persisted with tokens/latency/cost/pricing_version),
  BudgetEnforcer (caps halt pre-dispatch).
- `config/council.yaml` (roles/pairs/endpoints/models), `pricing.yaml`
  (versioned prices), `budget.yaml` (caps), schema_migrations framework
  (Phase 2 v2).

## 3. New persistence — schema v3 (migration, Phase-2 DBs renamed-backup, never deleted)

- `council_sessions` — id, brief, status, started/ended, total_cost_usd,
  pricing_version, arbiter_confidence.
- `council_calls` (or ai_calls extended) — + session_id, role, side
  (primary/parallel). Per-role cost measurement (§7) rides on this.
- `design_specs` — session_id, provider, alternative_no, spec_json,
  spec_hash, schema_valid.
- `engineering_reviews`, `defect_lists` — session_id, provider, payload_json.
- `arbiter_decisions` — session_id, chosen spec_ids (ranked 3), confidence,
  rationale, disagreement_register, binding=1.

## 4. Transcript UI (frontend)

- Session list (new) + session view: timeline by role; each role shows
  primary ‖ parallel outputs side by side with per-call cost/latency
  badges; disagreements highlighted; three spec cards (schema-valid badge,
  spec_hash, stated differences); engineering review and defect list
  panels; Arbiter decision card (winner, confidence, rationale,
  disagreement register); running session cost vs the $5 cap, live.
- Entry point: a "New Council session" box (plain-language brief in).

## 5. Split gate (as in Phase 2)

- `scripts/gate_phase3_auto.py`, two modes:
  - **Fixture mode (default, $0):** replays a recorded real session
    (`tests/fixtures/council_session_v1.json`, captured from the first live
    run) through schema validation → persistence → Arbiter binding → API.
    Proves the whole pipeline offline, forever, in CI-style runs.
  - **Live mode (`--live`, operator-approved spend):** one full real
    session; asserts 3 distinct schema-valid specs, engineering review,
    defect list, binding Arbiter decision with confidence, per-role costs
    logged, caps respected. Prints the per-role cost table (§7).
- `docs/operator/gate_phase3_visual.md`: run a brief in the UI; verify the
  transcript, three spec cards, review, defects, decision card with
  confidence, and the cost panel — eye-check checklist like Phase 2.

## 6. COSTING (operator amendment — schema designed NOW)

New `config/costing.yaml` (versioned like pricing.yaml; units in every
field name per Rule 6; per-entry currency). v1 schema:

```yaml
costing_version: "2026-08-v1"
meta: { default_currency: USD, notes: "operator-provided rates, Addis Ababa 2026" }
materials:
  <material_id>:                       # must match materials.yaml ids
    buy_price: { amount: null, currency: ETB, per: kg }        # per: kg|m3|sheet|slab
    waste_factor_pct: null
    fabrication:
      method: null                     # cnc_mill|hand_carve|cast|sheet_fabricate
      labor: { amount: null, currency: ETB, per: hour }
      machine: { amount: null, currency: ETB, per: hour }      # null if hand work
      hours_per_m3: null
      mold_pattern: { amount: null, currency: ETB, per: piece } # cast only; null else
    finishing: { amount: null, currency: ETB, per: m2 }        # polish/patina/seal
workshop:
  overhead_pct: null                   # power, consumables, space
install:
  crew_day_rate: { amount: null, currency: ETB, per: crew_day }
  crew_size: null
  days_per_tonne: null
  crane_day_rate: { amount: null, currency: ETB, per: day }    # null if none
  transport: { amount: null, currency: ETB, per: trip }
contingency_pct: null
markup_pct: null
```

**Rate data needed from the operator, and in what format:** the template
above with real numbers replacing the nulls. Specifically: (a) buy price +
unit for each of the four library materials (bronze per kg; basalt per
slab or m3; 316L sheet per sheet or kg; C35/45 per m3); (b) waste/yield
% per material; (c) who fabricates — in-house workshop or subcontract —
and the real hourly or day rates (mason/carver, metalworker, CNC
operator); (d) mold/pattern cost model for cast bronze (per-piece pattern
cost, mold amortization); (e) finishing per m² (polish, patina, sealant);
(f) install: crew day rate, crew size, crane if any, transport per trip;
(g) overhead/contingency/markup policy %. Ballparks are fine for v1 — the
schema versions every figure, and every cost report prints the
costing_version that computed it (same anti-stale-data rule as
pricing.yaml). FX: keep entries in the currency you actually pay in; one
`fx_rates` block (ETB→USD, dated) converts for USD-normalized reporting.

## 7. Cost control + per-role measurement

**Expected cost of one full Council session — ESTIMATE, before any live
run.** Basis: pricing.yaml rates (anthropic $3/$15, openai $2.50/$10,
kimi-k3 $3/$15 per 1M in/out — verify-live caveats apply) + Phase 1
measured behavior (kimi-k3 always reasons: ~6.3x anthropic per equivalent
text call, live gate 2026-08-01). Assumed shape: 16 calls (2 researcher +
6 designer + 2 geometrist + 2 engineer + 2 critic + 2 arbiter); average
~6k input tokens (later roles read the accumulated transcript), ~2.3k
output, kimi outputs ~4–6x from reasoning.

| role | providers | est. cost |
|---|---|---|
| researcher | kimi + openai | $0.18 |
| designer (×3 alternatives) | anthropic + openai | $0.29 |
| geometrist | anthropic + kimi | $0.23 |
| engineer | openai + anthropic | $0.13 |
| critic | openai + kimi | $0.20 |
| arbiter | openai + anthropic | $0.14 |
| **session total** | 16 calls | **≈ $1.15** |

Range: ~$0.60 (tight outputs) to ~$2.50 (long contexts, long K3
reasoning). Inside the $5 session cap with ~4x headroom; the $25 day cap
admits ~8–20 sessions. The BudgetEnforcer pre-dispatch-checks every call
against BOTH caps regardless — an estimate being wrong cannot produce a
surprise bill; it can only halt.

**Per-role cost measurement (operator requirement #5):** council_calls
records role + provider + side + tokens + cost + pricing_version per call.
The live gate prints the measured per-role × provider table (cost,
latency, output tokens). Reassignment recommendation comes FROM THAT
DATA — preliminary hypothesis only, from Phase 1: kimi-k3 is ~6x
anthropic per equivalent text call; if Phase 3 measurements confirm it
per role, the likely move is researcher primary kimi→openai (kimi
demoted to parallel/tiebreaker duties). No role changes before the data.

## 8. ADR-009 live-fetch list (before ANY provider-touching code)

1. anthropic: current Messages API shape + model availability on the
   operator account (docs.anthropic.com, fetched + date recorded).
2. openai: current chat/responses API shape + gpt-4o availability.
3. kimi: chat docs re-fetch (K3 fixed-parameter rules re-verified).
4. All three pricing pages → verify pricing.yaml, bump pricing_version
   if any number moved.
5. `models.list()` per provider from the operator's keys (availability is
   account-specific — the 2026-07-31 kimi list proved this matters).
Every fetch date recorded in DECISIONS.md.

## 9. Build order

1. Schema v3 migration + fixture-mode replay pipeline (offline-provable
   first: zero spend to develop against).
2. Council orchestrator: role sequence, parallel pairs, dynamic critic
   rule, schema validation with retry-on-invalid (bounded), Arbiter
   binding + distinctness enforcement.
3. Transcript UI + cost panel.
4. First live session (operator-approved, ≈$1–2.50) → fixture captured.
5. gate_phase3_auto.py (both modes) + gate_phase3_visual.md; per-role
   cost table printed; reassignment recommendation from measured data.

## 10. Risks

- **Provider JSON compliance** — the Designer must emit schema-valid
  JSON. Mitigation: schema in prompt + jsonschema validation + ONE
  bounded re-ask with the validation errors attached; failure is loud
  and persisted, never silent.
- **kimi-k3 reasoning token inflation** — measured per role (§7); caps
  bound the worst case.
- **Transcript context growth** — later roles read everything; the
  $2.50 high estimate assumes it. If exceeded, summarize researcher/
  geometrist outputs into the Arbiter context (recorded as a deviation).
- **Stale rates** — costing.yaml + pricing.yaml both versioned; every
  report prints the versions it used.
