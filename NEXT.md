# NEXT.md — the loop state file

**This file is the single source of truth for "what is left".** It is read at
the start of every session (`/lf-orient`) and rewritten at the end of every
slice (`/lf-close`). If this file and a phase plan disagree, this file is
stale and must be corrected in the same commit as the work.

Last updated: 2026-08-28 — **PR-3 closed** (loopback-only binding,
ADR-058; auto gate + operator visual gate both PASS). The Production v1
program (approved 2026-08-27 with seven binding amendments) has PR-0 and
PR-3 closed; PR-1 is next. Evidence: `PRODUCTION_V1_REPORT.md`.

---

## 0. Where the build actually stands

| phase | state | evidence |
|---|---|---|
| 1 — providers, spend caps, audit, gates | **CLOSED** | gate PASS 2026-08-01, `PHASE_1_REPORT.md` |
| 2 — geometry kernel, STEP/GLB, determinism | **CLOSED** | gate PASS 2026-08-04, canonical hash `e1a59fa6…` |
| 3 — the AI Council | **CLOSED** | gate PASS 2026-08-07, live $0.843842 |
| 4 — fabrication loop (AI writes CAD, sandbox runs) | **CLOSED** | gate PASS 2026-08-17, live $0.046777 |
| costing engine | **BUILT, gated, starved; reaches assemblies since 2026-08-27** | ADR-031/056; rate card still unfilled (B-3, 39 nulls) |
| 6 — primitive library | **A1 CLOSED; A2 + B + C1 + C2 BUILT (10 primitives, segmentation); D deferred** | auto gates PASS (ADR-052–056); pending: live gate `gate_phase6_visual.md`, eye gates 6b + 6c + 6c2 |
| 7A — assembly surface (API, manifest persistence) | **BUILT** | implemented 2026-08-21, `PHASE_7_COMPLETION_PLAN.md` §7A |
| 8 — L5 validation gates (structure/fabrication/hydraulics) | **BUILT, auto-gated** | auto PASS 2026-08-21 + 8b re-gate; visual pending |
| 9A — LUXEXCHANGE export package | **BUILT, auto-gated; digest now worker-state-independent** | auto PASS 2026-08-21/24; ADR-057 (PR-0); visual pending |
| 9B — Blender render worker (+9B.5 convert) | **BUILT, auto-gated** | auto PASS 2026-08-24, ADR-043/045; visual pending |
| 5 — vision critique loop | **BUILT, auto-gated, RUN LIVE** | auto PASS 2026-08-24; live 3-round run $0.042916; visual pending |
| 10 — vision-driven revision loop (R1–R7) | **PLANNED, deliberately OUTSIDE Production v1** | `PHASE_10_VISION_CRITIQUE_PLAN.md` |
| 11 — DesignDNA precedent store | **BUILT, auto-gated** | auto PASS 2026-08-22, ADR-038; visual pending |
| 12 — brief intake with provenance | **BUILT, auto-gated** | auto PASS 2026-08-22, ADR-039 |
| 13 — recovery + hardening | **Slice A only; B+ queued as PR-7A/B/C** | auto PASS 2026-08-22, ADR-040 |
| 14 + 14b — Designer Workspace, Blender-style controls | **BUILT, auto-gated** | auto PASS 2026-08-24, ADR-044/046; visual pending |
| 15 A–E — designer UX, draft preview, projects/variants | **BUILT, auto-gated** | auto PASS 2026-08-24, ADR-047–051; visual pending |
| **Production v1 program (PR-0 … PR-9)** | **APPROVED 2026-08-27; PR-0 CLOSED** | `PRODUCTION_V1_REPORT.md`, ADR-057; amendments in the approval transcript |

