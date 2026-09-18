# NEXT.md — the loop state file

**This file is the single source of truth for "what is left".** It is read at
the start of every session (`/lf-orient`) and rewritten at the end of every
slice (`/lf-close`). If this file and a phase plan disagree, this file is
stale and must be corrected in the same commit as the work.

Last updated: 2026-09-16 (2nd) — **SC-A1 CLOSED (ADR-072): `crescent_ring`,
the crescent-moon sculpture primitive — registry 12 → 13.** Vertical
partial-torus crescent (tube Ø80–500, span 90–330°, gap azimuth,
optional oval section), NEW material `stainless_316l_cast` (welded &
mirror-polished, PROVISIONAL fabricator-set envelope); photo replica
measures 1950 × 1950 × 350 mm exactly matching the owner's reference
dims; two-process STEP determinism pinned; assembly-proven (plinth +
stack_on, 5938 kg, PRE_FABRICATION); `height` is derived, never a spec
key (refused naming the relationship). **Scoped OUT honestly: the
reference's ORGANIC LIQUID FORMS are not claimed — hand-sculpted
free-form remains a future slice.** New roster script 31
`gate_sca1_auto.py` (63/63); msa1 54/54, FF-A2 63/63, PR-5 PASS,
FF-A1 36/36, FF-A3 55/55 (fixture regenerated via its designed path);
40 new tests; 142 targeted passed. Environment caveat unchanged
(host chain only; container chain + fresh full suite DEFERRED — disk
and engine). Before that:
**MS-A1 CLOSED (ADR-071): `perforated_screen`,
the first mesh-class (perforated-skin) primitive — registry 11 → 12.**
Flat or single-curved 316L sheet with a deterministic circle/hex
through-hole grid; ONE fused-compound boolean subtract; full FF-A1
integrity stack; COMPLETE mass; two-process STEP determinism pinned
(748-hole fixture; 1421-hole realistic panel builds in 17.8 s vs the
120 s sandbox timeout); assembly-proven (plinth + stack_on; basalt seat
refused honestly); export class PRE_FABRICATION with the honest
rate-incomplete BOM. **NOT claimed: this is NOT an open wire lattice —
B-11b stays OPEN and release-blocking until the owner supplies a real
mesh/lattice reference.** New roster script 30 `gate_msa1_auto.py`
(54/54); FF-A2/PR-5/FF-A1/FF-A3 re-run PASS; the exact-set census moved
in gate_ffa2 §1 with a D-10-frozen reason; the FF-A2/FF-A3 jpg checks
now fail on TRACKED jpgs only (host-honesty fix, security property
preserved). Environment caveat unchanged: host Docker engine down —
definitive in-container chain DEFERRED (recorded in ADR-071); host
chain is the standing evidence, NOT claimed as definitive.
Owner-delegated slice (ruling 2026-09-15: "approve and build everything
yourself"), $0, no live calls. Before that:
**D-28 SLICE CLOSED (ADR-070): the
reservation bound is the REAL serialized request envelope
(`min(context_window, utf8_bytes(request) + 256 framing margin)` × rates,
ceiling µUSD), never the whole context window — text requests only;
vision stays on the ADR-061 window bound; the ADR-061 values and the
$5/$25 caps are untouched; the owner ruling of 2026-09-14 is honoured on
every point (no council.yaml change, kimi retained, fail-closed
accounting strengthened, not weakened).** Every hold persists its
`bound_basis` JSON (additive startup-patched column); billed tokens above
the recorded bound engage `ceiling_violated` at settlement even when the
dollars fit; the startup census re-checks every settled text call in
history and locks GLOBALLY on the first falsification; pre-D-28 rows
reach both operator surfaces labelled `PRE_D28_FORMULA`. The measured
FF-A3 hold replays offline at **under $0.20** and the retry now fits
under $5 — FF-A3 Step 6 is UNBLOCKED for a separately cost-approved
retry (ADR-069's binding status stands until that retry runs).
**Environment caveat, recorded honestly:** the host Docker engine did
not start on the build machine, so the definitive in-container suite +
roster re-run is DEFERRED — the full suite ran on a host Python 3.12
venv and three platform fixes landed (the real `routes_ops.py` import
defect, a census-fixture prompt length, the `0.1 + 0.2` drift preamble —
see ADR-070). NOT claimed as the definitive chain. Before that:
**FF-A3 CLOSED (ADR-069)** with the owner's
binding status: **"typed-brief/Council contract implemented and
fixture-gated; live end-to-end selection blocked by D-28 and not
claimed."** A typed brief confirmed in the Brief tab can now reach the
ref-08 lens: the Designer index prints every primitive's parameter
vocabulary and honesty lines generated from the registry; the trusted
mapper covers `freeform_loop`'s 13 keys (12 scalars + `material_id`);
ratios are PLAIN numbers and any unit on one is refused; every Design
Spec is validated at the Designer boundary against the mapper and the
primitive's own arithmetic before it is persisted; a dry design may
carry an empty hydraulic network (schema change B). **What is NOT
claimed: no AI has selected this primitive from prose.** The one
authorized live demonstration (visual Step 6) **RAN and HALTED** after a
single successful call — kimi dropped its connection, its reservation
went UNCERTAIN at the full $3.268608 bound and the retry was refused by
the $5 run cap — so the Council never reached the Designer stage.
**Step 6 = NOT ACHIEVED, never PASS.** Definitive risk-based chain on
image `772e352a34ea`: 20/20 files host==image, suite **737 passed**
worker-REMOVED, **25/25** in-container gates incl. `gate_ffa3_auto`
**55/55**, PR-3 static, four host gates — **and `gate_phase9b_auto.py`
FAILED TWICE, preserved as FAIL and accepted as unrelated measured
infrastructure debt (D-29). This chain is NOT "all gates green."**
Real provider spend for the whole slice: **$0.007725**; reservation
`9077e77a…` remains UNCERTAIN and unreconciled. New debts D-27, D-28
(the next slice), D-29. Before that: **PR-5 CLOSED** (ADR-068: every surface that
describes lifting now says what the fabrication gate measures — the
GEOMETRIST contract, the two gate bases, the critique scorer and the
operator documents all say heaviest MODULE after segmentation and
per-axis envelope; the scorer scores the pick weight with an explicit
basis or returns None, and its silent 1,000 kg lift default is gone;
four documents corrected with dated notes beside preserved originals;
the D-10 sweep is now roster check `gate_pr5_auto` §5 — 8 growth
literals each carrying a real reason, 3 checks converted to timeless
forms; definitive risk-based chain on image `753490ced0af`: suite **720
passed** worker-removed (PR-4's 707 two-state run retained as the
unchanged baseline), all 28 roster gates green in their required
states, visual gate signed 2026-09-08 all six steps YES with the real
design `621d7497…` showing the heaviest of 9 modules, 1,472.19 kg vs
11,346.1 kg). Before that: **PR-4 CLOSED** (ADR-067: the transport
line LOADS the trucks — first-fit-decreasing over the measured
per-module masses, both limits checked unrounded, every trip printed
with its modules, load and remaining capacity, described only as "a
deterministic conservative feasible allocation" — instead of the
retired `max(ceil(mass/payload), ceil(modules/per_trip))` lower bound
that four 6 t modules at a 10 t payload disprove (4 trips, not 3);
definitive two-worker-state chain on final image `a8a6f3218ba8`: suite
**707 passed in BOTH states**, all 27 roster gates green incl.
`gate_pr4_auto` 9/9 sections and the D-10-seven-corrected
`gate_ffa1_auto` 36/36 (three exact symbols, never a wildcard — owner
ruling); operator visual gate signed 2026-09-07 all four steps YES;
the first chain's FAIL, the operator-approved hash-proven recovery
protocol and the new D-26 startup-write race are recorded in
ADR-067 / PRODUCTION_V1_REPORT.md; the rate card's transport entries
remain null and remain the operator's to supply). Before that: **FF-A2 CLOSED** (ADR-066: the
`freeform_loop` hollow-lens primitive — the platform's FIRST free-form
capability — exists end-to-end, PRE-FABRICATION only; definitive
two-worker-state chain on final image `044446e54c0e`: suite **672
passed in BOTH states**, all 26 roster gates green incl.
`gate_ffa2_auto` 63/63 zero-skipped and the D-10-six-corrected
`gate_ffa1_auto` 36/36; operator visual gate signed 2026-09-07 — Q1
YES with the left/right-opening viewing-orientation ruling, Q1b 3-D
scoop ACCEPTABLE, the 570-second render timeout preserved as a
separate operational finding, D-25; the owner's option-(a) ruling
re-derived the retired `rim_ratio` — whose 110 px/55 px landmark
measured the reference's 3-D surface scoop, unmeasurable in any
projection; preserved as history with its honest 1-of-60 FAIL — into
`projected_side_to_apex_band_ratio` measured exactly from the
reference image, 122/139 = 0.877698, band [0.7022, 1.0532], geometry
0.925; the originally approved tube-annulus construction failed
development and is preserved as ADR-066 evidence). Before
that: **FF-A1 CLOSED** (ADR-065, see the queue
entry: incomplete-mass truth + production freeform_integrity_v1, an
internal foundation with NO user-facing capability; visual gate signed
2026-09-04 with the unpasted-digest caveat recorded). Before that: **LF-103A CLOSED 2026-09-02 (e32805f)** and
the **free-form DISCOVERY slice CLOSED 2026-09-03** (ADR-064), closed
strictly as a DISCOVERY result, NOT completed capability:
**reference-faithful geometry and user-facing free-form capability
remain UNBUILT.** Definitive evidence on image `52209e4a6eea`: 540
tests passed in BOTH worker states, all 21 in-container roster scripts
exit 0, PR-3 static+live PASS, 9B + scope audit + Phase 14 frontend
PASS, discovery host gate 217/217 zero skipped, $0, no providers.
Operator visual ruling preserved verbatim: **Step 2 = NO** (probe forms
NOT reference-faithful), BREP-first APPROVED WITH CONDITIONS,
acceptance gate CHANGED (eight conditions), STEP canonical for 316L
CONFIRMED; **B-11b (mesh/lattice reference) stays open and
release-blocking**. The LF-103A close (ADR-063: the export
boundary enforces the gate verdict — FAILED never packages,
PRE-FABRICATION is marked+warranted, legacy zips fail closed, CLEAN is
builder-only until D-24; red-first 9-failed baseline recorded; 39 new +
109 affected tests green; `gate_lf103a_auto.py` = roster script 23,
PASS incl. hermeticity; full-roster re-run on image `9fe4c4328116` —
514 passed in BOTH worker states, all 23 roster scripts green, verbatim
chain in ADR-063; operator personally walked and signed the visual gate
PASS 2026-09-02, verbatim in `gate_lf103a_visual.md`; one commit + push
this close). Next in queue: **the free-form implementation slice**
(planned via `/lf-next` under the CHANGED acceptance gate; its operator
dependencies are B-11b and the fabricator inputs). Master Scope
audit CLOSED same day (ADR-062, countersigned: 31.6/100, one-third
complete; SCOPE.md authoritative). PR-0, PR-3, PR-1, PR-2 closed
(designs `76595edb…`/`313e5d20…` preserved pending a separate ruling).

**Milestone names (owner ruling 2026-09-01, ADR-062, use everywhere):**
Milestone A — **Free-form Sculpture Demonstrator** · Milestone B —
**Internal Fabrication-Geometry Beta** · Milestone C — **Production v1**
(normalized ≥ 80% AND every safety-critical system ≥ 4/5). **The
approved PR-0…PR-9 program delivers Milestone B; it is NOT Production
v1** and must not be described as such.

**Sequence after this audit closes (owner rulings, ADR-060 + ADR-062):**
audit close → **LF-103A** (close the unsafe export boundary — first
implementation slice, does NOT wait for LF-102's engineer values) →
**PR-2.5** free-form discovery (blocked on B-11) → free-form
implementation slice(s) → PR-4 onward. Release blocker B-10 (operator
workflow controls, folded into PR-7B) ruled 2026-08-28.

---

## 0. Where the build actually stands

| phase | state | evidence |
|---|---|---|
| 1 — providers, spend caps, audit, gates | **CLOSED** | gate PASS 2026-08-01, `PHASE_1_REPORT.md` |
| 2 — geometry kernel, STEP/GLB, determinism | **CLOSED** | gate PASS 2026-08-04, canonical hash `e1a59fa6…` |
| 3 — the AI Council | **CLOSED** | gate PASS 2026-08-07, live $0.843842 |
| 4 — fabrication loop (AI writes CAD, sandbox runs) | **CLOSED** | gate PASS 2026-08-17, live $0.046777 |
| costing engine | **BUILT, gated, starved; reaches assemblies since 2026-08-27** | ADR-031/056; rate card still unfilled (B-3, 39 nulls) |
| 6 — primitive library | **A1 CLOSED; A2 + B + C1 + C2 BUILT (10 primitives, segmentation); D RELEASE-BLOCKING (ADR-060, owner ruling 2026-08-28 — see PR-2.5)** | auto gates PASS (ADR-052–056); pending: live gate `gate_phase6_visual.md`, eye gates 6b + 6c + 6c2 |
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
| **PR program (PR-0 … PR-9) — delivers Milestone B, not Production v1 (ADR-062)** | **APPROVED 2026-08-27; PR-0, PR-3, PR-1, PR-2, PR-4, PR-5 CLOSED** | `PRODUCTION_V1_REPORT.md` (historical filename), ADR-057/058/059/061/067/068 |
| **Master Scope audit vs owner's 30-system scope** | **31.6/100 at `bfa5a77` — approximately one-third complete; only Geometry Integrity ≥4/5 among safety-critical systems** | `SCOPE.md`, `DEVELOPMENT_AUDIT.md`, ADR-062 |
| **LF-103A — export boundary enforces the gate verdict** | **CLOSED 2026-09-02** | ADR-063; auto gate + 23-script roster PASS on `9fe4c4328116`, 514 both worker states; visual gate signed 2026-09-02 |
| **PR-2.5 free-form DISCOVERY (not capability)** | **CLOSED 2026-09-03; visual Step 2 = NO — probe forms not reference-faithful; capability UNBUILT** | ADR-064; 540 both worker states + 24-script roster on `52209e4a6eea`; BREP-first approved with conditions; STEP canonical confirmed |
| **FF-A1 — incomplete-mass truth + freeform_integrity_v1 (internal foundation, no user-facing capability)** | **CLOSED 2026-09-04; visual signed (digest strings not pasted — caveat recorded)** | ADR-065; 591 both worker states + 25-script roster; in-container gate 35/35 zero skipped ×3 on `704fefba74fa` (one uncaptured 1/35 first-run transient recorded honestly); fifth D-10 instance corrected in the PR-2.5 host gate (218/218) |
| **FF-A2 — `freeform_loop`, the FIRST free-form primitive (ref-08 hollow lens, PRE-FABRICATION only)** | **CLOSED 2026-09-07; visual signed 2026-09-07 (Q1 YES, Q1b scoop ACCEPTABLE; 570 s render timeout = D-25, verdict by permitted viewport inspection)** | ADR-066; 672 both worker states + 26-script roster on final image `044446e54c0e`; `gate_ffa2_auto` 63/63 zero skipped; corrected `gate_ffa1_auto` 36/36 (sixth D-10 instance — its honest 1/35 FAIL on the operator's real design preserved); failed tube-annulus construction + measured kernel cliff preserved as evidence |
| **PR-4 — honest module transport costing (trips LOADED, never bounded)** | **CLOSED 2026-09-08; visual signed 2026-09-07 (all four steps YES)** | ADR-067; 707 both worker states + 27-script roster on final image `a8a6f3218ba8`; `gate_pr4_auto` PASS (disproof 3-vs-4 pinned; rate card sha-identical); first chain FAILED at `gate_ffa1` §1 = D-10 instance seven (census correctly caught the new consumer; corrected as three exact symbols by owner ruling), recovered under an operator-approved hash-proven protocol (15 production/test/config/build hashes identical); D-26 startup-write race recorded |
| **PR-5 — AI contract and document repair (one story about lifting)** | **CLOSED 2026-09-08; visual signed 2026-09-08 (all six steps YES; real design `621d7497…` reads heaviest of 9 modules, 1,472.19 kg vs 11,346.1 kg)** | ADR-068; risk-based definitive chain on `753490ced0af`: 26 files host==container, 132 focused + `gate_pr5_auto` 49/49, suite **720 passed** worker-removed (PR-4's 707 two-state evidence retained as the unchanged baseline), all 28 roster gates green (25 hermetic worker-removed, 9B worker-up, PR-3 static+live, 4 host gates); scorer's silent 1,000 kg default removed; D-10 sweep is now a roster check |

| **FF-A3 — a typed brief can ask for the ref-08 loop** | **CLOSED 2026-09-14 with the binding status "typed-brief/Council contract implemented and fixture-gated; live end-to-end selection blocked by D-28 and not claimed"; visual Steps 1–5 YES, Step 6 NOT ACHIEVED (never PASS)** | ADR-069; risk-based chain on `772e352a34ea`: 20/20 host==image, suite **737** worker-removed, **25/25** in-container gates incl. `gate_ffa3_auto` **55/55**, PR-3 static, 4 host gates; **`gate_phase9b_auto` FAILED TWICE — preserved as FAIL, accepted as unrelated infra debt D-29; NOT "all gates green"**; live Step 6 halted at the second call (kimi connection error → UNCERTAIN $3.268608 → retry refused by the $5 run cap), 0 specs, 0 decisions, $0.007725 spent |
| **D-28 SLICE — honest reservation bound** | **CLOSED 2026-09-15** | ADR-070; 61 targeted tests + full suite green on host 3.12 venv (container engine down — in-container chain DEFERRED, recorded); `gate_pr2_auto` PASS |
| **MS-A1 — `perforated_screen`, the first mesh-class (perforated-skin) primitive** | **CLOSED 2026-09-16 (owner-delegated slice); NOT an open lattice — B-11b stays OPEN** | ADR-071; `gate_msa1_auto` 54/54 (roster script 30); FF-A2/PR-5/FF-A1/FF-A3 re-run PASS on host venv; targeted pytest 119 passed; definitive container chain DEFERRED with the engine |
| **SC-A1 — `crescent_ring`, the crescent-moon sculpture primitive** | **CLOSED 2026-09-16 (owner-referenced photo: mirror-polished crescent, 1.9×2.0×0.4 m); organic liquid forms NOT claimed** | ADR-072; `gate_sca1_auto` 63/63 (roster script 31); new material `stainless_316l_cast` (provisional); msa1/FF-A2/PR-5/FF-A1/FF-A3 all re-run PASS; 40 new tests, 142 targeted passed; container chain DEFERRED |

**Suite and roster state:** after PR-2 the pytest suite (475) passed
with the render worker UP and with it removed — both runs recorded
verbatim in `PRODUCTION_V1_REPORT.md` on final image `09ff920ccbbb`;
after LF-103A the suite was 514 on `9fe4c4328116` (ADR-063); after the
discovery close 540 on `52209e4a6eea` (ADR-064); after FF-A1 591 on
`4ff126586ec3` (ADR-065); after FF-A2 672 on `044446e54c0e` (ADR-066);
after PR-4 707 in BOTH worker states on `a8a6f3218ba8` (ADR-067);
after PR-5 the suite is **720, passed worker-removed on final image
`753490ced0af` (2026-09-08)** under the operator's risk-based protocol
— PR-5 changed no worker-sensitive rendering or packaging code, so
PR-4's 707 two-state run is retained as the unchanged baseline; chain
evidence in ADR-068 and `PRODUCTION_V1_REPORT.md`; after the FF-A3
BUILD (not yet closed) the suite is **737 passed, worker up, on image
`0d4180d2b8d7` (2026-09-09, 6202.65 s)** — the definitive two-state or
risk-based chain is `/lf-gate`'s. The auto-gate
roster is 29 scripts as of 2026-09-09 (FF-A3 added `gate_ffa3_auto.py`,
hermetic, in the backend container, D-26-safe DB fingerprinting, builds
the rank-1 fixture lens in-process and the FF-A2 fixture in a second
process — ADR-069; before it 28: PR-5 added `gate_pr5_auto.py`, hermetic, in the
backend container, D-26-safe DB fingerprinting, carrying the D-10
sweep — ADR-068; PR-4 added `gate_pr4_auto.py`, hermetic, in the
backend container, rate card sha-checked — ADR-067; FF-A2 added `gate_ffa2_auto.py`,
hermetic, in the backend container, carrying the registry's
exact-eleven assertion — ADR-066; FF-A1 added `gate_ffa1_auto.py`,
hermetic, in the backend container — ADR-065; PR-2.5 discovery added
`gate_pr25_discovery_auto.py`, SPLIT-MODE: repo sections run anywhere;
artifact + operator-local reference sections skip loudly when their
inputs are absent; `--host-drift` git section runs only on the host —
ADR-064); before those it was 23: 20 in-container with the worker removed
(17 phase gates + `gate_pr1` + `gate_pr2` + `gate_lf103a`, hermetic),
`gate_pr3_auto` in both modes (static via stdin in-container, live on
the host), `gate_phase9b_auto` with the worker up, and
`gate_scope_audit_auto` (host or container — pure file checks); `gate_phase14_auto` is SPLIT (container run covers
`geometry`, host `--frontend-only` covers `frontend` — run both, check
each verdict's "sections run" line). Total live spend recorded since
Phase 4 closed: $0.042916 (Phase 5 run) plus the operator's 2026-08-28
Council/fabrication demonstration and a possible ~$0.84 unverified
incident exposure (B-2).

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
- [ ] **B-6 — SCOPE.md half RESOLVED 2026-09-01 (ADR-062): recovered
      verbatim and COUNTERSIGNED by the owner — now authoritative.**
      Still open: `SPEC_PHASE2.md`, `PHASE2_PLAN.md`, the "Master Build
      Order" and the "First Action" document — still cited, still never
      existed in this repository.
- [ ] **B-7 — Ruling: should a hollow plinth carry a CLOSED top face?**
      Changes STEP bytes for hollow-plinth designs, so it needs an
      explicit yes (ADR-053). Not a v1 blocker.
- [ ] **B-8 [release] — Named approvers for PR-8:** structural engineer,
      drafter, workshop/fabricator, rigging reviewer. A design cannot
      become `issued_for_fabrication` without them.
- [ ] **B-10 [release] — Operator workflow controls (fold into PR-7B).**
      The frontend can view Council sessions but cannot start a live
      Council run or launch fabrication. Fold real operator controls
      into PR-7B after durable job execution exists: projected-cost
      confirmation, Run Council, Arbiter review, Fabricate selected
      spec, resumable status, failure recovery, and automatic opening
      of the resulting design. Do not implement it early as a blocking
      browser request.
- [ ] **B-11 [release] — MOSTLY RESOLVED 2026-09-02 (ADR-064): 16
      reference images supplied (operator-local, uncommitted —
      manifest committed), materials ruled (316L welded plate +
      armature AND cast GRC), scale ruled (3.5–5.0 m), controls ruled
      (brief + parameter/control-point editing), fidelity ruled
      (silhouette + topology). STILL OPEN, split out as B-11b
      [release]:** at least one REAL mesh/lattice/perforated-skin
      reference image — none of the 16 shows one, and mesh capability
      stays release-blocking and unspecified until it arrives. Also
      still owed by fabricators: GRC datasheet (density, min shell,
      reinforcement, panel size, connections, mold limits), 316L
      forming radius + armature design basis.
- [ ] **B-9 — Confirm or deny the four unattributed render-worker starts**
      (12:12:30 / 12:17:29 / 12:25:36 UTC on 2026-08-27, after each
      deliberate stop; the earlier ~06:59/~07:19 pair you already
      confirmed). Every automated channel was eliminated by read-only
      forensics; manual Docker Desktop action is the surviving
      explanation, but it is attributed by elimination, not admission.
      **New window 2026-08-31:** the whole stack ran unattributed from
      08:07:03Z to ~09:41:56Z (backend exit 0, render-worker present
      and exit 137). Code is baked into the image so no code drift was
      possible, and the operator verified at the PR-2 sign-off that no
      provider call occurred in that window; who started and stopped it
      is still unconfirmed.

---

## 2. THE WORK QUEUE — the approved program, in order (PR-0…PR-9 delivers Milestone B — Internal Fabrication-Geometry Beta; not Production v1, per ADR-062)

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
- [x] **PR-2 — Hard spend caps (CLOSED 2026-09-01, ADR-061: auto gate
      PASS on final image `09ff920ccbbb` + operator visual gate signed
      PASS 2026-09-01).** Per-physical-attempt atomic reservations
      (BEGIN IMMEDIATE on a dedicated connection), integer micro-USD via
      Decimal half-up, one-transaction settlement (ai_calls +
      reservation + sessions), exact reservation_id 1:1 both ways,
      first-class spend scopes (open|closed|halted sticky), fail-closed
      `uncertain` attempts, provider-model/global safety locks + audited
      `spend_admin.py` resolution (`reconciled` orphan spend on every
      operator surface), context-window fallback bounds (no provider
      documents framing — first-party 2026-08-28; kimi holds $3.268608
      per call), `session_cap_usd` → `run_cap_usd`, `gate_pr2_auto.py`
      = roster script 21. Definitive evidence: 475 passed in BOTH
      worker states, 21/21 roster green, slice spend $0.00 — full chain
      in `PRODUCTION_V1_REPORT.md`. Operator rulings at sign-off:
      $5/run + $25/day RETAINED; the kimi fail-closed retry consequence
      acknowledged; the two accidental live-data designs (`76595edb…`,
      `313e5d20…`) PRESERVED — their cleanup is a separate ruling,
      deliberately not part of PR-2.
- [x] **PR-1 — Per-axis fabrication limits (CLOSED 2026-08-28, ADR-059:
      auto gate PASS + operator visual gate PASS).** `{x,y,z}`
      preserved end-to-end; the kernel, both assembler checks and the
      fabrication gate bind each axis on its own limit (binding axis =
      greatest extent/limit ratio, ties x→y→z); the Designer scalar
      stays a deliberate cubic envelope at the one assemble() boundary;
      malformed limits are structured 422s; the approved truth table
      runs live on the design API with spec recovery and verification,
      and geometry-rebuilding operations on ambiguous history refuse
      with the one exact rebuild action. Red-first: 11/11 new tests
      failed on pristine 16cf932; suites 449 passed in BOTH worker
      states; all 20 roster scripts green; the operator saw the 2.3 m
      column split to 2 × 1150 mm under a 2.2 m z-limit. **The real
      per-axis truck envelope is still UNKNOWN (operator measurement
      pending) — open under B-1; nothing was invented.** Evidence:
      `PRODUCTION_V1_REPORT.md`.

### Next up

- [x] **Master Scope Development Audit (CLOSED 2026-09-01, ADR-062:
      auto gate PASS + owner countersignature).** `SCOPE.md` (owner's
      scope verbatim, weights÷112, now owner-authoritative) +
      `DEVELOPMENT_AUDIT.md` (30-system scorecard at `bfa5a77`, final
      31.6/100 after the owner's three re-rulings, reconciliation of
      27.68/34.6/33.9/31.6, G0–G10 enforcement map, defect register
      D-13…D-23, Milestone A/B/C roadmap) + LIMITATIONS §21 + roster
      script 22. Docs + offline gate only; no production code touched.
      Sign-off verbatim in `gate_scope_audit_visual.md`.
- [x] **LF-103A — Close the unsafe export boundary (CLOSED 2026-09-02,
      ADR-063: auto gate PASS + full-roster re-run in both worker
      states on image `9fe4c4328116` + operator visual gate personally
      walked and signed PASS 2026-09-02, verbatim in
      `gate_lf103a_visual.md`).** Delivered: three-class verdict
      (REFUSED / PRE-FABRICATION / CLEAN) from persisted evidence only
      in `backend/app/geometry/package_class.py`; the builder itself
      raises `PackageRefused` (bypass closed, `app.main` maps to 409);
      export POST refuses FAILED before any geometry work with the
      failing numbers; fabrication-capable downloads
      (STEP/BREP/STL/DXF/SVG incl. `/latest.step`) refuse for FAILED;
      every attachment carries a class-marked Content-Disposition
      filename (mesh for FAILED = DIAGNOSTIC-NOT-FOR-FABRICATION;
      viewport streams untouched, ADR-034); PRE-FABRICATION packages
      seal marked entry names + deterministic `ENGINEERING_WARRANT.txt`
      (role map, no invented disciplines) + printed DXF/SVG
      NOT-FOR-CONSTRUCTION notice; legacy zips = LEGACY_UNCLASSIFIED,
      refuse with the one re-export action, bytes never rewritten;
      CLEAN is builder/test-only until **D-24** closes and LF-102 must
      not make it reachable before then. Canonical STEP bytes and
      `e1a59fa6…` untouched; packages byte-reproducible per (design,
      seed, class). Evidence: red-first (module absent + 9/10 boundary
      tests failed on pristine image), then 39 new + 109 affected tests
      green, `gate_lf103a_auto.py` PASS (hermetic, section [9] proves
      the real DB and data/exports untouched), `gate_phase9a_auto.py`
      PASS with the class assertion.
- [ ] **PR-2.5 — Free-form amorphous sculpture (ADR-060/ADR-064).
      DISCOVERY CLOSED 2026-09-03 — strictly a discovery result, NOT
      capability: visual Step 2 = NO, reference-faithful geometry and
      user-facing free-form capability remain UNBUILT. The
      IMPLEMENTATION slice(s) run via `/lf-next` under the owner's
      CHANGED acceptance gate (eight conditions in
      `PR2_5_FREEFORM_DISCOVERY.md`), split FF-A1 → FF-A2 (approved
      2026-09-03).**
- [x] **FF-A3 — a typed brief can ask for the ref-08 loop (CLOSED
      2026-09-14, ADR-069, with the owner's binding status:
      "typed-brief/Council contract implemented and fixture-gated; live
      end-to-end selection blocked by D-28 and not claimed"; auto gate
      `gate_ffa3_auto.py` = roster script 29, 55/55; visual gate
      `gate_ffa3_visual.md` SIGNED 2026-09-14 — Steps 1–5 YES, **Step 6
      NOT ACHIEVED, never PASS**).** Owner-approved 2026-09-09 with nine binding
      corrections. **Visual gate walked 2026-09-14: Steps 1–5 all YES
      (Step 3 with a recorded deviation — the operator asked the session
      to enter the intake fields through the same API the Brief tab
      calls, and the 30 m/s wind is a TEST value at the operator's
      instruction, never a site measurement). Step 6, the one authorized
      live demonstration, RAN and HALTED 46 s in: the researcher's
      primary openai call succeeded ($0.007725), the parallel kimi call
      failed with "Connection error.", its reservation went UNCERTAIN at
      the full $3.268608 bound, and the ADR-023 retry's reservation was
      refused by the $5.00 run cap. Session
      `2a7d3e5b-2b78-42f6-9479-637f0e1feaa6` = halted_budget, 0 design
      specs, 0 arbiter decisions — the Council NEVER REACHED the Designer
      stage, so it neither selected nor declined `freeform_loop`. The
      claim "typed brief → Council selection → sculpture" REMAINS
      UNMADE. Real money billed: $0.007725. The uncertain reservation
      `9077e77a-95ec-4633-b4be-c5a07ad4f74f` is PRESERVED and NOT
      reconciled — the owner is checking the Moonshot/Kimi console for
      2026-09-14 08:22–08:23 UTC and will report before any
      reconciliation. New debt D-28, promoted by the same ruling to the
      next slice. **Owner ruling 2026-09-14: no second Step 6 attempt
      now; no council.yaml change, no kimi removal, no weakening of
      fail-closed accounting, no increase to the $5/$25 caps; Step 6 is
      NEVER marked PASS; FF-A3 may pass its formal gates and close ONLY
      as "typed-brief/Council contract implemented and fixture-gated;
      live end-to-end selection blocked by D-28 and not claimed."**
      **Definitive risk-based chain run 2026-09-14 on image
      `772e352a34ea` (identical start/end): 20/20 files host==image;
      suite **737 passed** worker-REMOVED (PR-4's two-state baseline
      retained); **25/25** in-container gates incl. `gate_ffa3_auto`
      **55/55**; PR-3 static; scope audit, Phase 14 frontend, PR-2.5
      host-drift 218/218, PR-3 live. `gate_phase9b_auto.py` **FAILED
      TWICE and is NOT recorded as passing** — accepted by owner ruling
      as unrelated measured infrastructure debt (D-29: 1,904-directory
      scratch scan at 8.89 s per poll starves fixed gate waits; both the
      render and the conversion succeeded, only after their deadlines).
      **This chain is NOT "all gates green."** Evidence in
      `PRODUCTION_V1_REPORT.md`; not committed, not closed.**
      Delivered: the Designer index prints every
      primitive's parameter vocabulary (spec name -> registry key, unit,
      range, default) plus registry-derived honesty lines (316L-only,
      incomplete-mass inputs, PRE-FABRICATION), generated from
      `PRIMITIVES` + `spec_mapper.spec_aliases_for()`; the mapper covers
      `freeform_loop`'s 13 registry keys (12 scalars + `material_id`),
      refuses a `{value, unit}` object on any ratio/fraction target and
      refuses a `parameters.material_id` that contradicts the element;
      the Designer boundary (`orchestrator._validate_live_primitives`)
      runs the mapper + each primitive's `validate()` before persisting
      (any exception is an error, never a pass); schema change B — a
      dry design (`water.has_water = false`, present AND false) may carry
      an empty hydraulic network, wet or absent keeps 2 nodes/1 edge —
      plus the phantom-id and dimension/ratio description fixes; the
      demo-session loader takes a discovered basename only; fixtures
      `intake_ffa3_v1.json` (typed brief) and `council_session_ffa3_v1.json`
      (SYNTHETIC — prompts generated by the real builders, `--check`
      drift-guarded; **synthetic hand-authored Council alternatives
      prove replay and pipeline compatibility only, not that an AI
      selected the primitive from prose**). The claim "typed brief →
      Council selection → sculpture" is NOT made until the visual gate's
      Step 6 live demonstration is separately cost-approved, run and
      recorded. Preserved: one ref-08 family, 316L only, scalar
      controls, incomplete mass, unresolved fabrication inputs,
      integrity-gated, PRE-FABRICATION at best, registry unchanged at
      eleven, `e1a59fa6…` untouched.
- [x] **FF-A2 — the `freeform_loop` primitive (CLOSED 2026-09-07,
      ADR-066: definitive two-state chain on `044446e54c0e` — 672
      both worker states, 26-script roster green, `gate_ffa2_auto`
      63/63 zero skipped — + operator visual gate signed
      2026-09-07).** The owner-ruled hollow-lens +
      walled-window-bore construction (the approved tube-annulus
      failed development — full measured chain in ADR-066): one loft
      lens, sealed donut cavity, walled window bore, thin 316L
      interface plate (13.6 kg, never a foundation claim), 316L-only,
      wall 6–20 with 3 mm embedment + ≥3 mm ligament, truncated
      formable tips, registry 10→11 with the approved subset
      conversions, FF-A1's mass/integrity machinery ACTIVE (null
      total, costing 409, REFUSED on missing/failed/indeterminate
      rows, PRE-FABRICATION-only). Measured at defaults: topology
      contract [1,1]/2 components/1 cavity PASS; bore-to-cavity
      7.978 mm PASS (authoritative, owner clarification 2); wall
      min 1.666 ⇒ geometric_wall_measurement needs_input (honest);
      fidelity: after the owner's 2026-09-05 option-(a) ruling the
      retired `rim_ratio` (110 px/55 px — it measured the reference's
      3-D surface scoop, unmeasurable in projection; preserved as
      history with its definitive 1-of-60 gate FAIL) was re-derived as
      `projected_side_to_apex_band_ratio` exactly from the reference
      under the recorded instrument: 122/139 = 0.877698, band
      [0.7022, 1.0532]; the geometry measures 0.9167 — and the 3-D
      scoop stays a separate mandatory visual-gate comparison.
      **Closed on the definitive two-state chain (final image
      `044446e54c0e`, 2026-09-07): suite 672 in BOTH worker states
      (worker-removed 0:45:46 / worker-up 0:47:08, states pinned);
      all 26 roster gates green — `gate_ffa2_auto` 63/63 zero skipped
      (two-process STEP `c4136aec…`, bore clearance 7.978 mm, ratio
      0.925), corrected `gate_ffa1_auto` 36/36 (sixth D-10 instance:
      its "every manifest legacy-clean" assertion correctly FAILED
      1/35 on the operator's first real freeform_loop design
      `70b12dd3…` — FAIL preserved, design untouched, section ruled
      into the timeless all-legacy/keys<=>non-legacy form), pr25
      normal 198 + host-drift 218, 9B, PR-3 static+live, Phase 14
      both halves, scope audit. Visual gate signed 2026-09-07: Q1 YES
      (left/right opening difference accepted as viewing-orientation
      dependent), Q1b 3-D scoop ACCEPTABLE, Q2/Q3 YES; the 570 s
      render timeout preserved as operational finding D-25. Earlier
      history preserved: the honest 1-of-60 rim_ratio FAIL on
      `bd85f7d13fb7`, the failed tube-annulus construction, the
      measured kernel cliff, and the Docker-engine crash that voided
      the first stage-1 attempt.**
- [x] **FF-A1 — Incomplete-mass truth + production free-form
      validation (CLOSED 2026-09-04, ADR-065: full two-worker-state
      roster evidence + operator visual gate signed 2026-09-04 —
      Step 2's digest strings arrived as unpasted placeholders, caveat
      recorded verbatim in `gate_ffa1_visual.md`).** Internal
      truth foundation, no user-facing capability: `MassTruth`
      (total None never zero; malformed fails closed; frozen
      legacy-ten versioning seam keeps every old byte identical — 67
      real designs proven legacy-clean), all 28 audited mass consumers
      refuse/label incomplete mass (AST census + behavioral tests +
      20-attempt impossible-PASS proof), `freeform_integrity_v1`
      production stack persisted via the standard validation rows with
      missing/failed/indeterminate ⇒ REFUSED for applicable designs
      (persisted applicability snapshot, never the live registry;
      inherits D-24 — CLEAN stays unreachable). Evidence: red-first on
      `52209e4a6eea`; a development run caught + fixed a real
      regression (7 costing tests: the first incompleteness check
      failed closed on element-less legacy manifests); then the
      definitive chain on final image `4ff126586ec3` — 51/51 new
      tests, `gate_ffa1_auto.py` PASS 35/35 zero skipped (roster
      script 25), full suite **591 passed** (540 + 51), frontend
      typecheck PASS. Both runs verbatim in ADR-065. **FF-A2 (the
      ref-08 primitive) returns through `/lf-next` after FF-A1
      closes.** Delivered: the three-approach comparison (BREP /
      procedural mesh / import) with NO preselection, run in the
      geo-worker sandbox twice at real 3.5–5.0 m scale — all five
      primary geometric languages constructed as single kernel solids
      on the BREP route (closed varying-section loops only via
      butt-joined half-lofts; periodic sweeps are seam-defective or
      refused, kept as evidence), 13/13 contractual artifacts
      byte-identical cross-process, independent validation stack
      (OCC analyzer + self-interference + tessellation cross-check +
      genus) that REFUSED both deliberate-defect specimens, mesh route
      proven boolean-less, import route proven
      transform/validate/re-serialize only. Report:
      `PR2_5_FREEFORM_DISCOVERY.md` (BREP-first recommendation, STEP
      stays canonical — **any change to STEP as the canonical artifact
      requires an explicit architectural ruling, never an assumption**;
      acceptance-gate design for the implementation slice). **PR-4
      still waits until the free-form capability itself is built,
      gated, committed and pushed** (ADR-060). B-11b (mesh/lattice)
      and the fabricator inputs stay open; D-11 and D-12 remain
      discovery CANDIDATES only.
- [x] **PR-4 — Honest module transport costing.** **CLOSED 2026-09-08
      (ADR-067): built 2026-09-07, `gate_pr4_visual.md` signed by the
      operator 2026-09-07, definitive two-state chain all green on
      `a8a6f3218ba8` (707 both states, 27-script roster).** Per-module masses
      carried into the drivers (`module_masses_kg`, read off the
      manifest's segmentation elements); refuse when any module exceeds
      `truck_payload_kg` naming the module and both numbers;
      deterministic first-fit-decreasing allocation respecting payload
      AND `modules_per_trip`, compared unrounded; 0.1% [J]
      module-sum-vs-report conservation guard; independent ID-partition +
      mass-conservation verification. **Amendment 3 honoured:** the BOM
      calls it "a deterministic conservative feasible allocation", never
      minimal; prints every trip's module IDs, masses, total load and
      remaining capacity; `not_computable` when no valid allocation —
      never the old lower-bound `max(ceil(mass/payload),
      ceil(modules/per_trip))` presented as a trip count (the disproof —
      four 6 t modules at 10 t payload: bound 3, reality 4 — is pinned in
      `gate_pr4_auto.py` §3). Adversarial tests in
      `tests/test_transport_allocation.py` + `tests/test_costing.py`:
      module > payload; lower bound < feasible count; bed binds; weight
      binds. **Operator digest ruling recorded in ADR-067:** re-exports
      of old designs may get new package digests solely from the sealed
      BOM's new transport wording; sealed packages never rewritten;
      geometry/manifest/validation bytes unchanged. Rate card untouched
      (transport entries still null and the operator's). **Gate
      history 2026-09-07:** first definitive chain FAILED at
      `gate_ffa1_auto` §1 (D-10 instance seven, above) after suite 707
      passed worker-removed + 21 gates green; operator-approved
      hash-proven recovery protocol (15 production/test/config/build
      hashes identical before and after the census correction; only
      `gate_ffa1_auto.py` changed) — stage A on final image
      `a8a6f3218ba8…`: corrected FF-A1 36/36, all 25 in-container
      roster gates exit 0 incl. FF-A2, PR-4, PR-3 static; the 707
      worker-removed suite RETAINED; a solo FF-A1 run 3 s after the
      rebuild tripped §8's DB fingerprint on the backend's own startup
      writes (D-26, recorded, PASS on the identical image 25 min
      later). Stage B (worker-UP suite + 9B + host gates) evidence in
      PRODUCTION_V1_REPORT.md.
- [x] **PR-5 — AI contract and document repair.** **CLOSED 2026-09-08
      (ADR-068): built, `gate_pr5_visual.md` signed by the operator
      2026-09-08 (six steps YES), definitive risk-based chain all green
      on `753490ced0af` (720 passed worker-removed, 28-script roster in
      required states).** Cited by SYMBOL now (every line number
      the old entry carried had drifted — itself D-10 in a document):
      the GEOMETRIST contract's three "per element" sentences
      (`prompts.registry_surface`) → heaviest MODULE after segmentation
      + per-axis envelope, pin rewritten with the retired tokens
      asserted absent; the two `needs_input` bases in
      `gates.validate_fabrication_gate` → module kg + per-axis; the
      critique scorer (`critique.objective_score`/`objective_score_detail`
      /`facts_from_manifest`/`score_delta`) scores the PICK weight with
      an explicit basis (measured heaviest module / single complete
      element / unavailable), None — never 0.0 — when unavailable, and
      the live script's silent `max_lift_kg = 1000.0` default is GONE
      (`run_vision_critique.py` read a key no manifest has); operator doc
      07; four documents corrected with dated notes beside the preserved
      originals (LIMITATIONS §11 mapper covers TEN not four — the gap is
      `freeform_loop`, FF-A3's; §12 segmentation is built; PHASE_11_12_13A
      "9B untouched"; PHASE_6_REPORT "GATE: PASS" while its live gate is
      pending); the D-10 sweep is now a roster check (`gate_pr5_auto` §5:
      growth-collection equalities must carry a real `D-10-frozen:`
      reason; 6a2's literal unknown name, the scope audit's
      first-occurrence order and 6c2's `== 39` converted to timeless
      forms; the ADR-065 census caught the two new scorer symbols and
      they are listed exactly, no wildcard). The 2,685.7 kg array figure
      is settled (2,988 was a transposed ratio, corrected at its sites).
      Gate evidence in PRODUCTION_V1_REPORT.md.
- [x] **D-28 SLICE — an honest reservation bound (CLOSED 2026-09-15,
      ADR-070).** Separate and rollbackable. **Goal:**
      the fail-closed reservation is computed
      from the REAL serialized request envelope + the configured maximum
      output + a proven conservative margin — **never the model's entire
      unused context window**. Context size remains an ABSOLUTE CEILING,
      not an assumed billable request. **Binding constraints from the
      ruling:** no `council.yaml` change, kimi is not removed, the
      fail-closed accounting is not weakened, and the permanent $5 run /
      $25 day caps are NOT increased. **ADR-009 applies:** fetch and
      record current first-party provider documentation for every token
      and billing claim, with the fetch date — the reason ADR-061
      adopted the context-window fallback was that no first-party source
      documented message framing overhead; that fetch must be redone,
      not recalled. **Must test:** retries, uncertain holds, multibyte
      prompts (a byte-vs-character bound is a real underflow), maximum
      output, and reservation-UNDERFLOW safety (a bound that lands under
      the real cost must fail closed and lock, never silently absorb).
      Measured motivation in D-28 below and in `gate_ffa3_visual.md`.
      **All of it landed:** `tests/test_d28_envelope_bound.py` (37
      hermetic tests) covers every ruled test; the envelope is the sent
      envelope field-for-field for all three providers; the census is
      read-only and global-locking; the operator surfaces expose the
      basis. **Deferred:** the definitive in-container suite + roster
      re-run (host Docker engine down) — first action when the engine is
      back. Reservation `9077e77a…` remains owner-pending, unreconciled.
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
      resumable, completed; no silent partial success. **Plus B-10, the
      operator workflow controls (ruled 2026-08-28):** projected-cost
      confirmation, Run Council, Arbiter review, Fabricate selected
      spec, resumable status, failure recovery, automatic opening of
      the resulting design — built HERE, on durable job execution,
      never as a blocking browser request.
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
      **plus a MANDATORY fourth positive project (owner ruling
      2026-08-28, ADR-060): a genuinely amorphous free-form sculpture
      through the same full chain — PR-2.5 determines the exact fixture
      and manufacturing route** — each through intake-fixture → spec →
      assembly → segmentation →
      validation → costing → reproducible exports → DesignDNA → backend
      restart → reload/verify → backup → restore-verify; SEPARATE
      negative cases (oversized discrete array, missing approvals,
      module > payload, ambiguous pre-axis-limit history, reservation
      contention); restart proven by a host-side PowerShell orchestration
      gate if the in-container gate cannot restart safely — never a faked
      restart. $0, offline, both worker states.

### Deliberately OUTSIDE Production v1 (operator ruling 2026-08-27)

- **Phase 10** (autonomous vision-driven revision), native DWG/SKP,
  mobile UI, semantic search. Do not widen the release to these unless
  the acceptance gate genuinely requires it. (**Phase 6 slice D was
  REMOVED from this list by the owner's ruling of 2026-08-28, ADR-060**
  — free-form amorphous sculpture is now release-blocking; see PR-2.5
  above. The old three-primitive slice-D list is a hypothesis, not the
  requirement.)

### Debts — small, real, unscheduled

Pick one up when a slice finishes early. Each is one commit.

- [ ] **D-1 — `data/geo_scratch/` is never reaped.** Folded into PR-7C.
      **Widened 2026-09-14: `data/render_scratch/` is not reaped either
      — 1,904 job directories, and the backlog now has a MEASURED
      operational cost: one pending-job scan costs 8.89 s, which starved
      the Phase 9B gate TWICE (D-29). The cleanup design must be safe
      for evidence a gate or an open slice still depends on, and must be
      paired with bounded/indexed/event-driven pickup rather than longer
      timeouts; nothing is deleted without an owner instruction.**
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
      (6a1 exact-four, 6a2 `water_wall`, 6a1 "slice C" string), a
      fourth instance surfaced 2026-09-02: `gate_scope_audit_auto.py`
      §5 enforces queue order via FIRST-OCCURRENCE of "LF-103A" vs
      "PR-2.5" in NEXT.md, which any status paragraph can trip (worked
      around by wording, not by weakening the gate), and a FIFTH bit
      for real 2026-09-04: `gate_pr25_discovery_auto.py` §12 asserted
      "no production drift" against the LIVE working tree vs HEAD — a
      slice-scoped promise in a permanent roster gate, which correctly
      FAILED during FF-A1's uncommitted backend work. Corrected by
      operator ruling (ADR-065 evidence): the check now pins the
      discovery close commit `5cb0af3e2445…` by full hash (must
      resolve, else FAIL) and asserts THAT COMMIT changed no
      backend/app, config or schemas paths — a permanent historical
      truth; the timeless no-JPG-tracked check is unchanged. A SIXTH
      instance fired 2026-09-07: `gate_ffa1_auto.py` §6 asserted
      "EVERY stored manifest is legacy-clean" — true in the FF-A1 era,
      correctly FAILED 1-of-35 the moment the operator persisted the
      first real `freeform_loop` design (`70b12dd3…`, 2026-09-07
      05:40:29) during the FF-A2 visual walk; FAIL preserved verbatim,
      design untouched. Corrected by operator ruling to the timeless
      ADR-065 form: all-legacy manifests legacy-clean; new keys <=>
      non-legacy primitive both directions (no silent validation
      bypass); legacy/non-legacy counts printed. A SEVENTH instance
      fired 2026-09-07 in PR-4's definitive chain: `gate_ffa1_auto.py`
      §1's ADR-065 mass-consumer census correctly FAILED 1-of-36 on the
      new `app.costing.transport` module (`NoFeasibleAllocation` reads
      `mass_kg`; `TripAllocation` and `allocate_trips` read
      `total_mass_kg`; 31 consumers vs 29 allowlisted) — this one is
      the guard doing exactly its job on a genuinely new consumer, not
      an expired example. Audited: the allocator opens no manifest,
      report or DB and incomplete mass is refused UPSTREAM by
      `IncompleteMassError`. Corrected by operator ruling as THREE
      EXACT symbol entries, not a module wildcard; FAIL preserved
      verbatim in ADR-067 (D-10 instance seven). The tell
      is a roadmap phrase inside an assertion. **The sweep is now a
      permanent roster check (PR-5, ADR-068, `gate_pr5_auto` §5):**
      every growth-collection equality in every gate must carry a
      `D-10-frozen:` reason ≥ 8 words citing an ADR/record; 8 hits all
      justified, 25 structural equalities listed as reviewed; 6a2's
      literal unknown name, the scope audit's first-occurrence order
      and 6c2's `== 39` converted to timeless forms. Re-runs on every
      chain; slice D will trip `gate_ffa2`'s exact-eleven by design.
- [ ] **D-11 — Radial segmentation for round vessels.** Needs the
      operator's `gate_phase6c2_visual.md` §2 ruling first. PR-2.5
      discovery CANDIDATE (ADR-060) — promote only when a reference
      design and fabrication method prove it required.
- [ ] **D-12 — `blade_fin_array`/`lotus_petal_array` have no module
      decomposition** (hub + N blades; blade-root seam needs its own
      proof). PR-2.5 discovery CANDIDATE (ADR-060) — promote only when
      a reference design and fabrication method prove it required.
- [ ] **D-24 — Validation rows carry no shared validation-run identity
      (ADR-063, owner final condition 1).** Reports written by one
      validation operation are tied to the design only structurally
      (design_id FK + immutable geometry + the LF-103A seal-time hash
      check), not cryptographically. Until an additive
      `validation_basis` identity is persisted with every report of one
      run, production classification is structurally barred from CLEAN.
      **LF-102 must not make CLEAN reachable before this closes.**
- [ ] **D-25 — freeform_loop renders hit a 570-second timeout on this
      hardware (operator finding, 2026-09-07, FF-A2 visual walk).**
      The dense free-form tessellation is heavy for CPU Cycles on the
      i7-8550U; the visual verdict was completed by viewport
      inspection, which the gate permits, so nothing is invalidated —
      but renders of free-form designs need either a longer budget, a
      decimated render mesh, or fewer samples before Phase 10 /PR-9
      lean on them. Recorded, not resolved.
- [ ] **D-26 — `gate_ffa1_auto.py` §8 "real DB byte-identical" races
      the backend's own startup writes (found 2026-09-07, PR-4 recovery
      stage A).** The check fingerprints `data/luxuryform.db` at gate
      start and end to prove the GATE touched nothing; but `main.py`'s
      startup handler writes to that same file (`init_db()` sets
      `PRAGMA journal_mode=WAL` and creates tables, then PR-2's
      `recover_stale_spend_holds` / `reconcile_spend_books`). Run the
      gate within seconds of a container recreation and those writes
      land between the two fingerprints: measured FAIL at 3 s after
      `up --build` (`c27774d8dfaf` mid-write), PASS on the identical
      image and identical gate 25 minutes later (36/36, same
      `c27774d8dfaf` both ends). Not a PR-4 defect and not a gate
      defect in intent; an ordering hazard. Until fixed (wait for
      `/api/health` + a quiesced WAL before fingerprinting, or exclude
      the startup transaction), chain scripts must not run gate_ffa1
      first after a rebuild. Recorded, not resolved.
- [ ] **D-29 [operational, linked to D-1] — render-worker job pickup
      scales with the historical scratch backlog, so fixed gate waits
      starve (MEASURED 2026-09-14, FF-A3 definitive chain; the reason
      `gate_phase9b_auto.py` FAILED TWICE in that chain).** The worker
      rescans the ENTIRE scratch mount on every poll, statting ~4 paths
      per directory over a Docker bind mount to NTFS. Timed inside the
      worker container: **1,904 directories, `iterdir`+sort 0.04 s, one
      full pending-job scan 8.89 s, 0 pending jobs found.** Consequences
      measured in one chain: (a) a worker recreated mid-chain drained
      **50 stale conversion jobs** first and claimed the gate's render
      job only at 11:43:54Z though it was queued 11:39:17Z — the gate's
      fixed **300 s** deadline expired 11:44:17Z, and the render then
      finished successfully at 11:44:32Z (`ok: true`, `total_s 37.487`,
      four views); (b) on the authorized rerun the render passed in
      58.1 s and section 5's fixed **20 s** conversion wait expired at
      12:16:24Z while that conversion, `conv515aca28338d`, completed
      **ok at 12:16:28Z**. In both cases the WORK SUCCEEDED and the gate
      reported FAIL purely on scheduling order.
      **Owner ruling 2026-09-14 — the eventual correction MUST avoid
      rescanning every historical directory on each poll and MUST
      provide bounded, indexed or event-driven pickup PLUS safe
      retention/reaping. Merely increasing the timeouts is NOT an
      acceptable fix.** Same hazard family as D-26 (a fixed DURATION
      standing in for a CONDITION) and the direct operational cost of
      D-1's unreaped scratch. **No scratch artifact is to be deleted,
      moved or modified without an explicit owner instruction; the 1,902
      directories present at the time of this finding are preserved.**
- [x] **D-28 — one dropped connection on the kimi seat consumes 65% of
      the run cap and halts a Council session (measured 2026-09-14,
      FF-A3 Step 6). CLOSED 2026-09-15 by the D-28 slice (ADR-070): the
      reservation bound is now the real serialized request envelope +
      256-token framing margin (an explicit JUDGEMENT value), capped by
      the context window as an absolute ceiling — the kimi hold for the
      actual FF-A3 prompt is under $0.20 and a retry fits under $5.**
      The cap-safe reservation bound WAS context window
      × input rate + max_tokens × output rate (ADR-061 Amendment 4), so
      kimi-k3's 1,048,576-token window books **$3.268608 per call**
      against a $5.00 run cap, versus $0.4019 (openai, 128k) and
      $0.8729 (anthropic, 200k). A failed attempt goes UNCERTAIN at the
      full bound (fail closed, correct), so the ADR-023 retry's own
      reservation is then refused and the whole session halts — measured:
      a live session died 46 s in, after ONE successful call, on a
      transient "Connection error." from the Moonshot endpoint. On this
      operator's connection (CLAUDE.md: "slow and drops... has cost more
      time than any code defect") this will recur. Nothing here is a
      defect in the caps: the arithmetic is deliberately conservative and
      the failure was honest. What needs an owner ruling is whether a
      1 M-token context window should be allowed to price a reservation
      it can never use — options: a per-model reservation ceiling derived
      from the request's real prompt plus a proven margin (needs
      first-party framing documentation, which ADR-061 records does not
      exist), a lower `max_tokens` for the kimi seats, moving kimi out of
      the two optional seats, or a larger run cap for Council runs. Do
      not weaken the fail-closed rule. **Owner ruling 2026-09-14: this
      is PROMOTED to the next separate, rollbackable SLICE (see the work
      queue above), to be planned only after FF-A3 closes. The options
      list below is superseded by the ruling's goal: bound = real
      serialized request envelope + configured max output + a proven
      conservative margin; context size is an absolute ceiling, never an
      assumed billable request. council.yaml is not changed, kimi is not
      removed, fail-closed accounting is not weakened, and the $5/$25
      caps are NOT raised.**
- [ ] **D-27 — count/enumeration mapper targets still take a
      `{value, unit}` object and pass the unit through unchecked
      (found 2026-09-09, FF-A3).** `spec_mapper._dimension_to_number`
      now REFUSES a dimension object on `_ratio`/`_fraction` targets
      (ADR-069) but `tiers`, `steps`, `blade_count`, `petal_count` and
      `rim_treatment` still accept e.g. `{"value": 8, "unit": "deg"}`
      (the synthetic Phase 3 fixture does exactly that) and a unit in
      metres is still multiplied by 1000 on those targets. Out of range
      values are still refused by the primitive, so the failure is loud
      in practice, but the wrong-unit acceptance is silent. Fix: extend
      the plain-scalar rule to every non-dimensional target and
      regenerate `council_session_v1.json`. One commit.
- [ ] **D-13 — Critic independence reads the model's self-claimed
      `meta.provider`, not dispatch truth** (`orchestrator.py`; the true
      provider is already persisted two lines away). One-line fix + an
      adversarial lying-model test. Found 2026-09-01 audit.
- [ ] **D-14 — The critique objective never steers:** `margin = 1.0` is
      hardcoded and the composite score is recorded but never read as an
      accept/reject or stop criterion (`critique.py`).
- [ ] **D-15 — `CritiqueLoop` takes a db handle and never persists a
      round** — rounds live only in a script-written JSON file.
- [ ] **D-16 — The parallel arbiter reply is dispatched and billed but
      never parsed** — paid-for evidence nobody reads.
- [ ] **D-17 — `live_verify_providers.py`'s hand-rolled meter omits both
      ADR-061 safety-lock triggers** (`pricing_failure`, actual-above-
      bound), and its `models.list()` calls run unmetered on an
      unverified non-billing assumption.
- [ ] **D-18 — No static scan enforces the AI fence** (no SDK client or
      `_raw_*` call outside `backend/app/ai/providers/`). Cheapest
      missing guardrail; the `gate_pr2_auto.py` tail scan is the
      template.
- [ ] **D-19 — The budget gate binds only when `?budget_amount=` is
      passed, and the export path bypasses it entirely**; no ceiling is
      stored on a design. LF-103A closes the export half; the
      design-attached ceiling belongs to PR-6.
- [ ] **D-20 — Costing has no visual gate file at all** — the only gated
      surface with no operator eye gate.
- [ ] **D-21 — Segmentation planes know nothing about internal
      services** — a saw plane can bisect a nozzle bore. Needs
      service-aware cutting or a loud refusal when a plane crosses a
      fixture.
- [ ] **D-22 — The Blender camera rig is duplicated in two hand-synced
      files** (`backend/app/render/__init__.py` and
      `docker/render/render_scene.py`) — flagged in its own comment.
- [ ] **D-23 — The frontend never calls costing** — no BOM or price
      surface exists in the UI. Fold into PR-7B/B-10.
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
8. **Say the projected cost before spending.** Caps: $5 per LOGICAL run,
   $25 per UTC day (PR-2, ADR-061: enforced by atomic reservation; a
   kimi-k3 call holds $3.27 while in flight). Locks and uncertain holds
   clear only through `scripts/spend_admin.py`, audited, by reason.
9. **More than one session works this repo at once.** Before rebuilding
   containers, stashing, or touching another session's files: check, ask,
   coordinate. Local main can be ahead of origin — push after every close.
10. **Suite evidence pins the render-worker state at start AND end of the
    run.** For a worker-down run, REMOVE the container
    (`docker compose rm -sf render-worker`); recreate it with
    `docker compose --profile render up -d render-worker` when needed.
