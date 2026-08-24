# PHASE_3_REPORT.md — The AI Council (CLOSED 2026-08-07)

Phase 3 built the six-agent AI Council: brief → researcher, 3 designer
alternatives × 2 providers, geometrist, engineer, critic (dynamic rule:
never a producer provider), and a binding Arbiter decision — every call
logged with real tokens and real cost, hard-capped before every dispatch.

## PHASE 3 GATE: PASS (auto, fixture mode, $0 - 2026-08-07)

## Gate result

- **Auto gate** (`scripts/gate_phase3_auto.py`, fixture mode, $0): PASS
  2026-08-07 — config with cache-class prices, fixture replay (3/3
  schema-valid specs, recomputed costs, arbiter confidence 0.78),
  transcript API (demo-session idempotent, prefix resolution, 404s), cost
  rollup reconciliation. `--live` mode re-verifies the live path on demand.
- **Visual gate** (`docs/operator/gate_phase3_visual.md`): operator
  checklist against the Council UI.
- **First live session** (operator-run, 2026-08-07): COMPLETED,
  session 32e1c68f…, 17 calls, **measured cost $0.843842** against the
  $1.15 estimate (estimate was conservative; the model held).

Measured cost rollup, verbatim from the operator:

```
total_cost_usd: 0.843842   call_count: 17   pricing 2026-08-v3
by_role:     researcher 0.052389  designer 0.487861  geometrist 0.097887
             engineer 0.040931   critic 0.127566    arbiter 0.037208
by_provider: kimi 0.252440  openai 0.106641  anthropic 0.484761
cache_savings_usd: 0.000690
```

## What was built (5 build steps)

1. **Schema v3 + fixture replay** — council_sessions / council_calls /
   design_specs / engineering_reviews / defect_lists / arbiter_decisions;
   $0 replay pipeline (schema-validates specs, recomputes costs from
   tokens × pricing, enforces Arbiter invariants, tamper-evident canonical
   hashes); costing rates schema (config/costing.yaml — operator fills).
2. **Orchestrator** — dispatcher protocol, bounded re-ask (3), dynamic
   critic rule, Arbiter invariants in code, BudgetHalt → halted_budget.
3. **Transcript UI** — session list, per-call role cards (provider, tokens
   incl. cache split, cost, latency, full prompt/response), Arbiter
   decision card, cost panel vs $5/$25 caps; synthetic demo session.
4. **Live machinery** — POST /api/council/sessions (budget enforcer pinned
   to the real session id), capture_council_fixture.py, operator
   walkthrough with cmd + PowerShell variants.
5. **Split gate** — gate_phase3_auto.py (fixture $0 / --live) +
   gate_phase3_visual.md.

## Incidents and what they changed

- **First live attempt failed, $0 spent** (2026-08-07): a stale earlier-v3
  database file crashed mid-session (schema.sql edits never alter existing
  files), and a single kimi timeout aborted the session — the 220 s
  "timeout" was 3 hidden SDK-internal retries. **ADR-023**: startup
  additive schema patches + loud drift guard; audited retries
  (SDK-internal retries disabled, 3 attempts, 10→30 s backoff, 300 s
  per-attempt timeout, all env-tunable); failed non-critical calls now
  degrade the session instead of aborting (Arbiter and BudgetHalt never
  degrade).
- **Cache savings were ~zero in the live session** ($0.00069). Diagnosis:
  anthropic caches NOTHING without explicit cache_control markers (we sent
  none); kimi/openai automatic prefix caching needs byte-identical long
  prefixes, and our prompts were role-specific from the first word.
  **ADR-024**: prompts restructured static-prefix-first with a cache-break
  sentinel; the anthropic provider splits on it and marks the prefix
  cache_control=ephemeral (first-party docs fetched 2026-08-07). The
  designer prefix (schema ≈2.9k tokens) clears the ~1024-token minimum.
  Engagement will be MEASURED via the persisted cache token fields on the
  next live session.
- **Doc contradictions found by the Hub sync tooling** (Claude Code):
  LIMITATIONS.md §5 and PHASE_1_REPORT.md §7 overstated/stale states —
  fixed with visible correction history; docs are machine-read, so closed
  items move OUT of not-built lists.

## Known scope limits (carried in LIMITATIONS.md)

- ~~The static designer pair (anthropic‖openai) leaves only kimi eligible
  for the critic under the dynamic rule → sessions are degraded=1 by
  construction~~ — CORRECTED 2026-08-09 (ADR-025): that semantics made the
  badge meaningless (the operator's first live session flagged degraded
  with ZERO failed calls — it was the by-design critic exclusion). The
  flags are now split: **degraded** = a provider FAILURE left a seat
  empty/reduced; **corrected** = a bounded re-ask succeeded. The critic's
  producer exclusion is the rule working — informational, unflagged.
- The geometrist's Phase 3 output is prose feasibility notes; it WRITES
  code only from Phase 4.
- Designer spend is 58% of a session ($0.4879 of $0.8438). Options priced
  from measured data are recorded in DECISIONS.md; the operator decides
  before Phase 5 multiplies sessions.

Phase 3 is CLOSED. Next: Phase 4 — the geometrist writes parametric
build123d code from a Design Spec, executed in the ADR-005 sandbox, with
bounded automatic repair.
