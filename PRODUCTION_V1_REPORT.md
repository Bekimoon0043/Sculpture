# PRODUCTION_V1_REPORT.md — the closure program, one section per slice

The Production v1 closure program was approved by the operator on
2026-08-27: slices PR-0 → PR-3 → PR-1 → PR-2 → PR-4 → PR-5 → PR-6 →
PR-7A/7B/7C → PR-8 → PR-9, with seven binding amendments (cap semantics,
historical-scalar-limit provenance, transport wording, mixed-material
measurement paths, the PR-7 three-way split, immutable issuance snapshots,
and positive/negative acceptance cases). The approval transcript lives in
the operator's session of that date; NEXT.md §2 carries the queue.

**Amended by the owner's roadmap ruling of 2026-08-28 (ADR-060):**
free-form amorphous sculpture is a release-blocking Production v1
capability. The sequence after PR-2 is PR-2 close → PR-2.5 (free-form
discovery/acceptance plan, then approved implementation slice(s),
free-form gates and close) → PR-4; **PR-4 waits for the BUILT free-form
capability, not the approved plan.** PR-9's final acceptance gate gains a
mandatory FOURTH positive end-to-end project: a genuinely amorphous
sculpture (fixture and manufacturing route determined by PR-2.5). New
operator input blocker B-11 records the ground truth this needs
(reference designs, materials/processes, sculpting-controls ruling).

This report accumulates one section per closed slice, newest first, with
verbatim gate evidence — the same contract as the phase reports.

---

## PR-4 — transport trips are LOADED, never bounded (CLOSED 2026-09-08, ADR-067: auto gate PASS + operator visual gate PASS 2026-09-07)

`scripts/gate_pr4_auto.py` — 9 sections, exit 0, $0, offline, no AI call,
no database, and `config/costing.yaml` proven sha256-identical before and
after every run. Operator visual gate `gate_pr4_visual.md` SIGNED
2026-09-07 (all four steps YES, recorded verbatim in that file).

### What it makes true

The transport line no longer prints
`max(ceil(mass/payload), ceil(modules/per_trip))` — a LOWER BOUND — as
if it were a trip count. It loads the trucks: first-fit-decreasing over
the measured per-module masses, heaviest first, ties by module id, each
module on the first trip with room under BOTH the payload and the bed
count, every comparison unrounded. Amendment 3's wording is enforced at
the source and re-checked by the gate: **"a deterministic conservative
feasible allocation"**, never minimal or optimal.

### The disproof that retired the old formula

Four modules of 6,000 kg at a 10,000 kg payload, 4 per bed:

```
  4 modules x 6,000 kg, payload 10,000 kg, 4 per bed
  retired lower-bound arithmetic : 3 trips
  loaded trucks (this slice)     : 4 trips
  ok   the loaded count beats the bound -- 4 vs 3
```

Three trucks cannot legally carry four 6 t modules at 10 t each. The
bound understated the count, and an understated truck count understates
the quote and puts an illegal load on the road.

### The FAIL this slice produced, and the approved recovery

The first definitive chain (2026-09-07T10:55:10Z) FAILED at
`gate_ffa1_auto.py`, stage 1, gate 22 of 25 — the ADR-065 mass-consumer
census refusing PR-4's new `app.costing.transport` module. **D-10
instance seven**, preserved verbatim in DECISIONS.md with the audit:
the allocator is pure arithmetic over `(id, mass)` pairs, opens no
manifest/report/database, and **incomplete mass is refused UPSTREAM of
allocation** by `drivers_for_assembly`'s `IncompleteMassError` (proven
by `gate_pr4_auto` §7e and `gate_ffa1_auto` §2), so an incomplete figure
can never reach it. The operator ruled the correction as THREE EXACT
SYMBOLS rather than a module wildcard, and approved a hash-proven
recovery protocol instead of repeating the full two-hour chain.

### Evidence: what was REUSED and what was RE-RUN

Reported separately and honestly, as the operator required.

**REUSED from the first chain (production and test bytes proven
unchanged by the correction):**

| Evidence | Value |
|---|---|
| Full suite, render-worker REMOVED | **707 passed, 3 warnings in 3158.46s (0:52:38)**, exit 0 |
| Worker state during that run | pinned absent (`rm -sf`), verified at start |
| Rebuild + image pin (first chain) | `c654d8d4090c…`; `gate_pr4_auto.py` host==container `5902ff083c19` |

The reuse is justified by a hash proof recorded before and after the
correction: `backend/app` (all .py) `5954d543c23d…`, `frontend/src`
`2a4fe1223798…`, `tests` `2eda2350122c…`, `config` `8208c6205e21…`,
`schemas` `32cc259779ae…`, plus `pyproject.toml`, `docker-compose.yml`,
all five Dockerfiles, `.dockerignore`, `package.json` and
`package-lock.json` — **all 15 distinct entries identical**. The ONLY
changed file is `scripts/gate_ffa1_auto.py`
(`f56afbc40817…` → `7aff70d6d53e…`), which the suite does not execute.

**RE-RUN on the final corrected image (new evidence)** — final image
`a8a6f3218ba849e0…`, identical at stage A start (2026-09-07T12:11:51Z)
and at chain end (2026-09-08T07:19:58Z); corrected `gate_ffa1_auto.py`
host==container `7aff70d6d53e`:

| Evidence | Value |
|---|---|
| Corrected FF-A1 gate (roster position 22, DB quiesced) | **PASS 36/36**, census `31 consumer symbols found, all listed (allowlist entries: 32)`, §6 `79 all-legacy, 1 non-legacy`, §8 DB `c27774d8dfaf` both ends |
| Stage A in-container roster, worker REMOVED (verified absent at start and end) | all 25 exit 0: phase2/3/4/5/6a1/6a2/6b/6c/6c2, costing, 8/8b/9a/11/13a/14/15, pr1, pr2, lf103a, pr25_discovery, ffa1, **ffa2**, **pr4**, **pr3 static (stdin)** |
| Full suite, render-worker **UP** (pinned `Up 1 second` at start → `Up 56 minutes` at end) | **707 passed, 3 warnings in 3317.11s (0:55:17)**, exit 0 |
| `gate_phase9b_auto` (worker up) | exit 0 |
| Host gates | `gate_pr3_auto --live` 0 · `gate_scope_audit_auto` 0 · `gate_phase14_auto --frontend-only` 0 · `gate_pr25_discovery_auto --host-drift` 0 |

