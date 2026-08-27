# NEXT.md — the loop state file

**This file is the single source of truth for "what is left".** It is read at
the start of every session (`/lf-orient`) and rewritten at the end of every
slice (`/lf-close`). If this file and a phase plan disagree, this file is
stale and must be corrected in the same commit as the work.

Last updated: 2026-08-27 — Phase 6 slice C2 (segmentation) closed. Previous
rewrite 2026-08-26, after the merge to main (`99569b2`) surfaced 17 commits
of work (Phases 6A1 through 15E) that the version before it predated.
Derived from the phase reports, LIMITATIONS.md and DECISIONS.md as they
stand — not from memory.

---

## 0. Where the build actually stands

| phase | state | evidence |
|---|---|---|
| 1 — providers, spend caps, audit, gates | **CLOSED** | gate PASS 2026-08-01, `PHASE_1_REPORT.md` |
| 2 — geometry kernel, STEP/GLB, determinism | **CLOSED** | gate PASS 2026-08-04, canonical hash `e1a59fa6…` |
| 3 — the AI Council | **CLOSED** | gate PASS 2026-08-07, live $0.843842 |
| 4 — fabrication loop (AI writes CAD, sandbox runs) | **CLOSED** | gate PASS 2026-08-17, live $0.046777 |
| costing engine | **BUILT, gated, starved; reaches assemblies since 2026-08-27** | ADR-031/056; rate card still unfilled (B-3, now 39 nulls) |
| 6 — primitive library | **A1 CLOSED; A2 + B + C1 + C2 BUILT (10 primitives, segmentation); D not built** | auto gates PASS 2026-08-20 / 2026-08-26 / 2026-08-27 (ADR-052–056); pending: live gate `gate_phase6_visual.md`, eye gates 6b + 6c + 6c2 |
| 7A — assembly surface (API, manifest persistence) | **BUILT** | implemented 2026-08-21, `PHASE_7_COMPLETION_PLAN.md` §7A |
| 8 — L5 validation gates (structure/fabrication/hydraulics) | **BUILT, auto-gated** | auto PASS 2026-08-21 + 8b re-gate; visual pending |
| 9A — LUXEXCHANGE export package | **BUILT, auto-gated** | auto PASS 2026-08-21, re-proven 08-24; visual pending |
| 9B — Blender render worker (+9B.5 convert) | **BUILT, auto-gated** | auto PASS 2026-08-24, ADR-043/045; visual pending |
| 5 — vision critique loop | **BUILT, auto-gated, RUN LIVE** | auto PASS 2026-08-24; live 3-round run $0.042916, 5 deltas applied; visual pending |
| 10 — vision-driven revision loop (R1–R7) | **PLANNED, NOT built** | `PHASE_10_VISION_CRITIQUE_PLAN.md`; 9B dependency now satisfied |
| 11 — DesignDNA precedent store | **BUILT, auto-gated** | auto PASS 2026-08-22, ADR-038; visual pending |
| 12 — brief intake with provenance | **BUILT, auto-gated** | auto PASS 2026-08-22, ADR-039; closed Phase 8's hydraulic dependency |
| 13 — recovery + hardening | **Slice A only** | auto PASS 2026-08-22, ADR-040; NO resumable job runner yet |
| 14 + 14b — Designer Workspace, Blender-style controls | **BUILT, auto-gated** | auto PASS 2026-08-24, ADR-044/046; visual pending |
| 15 A–E — designer UX, draft preview, projects/variants | **BUILT, auto-gated** | auto PASS 2026-08-24, ADR-047–051; visual pending |

**Latest full roster (2026-08-27, clean rebuild): 17 of the 18
`gate_*_auto.py` scripts PASS, 0 FAIL.** Only `gate_phase9b_auto` was
not run — it requires the worker up. The gate roster is robust to
render-worker state (9a reports the four Blender formats `unavailable`
with it down and `included` with it up, and passes either way, ADR-045),
so this result stands regardless; **the pytest SUITE is not, and its
outstanding failure is recorded at D-9 below rather than rounded off.** Note `gate_phase14_auto` is SPLIT: the
container run covers `geometry`, and `python scripts\gate_phase14_auto.py
--frontend-only` on the host covers `frontend`; both were run, both PASS. Total live spend recorded since Phase 4 closed: $0.042916
(Phase 5 run) plus a possible ~$0.84 unverified incident exposure (B-2).

