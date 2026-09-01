# DEVELOPMENT_AUDIT.md — Master Scope Development Audit

**Baseline: commit `bfa5a77` (main, 2026-09-01, clean tree).** Scored
against `SCOPE.md` (the owner's 30-system scope, weights normalized by
112). **AUTHORITATIVE — the owner countersigned
`gate_scope_audit_visual.md` on 2026-09-01** (auto gate PASS + all five
sign-off lines yes; the full sign-off is recorded verbatim in that
file). The owner's closing line binds every future document: *"Nothing
in this audit is authorization to claim the platform is presently
production-ready."* Re-run guidance is at the end.

**Trust verdict, first line, no softening: LuxuryForm cannot currently be
trusted to produce a real production sculpture.** It can be trusted to
produce geometry that is one genuinely connected body, correctly split
into liftable modules, in a byte-reproducible tamper-evident package — and
it cannot say whether that piece stands up, holds water, or is safe in
public, because no gate profile is signed, the decisive thresholds are
null, and a design whose gates FAILED still seals a clean fabrication
package (LF-103A, queued first, closes that).

## Method

- Five parallel read-only domain agents (AI · geometry/structure ·
  water/lighting/motion · fabrication/commercial · visualization/
  integration/gates) audited the code at `bfa5a77`; a lead session
  adjudicated all scores against the agents, the owner's rubric, and the
  2026-08-28 in-chat audit, and independently re-verified the three
  decisive claims (unsigned null-threshold profiles; export not gated on
  validation; zero AquaFlow/CogniNet/DMX).
- Evidence rules: judged from code; recorded auto-gate PASS transcripts
  (`PRODUCTION_V1_REPORT.md`, `PHASE_*_REPORT.md`) count as automated
  evidence; an unsigned `gate_*_visual.md` counts as **not visually
  proven**. No containers were started and no provider was called ($0);
  the owner's "run the tests" instruction is satisfied by the recorded
  definitive evidence on this exact tree — 475 tests passing in BOTH
  render-worker states and 21/21 gate scripts green (2026-08-28, final
  image `09ff920ccbbb`, `PRODUCTION_V1_REPORT.md`).
- Confidence per row: **High** = lead-verified or proven by a recorded
  gate/exhaustive search; **Medium** = single-agent code reading;
  **Low** = interpretation-contested or deliberately generous (flagged).

## Executive summary

**LuxuryForm is approximately one-third complete against the full
30-system scope.** (Exact figure for the scorecard: raw 35.4/112 →
normalized 31.6/100 — treat the one-third phrasing, not the decimal, as
the honest statement of precision.)

**Maturity: Functional on a narrow vertical slice; Validated on
geometry/export integrity; Prototype-to-nonexistent across most of the
engineering scope.**

Three findings dominate:

1. **The chain breaks at "engineering."** Geometry → mass → segmentation →
   modules → seams → cost drivers is a real, measured, single-path chain.
   Geometry → structural verdict → foundation → member sizing does not
   exist; geometry → hydraulic network → pump does not exist; lighting,
   kinetics and simulation do not exist at all.
2. **No safety-critical gate can currently fail.** Every profile in
   `config/gate_profiles.yaml` ships `signed_off: false` and the three
   decisive thresholds are `null`, so a breach can only ever `warn`.
3. **Nothing blocks the package.** `POST …/exports`
   (`routes_assembly.py`, `post_design_exports`) consults gate statuses
   only to stamp them INSIDE the package; the platform's own blocking
   primitive (`LayeredGateReport.blocking`) has zero call sites — dead
   code. The only enforced downstream refusal in the platform is
   DesignDNA's accept (`store.py`, "cannot become a precedent").

## Score reconciliation (owner amendment 3)