**Suite and roster state after PR-0:** the pytest suite passes with the
render worker UP and with it removed — both runs recorded verbatim in
`PRODUCTION_V1_REPORT.md` with the worker state pinned before and after
each run. The auto-gate roster is 18 scripts: 17 run with the worker
down plus `gate_phase9b_auto` with it up; `gate_phase14_auto` is SPLIT
(container run covers `geometry`, host `--frontend-only` covers
`frontend` — run both, check each verdict's "sections run" line). Total
live spend recorded since Phase 4 closed: $0.042916 (Phase 5 run) plus a
possible ~$0.84 unverified incident exposure (B-2).

---

## 1. BLOCKERS — these need the operator, not the agent

Those marked **[release]** block calling the project Production v1.

- [ ] **B-1 [release] — Walk the visual gates.** Twelve checklists are
      outstanding: `gate_phase5_visual.md`, `gate_phase8_visual.md`,
      `gate_phase9a_visual.md`, `gate_phase9b_visual.md`,
      `gate_phase11_13a_visual.md`, `gate_phase14_visual.md`,
      `gate_phase14b_visual.md`, `gate_phase15_visual.md`,
      `gate_phase6b_visual.md`, `gate_phase6c_visual.md`,
      `gate_phase6c2_visual.md` (carries the grid-vs-radial cutting
      question and your real crane/truck limits) — all $0 — and
      `gate_phase6_visual.md`, the LIVE gate (≈$0.90–1.10, the only one
      that costs money). PR-9 will hand you one PowerShell walkthrough
      document ordering all twelve. Coordinate with any live session
      before touching containers.
- [ ] **B-2 [release] — ADR-033 incident: check the three provider
      consoles** for a possible ~$0.84 test-leak spend on 2026-08-20. The
      local audit rows died with the test temp DB; only the consoles hold
      the truth. Still unanswered.
- [ ] **B-3 [release] — Fill `config/costing.yaml`** (`2026-08-v2`, **39
      null entries**). *Blocks: any client-facing quote.* PR-6 delivers
      the exact checklist. **Biggest single win: quote basalt per m³ or
      per kg.** Per-slab needs a stock thickness + shell unrolling and is
      NOT unlocked by segmentation (ADR-056).
- [ ] **B-4 [release] — Verify token prices** against the three providers'
      price pages and bump `pricing_version` in `config/pricing.yaml`
      (currently `2026-08-v3`). Fix D-3 in the same pass. Feeds PR-2's
      reservation upper bounds.
- [ ] **B-5 [release] — Structural profile sign-off**, or Production v1
      ships with an explicit release note that profile-threshold breaches
      report `warn`, never `fail` (ADR-036/039 — deliberate).
- [ ] **B-6 — Supply or retire `SCOPE.md`** (and `SPEC_PHASE2.md`,
      `PHASE2_PLAN.md`, the "Master Build Order", the "First Action"
      document) — still cited, still never existed in this repository.
- [ ] **B-7 — Ruling: should a hollow plinth carry a CLOSED top face?**
      Changes STEP bytes for hollow-plinth designs, so it needs an
      explicit yes (ADR-053). Not a v1 blocker.
- [ ] **B-8 [release] — Named approvers for PR-8:** structural engineer,
      drafter, workshop/fabricator, rigging reviewer. A design cannot
      become `issued_for_fabrication` without them.
- [ ] **B-9 — Confirm or deny the four unattributed render-worker starts**
      (12:12:30 / 12:17:29 / 12:25:36 UTC on 2026-08-27, after each
      deliberate stop; the earlier ~06:59/~07:19 pair you already
      confirmed). Every automated channel was eliminated by read-only
      forensics; manual Docker Desktop action is the surviving
      explanation, but it is attributed by elimination, not admission.

---

## 2. THE WORK QUEUE — the approved Production v1 program, in order

Each entry is one loop iteration: `/lf-next` → approve → `/lf-build` →
`/lf-gate` → `/lf-close`. The seven operator amendments (2026-08-27) are
binding; the slice notes below carry the ones that bite.

### Closed under this program

- [x] **PR-0 — Both render-worker states first-class (2026-08-27,
      ADR-057).** D-9's six worker-state tests rewritten to assert the
      honest contract in BOTH states; D-9b's real defect fixed — the
      LUXEXCHANGE manifest now seals canonical `excluded` entries for the
      non-reproducible Blender tier, so the package content digest no
      longer follows the render worker's uptime; a new $0 regression test
      pins it. Baseline failures reported red before any edit; suite
      green worker-up AND worker-removed; full roster re-run. Evidence:
      `PRODUCTION_V1_REPORT.md`.
- [x] **PR-3 — Loopback by default (CLOSED 2026-08-28, ADR-058: auto
      gate PASS + operator visual gate PASS).** Host publishes bind
      `127.0.0.1` for backend 8000 / frontend 5173; `gate_pr3_auto.py`
      (roster script 19, split static/live) asserts the compose file AND
      the live sockets on every roster run; the operator's phone on the
      same Wi-Fi could not reach either port while localhost worked
      unchanged. `docs/operator/11_network_privacy.md`; LIMITATIONS §19
      records that the API has NO authentication and loopback is the
      only lock; no LAN-enable path ships. Evidence:
      `PRODUCTION_V1_REPORT.md`.

### Next up

- [ ] **PR-1 — Per-axis fabrication limits.** `max_module_m` `{x,y,z}`
      preserved end-to-end (mapper `spec_mapper.py:204` currently
      collapses it with `max()`); every limit positive or refused loudly;
      segmentation and the fabrication gate bind each axis to its own
      limit; the Designer API keeps its deliberate cubic-scalar path.
      **Amendment 2:** explicitly scalar Designer/API requests stay valid
      cubic envelopes — only designs whose `{x,y,z}` spec was collapsed
      (distinguished by stored request/spec provenance) get the
      `needs_input` rebuild request. Test: a 2.4 × 2.4 × 2.2 m envelope
      splits/refuses a module whose Z exceeds 2.2 m.
- [ ] **PR-2 — Hard spend caps.** Atomic DB-backed reservations (BEGIN
      IMMEDIATE) taken before dispatch, settled to actual cost, released/
      recorded on provider errors; concurrent test proving two calls
      cannot jointly exceed a cap (test doubles only). **Amendment 1:**
      $25/UTC-day is the global hard ceiling; $5 binds per LOGICAL run
      (one Council run / one fabrication run incl. repairs / one critique
      run incl. rounds); retries and resumes keep the original spend-scope
      ID; reservations use a demonstrably cap-safe upper bound, not the
      chars/4 estimate, documented and gated for text AND vision.
- [ ] **PR-4 — Honest module transport costing.** Per-module masses
      carried into the drivers; refuse when any module exceeds
      `truck_payload_kg`; deterministic first-fit-decreasing allocation
      respecting payload AND `modules_per_trip`. **Amendment 3:** the BOM
      calls it "a deterministic conservative feasible allocation", never
      minimal; prints every trip's module IDs, masses, total load and
      remaining capacity; `not_computable` when no valid allocation —
      never the old lower-bound `max(ceil(mass/payload),
      ceil(modules/per_trip))` presented as a trip count. Adversarial
      tests: module > payload; lower bound < feasible count; bed binds;
      weight binds.
- [ ] **PR-5 — AI contract and document repair.** "per element" →
      "per module after segmentation" in the GEOMETRIST prompt
      (`prompts.py:284-285`, `:332`) with the pinning test rewritten; the
      two stale `needs_input` gate bases (`gates.py:876/897`); the
      critique scorer's total-mass-vs-lift basis (`critique.py:459-461`);
      operator doc 07; stale not-built claims (LIMITATIONS §12
      "segmentation is slice C", §11 "four primitives" mapper note,
      `PHASE_11_12_13A_REPORT.md` "9B untouched", `PHASE_6_REPORT.md`
      self-contradiction); the D-10 sweep across ALL gates for roadmap
      phrases inside assertions, frozen sets and rotating unknown-name
      examples. The 2,685.7 kg array figure is settled (gate transcript;
      2,988 was a transposed ratio, already corrected at its four sites).
- [ ] **PR-6 — Costing tie-off machinery.** **Amendment 4 first:** one
      trusted measurement path per material for volume/mass, exposed
      finishing area (never proportional allocation of total surface),
      fabrication hours, purchase, split seams, and cross-material joints
      — each joint's owning rate defined or explicitly selected, never
      double-billed, never silently one side. Then: per-element costing
      replacing the HTTP 409 mixed-material refusal; shared crane/
      transport/install added once at assembly level; confirmed intake
      budgets bound to the BOM budget gate (LIMITATIONS §15); incomplete
      costing structurally unable to render a total or a quote;
      client-ready quote only as a test fixture until B-3 lands. Deliver
      the operator's 39-entry rate-card checklist + B-4 worksheet.
- [ ] **PR-7A — Checkpoint/resume engine.** Artifact-boundary checkpoints
      on the hardened `JobRow`; kill-and-resume gate at every boundary
      asserting an identical final `content_digest`.
- [ ] **PR-7B — Retry, failure classes, job status.** Transient-only
      auto-retry with spend attribution; failure class + one safe next
      action persisted; operator status API/UI for active, failed,
      resumable, completed; no silent partial success.
- [ ] **PR-7C — Backup and cleanup.** Scheduled-backup instructions the
      operator installs (not auto-installed), retention/rotation,
      restore verification over N packages (not just the newest),
      controlled reaping for `data/geo_scratch/` and render scratch
      (closes D-1).
- [ ] **PR-8 — Release states and human approvals.** `draft` →
      `pre_fabrication` → `issued_for_fabrication`; approvals by the B-8
      names; rigging required when the fabrication gate says rigging
      input is required — not from a possibly-null threshold.
      **Amendment 6:** approvals are mutable business records and never
      enter the deterministic package — issuance is an immutable
      `design_issuances` snapshot (issuance ID/revision, approval digest,
      package digest, timestamp, immutable artifact); an issued package
      is deterministic per (design_id, issuance_id); changed approvals
      create a NEW revision, never rewrite an issued one. Plus the
      drawing-package assessment: what exists, what is buildable
      in-scope, what is recorded as required external professional input
      — never fabricated content.
- [ ] **PR-9 — Visual walkthrough + final acceptance gate.** One
      PowerShell document ordering all twelve B-1 visual gates with costs
      stated. Then `gate_production_v1_auto.py` — **Amendment 7:** three
      POSITIVE end-to-end projects (segmented single-material basin;
      valid mixed-material assembly with per-material costing; a
      multi-element project exercising hydraulics, lineage and approvals)
      each through intake-fixture → spec → assembly → segmentation →
      validation → costing → reproducible exports → DesignDNA → backend
      restart → reload/verify → backup → restore-verify; SEPARATE
      negative cases (oversized discrete array, missing approvals,
      module > payload, ambiguous pre-axis-limit history, reservation
      contention); restart proven by a host-side PowerShell orchestration
      gate if the in-container gate cannot restart safely — never a faked
      restart. $0, offline, both worker states.

### Deliberately OUTSIDE Production v1 (operator ruling 2026-08-27)

- **Phase 6 slice D** (free-form: `basin_elliptical`, `basin_spline`,
  `spline_loft_mass`), **Phase 10** (autonomous vision-driven revision),
  native DWG/SKP, mobile UI, semantic search. Do not widen the release
  to these unless the acceptance gate genuinely requires it.

### Debts — small, real, unscheduled

Pick one up when a slice finishes early. Each is one commit.

- [ ] **D-1 — `data/geo_scratch/` is never reaped.** Folded into PR-7C.
- [ ] **D-2 — The synthetic demo Council session lies.** `54e12d62` shows
      `completed`, `$1.2624`, zero `ai_calls` rows. Mark it or delete it.
- [ ] **D-3 — Doc drift: LIMITATIONS §4 says `pricing.yaml` ships
      `2026-07-v1`; the file says `2026-08-v3`.** Fix with B-4.
- [ ] **D-4 — `PHASE_11_12_13A_REPORT.md` still says "Phase 9B and Phase
      10 are untouched".** Folded into PR-5.
- [ ] **D-5 — The repair loop has never rescued a run.** Revisit when the
      failure surface changes; rename honestly if unchanged.
- [ ] **D-6 — The three.js app chunk exceeds Vite's 500 kB warning.**
- [ ] **D-7 — DAE/3MF exporters need two small pip packages**
      (`pycollada`, `networkx`) — a download, so the operator's call.
- [ ] **D-8 — The Council panel has no `use_precedents` toggle.**
- [ ] **D-10 — Gate examples with a built-in expiry.** Bit three times
      (6a1 exact-four, 6a2 `water_wall`, 6a1 "slice C" string). The tell
      is a roadmap phrase inside an assertion. Full sweep folded into
      PR-5; re-sweep before slice D ever widens the registry.
- [ ] **D-11 — Radial segmentation for round vessels.** Needs the
      operator's `gate_phase6c2_visual.md` §2 ruling first.
- [ ] **D-12 — `blade_fin_array`/`lotus_petal_array` have no module
      decomposition** (hub + N blades; blade-root seam needs its own
      proof).
- [x] **D-9 — CLOSED by PR-0 (2026-08-27, ADR-057).** The six
      worker-state tests now assert the honest contract in both states;
      reported red on the pristine image before any edit (five by name,
      verbatim in `PRODUCTION_V1_REPORT.md`), then green in both states
      after the fix. The container-start attribution question lives on as
      B-9; the operational lessons (pin state at start AND end; shared
      containers; `rm -sf` not `stop` for a worker-down run) are recorded
      in ADR-057 and the D-9 history in git.
- [x] **D-9b — CLOSED by PR-0 (2026-08-27, ADR-057).** The package
      content digest no longer depends on render-worker state: the sealed
      manifest carries canonical `excluded` entries for the
      non-reproducible tier, and a $0 regression test seals the same
      design from both states' results and asserts byte-identical
      packages. Clean full-suite runs now exist in BOTH worker states —
      verbatim in `PRODUCTION_V1_REPORT.md`.

---

## 3. Loop discipline — the rules that do not bend

Carried from `CLAUDE.md`. The commands in `.claude/commands/` enforce them;
this is the human-readable version.

1. **Plan before code on any new slice, and wait for approval.**
2. **No stubs, no mocks, no placeholders, no TODO.** Written means working
   and proven by a test on real data.
3. **Every slice ends at a hard gate**, split: `gate_*_auto.py` ($0 forever,
   non-interactive, clear exit codes) and a `gate_*_visual.md` the operator
   checks by eye.
4. **One commit per gate**, rolled back as one unit, with `LIMITATIONS.md`,
   `DECISIONS.md`, the phase report and **this file** updated in it.
5. **Never claim it works without the command and its real output.**
6. **ADR-009:** no endpoint, model string, SDK shape or price from recall.
   Fetch live docs, record the fetch date.
7. **ADR-005:** AI-written code executes only in the sandbox. Never in tests,
   never in the gate.
8. **Say the projected cost before spending.** Caps: $5/session, $25/day
   (PR-2 re-scopes the $5 to a logical run, per Amendment 1).
9. **More than one session works this repo at once.** Before rebuilding
   containers, stashing, or touching another session's files: check, ask,
   coordinate. Local main can be ahead of origin — push after every close.
10. **Suite evidence pins the render-worker state at start AND end of the
    run.** For a worker-down run, REMOVE the container
    (`docker compose rm -sf render-worker`); recreate it with
    `docker compose --profile render up -d render-worker` when needed.