---

## 1. BLOCKERS — these need the operator, not the agent

- [ ] **B-1 — Walk the visual gates.** *Blocks: closing phases 5, 8, 9A, 9B,
      11–15; they are all auto-gated only and "nobody has looked at the
      pixels."* Eight checklists are outstanding: `gate_phase5_visual.md`,
      `gate_phase8_visual.md`, `gate_phase9a_visual.md`,
      `gate_phase9b_visual.md`, `gate_phase11_13a_visual.md`,
      `gate_phase14_visual.md`, `gate_phase14b_visual.md`,
      `gate_phase15_visual.md`, `gate_phase6_visual.md` — the Phase 6
      LIVE gate (≈$0.90–1.10 spend, the only one that costs money; it is
      THE operator's gate the phase is named for) — and
      `gate_phase6b_visual.md` (treatments + nozzles by eye, $0),
      `gate_phase6c_visual.md` (the six new masses by eye, $0) and
      `gate_phase6c2_visual.md` (segmentation, $0 — **it carries the one
      question only the operator can answer: does your shop cut a round
      basin on a square grid or radially?**). First:
      `docker compose up --build -d`
      (backend AND frontend images changed), optionally
      `docker compose --profile render up -d render-worker`. Coordinate with
      any other live session before rebuilding shared containers.
- [ ] **B-2 — ADR-033 incident: check the three provider consoles** for a
      possible ~$0.84 test-leak spend on 2026-08-20 (a full-suite run outside
      Docker leaked real `.env` keys past the test fixture; the local audit
      rows died with the test temp DB, so only the consoles hold the truth).
      Asked for in `PHASE_6_REPORT.md`; still unanswered.
- [ ] **B-3 — Fill `config/costing.yaml`** (now `2026-08-v2`, **39 null
      entries, up from 33**). *Blocks: any client-facing quote.* `GET
      /api/costing/rate-card` names every one. Slice C2 added six: a
      per-material `seam` rate (quote it `per: m` for a welded run or
      `per: m2` for a bedded face — whichever your shop works in) plus
      `install.truck_payload_kg` and `install.modules_per_trip`. Those six
      are the price of the seam and transport lines becoming real.
      **Biggest single win is unchanged: quote basalt per m³ or per kg.**
      Per-slab is NOT unlocked by segmentation and never was — it needs a
      slab THICKNESS (absent from materials.yaml) and shell unrolling
      (LIMITATIONS §10, ADR-056).
- [ ] **B-4 — Verify token prices** against the three providers' price pages
      and bump `pricing_version` in `config/pricing.yaml` (currently
      `2026-08-v3`). *Blocks: trusting any cost number.* Fix D-3 in the same
      pass.
- [ ] **B-5 — Structural profile sign-off.** `config/gate_profiles.yaml`
      ships `signed_off: false`, so profile-threshold breaches report `warn`,
      never `fail`; `overturning_safety_factor` stays `needs_input` until a
      structural engineer signs a value (ADR-036/039 — deliberate, not a
      defect). Sign it when a real project needs `fail` to bind.
- [ ] **B-6 — Supply or retire `SCOPE.md`.** Still cited as authority by
      the reports and `registry.py`, still never existed in this repository.
      Same for `SPEC_PHASE2.md`, `PHASE2_PLAN.md`, the "Master Build Order"
      and the "First Action" document.
- [ ] **B-7 — Ruling: should a hollow plinth carry a CLOSED top face?**
      Today it is an open tube (A1 design; the open ring in the operator's
      viewport). Capping it makes it read as a pedestal and widens every
      stack seat — but it changes STEP bytes for hollow-plinth designs, so
      it needs an explicit yes, with slice B (profiles) the natural moment.
      ADR-053 records why it was NOT bundled into the bearing fix.

---

## 2. THE WORK QUEUE — in order

Each entry is one loop iteration: `/lf-next` → approve → `/lf-build` →
`/lf-gate` → `/lf-close`.

### Next up

- [x] **W-1 — Phase 6 slice A2 tie-off — BUILT 2026-08-26, auto gate PASS
      at $0 (ADR-052).** The fabrication → design bridge (one shared
      persistence path, byte-identical STEP across both paths and across
      two processes), lineage columns, two-tier prompt surface (11,267 →
      8,144 chars measured), honest bridge failure, 6 new tests. What
      remains is the operator's LIVE gate — `gate_phase6_visual.md`,
      ≈$0.90–1.10 — now queued under B-1 with the other visual gates.
      Mixed-material costing moved to W-7 (LIMITATIONS §11 says why).
      **Same-day additions (ADR-053 + operator-reported fixes):** the
      operator's screenshots exposed a live design bearing 1,550 kg on a
      2 mm lip — stack_on now enforces a seat-bearing floor from the
      signed §2.1 numbers. Plus five UI fixes from live use: rail label
      clipping, JSON-blob check values, stepper deep-links (Validate →
      Checks, Export → Output), the workspace reopening the operator's
      OWN design instead of the shared DB's newest, and the Cascade tool
      labelled as the legacy single-primitive tool. Rebuild any
      pre-2026-08-26 assembly before quoting it.
- [x] **W-2 — Phase 6 slice B — BUILT 2026-08-26, auto gate PASS at $0
      (ADR-054).** weir_edge/coping/pool_edge drawn INTO the basin's
      revolved profile; nozzle_ring cut by trusted code with exact volume
      arithmetic (59,992 mm³ measured = expected); weir/nozzle numbers
      wired from `hydraulic_network` with refusal-not-default; the signed
      feature/radius floors now load-bearing (316L formula included).
      Plan correction recorded openly (ADR-054 §2): crest-elevation
      consistency replaced the incoherent weir-depth derivation. Operator
      eye gate: `gate_phase6b_visual.md` ($0), queued under B-1. Slice
      limits (360° crests, one bore size, basin-only) in LIMITATIONS §11.
- [x] **W-3 — Phase 6 slice C1 — BUILT 2026-08-26, auto gate PASS at $0
      (ADR-055).** Six masses (registry 4 → 10), arrays fusing in index
      order with the tangency band refused, conservative seats for rect
      footprints and the torus chord. THE GATE C COMPOSITION proven:
      24-blade array in a 3-primitive assembly, byte-identical STEP
      `956436c1…` across two processes. Eye gate `gate_phase6c_visual.md`
      queued under B-1. **Correction (plan §8.1):** segmentation was
      wrongly bolted onto this entry — it is costing-driver work and is
      now its own item below.
- [x] **W-3b — Phase 6 slice C2 — BUILT 2026-08-27, auto gate PASS at $0
      (ADR-056).** An element over `fabrication.max_module_m` is now CUT by
      the kernel into modules, and both workshop limits bind on the modules:
      a 5 m basalt basin that weighs 11,346 kg as one piece and was
      previously REFUSED now builds as 9 modules, heaviest 1,472 kg.
      Volume conserved to 0.0000000000%; the module count is measured
      (a hollow tube's 3x3x2 grid predicts 18 pieces and truly yields 16);
      the quartered basin's seam area and perimeter match hand arithmetic
      exactly, counted once per interface, not once per cut face.
      `blade_fin_array`/`lotus_petal_array` are refused by name rather
      than fragmented (a naive grid gives 25 pieces, lightest 0.9 kg).
      **Two of three** costing lines moved from `not_computable` to
      `missing_rate`; `crane_pick_kg` is now the heaviest MODULE.
      **Plan corrections recorded openly (ADR-056):** per-slab purchase is
      NOT unlocked by segmentation (see B-3); and the slice had to fix two
      latent defects first — `/api/costing/bom/{id}` returned HTTP 500 for
      every assembly ever built, and `/api/costing/bom/{id}.txt` (the
      document handed to a client) returned 404 for every design. Eye gate
      `gate_phase6c2_visual.md` queued under B-1, and it carries a real
      question for the operator about how the yard cuts.
- [ ] **W-4 — Phase 6 slice D: free-form.** `basin_elliptical`,
      `basin_spline`, `spline_loft_mass`. **Gate D:** a free-form mass
      composed with two library primitives — *or* an honest LIMITATIONS
      entry saying which part of the watertight-by-construction guarantee
      does not hold. Both acceptable; neither is "tune until green".
- [ ] **W-5 — Phase 10: the vision-driven revision loop.** The 9B blocker is
      cleared. Build to the corrected plan (R1–R7): round-over-round image
      comparison, in-frame scale cues, `{element_id, parameter, from, to}`
      deltas resolved against the live registry, per-delta
      accepted/clamped/rejected outcomes, Phase 8 re-gate every round with
      revert-on-regression, per-run cost ceiling. Renders cost minutes, not
      seconds (≈29 s per 4-view round at gate settings) — size
      `max_vision_iterations` against that.
- [ ] **W-6 — Phase 13 slices B+: the resumable job runner.** Checkpoint at
      artifact boundaries on the hardened `JobRow` contract; auto-retry
      transient only; kill-and-resume gate at every boundary asserting an
      identical final `content_digest`; per-job status UI naming the failure
      class and one next action; retry spend as its own dashboard line.
- [ ] **W-7 — Costing tie-off.** After B-3 (the rate card, including the
      six new entries): intake budget wired to the binding budget check
      (LIMITATIONS §15), **per-element costing for mixed materials** — an
      assembly with two materials is refused with HTTP 409 today rather
      than mispriced — and the first client-ready quote. The seam rate and
      the module/seam drivers landed with W-3b; what is left here is
      money, not measurement.
- [ ] **W-8 — Final acceptance run** against the completion gate in
      `PHASE_7_COMPLETION_PLAN.md`: brief → spec → assembly → gates → render
      → critique → deltas → re-solve → export package → DesignDNA precedent,
      surviving a backend restart.

### Debts — small, real, unscheduled

Pick one up when a slice finishes early. Each is one commit.

- [ ] **D-1 — `data/geo_scratch/` is never reaped.** 23 directories and
      counting. Harmless, not a cleanup story. (LIMITATIONS §9)
- [ ] **D-2 — The synthetic demo Council session lies.** `54e12d62` shows
      `completed`, `total_cost_usd $1.2624`, zero `ai_calls` rows. Mark it or
      delete it. (The `/api/ops/costs` two-ledger view already exposes it.)
- [ ] **D-3 — Doc drift: LIMITATIONS §4 says `pricing.yaml` ships
      `2026-07-v1`; the file says `2026-08-v3`.** Fix with B-4.
- [ ] **D-4 — `PHASE_11_12_13A_REPORT.md` still says "Phase 9B and Phase 10
      are untouched"** — stale since 2026-08-24; 9B is built and auto-gated.
      One-line correction with a date.
- [ ] **D-5 — The repair loop has never rescued a run** (rounds 2–3
      diagnostic, not corrective, across four live runs). Revisit once Phase
      6 A2 changes the failure surface; rename honestly if unchanged.
- [ ] **D-6 — The three.js app chunk exceeds Vite's 500 kB warning.**
      Performance item, not a failed build. (PHASE_15_REPORT)
- [ ] **D-7 — DAE/3MF exporters need two small pip packages** (`pycollada`,
      `networkx`) — a download on the operator's connection, so his call, not
      done behind his back. (LIMITATIONS §13)
- [ ] **D-8 — The Council panel has no `use_precedents` toggle** though the
      API supports it. (LIMITATIONS §17)
- [ ] **D-10 — Gate examples with a built-in expiry.** Slice C1 broke two
      older gates by widening the registry: 6a1 pinned the EXACT four
      primitives, 6a2 used `water_wall` as its example "unknown" primitive
      until C1 made it real. Both corrected 2026-08-26 (ADR-055; 6a1 on
      the operator's ruling). Sweep the other gates for the same pattern
      — frozen sets and hard-coded not-yet-built names — before slice D
      widens the registry again.
      **It bit a THIRD time on 2026-08-27 (ADR-056):** `gate_phase6a1_auto`
      §4 asserted "element bigger than max_module_m (segmentation is slice
      C)" and matched the literal string `"slice C"` in the refusal — so
      the slice that built segmentation turned it red. Corrected to assert
      the refusals A1's own semantics still preserve. **The tell is a
      roadmap phrase inside an assertion** ("slice C", "not built yet",
      "arrives in"). Grep the gates for those strings before slice D.
- [ ] **D-11 — Radial segmentation for round vessels.** Today a round
      basin is cut on an axis-aligned square grid; a stone mason would
      more likely cut pie segments. Needs the operator's ruling first
      (`gate_phase6c2_visual.md` §2 asks it). Not a defect — the grid is
      geometrically exact and works for every shape in the library — but
      probably not how the yard works. (ADR-056, LIMITATIONS §11)
- [ ] **D-12 — `blade_fin_array`/`lotus_petal_array` have no module
      decomposition.** Refused by name when oversized, which is honest but
      is not the answer. The real one is hub + N blades, and the count is
      exact from `blade_count`; what it needs is the blade-root seam
      measured and proven. (ADR-056)
- [ ] **D-9 — Five export tests assume the render worker is DOWN** and fail
      with it running (`assert 'included' == 'unavailable'`; three in
      `test_export_package.py`, two in `test_assembly_api.py`). Found
      2026-08-26 running the full suite with the worker up; reproduced on
      pristine image code, so it predates slice A2. The 9A GATE already
      accepts both worker states — the tests should too. Until fixed,
      "full suite green" is only true with the render worker stopped.
      **Update 2026-08-27:** a SIXTH test joins them intermittently —
      `test_export_package_is_reproducible_and_self_verifying` failed on
      two different digests in a full worker-up suite run, but PASSES when
      `test_assembly_api.py` is run alone with the worker up, and passes
      with the worker stopped. So it is load-sensitive, not deterministic:
      under a loaded 4-core box a Blender-tier convert job apparently
      lands in one export and not the other, and the format statuses are
      sealed into the manifest. Fix it with the other five — the package
      digest should not depend on whether an explicitly
      NON-reproducible tier happened to finish.
      **Attribution, 2026-08-27 — six starts, all pointing at a human
      hand, four of them by elimination rather than confession.** The
      operator confirmed starting `luxuryform-render-worker-1` himself via
      Docker Desktop for the ~06:59 and ~07:19 pair. Four more followed,
      after a `docker compose stop render-worker` each time: 12:12:30,
      12:17:29 and 12:25:36 (docker `TimeNano`). The 12:25:36 start landed
      three minutes into a four-minute `pytest tests/test_export_package.py`
      run and flipped its result.
      Session `luxuryform-61` ran read-only forensics and eliminated every
      automated channel: `RestartPolicy=no` / `RestartCount=0`; no
      scheduled task matching docker/compose/luxuryform; no host process
      with `compose` in its command line except VS Code's compose language
      servers, which parse and execute nothing; the only running WSL
      distro is `docker-desktop` itself, with no compose process inside;
      no Claude cron jobs; and all three peer sessions denied it with
      evidence.
      **The interval is the evidence, and my first note got it wrong.** I
      wrote "roughly three minutes after each stop", implying a timer. The
      real gaps are **33 seconds** (12:17:29) and **3 m 05 s** (12:25:36).
      That variance is human-like, not timer-like, and it is what makes
      manual Docker Desktop action the surviving explanation.
      **Still UNCONFIRMED for the four:** attributed by elimination, not
      by admission. `luxuryform-61` has put the question to the operator.
      Do not record it as settled until he answers — this file has already
      carried one confidently wrong cause (see the OOM correction).
      **Three lessons, all binding on any future suite claim:**
      (a) pin and re-verify the render-worker state at the END of a run,
      not just the start; (b) these containers are SHARED — check
      `ListAgents` and coordinate before assuming you own the worker;
      (c) for a worker-DOWN run use `docker compose rm -sf render-worker`
      rather than `stop` — **a removed container has no Start button in
      Docker Desktop to click** — and recreate it with the render profile
      when you need it up. (`luxuryform-61`'s measure, adopted here.)
- [ ] **D-9b — The C2 code has no clean full-suite run.** Best measured
      result on it: `432 passed, 1 failed in 796.34s`, the failure being
      the D-9 test above. Every attempt to get a clean one was
      contaminated by the worker restarts described in D-9. Nothing was
      edited to make it pass. Close this by fixing D-9 (make the five
      tests accept both worker states, as the 9A gate already does),
      then re-running the suite once — not by re-running it hoping for
      a quiet window.

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
8. **Say the projected cost before spending.** Caps: $5/session, $25/day.
9. **More than one session works this repo at once.** Before rebuilding
   containers, stashing, or touching another session's files: check, ask,
   coordinate. Local main can be ahead of origin — push after every close.