One honest wrinkle, recorded as debt **D-26**: the corrected FF-A1
gate's SOLO run in stage A — started 3 seconds after `up --build`
recreated the backend — FAILED 1/36 on §8 `real DB byte-identical`
(`c27774d8dfaf` mid-write), because the backend's own startup handler
writes the production DB (`init_db()` WAL pragma + table creation,
then PR-2's spend-hold recovery and reconciliation). The identical
gate on the identical image passed 36/36 twenty-five minutes later in
the roster with the DB quiesced. Not a PR-4 defect, not a census
defect; an ordering hazard in chain scripts, preserved verbatim rather
than re-run away. $0 throughout; no providers; no downloads; no
reference JPG or generated artifact enters the commit.

---

## PR-2 — spend caps enforce by atomic reservation (CLOSED 2026-09-01, ADR-061: auto gate PASS + operator visual gate PASS)

**Scope (approved 2026-08-28 with eleven mandatory technical amendments
and two rulings).** ADR-003's cap was a raceable check-then-call; PR-2
replaces it with per-physical-attempt atomic reservations (BEGIN
IMMEDIATE on a dedicated connection), integer micro-USD accounting via
Decimal half-up conversion, one-transaction settlement (ai_calls +
reservation + sessions ledger), exact reservation_id correlation with
1:1 unique partial indexes in both directions, first-class spend scopes
(`open|closed|halted`, halted sticky), fail-closed uncertainty (no
first-party proof of non-billing exists — every failed attempt counts at
its full bound), provider-model/global safety locks on pricing failure /
bound-exceeded / ledger mismatch with an audited `spend_admin.py`
resolution surface, and the mandated context-window fallback bound
(no provider documents message framing — checked first-party
2026-08-28). Rulings applied: fabrication spend accumulates across every
re-POST of one (session, spec) via a full-identity uuid5 scope;
`session_cap_usd` → `run_cap_usd` everywhere live (historical records
untouched).

### ADR-009 fetches (2026-08-28, recorded in pricing.yaml `2026-08-v4`)

- claude-sonnet-4-5: "Context window: 200K tokens · Max output: 64K" +
  prices re-confirmed ($3/$15/$0.30/$3.75) —
  platform.claude.com/docs/en/models/sonnet-4-5/overview.
- gpt-4o: "128,000 context window" / "16,384 max output tokens" —
  developers.openai.com/api/docs/models/gpt-4o (PRICES remain
  tracker-only; B-4 stays open).
- kimi-k3: "1,048,576 tokens" context + prices re-confirmed —
  platform.kimi.ai/docs/pricing/chat-k3.md.
- None of the three pages documents per-message framing overhead, so per
  Amendment 4 ALL providers reserve at the context-window fallback.
  Resulting bounds at 8,192 output tokens, exact:
  anthropic $0.872880 · openai $0.401920 · **kimi $3.268608** (the
  stated consequence: a kimi call needs that much free headroom while in
  flight).

### Red-first baseline — new PR-2 tests vs PRISTINE `f5541da`

Detached read-only worktree at `f5541da` (backend + config + tests all
mounted `:ro` into a throwaway `docker compose run --rm --no-deps`
container; shared tree and live containers untouched; the pristine
config still reads `session_cap_usd`). One attempt, verbatim:

```
ImportError while importing test module '/app/tests/test_spend_reservations.py'.
tests/test_spend_reservations.py:34: in <module>
    from app.ai.call_log import reserve_bound_usd_micro
E   ImportError: cannot import name 'reserve_bound_usd_micro' from 'app.ai.call_log' (/app/backend/app/ai/call_log.py)
ERROR tests/test_spend_reservations.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.00s
```

**True baseline, stated precisely: 1 collection error, 0 tests
executed.** Reason: `reserve_bound_usd_micro` did not exist in the
pristine code. Therefore the new PR-2 test suite is structurally
incompatible with the old implementation — the reservation API and its
test module cannot exist or run against `f5541da`. This does NOT claim
21 individual failing assertions; no test body executed. (An earlier
invocation of the same run failed at container CREATION — Docker cannot
create a single-file mountpoint inside a read-only directory mount —
before any test executed; the staged re-invocation above is the same
single baseline attempt.)

### Intermediate runs — NEW code, OLD tests (not a baseline)

Run 1 on the first PR-2 image (worker UP, pinned `08:26:36Z` before and
after): `17 failed, 456 passed in 596.02s`. All 21 new tests passed; all
17 failures were old tests asserting the pre-PR-2 contract — six
`test_budget.py` tests (`session_cap_usd` kwarg / removed
`pre_dispatch_check`, `record_actual`, `spent_session`), six
`'2026-08-v4' == '2026-08-v3'` literals (`test_call_log`,
`test_pricing`, `test_providers_offline` x3, `test_cache_pricing`),
`test_council_api` (rollup key rename), two `test_retry_and_degradation`
tests (the kimi retry legitimately halts once an uncertain first attempt
holds $3.149568 under a $5 run cap), `test_cache_pricing::
test_unpriced_cache_class_fails_but_call_is_audited` (its hand-made
pricing had no context window, so the dispatch now refused BEFORE
spending), and `test_schema_patches` (the declared-patch list gained
`ai_calls.reservation_id`). No production defect among them; each old
test was rewritten to the same intent on the new contract (details in
the tests' own comments). Run 2 after those rewrites: `2 failed, 471
passed in 656.22s` — a second `v3` literal at `test_council_api.py:110`
masked in run 1 by the KeyError above it, and my own rewritten
exhaustion assertion (attempt 2's row already carries attempt 1's retry
note). Production code did not change between runs 1, 2 and 3.

### Definitive run on the second PR-2 image — SUPERSEDED (see below)

Worker UP, pinned `08:26:36Z` before AND after: `473 passed, 2 warnings
in 602.00s`. Host: `gate_phase14_auto --frontend-only` PASS;
`gate_pr3_auto --live` PASS (live-lan + live-loopback);
`tsc --noEmit && vite build` ✓ 6.26s.

### CONTAMINATED chain — preserved, NOT definitive

Worker REMOVED (`docker compose rm -sf render-worker`; listing empty
before the suite, after the suite and after the roster), started
12:53:53Z. During 12:50:49Z–~13:2xZ a second session
(`luxuryform-65`, a read-only scope audit) ran two concurrent full
pytest suites, two roster scripts (`gate_costing_auto` exit 0,
`gate_phase11_auto` killed in flight) and API POSTs inside the SAME
`luxuryform-backend-1` — it changed no files, no images, no container
state and never touched the render worker; it wrote two designs
(`76595edb-…`, `313e5d20-…`) with validation/export rows and files into
the operator's live `data/` — recorded as unexpected live-data test
artifacts, untouched pending a separate ruling. **No real provider spend
occurred in that window** (live DB, read-only: 0 `ai_calls`, 0
reservations, 0 scopes, 0 locks, 0 budget events, 0 sessions between
12:40Z and 13:40Z). Output of the contaminated chain, verbatim:

```
worker-listing-before-suite: [] (empty = removed)
473 passed, 2 warnings in 992.72s (0:16:32)
worker-listing-after-suite: [] (empty = removed)
=== ROSTER (worker removed) ===
ROSTER gate_costing_auto.py exit=0 :: ... | COSTING GATE: PASS
ROSTER gate_phase11_auto.py exit=0 :: ... | PASS — Phase 11 auto gate
ROSTER gate_phase13a_auto.py exit=0 :: ... | PASS — Phase 13a auto gate
ROSTER gate_phase14_auto.py exit=0 :: NOT covered in this run: frontend | PASS
ROSTER gate_phase15_auto.py exit=0 :: PASS - Phase 15 sections: backend
ROSTER gate_phase2_auto.py exit=0 :: ... | PHASE 2 AUTO GATE: PASS
ROSTER gate_phase3_auto.py exit=0 :: ... | VERDICT: PASS
ROSTER gate_phase4_auto.py exit=0 :: ... | VERDICT: PASS
ROSTER gate_phase5_auto.py exit=0 :: ... | Phase 5 auto gate PASS
ROSTER gate_phase6a1_auto.py exit=0 :: ... | PASS — Phase 6 slice A1
ROSTER gate_phase6a2_auto.py exit=0 :: ... | PASS — Phase 6 slice A2
ROSTER gate_phase6b_auto.py exit=0 :: ... | PASS — Phase 6 slice B
ROSTER gate_phase6c_auto.py exit=0 :: ... | PASS — Phase 6 slice C1
ROSTER gate_phase6c2_auto.py exit=0 :: PASS — Phase 6 slice C2
ROSTER gate_phase8_auto.py exit=0 :: ... | PASS — Phase 8 auto gate
ROSTER gate_phase8b_auto.py exit=0 :: PASS — Phase 8b re-gate
ROSTER gate_phase9a_auto.py exit=0 :: ... content digest : bb374499df4d8e12... | PASS — Phase 9A
ROSTER gate_phase9b_auto.py :: deferred (worker-up)
ROSTER gate_pr1_auto.py exit=0 :: PASS — PR-1 auto gate
ROSTER gate_pr2_auto.py exit=0 :: ok a book mismatch engages a GLOBAL lock (fail closed) :: problems: ['settled reservation r-dead has no ai_call', 'settled reservation r-bad has no ai_call'] | PASS — PR-2 auto gate
ROSTER gate_pr3_auto.py[static,stdin] exit=0 :: PASS
worker-listing-after-roster: [] (empty = removed)
```

### Intermediate defect (distinct from the contamination incident) — fixed in-slice, image rebuilt

**Exposed by:** the `gate_pr2_auto` §5 detail line quoted in the
contaminated chain above — not by a failing test; the gate PASSED
(it expected a lock from the deliberately tampered `r-bad` row) while
its detail wrongly named `r-dead`, the hold the operator had just
reconciled through `resolve_uncertain_hold`, as a book mismatch.
**Root cause:** `resolve_uncertain_hold` marked the hold `settled` with
`ai_call_id` NULL; `reconcile_spend_books` treats every `settled` row as
owing a 1:1 `ai_calls` row, and `_day_spent_micro` derives settled money
only from 'ok' `ai_calls` rows. **Consequences in the pre-fix code:**
(1) any operator hold reconciliation would engage a GLOBAL safety lock
at the next backend startup (fail-closed, but wrong); (2) a hold
reconciled to a NONZERO console-verified amount vanished from the day
sum — an under-count. **Fix (production: `budget.py` only —
`_day_spent_micro`, `_run_spent_micro`, `resolve_uncertain_hold`;
schema/models comments; tests + gate §5 + spend_admin wording):**
operator-reconciled holds get their own status `reconciled`, counted at
the verified amount in BOTH cap sums and exempt from the 1:1 assertion.
**Scope:** corrects the accounting of the already-approved audited
resolution path; no new capability. **Superseded by the rebuild:** the
473-pass worker-up run on image `fbc4883dd98b` and the host
`gate_pr3 --live`; standing: the true baseline, the ADR-009 fetches,
`gate_phase14 --frontend-only` and the frontend build (no frontend
file changed). Red-first for the fix, new tests vs the pre-fix PR-2
image (host tests mounted `:ro` into a throwaway `docker compose run`),
verbatim:

```
/app/tests/test_spend_reservations.py:622: assert 0.0 == 0.3 ± 3.0e-07
FAILED tests/test_spend_reservations.py::test_startup_recovery_classifies_dead_holds_uncertain
FAILED tests/test_spend_reservations.py::test_a_nonzero_reconciliation_still_counts_against_both_caps
2 failed in 2.92s
```

The gate's §5 now asserts both properties explicitly.

**Same defect, second half — the operator surfaces.** Before the
definitive runs the operator required the `reconciled` book to reach
every operator-facing surface. Inspection: `/api/ops/costs` summed
`ai_calls` only (a $0.30 reconciled orphan was invisible in Operations
total spend), `/api/logs/budget` listed only held/uncertain holds, and
the reconciler had no explicit double-count guard. Fix (production:
`routes_ops.py`, `routes_logs.py`, `budget.reconcile_spend_books`):
the truth model is now stated in code and on the wire —
`total_usd = ai_calls_usd + reconciled_usd`, non-overlapping;
`reconciled_unmatched_spend` rows carry reservation id, scope, session,
dispatch day, amount, linked call (never an 'ok' one) and audit note on
both endpoints; `by_day` includes reconciled amounts on their dispatch
day; the sessions ledger stays ai_calls-derived so the existing
ai_calls<->sessions reconciliation (and `gate_phase13a` §5) remains
honest; `reconciled_double_counts` is a live finding. Red-first for
this half, new test vs the image `ae925db7` (pre-surface-fix), verbatim:

```
/app/tests/test_spend_reservations.py:755: KeyError: 'ai_calls_usd'
FAILED tests/test_spend_reservations.py::test_a_reconciled_orphan_reaches_every_operator_surface
1 failed in 3.86s
```

Gate §7 now seeds a $0.30 orphan on a fresh throwaway DB and asserts
both surfaces. The image was rebuilt ONCE MORE with both halves;
everything below is on THAT final image (ids recorded there).

### DEFINITIVE evidence — final image `09ff920ccbbb`, exclusive control

Exclusive state verified before launch: no foreign process in the
container (only uvicorn), no host `docker exec` clients, HEAD `f5541da`,
every changed path mine, render worker REMOVED. Final backend image
`sha256:09ff920ccbbb…` / container `c3369a7ab89b…` (started
13:37:05Z); the image id is re-read at the END of each stage.

**Stage 1 — render worker REMOVED**, verbatim:

```
image: sha256:09ff920ccbbb857c1f5a4bed52d4ba54a2d7675a51a83e838f6fa42a4c53d965 container: c3369a7ab89be8f5633ad46b2b1a2469a7a990480ec7b5d2729a173210c4b938
worker-listing-before-suite: [] (empty = removed)
475 passed, 2 warnings in 940.98s (0:15:40)
worker-listing-after-suite: [] (empty = removed)
=== ROSTER (worker removed) ===
ROSTER gate_costing_auto.py exit=0 :: ... | COSTING GATE: PASS
ROSTER gate_phase11_auto.py exit=0 :: export 3MF failed: No module named 'networkx' (D-7) | PASS — Phase 11 auto gate
ROSTER gate_phase13a_auto.py exit=0 :: ... | PASS — Phase 13a auto gate
ROSTER gate_phase14_auto.py exit=0 :: NOT covered in this run: frontend | PASS (geometry)
ROSTER gate_phase15_auto.py exit=0 :: PASS - Phase 15 sections: backend
ROSTER gate_phase2_auto.py exit=0 :: ... | PHASE 2 AUTO GATE: PASS
ROSTER gate_phase3_auto.py exit=0 :: ... | VERDICT: PASS
ROSTER gate_phase4_auto.py exit=0 :: ... | VERDICT: PASS
ROSTER gate_phase5_auto.py exit=0 :: ... | Phase 5 auto gate PASS
ROSTER gate_phase6a1_auto.py exit=0 :: ... | PASS — Phase 6 slice A1
ROSTER gate_phase6a2_auto.py exit=0 :: ... | PASS — Phase 6 slice A2
ROSTER gate_phase6b_auto.py exit=0 :: ... | PASS — Phase 6 slice B
ROSTER gate_phase6c_auto.py exit=0 :: ... | PASS — Phase 6 slice C1
ROSTER gate_phase6c2_auto.py exit=0 :: PASS — Phase 6 slice C2
ROSTER gate_phase8_auto.py exit=0 :: ... | PASS — Phase 8 auto gate
ROSTER gate_phase8b_auto.py exit=0 :: PASS — Phase 8b re-gate
ROSTER gate_phase9a_auto.py exit=0 :: ... content digest : bb374499df4d8e1262d8939d2fdcb573c5c1e13a8bdb4e4c3bf5afc8ce3c29c4 | PASS — Phase 9A
ROSTER gate_phase9b_auto.py :: deferred (worker-up stage)
ROSTER gate_pr1_auto.py exit=0 :: PASS — PR-1 auto gate
ROSTER gate_pr2_auto.py exit=0 :: ok a book mismatch engages a GLOBAL lock (fail closed) :: problems: ['settled reservation r-bad has no ai_call'] | PASS — PR-2 auto gate
ROSTER gate_pr3_auto.py[static,stdin] exit=0 :: PASS
worker-listing-after-roster: [] (empty = removed)
image-after: sha256:09ff920ccbbb857c1f5a4bed52d4ba54a2d7675a51a83e838f6fa42a4c53d965
```

The suite is 475 (the 473 plus the two defect tests). The `gate_pr2`
§5 detail now names ONLY the deliberately tampered `r-bad` — the
reconciled `r-dead` is no longer a mismatch, the defect fix visible in
the gate's own output. Host on the final backend: `gate_pr3_auto
--live` exit 0 PASS (live-lan + live-loopback); standing from earlier
(no frontend file changed): `gate_phase14_auto --frontend-only` PASS,
`tsc --noEmit && vite build` ✓ 6.26s.

**Stage 2 — render worker RESTORED** (`docker compose --profile render
up -d render-worker`), verbatim:

```
worker BEFORE suite: running started 2026-08-28T14:02:02.074233988Z
image: sha256:09ff920ccbbb857c1f5a4bed52d4ba54a2d7675a51a83e838f6fa42a4c53d965 container: c3369a7ab89be8f5633ad46b2b1a2469a7a990480ec7b5d2729a173210c4b938
475 passed, 2 warnings in 849.50s (0:14:09)
worker AFTER suite: running started 2026-08-28T14:02:02.074233988Z
GATE gate_phase9b_auto exit=0 :: Phase 9B auto gate PASS
worker AFTER 9b: running started 2026-08-28T14:02:02.074233988Z
image-after: sha256:09ff920ccbbb857c1f5a4bed52d4ba54a2d7675a51a83e838f6fa42a4c53d965
```

**Roster accounting on the final image, explicit:** 19 scripts
in-container with the worker REMOVED (17 phase gates + `gate_pr1` +
`gate_pr2`) = 19; script 20 `gate_pr3_auto` in BOTH modes (static via
stdin in-container, live on the host); script 21 `gate_phase9b_auto`
with the worker restored — **21 of 21 green**, plus `gate_phase14`'s
host half. Suite green in BOTH worker states on the final image, worker
state pinned at every boundary, backend image id identical at the end
of every stage. Total live spend by this slice: **$0.00** (no provider
call was made at any point; the live DB shows none).

### Operator visual gate — SIGNED PASS 2026-09-01

Pre-sign-off state verification (2026-09-01, three read-only checks,
reconciled): HEAD `f5541da` = `origin/main`; the uncommitted change set
was exactly the 44 recorded paths, nothing staged, no stashes, no file
outside PR-2's scope; image `09ff920ccbbb` still `luxuryform-backend:
latest` with the evidence container `c3369a7ab89b…` pointing at the
exact digest; no code/test/config file modified after the image build
(only the .md reports, written after the evidence, as expected).
Observed and recorded: an unattributed container run on 2026-08-31
(backend up 08:07:03Z → stopped 09:41:56Z, exit 0) — code is baked into
the image so no code drift was possible; the operator verified below
that no provider call occurred in that window. `gate_pr2_visual.md` was
completed doc-only before signing (named `reconciled_unmatched_spend`
in step 1, the $5/$25 values in step 2, auto-gate sections [1]/[4]/[5]/
[7] in step 3, and replaced the stale rebuild prerequisite with a
no-rebuild start, since a rebuild after the doc changes would have
minted a new image id).

The operator's sign-off, verbatim (2026-09-01):

> PR-2 visual gate signed PASS.
>
> - Operations ledgers reconcile.
> - No provider calls occurred during the unexplained 2026-08-31
>   container window.
> - The latest legitimate paid activity is my 2026-08-28
>   Council/fabrication demonstration.
> - Budget API exposes run_cap_usd, day_cap_usd, open_holds,
>   active_safety_locks and reconciled_unmatched_spend.
> - open_holds, active_safety_locks and reconciled_unmatched_spend are
>   empty.
> - config/budget.yaml uses run_cap_usd; session_cap_usd is absent.
> - gate_pr2_auto.py PASS.
> - spend_admin.py list shows no unresolved entries.
> - I approve retaining $5 per logical run and $25 per UTC day.
> - I understand that an uncertain Kimi attempt can prevent an
>   automatic retry within the same $5 run.
>
> Proceed with /lf-close, one PR-2 commit and push. Preserve the two
> accidental test designs; do not clean them up in PR-2.

**Status: CLOSED — auto gate PASS on the final image + operator visual
gate signed PASS 2026-09-01. $5/run and $25/day retained by explicit
ruling. Designs `76595edb…` and `313e5d20…` preserved; their cleanup is
a separate operator ruling.**

---

## PR-1 — max_module_m binds per axis (CLOSED 2026-08-28: auto gate PASS + operator visual gate PASS)

**Scope (approved with 7 amendments 2026-08-28).** The Design Spec has
always required `fabrication.max_module_m` as `{x,y,z}`;
`spec_mapper.py:204` collapsed it with `max()` so every spec-path design
was gated on its LOOSEST axis. PR-1 preserves the axes end-to-end
(mapper, assembler pre-cut and post-cut, segmentation kernel,
fabrication gate), keeps the Designer's scalar as a deliberate cubic
envelope at the one `assemble()` boundary, enforces the approved
compatibility truth table with live provenance on the design API, and
refuses geometry-rebuilding operations on ambiguous history with one
exact next action. Decisions: ADR-059. Deferred to PR-5 per Amendment 7:
the `run_vision_critique.py` lookup + scorer contract repair.

### Compatibility evidence, verbatim — PRISTINE tests against the NEW
backend. **This is NOT the red-first baseline** (that is the next block):
it shows which recorded old-contract assertions the new behaviour
breaks, i.e. what the rewrite had to re-assert as the new truth:

```
docker compose exec -T backend python -m pytest tests/test_spec_mapper.py tests/test_segmentation.py tests/test_assembly.py tests/test_validation_gates.py -q
FAILED tests/test_spec_mapper.py::test_fabrication_limits_from_spec_scalarizes_module_box
FAILED tests/test_segmentation.py::test_segmentation_conserves_volume_exactly
FAILED tests/test_segmentation.py::test_a_five_metre_basin_becomes_liftable_modules
FAILED tests/test_segmentation.py::test_module_count_is_measured_not_predicted
FAILED tests/test_segmentation.py::test_seam_area_and_length_match_hand_arithmetic
FAILED tests/test_segmentation.py::test_an_unsplit_solid_has_no_seam - TypeEr...
FAILED tests/test_segmentation.py::test_the_same_cut_twice_is_byte_identical
FAILED tests/test_segmentation.py::test_plane_order_does_not_change_the_engineering
FAILED tests/test_segmentation.py::test_a_runaway_module_limit_is_refused_with_the_numbers
FAILED tests/test_validation_gates.py::test_an_oversized_element_in_a_pre_segmentation_manifest_asks_for_a_rebuild
FAILED tests/test_validation_gates.py::test_a_segmented_element_reports_its_measured_modules
11 failed, 60 passed in 78.32s (0:01:18)
```

The eleven are exactly the predicted classes: the collapse pin (the test
name itself asserts the defect), the eight scalar `segment_solid` call
sites (the kernel now takes one shape only), and the two gate tests
whose scalar fixture now honestly reads needs_input — a scalar without
confirmed cubic provenance is never assumed cubic (Amendment 1 row 5).

### THE red-first baseline, verbatim — NEW per-axis tests against
PRISTINE `16cf932` production code (detached git worktree mounted
read-only into a throwaway container; shared tree and live containers
untouched):

```
docker compose run --rm --no-deps -T -v <worktree>\backend:/app/backend:ro -v <repo>\tests:/app/tests:ro backend python -m pytest <the 11 new per-axis tests> -q
FAILED tests/test_spec_mapper.py::test_fabrication_limits_from_spec_preserves_the_axes
FAILED tests/test_spec_mapper.py::test_fabrication_limits_from_spec_refuses_a_scalar
FAILED tests/test_spec_mapper.py::test_fabrication_limits_from_spec_refuses_bad_axes
FAILED tests/test_segmentation.py::test_the_z_axis_binds_on_its_own_limit - T...
FAILED tests/test_segmentation.py::test_the_kernel_takes_exactly_one_limit_shape
FAILED tests/test_segmentation.py::test_a_zero_axis_is_refused_per_axis - Typ...
FAILED tests/test_segmentation.py::test_assemble_takes_the_spec_object_and_splits_the_tall_axis
FAILED tests/test_segmentation.py::test_assemble_refuses_malformed_module_limits
FAILED tests/test_validation_gates.py::test_the_binding_axis_is_the_ratio_not_the_largest_dimension
FAILED tests/test_validation_gates.py::test_a_z_bound_module_fails_even_when_x_and_y_fit
FAILED tests/test_validation_gates.py::test_the_scalar_truth_table_in_the_gate
11 failed in 16.90s
```

**11 of 11 red on the old code — the tests genuinely detect the defect.**
Honest scope note: the four new API-level tests
(`test_assembly_api.py`: malformed→422, per-axis round-trip, the
collapsed-spec refusals, the cubic control) were NOT part of this
baseline run — they need the TestClient/DB stack inside the throwaway
container; their old-code failure modes (HTTP 500 from the TypeError,
and a missing `module_limit_provenance` key) are implied but were not
executed against pristine code.

**One fixture defect in the slice's own first test build, fixed openly:**
the Z-split tests first used `basin_round` at height 2,300 mm, which its
own parameter envelope (max 900 mm) rightly refused — reported by the
first green run (`2 failed, 112 passed in 282.90s`), moved to
`sculptural_column` (envelope 300–6,000 mm), both green (21.34s).

### Full suites on the final image, verbatim — both worker states

Render worker UP (instance pinned identical before and after,
StartedAt 2026-08-27T13:38:44.157457612Z):

```
docker compose exec -T backend python -m pytest tests/ -q
449 passed, 2 warnings in 560.89s (0:09:20)
```

(449 = the 434 pre-PR-1 tests + 15 new per-axis tests.)

Render worker REMOVED (verified empty before and after):

```
docker compose rm -sf render-worker
docker compose exec -T backend python -m pytest tests/ -q
449 passed, 2 warnings in 882.82s (0:14:42)
```

### `gate_pr1_auto.py` — PASS, exit 0, verbatim (worker removed)

```
[1] MAPPER — the spec's axes survive; bad shapes are refused
  ok   axes preserved exactly :: {'x': 2.4, 'y': 2.4, 'z': 2.2}
  ok   refuses scalar (Design-Spec path must refuse — Amendment 3)
  ok   refuses missing axis / extra axis / boolean axis /
       non-finite axis / zero axis / negative axis
[2] THE Z-AXIS PROOF — 2.4 x 2.4 x 2.2 m cuts a 2.3 m column
  ok   grid splits ONLY the z axis :: {'x': 1, 'y': 1, 'z': 2}
  ok   more than one module :: 2 modules
  ok   every module fits z <= 2200 mm :: tallest module z = 1150.0 mm
  ok   volume conserved :: 0.0000000000 %
[3] THE CLOSED DEFECT — the collapsed value ships it whole
  ok   max(x,y,z)=2.4 cubic does NOT split it :: 1 module — 2,300 mm
       tall against the declared 2,200 mm truck
[4] BOUNDARY — assemble(): cubic compat, loud refusals
  ok   manifest round-trips the dict :: {'x': 2.4, 'y': 2.4, 'z': 2.2}
  ok   assemble cut the tall axis :: 2 modules
  ok   Designer scalar normalizes to a cubic dict :: {'x': 4.0, ...}
  ok   all 6 malformed limits refused as ConstraintViolation :: 6/6
  ok   discrete-array refusal names the binding axis from a dict ::
       "... exceeds max_module_m x 0.8 m / y 3 m / z 3 m on the x axis
       (2300 mm vs 800 mm) ..."
[5] PROVENANCE TRUTH TABLE — through the real API
  ok   row 1: spec_id NULL + scalar -> cubic, valid
  ok   row 2: spec_id NULL + {x,y,z} -> per-axis, valid
  ok   row 4: spec-backed scalar -> collapsed_spec needs_input
  ok   recovered spec axes ride along; the one next action names the
       rebuild; geometry-rebuilding endpoint refuses with 409
  ok   row 5: mismatched spec -> unverifiable, never cubic
[6] CANONICAL HASHES — all four unmoved
  ok   e1a59fa6... / 529014af... / 6038d26f... / 956436c1...
[7] DETERMINISM — non-cubic cut byte-identical across processes :: 597 chars
PASS — PR-1 auto gate: all sections passed at $0, no network, no AI call.
GATE gate_pr1_auto exit=0
```

### Full roster, final image, worker REMOVED — verbatim, one line each

```
ROSTER gate_phase2_auto.py exit=0
ROSTER gate_phase3_auto.py exit=0 :: VERDICT: PASS
ROSTER gate_phase4_auto.py exit=0 :: VERDICT: PASS
ROSTER gate_phase5_auto.py exit=0
ROSTER gate_phase6a1_auto.py exit=0 :: PASS
ROSTER gate_phase6a2_auto.py exit=1   <- reported red, diagnosed below
ROSTER gate_phase6b_auto.py exit=0 :: PASS
ROSTER gate_phase6c_auto.py exit=0 :: PASS
ROSTER gate_phase6c2_auto.py exit=0 :: PASS
ROSTER gate_costing_auto.py exit=0
ROSTER gate_phase8_auto.py exit=0 :: PASS
ROSTER gate_phase8b_auto.py exit=0 :: PASS
ROSTER gate_phase9a_auto.py exit=0 :: PASS
ROSTER gate_phase11_auto.py exit=0 :: PASS
ROSTER gate_phase13a_auto.py exit=0 :: PASS
ROSTER gate_phase14_auto.py exit=0 :: PASS (container: geometry sections)
ROSTER gate_phase15_auto.py exit=0 :: PASS
ROSTER gate_pr1_auto.py exit=0 :: PASS
ROSTER gate_pr3_auto (static, stdin) exit=0 :: PASS
HOST gate_pr3_auto --live exit=0 :: PASS (loopback + LAN)
HOST gate_phase14_auto --frontend-only exit=1   <- reported red, below
```

**Two reds in the first roster pass, both diagnosed from real output and
fixed openly (Rule 12; neither check weakened):**

1. `gate_phase6a2_auto` §5: its bridge stand-in design persists
   `spec_id` SET with a SCALAR `max_module_m: 3.0` and a stand-in spec
   of `"{}"` — synthetically the exact ambiguous-history class of the
   approved truth table (spec-backed scalar, nothing recoverable), so
   the new export guard refused with HTTP 409 exactly as ruled
   ("missing provenance -> needs_input; never assume cubic"). The gate
   FIXTURE moved to the new truth — a current-code fabrication program
   passes the spec's per-axis object, so the stand-in now declares
   `{"x": 3.0, "y": 3.0, "z": 3.0}`. The D-10 fixture-expiry pattern's
   fourth occurrence; STEP bytes unaffected (limits never reach
   geometry). Re-run green below.
2. `gate_phase14_auto --frontend-only`: `npm run build` exited 2 —
   `DesignerWorkspace.tsx:167` restores a stored request into the
   document, whose `fabrication` was typed scalar-only; a restored
   per-axis design could not type-check. The document type widened to
   `FabricationValue` and carries a restored `{x,y,z}` through to
   rebuilds VERBATIM (no silent drop; there is no fabrication editor UI
   to misrender — `set-fabrication` has no dispatcher). Re-run:
   `npm run build` ✓ built in 2.98s, exit 0.

### Re-runs after the two fixes, and 9B — verbatim

```
ROSTER gate_phase6a2_auto.py exit=0 :: PASS — Phase 6 slice A2 auto gate: all sections passed at $0, no network, no AI-written code executed.
HOST gate_phase14_auto --frontend-only exit=0 :: PASS (npm run build ✓)
docker compose --profile render up -d render-worker
running started 2026-08-28T08:26:36.493402363Z
GATE gate_phase9b_auto exit=0
running started 2026-08-28T08:26:36.493402363Z
```

### What PR-1 makes true

- Every axis of `fabrication.max_module_m` binds on its own limit at
  all three enforcement sites, via one shared kernel vocabulary; the
  binding axis is the greatest extent/limit ratio, ties x→y→z.
- The Designer's single number remains a valid, deliberate cubic
  envelope at the one `assemble()` boundary; the Design-Spec mapper
  preserves `{x,y,z}` and refuses scalars; malformed limits are
  structured HTTP 422s, never TypeErrors or 500s.
- The approved compatibility truth table runs live on the design API
  with spec recovery + verification; ambiguous history refuses
  geometry rebuilds with one exact next action and stays viewable.
- Red-first proven: 11/11 new tests failed on pristine `16cf932`.
  Suites: 449 passed in BOTH worker states on the final image.
- **All 20 roster scripts green, counted explicitly:** 18 scripts run
  in-container with the worker removed (`gate_phase2/3/4/5/6a1/6a2/6b/
  6c/6c2/costing/8/8b/9a/11/13a/14/15_auto.py` = 17, plus
  `gate_pr1_auto.py` = 18); script 19, `gate_pr3_auto.py`, run in BOTH
  its modes (static in-container with the host's live compose file
  piped in, live on the host); script 20, `gate_phase9b_auto.py`, run
  with the worker restored and its instance pinned. `gate_phase14_auto`
  and `gate_pr3_auto` each covered on both their sides per their own
  split-coverage contracts.
- Canonical STEP hashes: all four re-asserted unmoved.

### Cost

$0.00 — no AI call anywhere in the slice; no network beyond the local
Docker daemon and loopback.

**Operator visual gate (`gate_pr1_visual.md`, $0): PASS, signed
2026-08-28.** The operator's result, verbatim:

> - The 2.3 m column split into exactly two modules under the 2.2 m Z
>   limit.
> - Grid was 1 × 1 × 2.
> - Both module heights were 1150 mm, safely below 2200 mm.
> - Volume delta was 0%.
> - The basis named X 2.4 m, Y 2.4 m and Z 2.2 m.
> - Checks correctly reported "binding axis z" and compared 1150 mm
>   against 2200 mm.
> - The normal Designer scalar build completed correctly with no
>   historical-rebuild warning.
> - Historical spec-design check: n/a.
> - Real truck envelope: UNKNOWN pending workshop/truck measurement;
>   keep B-1 open and do not invent values.

The real per-axis truck envelope remains an open operator input under
B-1 — no value was invented; the platform keeps enforcing whatever the
operator declares per design until the measured numbers arrive.

**PR-1 CLOSED 2026-08-28: auto gate PASS + operator visual gate PASS.**

---

## PR-3 — the platform answers on loopback only (CLOSED 2026-08-28: auto gate PASS + operator visual gate PASS)

**Scope (approved with amendments 2026-08-27).** docker-compose.yml
published ports 8000/5173 on every host interface while the API has no
authentication — anyone on the LAN could read designs and transcripts
and dispatch PAID provider calls. Change: host publishes bind
`127.0.0.1` (3-part form); a standing roster gate (`gate_pr3_auto.py`,
the 19th script) asserts the compose file AND the live sockets; operator
doc `docs/operator/11_network_privacy.md`; LIMITATIONS §19 records the
no-authentication truth; no LAN-enable path ships. Decisions: ADR-058.
Container-internal binds (uvicorn/Vite `0.0.0.0`) are untouched — they
are what the publish and the compose network connect to.

**Two defects in the slice's own first build, found by its own gate and
fixed openly (Rule 12):** (1) the first live run's health check hit the
backend seconds after a recreate and failed with RemoteDisconnected
(docker-proxy accepts, backend not yet listening) — twice; the positive
loopback checks gained a 60 s startup deadline with per-attempt
reporting (judgement value, ADR-058), which still fails loudly if the
service never becomes healthy. (2) The static section as first written
would have parsed the IMAGE's baked build-time copy of
docker-compose.yml when run in-container — a stale snapshot that could
pass while the governing host file regressed, the exact silent hole the
gate exists to close; it now refuses the baked copy by name and takes
the host's live file over stdin. (Operational note: one rebuild+gate
run on 2026-08-27 hung for ~16 h — laptop sleep mid-build, no evidence
produced; the run was stopped and repeated identically.)

### Gate evidence, verbatim (2026-08-28)

Binding applied and observed (`docker compose up -d`, then `docker port`):

```
8000/tcp -> 127.0.0.1:8000
5173/tcp -> 127.0.0.1:5173
```

STATIC — in the backend container, the HOST's live compose file piped in:

```
Get-Content docker-compose.yml -Raw | docker compose exec -T backend python scripts/gate_pr3_auto.py --static --stdin
STATIC: parsing docker-compose.yml from stdin (the HOST's live file)
  ok   backend: ports '127.0.0.1:8000:8000' is loopback-bound
  ok   frontend: ports '127.0.0.1:5173:5173' is loopback-bound
  ok   geo-worker: network_mode none, no ports
  ok   render-worker: network_mode none, no ports
  ok   frontend: VITE_API_TARGET='http://backend:8000' (service DNS — the UI never crosses a host port, so loopback cannot break it)
STATIC: PASS
sections run: static
PASS — all sections that ran passed at $0 with no network beyond this machine's own interfaces.
STATIC-EXIT=0
```

LIVE — on the host:

```
python scripts\gate_pr3_auto.py --live
LIVE: positive checks on loopback — the real services, not just open ports (booting services are retried until 60 s, then failed loudly)
  ok   127.0.0.1:8000/api/health -> HTTP 200, status='ok', db.ok=True (attempt 19)
  ok   127.0.0.1:5173/ -> HTTP 200, serves 'LuxuryForm Studio' (attempt 1)
LIVE loopback: PASS
LIVE LAN: negative checks — every non-loopback IPv4 must REFUSE (8000, 5173): ['172.25.16.1', '192.168.0.144']
  ok   172.25.16.1:8000 refused (timeout 2.0s)
  ok   172.25.16.1:5173 refused (timeout 2.0s)
  ok   192.168.0.144:8000 refused (timeout 2.0s)
  ok   192.168.0.144:5173 refused (timeout 2.0s)
LIVE LAN: PASS
sections run: live-lan, live-loopback
PASS — all sections that ran passed at $0 with no network beyond this machine's own interfaces.
LIVE-EXIT=0
```

All three required sections — static, live-loopback, live-lan — ran and
passed.

**Operator visual gate (`gate_pr3_visual.md`, $0): PASS, signed
2026-08-28** — the operator confirmed the localhost frontend and health
endpoint work, an existing saved design loads correctly, and their phone
on the same Wi-Fi could not reach either port. The off-machine refusal
is thereby confirmed independently of the gate's own on-machine checks.

### Cost

$0.00 — no AI call; no network beyond this machine's own interfaces.

---

## PR-0 — both render-worker states, and a state-independent package digest (2026-08-27)

**Scope.** Entry condition: Phase 6 C2 committed and pushed by the peer
session (`2ad065b`, docs correction `b31a09c`). Work: close debts D-9
(six tests hard-coded the render worker being DOWN) and D-9b (the
LUXEXCHANGE content digest depended on the render worker's uptime), then
prove the suite and gate roster in BOTH worker states. Decisions:
ADR-057.

**The D-9b mechanism, found by reading, confirmed by the baseline.** The
sealed manifest recorded each Blender-tier format's runtime status
(`included` when the worker was up, `unavailable` when it was down —
different reason text, different nulled fields). The manifest is covered
by `CHECKSUMS.sha256`, whose own hash IS the content digest, so the
digest followed the worker's uptime; under load, one export's conversion
could land while the next timed out, and two digests of one design
differed (NEXT.md's intermittent "sixth test").

**Fix.** `luxexchange.py` seals a canonical, spec-derived entry for every
format the registry declares `deterministic: False` (USD/USDZ/FBX/ABC):
status `excluded`, no path/sha256/bytes/duration, one fixed
`excluded_reason`; `omitted_non_reproducible` always lists all four. The
exports API keeps the live per-run status, so the ADR-045 operator
surface is unchanged. Six tests rewritten to assert the honest contract
per observed state (never `failed`, never silent); one new $0 regression
test seals the same design from worker-down results and from synthesized
worker-up results and asserts byte-identical packages.

### Gate evidence, verbatim

**Baseline red — pristine image `b31a09c`, render worker UP, state pinned
before and after (identical StartedAt = uncontaminated run):**

```
running started 2026-08-27T12:25:35.844953685Z
docker compose exec -T backend python -m pytest tests/test_export_package.py tests/test_assembly_api.py -q
FAILED tests/test_export_package.py::test_formats_needing_the_render_worker_are_unavailable_not_failed
FAILED tests/test_export_package.py::test_all_exported_formats_are_byte_identical_across_runs
FAILED tests/test_export_package.py::test_package_manifest_is_honest_about_what_is_missing
FAILED tests/test_assembly_api.py::test_export_status_reports_four_honest_statuses
FAILED tests/test_assembly_api.py::test_an_absent_format_refuses_with_its_reason_not_a_broken_file
5 failed, 42 passed, 2 warnings in 235.42s (0:03:55)
running started 2026-08-27T12:25:35.844953685Z
```

(The intermittent sixth, `test_export_package_is_reproducible_and_self_
verifying`, passed in this baseline — consistent with its recorded
load-sensitivity; the new regression test now pins its failure mode
deterministically.)

**Full suite, fixes baked, render worker UP — clean rebuild then
`docker compose exec -T backend python -m pytest tests/ -q`, worker state
pinned before and after (identical StartedAt = uncontaminated):**

```
running started 2026-08-27T12:25:35.844953685Z
434 passed, 2 warnings in 407.96s (0:06:47)
running started 2026-08-27T12:25:35.844953685Z
```

**One defect in this slice's own work, found by the worker-down run and
fixed openly (Rule 12).** The first worker-down full suite — with the
worker REMOVED (`docker compose rm -sf render-worker`), removal verified
before and after — reported:

```
FAILED tests/test_assembly_api.py::test_export_status_reports_four_honest_statuses
1 failed, 433 passed, 2 warnings in 827.27s (0:13:47)
```

The failure was in the rewritten test itself: its `unavailable` branch
asserted `usd["reason"]`, but the exports API serves the reason merged
into the row's `error` field (`routes_assembly._export_rows`; the exports
table has no reason column) — a key the API never serves, which the
worker-UP run could not catch because that branch is not taken with the
worker running. The assertion was corrected to `usd["error"]`, the image
rebuilt, and BOTH full suites re-run on the final image (worker-down
first, then worker-up after the worker was restored for the 9B gate), so
the two clean-state proofs below come from identical code.

**Full suite, final image, render worker REMOVED — removal verified
before and after the run:**

```
docker compose rm -sf render-worker   (listing empty before AND after)
docker compose exec -T backend python -m pytest tests/ -q
434 passed, 2 warnings in 839.67s (0:13:59)
```

**Full auto-gate roster, final image, render worker REMOVED (verified
empty before and after) — every gate run explicitly, one line each,
verbatim:**

```
ROSTER gate_phase2_auto.py exit=0 :: Next: the operator visual gate — docs/operator/gate_phase2_visual.md
ROSTER gate_phase3_auto.py exit=0 :: VERDICT: PASS
ROSTER gate_phase4_auto.py exit=0 :: VERDICT: PASS
ROSTER gate_phase5_auto.py exit=0 :: ============================================================
ROSTER gate_phase6a1_auto.py exit=0 :: PASS — Phase 6 slice A1 auto gate: all sections passed at $0.
ROSTER gate_phase6a2_auto.py exit=0 :: PASS — Phase 6 slice A2 auto gate: all sections passed at $0, no network, no AI-written code executed.
ROSTER gate_phase6b_auto.py exit=0 :: PASS — Phase 6 slice B auto gate: all sections passed at $0, no network, no AI-written code executed.
ROSTER gate_phase6c_auto.py exit=0 :: PASS — Phase 6 slice C1 auto gate: all sections passed at $0, no network, no AI-written code executed.
ROSTER gate_phase6c2_auto.py exit=0 :: PASS — Phase 6 slice C2 auto gate: all sections passed at $0, no network, no AI-written code executed.
ROSTER gate_costing_auto.py exit=0 :: about that — it does not prove a client-ready quote exists.
ROSTER gate_phase8_auto.py exit=0 :: PASS — Phase 8 auto gate: all sections passed at $0.
ROSTER gate_phase8b_auto.py exit=0 :: PASS — Phase 8b re-gate: intake context drives the gates at $0.
ROSTER gate_phase9a_auto.py exit=0 :: PASS — Phase 9A auto gate: all sections passed at $0, no network.
ROSTER gate_phase11_auto.py exit=0 :: PASS — Phase 11 auto gate: all sections passed at $0.
ROSTER gate_phase13a_auto.py exit=0 :: PASS — Phase 13a auto gate: all sections passed at $0.
ROSTER gate_phase14_auto.py exit=0 :: PASS — all sections that ran passed at $0 with no network
ROSTER gate_phase15_auto.py exit=0 :: PASS - Phase 15 sections: backend ($0, offline)
---host frontend section---
sections run: frontend
NOT covered in this run: geometry — see commands above.
PASS — all sections that ran passed at $0 with no network
HOST gate_phase14_auto --frontend-only exit=0
```

17 of 18 `gate_*_auto.py` scripts, exit 0 each, plus `gate_phase14_auto`
run on BOTH its sides (container `geometry`, host `frontend`) per its own
split-coverage contract. The 18th, `gate_phase9b_auto`, requires the
render worker and is recorded below with the worker restored.

**Render worker restored (`docker compose --profile render up -d
render-worker`), then the 9B gate, the 9A gate in the worker-UP state,
and the final worker-UP full suite — worker StartedAt identical at every
checkpoint (one uninterrupted instance for the whole phase), verbatim:**

```
running started 2026-08-27T13:38:44.157457612Z
GATE gate_phase9b_auto exit=0
GATE gate_phase9a_auto (worker UP) exit=0 :: PASS — Phase 9A auto gate: all sections passed at $0, no network.
running started 2026-08-27T13:38:44.157457612Z
docker compose exec -T backend python -m pytest tests/ -q
434 passed, 2 warnings in 376.07s (0:06:16)
running started 2026-08-27T13:38:44.157457612Z
```

With this, `gate_phase9a_auto` has passed in BOTH worker states on the
fixed code — the direct proof of ADR-057's digest property in the state
that used to break it.

### What PR-0 makes true

- The pytest suite (434 tests) passes with the render worker UP
  (407.96s / 376.07s runs) and with it REMOVED (839.67s run) — on the
  same image, states pinned and verified at every run boundary.
- All 18 auto gates pass: 17 with the worker down + `gate_phase9b_auto`
  with it up; `gate_phase14_auto` covered on both its container and host
  sides.
- The LUXEXCHANGE content digest no longer depends on render-worker
  state (ADR-057); a $0 regression test pins the property forever.
- Debts D-9 and D-9b are closed. The container-start attribution
  question survives as NEXT.md B-9; the operational lessons (pin state
  at start AND end, `rm -sf` not `stop` for a worker-down run) are in
  ADR-057 and NEXT.md §3 rule 10.

### Cost

$0.00 — no AI call anywhere in the slice; no network beyond the local
Docker daemon.