| Figure | Source | What it is | Why it differs |
|---|---|---|---|
| **27.68%** | Operator-reported earlier audit | Not present in any local transcript, repo file, or artifact — per-system scores unavailable. 27.68% corresponds **exactly** to raw 31.0/112, so it was almost certainly an earlier scoring against the same 112-point weights. | Cannot be attributed per-system from surviving records; at the total level it is consistent with scoring before later slices landed and/or stricter readings. Recorded honestly as unattributable in detail. |
| **34.6%** (38.8/112) | 2026-08-28 in-chat audit (session `luxuryform-65`) | Live-API audit, partial test execution, single auditor. | vs final: mostly **rubric interpretation**, now fixed by the owner's rulings — it scored #2=4, #16=3, #23=3, #24=3, #3=5 under a narrower "score what exists" reading; the 2026-09-01 audit lowered those (see rulings) and raised #5 2→3 and #21 2→3 where recorded gate evidence proves the machinery Functional. Evidence changes between the two dates are negligible (PR-2 closed spend caps — not a scored system). |
| **33.9%** (38.0/112) | 2026-09-01 audit, pre-amendment | Five domain agents + lead adjudication at `bfa5a77`. | vs final: the owner's amendment-3 re-rulings below (−2.6 raw). |
| **31.6%** (35.4/112) | **FINAL — this document** | After the owner's re-rulings of #2, #16, #25. | Authoritative once countersigned. |

**The three re-rulings (evidence-based, recorded verbatim):**

- **#2 Parametric Geometry 4 → 3.** The owner's primary product
  requirement — complicated amorphous/organic sculpture — is absent and
  release-blocking (ADR-060). What exists is excellent within a fixed
  10-primitive revolve/extrude/array vocabulary with **no rotation
  anywhere** (placements are pure translations). Validated-for-a-fraction
  is Functional for the system the owner scoped.
- **#16 Panelization 3 → 2.** Segmentation is solid module *cutting* —
  exact, gated, measured — but it is not panelization: no shell panels,
  no flat patterns, no per-module manufacturing CAD (module solids are
  discarded after measurement; no fabricator can receive a module as
  geometry). A validated adjacent capability does not make the scoped
  system Functional.
- **#25 Optimization 2 → 1.** The objective score never steers the loop
  (`margin = 1.0` hardcoded; the score is recorded and never read), there
  is no persistence (the injected db handle is unused), no API route, and
  the plan is a hardcoded 2-element demo; of two live runs, one applied
  zero deltas. A live demonstrator of bounded critique-application is
  Concept-plus, not a prototype optimizer.

## Complete scorecard

Weighted = weight × score / 5. Full per-row detail (missing proof,
professional input, next dependency) follows the table.

