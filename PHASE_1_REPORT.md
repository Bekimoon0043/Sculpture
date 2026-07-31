# PHASE_1_REPORT.md — LuxuryForm Studio v1, Phase 1

**Status: Phase 1 code COMPLETE and locally verified. The live 3-provider gate
verdict requires the operator's API keys (and Docker) on the operator's
machine — see "What the operator must run" below.**

---

## What was built

Exactly the Phase 1 scope from the Master Build Order §11 plus operator
Amendments 1–6:

- **Repository + packaging** — `pyproject.toml` with every dependency pinned
  `==` to a version verified to install from PyPI; Python 3.11; the `app`
  package under `backend/`.
- **Docker** — `Dockerfile` (python:3.11-slim), `docker-compose.yml` (single
  `backend` service; frontend arrives Phase 2), `.env.example`, ignore files.
- **Config system** — `core/config.py` loads and structurally validates
  `config/council.yaml` (role→provider map verbatim from the approved First
  Action §4, operator-editable model defaults), `config/pricing.yaml`
  (versioned, effective dates — ADR-006), `config/budget.yaml` (Amendment 2
  caps), `config/materials.yaml` (real starter set, units explicit).
  Malformed YAML fails loudly at startup; missing API keys warn and report
  "not configured" — key material is never logged.
- **Database** — SQLite WAL (`core/db/schema.sql` + `database.py`):
  Phase 1 tables `sessions`, `ai_calls`, `budget_events`, `jobs`, PLUS the
  full later-phase table set created now (approved plan §D3, ADR-001).
- **Core modules** — `core/units.py` (unit-safe `Quantity`, Rule 6),
  `core/seeds.py` (Amendment 1 determinism context + verbatim guarantee),
  `core/budget.py` (Amendment 2 `BudgetEnforcer`/`BudgetHalt`).
