"""The AI Council (Phase 3).

Six roles, multi-provider, per PHASE_3_PLAN.md (operator-approved
2026-08-04). Two entry points live here:

- ``replay`` -- fixture-mode replay: persists a captured Council session
  from tests/fixtures/ into the database with ZERO provider calls ($0).
  This is how the offline gate and all development run.
- (build step 2) ``orchestrator`` -- the live Council: role sequence,
  parallel pairs, dynamic critic rule, schema validation with bounded
  re-ask, Arbiter binding + distinctness enforcement. Every provider
  detail in the orchestrator is ADR-009 live-fetched, never recalled.
"""