| # | System | Wt | Score | Conf | Wtd | Strongest evidence | Main gap |
|---|---|---|---|---|---|---|---|
| 1 | AI Concept Generation | 4 | 3 | Med | 2.4 | 6-role Council with code-enforced invariants (`orchestrator.py`: distinct-hash arbiter refusal, too-few-candidates abort); `gate_phase3_auto` PASS; 23 tests; one live session $0.843842 | n=1 live run; unsigned visual gate; synchronous non-resumable route |
| 2 | Parametric 3D Geometry | 7 | 3 | High | 4.2 | 10 primitives, generated-from-table bounds; cross-process byte-identical STEP (`gate_phase6c_auto`) | **Owner ruling**: amorphous/organic absent (ADR-060) and no rotation — the primary form language does not exist |
| 3 | Geometry Integrity | 5 | 4 | High | 4.0 | One-connected-body enforced 4 ways in `assembly.py` (joint must interfere; `len(parts)!=1` RuntimeError; tangency refusal; volume conservation) + mesh `body_count==1`; bearing-seat floor (ADR-053) | Seams measured, never *designed* (no joint capacity/bonding spec); visual gates unsigned |
| 4 | Material Engineering | 4 | 2 | High | 1.6 | Enforced fabrication envelopes with recorded arithmetic (`materials.yaml`, wall/joint/clearance/feature floors) | **Zero mechanical properties** — no strength, modulus, thermal, fatigue; blocks #6/#7/#15/#17 |
| 5 | Structural Load Engine | 7 | 3 | High | 4.2 | Real statics: measured mass, stored water, ISA altitude-corrected wind q=½ρv², overturning, bearing; 28 tests; `gate_phase8/8b` PASS | Cannot fail: thresholds null, profiles unsigned (B-5); no seismic/sliding/eccentricity; bbox silhouette |
| 6 | Structural/FEA Analysis | 7 | 0 | High | 0.0 | Absent by exhaustive search; disclaimed in code ("statics, not FEA") | Everything; hard professional dependency |
| 7 | Foundation/Anchors | 4 | 1 | High | 0.8 | One bearing division vs `allowable_bearing_kpa`, else `needs_input` naming the geotech survey | No footing/anchor/reinforcement design; bbox footprint unconservative for hollow bases |
| 8 | Hydraulic Engineering | 7 | 2 | High | 2.8 | Capacity/freeboard/turnover/continuity-bore real and gated from confirmed intake (`gate_phase8b`) | Schema-required `hydraulic_network.edges` read by **nothing**; no head/friction/pump/weir-discharge; cannot fail |
| 9 | Water Simulation | 4 | 0 | High | 0.0 | Absent by exhaustive search | Everything |
| 10 | Pump/Equipment Selection | 3 | 1 | High | 0.6 | Turnover sanity check; `pump_curve_ref` schema string with zero consumers | No curves, duty point, equipment DB or schedule |
| 11 | Lighting Engineering | 5 | 1 | Low | 1.0 | Schema `lighting[]` block (typed, bounded) — zero consumers | Everything else; generous 1 (a stricter read is 0) |
| 12 | Lighting Simulation | 3 | 0 | High | 0.0 | Blender rig is fixed 3-point critique clay, not lighting design | Everything |
| 13 | Dynamic Lighting | 3 | 0 | High | 0.0 | Zero DMX/Art-Net/sACN/show-control | Everything |
| 14 | Kinetic Engineering | 3 | 0 | High | 0.0 | "Kinetic" appears once, describing a static fin ring | Everything |
| 15 | Structural Skeleton Generator | 5 | 0 | High | 0.0 | Absent; hollowing is a mass lever, not an armature | Everything; downstream of free-form + #4 + #6 |
| 16 | Panelization | 4 | 2 | High | 1.6 | Segmentation: exact conservation, per-axis limits, measured modules (`gate_phase6c2`, `gate_pr1` signed) | **Owner ruling**: not panelization — no panels, no flat patterns, no per-module CAD (module solids discarded) |
| 17 | Welding Engineering | 3 | 1 | High | 0.6 | Seam length/area measured off real cut faces | Zero weld sizing/prep/symbols/access/WPS/NDT; needs a certified welding engineer |
| 18 | Internal Service Routing | 3 | 1 | High | 0.6 | Real drilled nozzle bores with web/severance guards; service-void annulus | Penetrations aren't routes; `edges`/`service_voids` unconsumed; saw planes can bisect a bore (D-21) |
| 19 | Maintainability | 2 | 1 | Low | 0.4 | Bore-reach + service-void clearance checks | No access analysis, drain-down, or manual; generous 1 (stricter read is 0) |
| 20 | Fabrication Sequencing | 2 | 0 | High | 0.0 | All ordering in the repo is determinism ordering; the joint tree is never consumed as a sequence | Everything |
| 21 | BOM | 3 | 3 | High | 1.8 | Gate-proven honesty machinery: four statuses, single measurement path, no money without a rate (`gate_costing_auto` §4), assembly-path fixes regression-tested | Cost-BOM only; 39-null rate card (B-3); no parts BOM; **no costing visual gate exists** (D-20) |
| 22 | Cost/Quotation | 3 | 2 | High | 1.2 | Budget binds honestly (incomplete → `not_performed`, never pass); mixed-material 409 | No quote possible: totals only ever produced on a gate construct; no quote document; ceiling is a query param (D-19) |
| 23 | Engineering AI Copilot | 4 | 1 | Med | 0.8 | ENGINEER seat + `engineering_reviews`/`defect_lists` tables (batch prose) | **No interactive copilot surface exists anywhere** (adjudicated: prior audits said 3 and 0) |
| 24 | Multi-Agent Review | 2 | 2 | High | 0.8 | Genuinely multi-provider pipeline seats; critic-producer exclusion in code; mandatory disagreement register | 4 seats, not the 7 disciplines (structural+hydraulic+fabrication fused into one prompt); exclusion reads model-claimed provider (D-13) |
| 25 | Optimization | 2 | 1 | High | 0.4 | Live annealed critique loop, $0.042916, 5 deltas applied, geometry changed | **Owner ruling**: score never steers (margin hardcoded), no persistence/API, hardcoded plan, second run applied 0 deltas |
| 26 | CAD/Manufacturing Export | 4 | 3 | High | 2.4 | Byte-reproducible self-verifying LUXEXCHANGE with one-bit tamper detection (`gate_phase9a`); worker-state-independent digest (ADR-057) | Manufacturing half absent (no CNC/flat patterns/per-module CAD); IGES absent entirely; visual gate unsigned |
| 27 | Engineering Documentation | 3 | 2 | High | 1.2 | Reproducible 2-view DXF/SVG + sealed per-gate validation JSONs + BOM JSON | 8 of the owner's 11 documents don't exist; no dims/title block; no PDF toolchain at all |
| 28 | Visualization | 2 | 3 | High | 1.2 | One kernel, one tessellation policy drives viewport + renders; real three.js instrument; gated Cycles worker | Clay stills only; appearance is a frontend hash; no day/night/360°/water/animation |
| 29 | AquaFlow Integration | 2 | 0 | High | 0.0 | Zero mentions repo-wide (lead-verified) | The nozzle ring is hole geometry, not a fixture contract; no return channel |
| 30 | Learning/CogniNet | 2 | 2 | High | 0.8 | DesignDNA: digest-keyed, explainable, quarantined injection, gated | Zero CogniNet; **failures refused entry**; no as-built feedback of any kind |