- **AI provider layer** — one ABC (`ai/provider.py`), three real providers
  (official `anthropic` and `openai` SDKs; Kimi via the `openai` SDK against
  Moonshot's OpenAI-compatible endpoint), 60 s timeouts, and the single
  logged dispatch path `ai/call_log.py`: estimate → cap check → dispatch →
  real token-cost math → full ai_calls row (Rule 8) → honest ProviderError on
  failure. No key → error before any network. No price entry → error, never a
  guessed price.
- **API** — `GET /api/health`, `GET /api/logs/calls`, `GET /api/logs/budget`,
  `GET /api/schema/design-spec`; `init_db()` on startup.
- **Design Spec schema** — `schemas/design_spec_v1.json`: the approved base
  schema + Amendment 3 (required `hydraulic_network`) + Amendment 4
  (`budget: {amount, currency, fx_date}` via `$defs/money`, replacing
  `budget_etb_max`) + `meta.spec_hash` (Amendment 1 unit of record).
- **Tests** — 36 offline tests (units, budget, pricing, call log, schema,
  all three providers via injected, hand-constructed SDK transports — mocks
  that pretend to be a provider's SDK client; see LIMITATIONS.md §7). All
  pass with NO API keys and NO network.
- **Gate** — `scripts/gate_phase1.py` (design below).
- **Docs** — README, DECISIONS (ADR-001…008), LIMITATIONS, operator guide.

## Gate design (scripts/gate_phase1.py)

Six numbered sections, exit 0 only on full PASS:

1. **CONFIG & DB** — settings, per-provider key status (never key material),
   pricing version, budget caps; initialises a FRESH throwaway DB at
   `data/gate_run.db` (deleted first) so the gate is repeatable.
2. **TEXT CALLS** — sends `Reply with the word LUXURYFORM and nothing else.`
   to each configured provider through the real dispatch path; prints model,
   response, tokens, latency, cost; then SELECTs the persisted `ai_calls`
   rows as proof of logging. Missing key →
   `FAIL — <provider>: not configured (set <ENV_VAR> in .env)`.
3. **VISION CALLS (Amendment 5)** — generates the deterministic 256×256 test
   image (seeded, Pillow) if absent; sends it with
   `Describe this image in one sentence. Include the dominant color.` to each
   provider's vision model; prints response, bytes/resolution accepted,
   tokens, cost. Failure → `FAIL — <provider> vision: <raw error>` plus the
   printed ACTION to record it in LIMITATIONS.md.
4. **SPEND-CAP PROOF (Amendment 2)** — offline, no network: a BudgetEnforcer
   with session cap $0.01, a synthetic $0.02 actual written into the gate DB,
   then `pre_dispatch_check($0.005)` — which MUST raise BudgetHalt. The halt
   reason and the persisted `budget_events` + `jobs(halted_budget)` rows are
   printed as proof. Also confirms `max_vision_iterations=6` is loaded and
   validated from `config/budget.yaml`.
5. **DETERMINISM STATEMENT (Amendment 1)** — the guarantee, verbatim, plus
   the explicit statement that no gate ever tests brief-level
   reproducibility.
6. **VERDICT** — `PHASE 1 GATE: PASS` (exit 0) only if all three providers
   pass text AND vision and sections 1–4 pass; otherwise
   `PHASE 1 GATE: FAIL — <exact reasons>` (exit 1).

## What the build sandbox could NOT prove (honest, per §13)

- **No API keys in the sandbox** → the live 3-provider text/vision calls
  could not be exercised here. What WAS proven locally instead: the complete
  dispatch path (estimate → cap check → dispatch → cost → logging) against
  injected hand-constructed SDK transports in the offline test suite — mocks,
  mirroring the SDK response shape as ASSUMED, not as verified — plus the
  honest missing-key FAIL path in the gate itself, and the full cap-halt
  machinery.
- **No Docker in the sandbox** → `docker compose up --build -d` could not be
  run here. The Dockerfile/compose file are static and simple, but the
  operator's machine performs the first real build.
- **Pricing values** are published list prices as of 2026-07 and are flagged
  in-file for operator verification (LIMITATIONS.md §4).

## What the operator must run (Windows, exact commands)

```bat
cd C:\luxuryform
copy .env.example .env
notepad .env
REM  paste ANTHROPIC_API_KEY, OPENAI_API_KEY, MOONSHOT_API_KEY, save, close
docker compose up --build -d
docker compose exec backend python scripts/gate_phase1.py
```

Expected cost per gate run: **$0.01–0.05**. Full walkthrough and the meaning
of every FAIL message: `docs/operator/01_starting_the_platform.md`.

## Verified locally (build sandbox, 2026-07-31)

- `pip install -e /mnt/agents/output/luxuryform[dev]` — clean install, all
  pinned versions exist on PyPI.
- `pytest tests -q` — **36 passed**.
- `python scripts/gate_phase1.py` with NO keys — **exit 1**, honest
  per-provider FAIL lines naming the exact env var to set, and a passing
  spend-cap-proof section. Transcript below, verbatim.

```
------------------------------------------------------------------------
[1/6] CONFIG & DB
------------------------------------------------------------------------
Provider key status (key material is never printed):
  anthropic  missing (set ANTHROPIC_API_KEY in .env)
  openai     missing (set OPENAI_API_KEY in .env)
  kimi       missing (set MOONSHOT_API_KEY in .env)
pricing_version: 2026-07-v1
budget caps: session_cap_usd=$5.00, day_cap_usd=$25.00, max_vision_iterations=6, on_breach=halt_and_report
gate DB: fresh /mnt/agents/output/luxuryform/data/gate_run.db (deleted first, schema applied) — WAL mode
PASS — section 1: config loaded, DB initialised

------------------------------------------------------------------------
[2/6] TEXT CALLS — 'Reply with the word LUXURYFORM and nothing else.'
------------------------------------------------------------------------
FAIL — anthropic: not configured (set ANTHROPIC_API_KEY in .env)
FAIL — openai: not configured (set OPENAI_API_KEY in .env)
FAIL — kimi: not configured (set MOONSHOT_API_KEY in .env)

ai_calls rows persisted for session gate-98f78c91-299b-4881-a898-0e06b96af2da (proof of log):
  (no rows — no provider calls were made)

------------------------------------------------------------------------
[3/6] VISION CALLS (Amendment 5)
------------------------------------------------------------------------
test image: /mnt/agents/output/luxuryform/scripts/assets/gate_test_image.png (2214 bytes, 256x256)
FAIL — anthropic vision: not configured (set ANTHROPIC_API_KEY in .env)
FAIL — openai vision: not configured (set OPENAI_API_KEY in .env)
FAIL — kimi vision: not configured (set MOONSHOT_API_KEY in .env)

------------------------------------------------------------------------
[4/6] SPEND-CAP PROOF (Amendment 2) — offline, no network
------------------------------------------------------------------------
max_vision_iterations=6 loaded and validated from config/budget.yaml (enforced in Phase 5)
synthetic spend recorded: $0.020000 against a session cap of $0.010000
BudgetHalt raised as required. Reason: session spend cap would be breached: spent $0.020000 + estimated $0.005000 > session cap $0.010000 — halting, state persisted (Amendment 2: halt_and_report)
persisted budget_events rows:
  id=2a26c3d1-5bea-4ee2-acf1-c933f53f4245 type=cap_breach detail={"attempted_estimate_usd": 0.005, "cap_kind": "session", "cap_usd": 0.01, "spent_usd": 0.02}
persisted jobs rows (halted state):
  id=def642e2-92a1-47aa-b314-8cdb390c8090 type=ai_dispatch status=halted_budget halt_reason=session spend cap would be breached: spent $0.020000 + estimated $0.005000 > session cap $0.010000 — halting, state persisted (Amendment 2: halt_and_report)
    state_json={"attempted_estimate_usd": 0.005, "cap_kind": "session", "day_cap_usd": 25.0, "halted_at": "2026-07-31T12:36:27.701248+00:00", "session_cap_usd": 0.01, "session_id": "gate-cap-proof-976623f5-c2b5-485b-84cc-da85d35673cb", "spent_session_usd": 0.02, "spent_today_usd": 0.02}
PASS — section 4: cap breach halted the run and persisted state

------------------------------------------------------------------------
[5/6] DETERMINISM STATEMENT (Amendment 1)
------------------------------------------------------------------------
"Identical Design Spec + identical seed + pinned Docker image = byte-identical canonical geometry (STEP + parameter set). Brief → Spec is non-deterministic by nature; every Spec is therefore persisted permanently as the reproducible unit of record."

This gate does NOT and will never test brief-level reproducibility; determinism starts at the persisted Design Spec.

------------------------------------------------------------------------
[6/6] VERDICT
------------------------------------------------------------------------
PHASE 1 GATE: FAIL — anthropic text: not configured (set ANTHROPIC_API_KEY in .env); openai text: not configured (set OPENAI_API_KEY in .env); kimi text: not configured (set MOONSHOT_API_KEY in .env); anthropic vision: not configured (set ANTHROPIC_API_KEY in .env); openai vision: not configured (set OPENAI_API_KEY in .env); kimi vision: not configured (set MOONSHOT_API_KEY in .env)

Note: provider FAILs above name the exact env var to set in .env. With all three keys set, re-run this script (expected API cost $0.01–0.05 per run).
```
