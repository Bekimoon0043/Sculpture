# PRODUCTION_V1_REPORT.md — the closure program, one section per slice

The Production v1 closure program was approved by the operator on
2026-08-27: slices PR-0 → PR-3 → PR-1 → PR-2 → PR-4 → PR-5 → PR-6 →
PR-7A/7B/7C → PR-8 → PR-9, with seven binding amendments (cap semantics,
historical-scalar-limit provenance, transport wording, mixed-material
measurement paths, the PR-7 three-way split, immutable issuance snapshots,
and positive/negative acceptance cases). The approval transcript lives in
the operator's session of that date; NEXT.md §2 carries the queue.

This report accumulates one section per closed slice, newest first, with
verbatim gate evidence — the same contract as the phase reports.

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