**Raw total 35.4 / 112 → normalized 31.6 / 100.**

<!-- SCORE-TABLE
{"baseline": "bfa5a77", "raw_total": 35.4, "normalized": 31.6,
 "scores": [[1,4,3],[2,7,3],[3,5,4],[4,4,2],[5,7,3],[6,7,0],[7,4,1],[8,7,2],[9,4,0],[10,3,1],[11,5,1],[12,3,0],[13,3,0],[14,3,0],[15,5,0],[16,4,2],[17,3,1],[18,3,1],[19,2,1],[20,2,0],[21,3,3],[22,3,2],[23,4,1],[24,2,2],[25,2,1],[26,4,3],[27,3,2],[28,2,3],[29,2,0],[30,2,2]]}
-->

### Per-row detail: missing proof · professional input · next dependency

| # | Missing end-to-end proof | Professional input required | Next dependency |
|---|---|---|---|
| 1 | ≥2 more live sessions on different brief classes; signed visual gate | none (concept stage) | async job execution (PR-7A/B) |
| 2 | free-form generation of any kind; signed Phase 6 visual gates | none | **PR-2.5** (B-11 references) |
| 3 | signed visual gates; a workshop-built joint matching the modelled seam | fabricator confirmation of joint practice | joint/bonding spec slice |
| 4 | none for what exists | structural engineer signs an allowables block per material | LF-101 |
| 5 | a design that can FAIL overturning/bearing | structural engineer signs thresholds + profile | LF-102 (B-5) |
| 6 | everything | licensed structural engineer (per-project or FEA path) | LF-101 → LF-102 → LF-109 |
| 7 | a verdict, then a sized footing | geotechnical survey + structural engineer | LF-102, LF-106 |
| 8 | head/duty-point computation from the declared network | MEP/fountain engineer signs hydraulic thresholds | LF-104 |
| 9 | everything | none yet (downstream of #8) | E2 epoch |
| 10 | duty point → selection | pump vendor data + MEP | LF-104 → LF-107 |
| 11 | any consumer of the schema block | licensed electrical engineer (submerged fixtures are code-bound) | E3 epoch |
| 12 | everything | — | #11 first |
| 13 | everything | — | #11 first, AquaFlow boundary |
| 14 | everything | mechanical engineer | E3 epoch |
| 15 | everything | structural engineer | free-form + LF-101/102/106 |
| 16 | per-module CAD export; a panel decomposition of any shell | fabricator ruling on cutting practice (grid vs radial, 6c2 visual §2) | per-module export slice; PR-2.5 informs panels |
| 17 | any weld artifact | certified welding engineer (IWE/CSWIP) | LF-101 first |
| 18 | a routed pipe/cable path | MEP coordination | LF-104; service-aware segmentation (D-21) |
| 19 | any maintainability artifact | operations/maintenance input | E4 epoch |
| 20 | any sequence output | rigging/erection engineer | PR-4 + declared rigging |
| 21 | a real design totalling with real money | operator supplies B-3 rates (basalt per m³/kg is the biggest win) | B-3/B-4 → PR-6 |
| 22 | a client-ready quotation document under release states | operator rates + B-8 approvers | B-3/B-4, PR-6, PR-8 |
| 23 | any interactive surface | none | discipline calculators first (LF-110 after LF-102/104) |
| 24 | discipline seats with tool access; dispatch-truth exclusion test | PE/MEP sign that AI review is advisory input only | D-13 fix; LF-110 |
| 25 | an objective that steers; a persisted, API-driven run on a real design | designer sign-off on applied deltas | D-14/D-15; real objective after LF-102 |
| 26 | per-module CAD; signed 9A visual gate | none | per-module export slice; D-7 (DAE/3MF) operator call |
| 27 | any dimensioned, issuable document | draughtsman standards; engineer-signed calc reports | LF-108 after LF-101 |
| 28 | client-grade presentation renders | none | E5/presentation epoch (deliberately after engineering trust) |
| 29 | any contract artifact | AquaFlow owner (same company) defines the boundary | E6 epoch; manifest fixtures are the seed |
| 30 | any learning signal; failure/as-built capture | none | as-built feedback slice (E5) |

<!-- EVIDENCE-ANCHORS
{"anchors": [
 {"file": "backend/app/geometry/assembly.py", "must_contain": "expected 1"},
 {"file": "backend/app/geometry/assembly.py", "must_contain": "TANGENT"},
 {"file": "backend/app/geometry/gates.py", "must_contain": "def validate_structural_gate"},
 {"file": "backend/app/geometry/gates.py", "must_contain": "def validate_hydraulic_gate"},
 {"file": "backend/app/geometry/gates.py", "must_contain": "def validate_fabrication_gate"},
 {"file": "backend/app/geometry/gates.py", "must_contain": "def blocking"},
 {"file": "config/gate_profiles.yaml", "must_contain": "signed_off"},
 {"file": "config/gate_profiles.yaml", "must_contain": "design_wind_speed_m_s"},
 {"file": "backend/app/api/routes_assembly.py", "must_contain": "def post_design_exports"},
 {"file": "backend/app/geometry/segmentation.py", "must_contain": "def segment_solid"},
 {"file": "backend/app/ai/call_log.py", "must_contain": "uncapped paid dispatch"},
 {"file": "backend/app/dna/store.py", "must_contain": "cannot become a precedent"},
 {"file": "backend/app/council/prompts.py", "must_contain": "disagreement_register"},
 {"file": "backend/app/council/critique.py", "must_contain": "objective_score"},
 {"file": "backend/app/council/orchestrator.py", "must_contain": "producers"},
 {"file": "schemas/design_spec_v1.json", "must_contain": "hydraulic_network"},
 {"file": "backend/app/geometry/luxexchange.py", "must_contain": "content_digest"},
 {"file": "backend/app/geometry/export_formats.py", "must_contain": "README_DWG_SKP"},
 {"file": "backend/app/costing/budget.py", "must_contain": "BudgetViolation"},
 {"file": "backend/app/geometry/primitives/sculptural_column.py", "must_contain": "6000"},
 {"file": "docker/render/render_scene.py", "must_contain": "build_lighting"},
 {"file": "config/costing.yaml", "must_contain": ""},
 {"file": "scripts/spend_admin.py", "must_contain": ""},
 {"file": "PRODUCTION_V1_REPORT.md", "must_contain": "09ff920ccbbb"}
]}
-->

## Critical safety/engineering assessment

Safety-critical systems (per SCOPE.md designation) and their scores:
**#3 Geometry Integrity = 4 ✓** — the only one at or above 4/5.
**Below 4/5: #5 Structural Load (3), #6 FEA (0), #7 Foundation (1),
#8 Hydraulic (2), #16 Panelization/fabrication (2), #17 Welding (1),
#19 Maintainability (1).**

- **Geometry integrity — TRUSTWORTHY.** The one-connected-body rule is
  enforced by code at four independent levels and re-proven on the mesh;
  the system refuses to build a disconnected body. Not visual credit.
- **Structural — NOT TRUSTWORTHY.** Correct engine, no fuel, safety catch
  off: null thresholds, unsigned profiles, breaches warn.
- **Hydraulic — NOT TRUSTWORTHY.** What runs is honest; the network the
  schema requires is a nozzle-locator — its edges are read by nothing.
- **Foundation/anchors — ESSENTIALLY ABSENT.**
- **Fabrication — PARTIALLY TRUSTWORTHY.** Module limits real and
  per-axis; but `strict=False` on the operator/export paths, rigging
  permanently `needs_input`, and no module ever leaves as CAD.
- **Maintainability — ABSENT.**

By the owner's own rule — a failed safety-critical gate must prevent
production-ready classification — **LuxuryForm is not production-ready,
and today it cannot even self-classify**, because G4/G5 are structurally
incapable of failing and G10 does not exist.

## Gates G0–G10 — enforcement map

The G-labels exist nowhere in the repo; this maps them to what does.
"Enforced" means a failure blocks a downstream action in code.

| Gate | Exists as | Enforced? | Status |
|---|---|---|---|
| G0 Brief Complete | intake confirm (tier-1/2 readiness, 409) | Narrowly — blocks *confirmation* only; builds proceed with no intake | Functional |
| G1 Concept Approved | arbiter validity (3 distinct ids or session fails); fabricate requires a decision (422) | Inside the Council only; Designer builds don't check | Functional |
| G2 Geometry Valid | hard constraints → build 422; mesh fail → costing refuses, fabrication repairs | **Mostly enforced** — but a mesh fail does NOT block export | Strong |
| G3 Material Valid | wall/material floors, always binding | Enforced at build | Strong |
| G4 Structural PASS | `validate_structural_gate` | **ADVISORY** — blocks nothing; cannot fail (B-5) | Computation functional |
| G5 Hydraulic PASS | `validate_hydraulic_gate` | **ADVISORY** | Partial computation |
| G6 Lighting PASS | — | — | **Nonexistent** |
| G7 Fabrication PASS | `validate_fabrication_gate` + segmentation | Enforced only under `strict=True`; operator/export paths use `strict=False` | Split |
| G8 Maintainability | — | — | **Nonexistent** |
| G9 Cost PASS | budget check on the BOM route | Only when `?budget_amount=` is passed; export path bypasses it (D-19) | Holes |
| G10 Package Approved | — (PR-8 unbuilt; B-8 approvers unnamed) | DesignDNA accept refuses `fail` — the only enforced downstream refusal | **Nonexistent** |

## Traceability

**Owner's original test (Height 6 m → 8 m): preserved as specified, and
UNRUNNABLE under the current primitive envelope.** The tallest primitive
(`sculptural_column`) caps `height_mm` at 6000; 8 m on any single element
is refused with a 422 before any chain can propagate. This is recorded as
the owner asked, not silently rewritten.

**Stacked-assembly traceability test (replacement, code-traced at
`bfa5a77`; live execution belongs to the next suite run / PR-9):** change
a column 1.2 m → 1.8 m inside a 3-element stacked assembly
(plinth → basin_round → column). One `assemble()` call automatically
recomputes: parameter cross-constraints → geometry → derived anchors
(children move) → fixture bores re-cut → exact volume → **mass =
volume × density** → conservation check → **segmentation** (modules,
seams, heaviest module) → fabrication limits → STEP/GLB/scene.glb →
mesh validation → **structural loads** (centroid, lever, bearing, wind
silhouette) → hydraulic capacity/freeboard → **BOM drivers** (read from
the validation report, never re-measured — the BOM cannot disagree with
the gate).

The chain breaks in four places, ascending seriousness: (1) costing and
renders need manual reruns with **no staleness signal**; (2) hydraulic
operating conditions (depth/flow/bore) are human-entered and go stale;
(3) the two checks most sensitive to height — bearing and overturning —
are `needs_input` by default because their thresholds ship null; (4)
lighting/foundation/skeleton consequences don't exist to compute.

## Outputs · AI architecture · AquaFlow · Learning (condensed)

- **Outputs**: STEP/BREP/STL/DXF/SVG/GLB/OBJ/PLY sealed and reproducible;
  USD/USDZ/FBX/ABC produced but excluded (non-reproducible, ADR-045/057);
  DAE/3MF unavailable (D-7); DWG/SKP impossible with in-package
  workaround; **IGES absent entirely**; CNC/flat patterns/panel drawings
  absent; the DXF is undimensioned 2-view line art; of the owner's
  document list, only machine-readable JSONs + the cost-BOM exist.
- **AI architecture**: six genuinely separated pipeline seats
  (distinct providers, code-enforced critic exclusion, binding arbiter) —
  but pipeline stages, not disciplines: Designer ✓, Chief-Engineer ≈
  arbiter, Structural/Hydraulic/Lighting/Cost ✗ (one fused ENGINEER
  prompt). The exclusion rule reads the model's self-claimed provider
  (D-13).
- **AquaFlow**: zero. The assembly manifest's nozzle fixtures (position,
  count, bore, cut into real geometry) are the natural seed of a future
  fixture-coordinate export; no contract exists in either direction.
- **Learning/CogniNet**: zero CogniNet. DesignDNA is real, explainable,
  quarantined memory of **successes only** — failures are refused entry,
  and no as-built data (hours, actual costs, supplier prices, failures,
  site/install problems, performance) is captured anywhere.

## New-defect register (recorded as debts D-13…D-23 in NEXT.md)

| ID | Defect | Found by |
|---|---|---|
| D-13 | Critic producer-exclusion reads model-claimed `meta.provider`, not dispatch truth — a lying model defeats the independence rule (one-line fix + adversarial test) | AI agent |
| D-14 | Critique objective: `margin = 1.0` hardcoded; the score is recorded and never steers or stops the loop | AI agent |
| D-15 | `CritiqueLoop` stores an injected db handle and never persists a round (JSON file only) | AI agent |
| D-16 | The parallel arbiter reply is dispatched and billed but never parsed — paid-for evidence nobody reads | AI agent |
| D-17 | `live_verify_providers.py`'s hand-rolled meter omits both ADR-061 safety-lock triggers (`pricing_failure`, actual-above-bound); `models.list()` runs unmetered on an unverified non-billing assumption | AI agent |
| D-18 | No static scan enforces the AI fence (no SDK client / `_raw_*` outside `app/ai/providers/`) — cheapest missing guardrail | AI agent |
| D-19 | Budget gate runs only when `?budget_amount=` is passed; the export path bypasses it entirely; no ceiling is stored on a design | gates agent |
| D-20 | Costing has no visual gate file at all | fabrication agent |
| D-21 | Segmentation planes know nothing about internal services — a saw plane can bisect a nozzle bore | water agent |
| D-22 | The Blender camera rig is duplicated in two hand-synced files | viz agent |
| D-23 | The frontend never calls costing — no BOM/price surface exists in the UI | gates agent |

Also recorded: `LayeredGateReport.blocking` is dead code (consumed by
LF-103A); the frontend has zero tests (`tsc + vite build` is a compile
check, not a test — LF-105).

## Roadmap

Architectural invariants preserved throughout: **LLMs produce constrained
specifications/programs; deterministic kernels create geometry.** No
BREP/mesh/hybrid representation is preselected before the B-11 references
and installed-kernel feasibility are examined; any change to STEP as the
canonical artifact requires an explicit ruling.

**Immediately after this audit closes (owner ruling, 2026-09-01):**

- **LF-103A — close the unsafe export boundary.** FAILED validation must
  never produce a clean fabrication package. NEEDS_INPUT may produce an
  explicitly **PRE-FABRICATION** package — visibly watermarked, carrying
  `ENGINEERING_WARRANT.txt` naming every unresolved check and the
  professional input each requires. A package must never appear
  production-ready while thresholds are unsigned. Viewing and diagnostic
  exports are preserved; only clean fabrication/issuance claims are
  blocked. **Deliberately does not wait for LF-102's engineer values.**

**Milestone A — Free-form Sculpture Demonstrator.** LF-103A → **PR-2.5
discovery** (blocked on B-11: 3–5 reference designs, materials/processes,
sculpting-controls ruling) → approved free-form implementation slice(s)
with their own gates → the demonstration chain: brief → Council
alternatives → deterministic watertight free-form geometry → validation →
segmentation → render → export.

**Milestone B — Internal Fabrication-Geometry Beta.** Milestone A plus
the trust core: LF-102 (signed thresholds — engineer's numbers), LF-101
(material allowables — the keystone), B-3/B-4 (rate card + verified
prices → first real quote total), minimal LF-104 (consume
`hydraulic_network.edges` → head + duty point), B-10/PR-7A/B (operator
workflow controls on durable jobs), the cheap safety fixes (D-13, D-18),
LF-105 (frontend tests), and the B-1 visual-gate walkthrough. **The
approved PR-4…PR-9 program runs inside this milestone and delivers it —
PR-0…PR-9 is Milestone B, not Production v1.**

**Milestone C — Production v1** (normalized ≥ 80% AND every
safety-critical system ≥ 4/5). Honest arithmetic: 80/100 ≈ 89.6/112 raw
vs 35.4 today. **Not reachable by code alone.** Staged epochs after B,
each needing hired professional engineering input: E1 structural
(foundation design, skeleton generator, FEA-or-defensible-closed-form —
structural PE), E2 water (network solver, pump selection, equipment
schedules — MEP), E3 lighting + kinetics (electrical engineer;
submerged-fixture safety codes), E4 manufacturing (dimensioned drawing
engine, per-module CAD, flat patterns, sequencing, maintainability
docs), E5 intelligence (discipline agents with tool access to real
calculators; as-built feedback so DesignDNA learns from failures and
actuals), E6 AquaFlow contract. Professional sign-offs (B-8, PE, MEP,
electrical, welding) are prerequisites, not enhancements.

## Re-running this audit

1. Note the baseline: this document scores commit `bfa5a77`. A re-audit
   must state its own commit and re-verify, not inherit, every score.
2. `python scripts/gate_scope_audit_auto.py` (host or backend container,
   $0, offline) verifies this document's internal consistency and its
   evidence anchors against the working tree.
3. The scoring rubric, weights (÷112) and safety-critical set come from
   `SCOPE.md` — never from a session's memory of them.
