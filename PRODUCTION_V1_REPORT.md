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

## PR-6 — per-element costing, one-owned joints, confirmed budgets bind (BUILT 2026-09-28, ADR-074: auto gate PASS + definitive in-container chain PASS; visual gate PENDING; NOT closed)

### What it makes true

A design made of two materials used to be **unpriceable by construction**:
`GET /api/costing/bom/{id}` answered **HTTP 409 `mixed_material_assembly`**.
It now answers **HTTP 200** with a per-element BOM. Every element is measured
once, in its own material, from the manifest the assembler already persisted
(`mass_kg`, `volume_mm3`, and — new in PR-6 — `surface_area_mm2`, summed from
that element's own BREP while it is still in memory in `assembly.py`). One
measurement path per element; costing never reopens or reconstructs geometry.

- **Finishing is that element's own skin minus the joint faces touching it**
  (gate: `p1 exposed = 6.0 - 0.5 = 5.5000 m2`, `b1 exposed = 10.0 - 0.5 =
  9.5000 m2`), never a proportional share of the fused total. A manifest with
  no per-element skin reports `NOT_COMPUTABLE` and produces **no total**,
  naming the one rebuild action.
- **Split seams stay with the element that owns the cut.** Conservation is
  asserted, not assumed: `split 4.000000 + joint 3.000000 = 7.000000 m`;
  `manifest 7.000000 m`; `sum(seam lines) == split + joint` to 1e-6.
- **A cross-material seam is billed exactly once** — to one owner chosen by one
  recorded rule, or to nobody. With the shipped card's
  `joints.cross_material_owner: null` the line is `missing_rate` naming that
  path and **neither side is charged**. The gate pins the disproof:
  `both sides = 1200.00 ETB; once = 300.00 ETB` — overstating is impossible.
  Allowed values are `parent` (the element joined onto), `child` (the joined-on
  element) and `stronger_rate` (higher seam rate, only when both rates share
  currency/unit; ties go to parent and say so). This is a LuxuryCon commercial
  decision, so it ships **null and refuses** rather than guessing.
- **Shared costs occur once, at assembly level.** `install_crane`,
  `install_crew` and `install_transport` each appear exactly once, and the crane
  pick is the **heaviest module**, not the assembly mass:
  `pick=2700.0 total=7800.0`.
- **A confirmed brief's budget binds.** `budget.amount_max` is evaluated with
  no query parameter; an explicit parameter overrides it and both paths print
  their source; a **draft never binds** (`editing the intake reopens it as
  draft` → `a draft intake no longer binds the BOM`). A **complete** BOM above
  the confirmed ceiling raises **HTTP 422 before** a JobRow, a geometry
  rebuild, an export file, an ExportRow or a package byte is written. An
  **incomplete** BOM is `not_performed`, never PASS.
- **No total, no quote, while anything is missing.** Unchanged and preserved:
  with the real card the API reports `complete=False total=None` and the
  rendered text prints no TOTAL.

### The refusal this retires, and what REPLACES it in the permanent gate

The retired contract was asserted by the **permanent Phase 6C2 gate**, section
10, titled *"MIXED MATERIAL — refused, never mispriced"*, whose two checks were
`a mixed-material assembly is refused with 409` and `and the refusal names both
materials`. PR-6 replaced that section **in place** — it now reads *"MIXED
MATERIAL — per-element, never mispriced (PR-6)"* and asserts the opposite
facts: **HTTP 200, not 409**; `drivers.materials` equal to both real materials;
`elements` covering both; fabrication lines prefixed `p1/` and `b1/`; and the
real unfilled card still yielding `complete: False` with `total_usd: None`.
`tests/test_costing.py` never asserted the refusal and was not touched. The
string `mixed_material` now appears nowhere in production code, tests or gates
except as history in the new gate's own docstring — checked by grep, not
asserted from memory.

### Evidence — image `e5e5b4ecfa22`, identical at roster start and end

| Run | Result |
|---|---|
| `gate_pr6_auto.py` (roster script 32, in-container, throwaway DB) | **PASS — all 43 checks**, 10 sections, $0, no provider; `config/costing.yaml` sha256 `0f21cc458cb4…` byte-identical before/after; real DB/exports fingerprint `ee84c97fa5ee…` byte-identical |
| Full in-container roster on the pinned image, one gate at a time | **29/29 in-container gates PASS, 0 failures** (`gate_phase9b_auto.py` NOT RUN — the render-worker image is not built here; see the render-worker note under B-12) |
| Host-side gate modes | **PR-3 `--static` PASS, PR-3 `--live` PASS (LAN + loopback), `gate_scope_audit_auto` PASS, `gate_pr25_discovery_auto --host-drift` 66/66 PASS, `gate_phase14_auto --frontend-only` PASS** |
| Full pytest suite, `geo-worker` UP, same image | **860 passed, 4 warnings in 1589.18s (0:26:29), exit 0** |
| Full pytest suite, `geo-worker` REMOVED, same image | **860 passed, 4 warnings in 1642.17s (0:27:22)** — the same 860 as the `geo-worker`-UP run. Summary line verbatim; see the exit-code note below |

**Exit-code note, stated rather than glossed.** The `geo-worker`-UP run
captured its code: `SUITE_EXIT=0 ELAPSED_S=1591`. The `geo-worker`-REMOVED run
did **not**: the wrapper script that appends `SUITE_EXIT` deadlocked on stdin
(a hung `docker` client at 0 % CPU) and was killed; the run was relaunched with
plain file redirection, so nothing recorded the code. What IS verbatim is the
pytest summary — `860 passed, 4 warnings in 1642.17s (0:27:22)` — which carries
no failure and no error count. Recorded as a tooling wart of this session, not
as a product defect, and not upgraded into a claim it cannot support.

The focused evidence that preceded the final chain (recorded in ADR-074): 115
costing/mass/transport tests, 95 assembly/API/segmentation tests and 76 PR-6 +
export-boundary tests, all PASS.

**Measured operational note (D-1 family — recorded, not a new debt).** The
suite and the gates write real render-job scratch directories under
`data/render_scratch/`: **220 exist on this machine, 36 of them created during
today's chain.** The production database and exports are untouched (both
fingerprints above are byte-identical before and after), and D-1/D-29 already
record that these trees are never reaped and what that costs; nothing here is
deleted without an operator instruction.

The live API row in the gate is the one that matters most, because it is the
whole slice in one line: `mixed-material BOM returns HTTP 200, not 409 —
HTTP 200`, with `assembler persists each element's real skin area —
b1=4565362.444196689, p1=4838052.686528281` on a real two-material build.

### Cost

**$0.** Offline, no provider call, no AI-written code executed, no production
data touched (both fingerprints above).

### Not claimed

- **No client-ready quote.** `costing_version` is `2026-09-v3` and the real
  card has **47 required null entries** — verified against the running API, not
  from memory: `missing_count = 47`, and entry 45 of 47 is exactly
  `joints.cross_material_owner` (35 = 5 materials × 7 fields, plus 12
  shared/install/commercial/FX). B-3 stays release-blocking; the operator
  checklist is `docs/operator/12_rate_card_checklist.md`.
- **No frontend costing screen** (D-23 remains; PR-7B/B-10).
- **No live spend beyond what is already recorded**; the B-4 provider-price
  worksheet is delivered as a worksheet, not as fetched prices.
- **`gate_phase9b_auto.py` was NOT run** — the render-worker (Blender) image has
  not been built on this machine (a large download, deferred pending the
  operator's decision recorded under B-12) — and must never be reported as
  PASS until that image exists here.

---

## FF-A3 — a typed brief can ask for the ref-08 loop (BUILT 2026-09-09, ADR-069: auto gate PASS; visual gate PENDING; NOT closed)

**Claim, exactly.** A brief typed into the Brief tab and confirmed can
reach `freeform_loop`: the Designer index now prints every primitive's
parameter vocabulary and honesty lines generated from the registry; the
trusted mapper covers the lens's 13 registry keys (12 scalars +
`material_id`); the Designer boundary runs the mapper and each
primitive's own `validate()` before a spec is persisted; a dry design may
carry an empty hydraulic network; a ratio is a plain number. **Synthetic
hand-authored Council alternatives prove replay and pipeline
compatibility only — not that an AI selected the primitive from prose.**
The claim "typed brief → Council selection → sculpture" is not made
until the visual gate's Step 6 live demonstration is separately
cost-approved, run and recorded. One ref-08 family, 316L only, scalar
controls, incomplete mass, unresolved fabrication inputs, integrity-
gated, PRE-FABRICATION at best — all preserved; registry unchanged at
eleven; `e1a59fa6…` untouched. $0 throughout; no provider; no download.

### Build story, honestly

- **Red-first collapsed into same-window authoring** (as in PR-4/PR-5):
  the new test module and the code were written in the same pass. The
  first run of the new tests found three of the author's own defects,
  each fixed in the TEST or the GENERATOR, never in the checked code:
  the boundary re-ask needle assumed the embedment sentence ("wall_mm
  >= 6") but the registry's own text is the range floor
  (`wall_mm=4.0: Input should be greater than or equal to 6`, which
  fires first); the fixture generator set the altitude as the int 2355
  while the API round-trips the intake through its wire format and
  prints `2355.0 m` — the generator now round-trips the same way; the
  transcript API key is `specs`, not `design_specs`.
- **A real finding in the suite's canonical spec:** with the Designer
  boundary running the mapper, `valid_example_spec()` was refused —
  its nozzle node targeted `column_01`, which the slice-B rule
  (ADR-054) has refused since 2026-08-26. Every scripted Council test
  had been persisting a spec that fabrication would refuse. The node
  now targets `basin_01`; the check was not loosened.
- **The kernel cliff bit the fixture, loudly:** three of the six
  hand-authored alternatives passed the primitive's `validate()` and
  were REFUSED at build — the exact mirror of the acceptance lens
  (twist −20°, skew −0.15): "inner lens produced 1 solids, volume
  −326316588654.8 mm³ — expected one positive solid"; 4800×2700×1000,
  wall 8, twist −25°: "cavity collapsed or split: clearance corridor
  left 1 solids, volume −27648.4 mm³"; 3600×2200×800, twist −35°:
  "clearance corridor left 2 solids". Every refused set had a
  negative twist; six replacement candidates with positive twist all
  built (95.0 / 57.4 / 22.4 / 60.2 / 55.4 / 66.5 s) and three were
  taken. All six fixture alternatives then built through the kernel
  (85.4 / 38.5 / 22.0 / 34.1 / 53.4 / 38.8 s, one module each).
  Recorded in ADR-069 decision 6; `validate()` accepting what the
  kernel refuses remains the FF-A2 limitation.
- **Owner corrections 1–9** applied as written; PR-7A relayed and
  held at `1292e6c`; ADR-069 taken on main.

### Focused suite (development image, 2026-09-09)

`tests/test_ffa3_council_freeform.py` (17 tests) plus every module
touching prompts, mapper, schema, orchestrator, replay, intake,
fabrication and cascade:

```
155 passed, 2 warnings in 302.75s (0:05:02)
```

Host gates on the same tree: `gate_scope_audit_auto.py` PASS;
`gate_pr25_discovery_auto.py --host-drift` PASS 218/218, zero skipped.

### Development gate run (first run, container with the copied files)

`scripts/gate_ffa3_auto.py` — 9 sections, **55 checks, exit 0**, first
run, no gate edited to pass. Highlights, verbatim:

```
[5 fixture replay + registry validity + explicit parameters]
    synthetic: True
  [5] fixture == live prompt builders + schema + registry today    PASS  (245013 bytes)
    replayed f5a3e1c8: 15 calls, 6 specs, recomputed $0.20223 (never spent)
  [5] every spec names freeform_loop and passes mapper + validate() PASS  (6/6)
  [5] rank 1 states all 12 scalars + material_id explicitly (13/13) PASS  (13/13)
[6 trusted build of the rank-1 spec (mapper -> assemble -> persist)]
    design 6e40e2c4 built in 276.4 s; STEP f3ccb95345d8534b
  [6] hydraulics: water_designed basis 'has_water = false' from the intake PASS
    this process  pid 151  STEP f3ccb95345d8534ba30aa98e6817d6f0b341a80cf9c8ca36c860f5f54dca4d14
    other process pid 201  STEP f3ccb95345d8534ba30aa98e6817d6f0b341a80cf9c8ca36c860f5f54dca4d14
  [6] STEP sha256 == FF-A2 fixture STEP built in a second process  PASS
[7 export truth]
  [7] two package downloads byte-identical                         PASS  (2401702 bytes sha 53f4267adbe9)
[8 negatives]
  [8] two lenses (no joint possible) refused by the assembler      PASS  (an assembly needs exactly ONE root element (no joint); found 2: ['loop_01', 'loop_02'])
  [8] a lens stacked on a lens refused (cannot parent)             PASS  (loop_02: cannot stack_on loop_01 — primitive 'freeform_loop' exposes no stackable top face)
PASS -- all 55 checks passed at $0, offline, with no AI call and no production data touched.
```

The rank-1 Council spec's STEP digest `f3ccb953…` is the FF-A2
acceptance lens's digest, produced by two different processes.

### Definitive run on the rebuilt image (2026-09-09T09:46:18Z → 09:53:44Z)

Image `sha256:0d4180d2b8d79de7581b8360d8a131bbd569e2692cd82fb725aab9aee8371867`
(built 09:42:58Z); render worker UP, pinned at start; 12 of 12 FF-A3
files host == container by sha256 (`spec_mapper.py 2635b47e3781`,
`prompts.py 2fb3106344b8`, `orchestrator.py 3681540ed1ae`,
`routes_council.py 6419f93b84b1`, `design_spec_v1.json b96b783e4584`,
`gate_ffa3_auto.py 302ef55de5f0`, `make_ffa3_fixture.py 607b91f80a9c`,
`gate_pr5_auto.py 21fd408df6bf`, `council_session_ffa3_v1.json
d82404f37e3a`, `intake_ffa3_v1.json f4b8674d363a`,
`test_ffa3_council_freeform.py 97aa2b2cb875`, `test_design_spec_schema.py
bd2b667f9cfb`). `scripts/gate_ffa3_auto.py` **exit 0, 55/55**, verbatim
verdict lines:

```
[9 hermeticity before (health + settled fingerprint, D-26-safe)]
  [9] backend healthy before any production fingerprint            PASS  (HTTP 200 status='ok' after 0 poll(s))
  [9] DB/WAL fingerprint settled (two identical reads)             PASS  (db=a0e7225c322a wal=e3b0c44298fc after 1 poll(s))
[1 vocabulary truth: what the DESIGNER is told (registry-driven)]
  [1] 12 scalar keys + material_id = 13 registry keys              PASS  (12 + 1)
  [1] every scalar key printed with its [min..max]                 PASS  (12 keys)
  [1] ratio keys marked PLAIN number                               PASS  (plan_skew_ratio, bore_center_height_fraction, waist_height_fraction)
  [1] 316L-only line derived from SUPPORTED_MATERIAL               PASS
  [1] incomplete-mass inputs derived from INCOMPLETE_MASS_INPUTS   PASS  (3 inputs)
  [1] PRE-FABRICATION line derived from REQUIRES_FREEFORM_INTEGRITY PASS
  [1] every registered primitive gets a vocabulary line            PASS  (11 of 11)
  [1] schema primitive description names no phantom primitive      PASS  (no ids named; live index cited)
  [1] schema states {value, unit} for dimensions, PLAIN scalars for ratios/counts/enums PASS
[2 mapper truth: spec names -> registry keys, ratios plain]
  [2] no alias dangles (every target is a registry key)            PASS  (20 aliases)
  [2] every scalar key has at least one spec-level name            PASS  (all 12)
  [2] rank-1 Council spec maps to EXACTLY the FF-A2 acceptance parameters PASS
  [2] every ratio x every unit refused verbatim                    PASS  (18/18)
  [2] unknown parameter name refused naming the keys               PASS  (loop_01: freeform_loop: parameter 'petal_count' is not supported by th)
  [2] parameters.material_id contradiction refused                 PASS  (loop_01: freeform_loop: parameters.material_id='basalt_slab' contradic)
[3 Designer boundary: registry refusal -> re-ask, never persisted]
  [3] session completed with corrected=1                           PASS  (status=completed corrected=1)
  [3] exactly one re-ask carrying the registry's own text          PASS  (1 re-ask(s))
  [3] the refused spec was never persisted; 6 valid specs stand    PASS  (6 specs)
[4 typed intake -> composed Council brief (real API)]
  [4] intake created from operator-typed fields                    PASS  (HTTP 201)
  [4] no parsed/default field — operator or unknown only           PASS  (operator, unknown)
  [4] intake confirmed (tiers 1-2 answered)                        PASS  (HTTP 200 status=confirmed)
  [4] composed brief == fixture brief_text (one id substituted)    PASS  (1668 chars)
  [4] dry design: has_water false is operator-sourced              PASS
[5 fixture replay + registry validity + explicit parameters]
  [5] fixture is marked synthetic and states what it proves        PASS
  [5] fixture == live prompt builders + schema + registry today    PASS  (245013 bytes)
    replayed f5a3e1c8: 15 calls, 6 specs, recomputed $0.20223 (never spent)
  [5] 6 specs replayed, cost recomputed > 0                        PASS
  [5] every spec names freeform_loop and passes mapper + validate() PASS  (6/6)
  [5] rank 1 states all 12 scalars + material_id explicitly (13/13) PASS  (13/13)
[6 trusted build of the rank-1 spec (mapper -> assemble -> persist)]
    design e2d94385 built in 226.3 s; STEP f3ccb95345d8534b
  [6] one element, primitive freeform_loop                         PASS
  [6] total_mass_kg is null (never zero)                           PASS
  [6] required_validation_gates == what the registry declares      PASS  (freeform_integrity_v1)
  [6] design row carries the Council spec id (lineage)             PASS
  [6] freeform_integrity_v1 row PASS against the persisted topology PASS  (pass)
  [6] hydraulics: water_designed basis 'has_water = false' from the intake PASS  (hydraulics: water_context_v1.has_water = false)
  [6] fabrication lift row NEEDS INPUT naming the armature         PASS  (needs_input)
  [6] structural total_mass_kg NEEDS INPUT                         PASS  (needs_input)
    this process  pid 167  STEP f3ccb95345d8534ba30aa98e6817d6f0b341a80cf9c8ca36c860f5f54dca4d14
    other process pid 185  STEP f3ccb95345d8534ba30aa98e6817d6f0b341a80cf9c8ca36c860f5f54dca4d14
  [6] STEP sha256 == FF-A2 fixture STEP built in a second process  PASS
[7 export truth: PRE-FABRICATION, unresolved-only warrant, reproducible]
  [7] export seals PRE-FABRICATION                                 PASS  (HTTP 200 pre_fabrication)
  [7] two package downloads byte-identical                         PASS  (2401711 bytes sha 3ec3d9492368)
  [7] warrant names the unresolved professional inputs             PASS
  [7] warrant carries no passing statuses                          PASS
[8 negatives: single-element claim, wrong material, ratio unit]
  [8] two lenses (no joint possible) refused by the assembler      PASS  (an assembly needs exactly ONE root element (no joint); found 2: ['loop_01', 'loop_02'])
  [8] a lens stacked on a lens refused (cannot parent)             PASS  (loop_02: cannot stack_on loop_01 — primitive 'freeform_loop' exposes no stackable top face)
  [8] wrong material refused at the Designer boundary by name      PASS  (registry refusal: material_id='basalt_slab' is not supported by freeform_loop: only 'stain)
  [8] ratio with a unit refused at the Designer boundary           PASS  (registry refusal: loop_01: freeform_loop.skew: plan_skew_ratio is a dimensionless ratio an)
[9 hermeticity after + $0 static scan]
  [9] real DB byte-identical                                       PASS  (a0e7225c322a -> a0e7225c322a)
  [9] real WAL byte-identical                                      PASS  (e3b0c44298fc -> e3b0c44298fc)
  [9] spec_mapper.py provider-free                                 PASS
  [9] prompts.py provider-free                                     PASS
  [9] orchestrator.py provider-free                                PASS
  [9] make_ffa3_fixture.py provider-free                           PASS
  [9] gate_ffa3_auto.py provider-free                              PASS
  [9] no reference JPG in this tree (operator-local only)          PASS  (0 found)
PASS -- all 55 checks passed at $0, offline, with no AI call and no production data touched.
```

Note on the package digest: the two downloads within one run are
byte-identical (the check); across the two runs the package digest
differs (`53f4267adbe9` vs `3ec3d9492368`, 2,401,702 vs 2,401,711
bytes) because each run persists a new design id and intake id into a
fresh throwaway DB and the package records that identity. The STEP
digest, which records geometry only, is identical across both runs and
both processes: `f3ccb953…`.

### Definitive FF-A3 /lf-gate — risk-based protocol (2026-09-14)

Authorized by the operator under the PR-5 precedent. **Risk basis,
stated explicitly as the protocol requires: FF-A3 changes no rendering,
no packaging and no render-worker code** — its diff touches the Council
prompt/orchestrator, the trusted spec mapper, the Design Spec schema,
the demo-fixture loader, two fixtures, one test module, one new gate and
the documents. PR-4's two-state suite baseline is therefore RETAINED and
the suite was run ONCE, in the worker-REMOVED state.

Backend image **`sha256:772e352a34ea7b3bb6d1fcddab711f2b0348dd5ec4968604e0438ae8fb9013c3`**,
built from the final working tree at 09:02:08Z and **identical at the
start and the end of the chain**. (The image `0d4180d2b8d7` cited in the
build-stage evidence above no longer exists: the operator's own Step 1
rebuild replaced it with `f48d70fa` at 06:37Z, and this chain then built
`772e352a34ea` from the final tree. No code differs between them; the
documents edited after 06:37Z are in this image, which is why the
rebuild mattered.)

| # | stage | result |
|---|---|---|
| 1 | rebuild from the final tree, pin the image | `772e352a34ea`, containers recreated 09:02:08Z |
| 2 | host vs image byte identity, all 20 changed/new files | **20 SAME, 0 DIFF, 0 missing** |
| 3 | render worker removed with `compose rm -sf` | absent: `no such object`, 0 containers named render-worker |
| 4 | full pytest suite, worker REMOVED | **737 passed, exit 0, 5919.57s (1:38:39)** |
| 5 | in-container roster, worker REMOVED | **25 of 25 exit 0** (list below) |
| 6 | `gate_pr3_auto.py --static --stdin`, in-container | PASS, `sections run: static` |
| 7 | worker restored and pinned 11:37:02Z, `gate_phase9b_auto.py` | **FAILED. Rerun once under authorization: FAILED AGAIN at a later section. Both transcripts preserved below. NOT passing in this chain; accepted as unrelated measured infrastructure debt (D-29) under the risk-based exception.** |
| 8 | host and split-mode gates | scope audit PASS; `gate_phase14 --frontend-only` PASS (`sections run: frontend`); `gate_pr25_discovery --host-drift` **218/218**; `gate_pr3 --live` PASS (`live-lan, live-loopback`) |
| 9 | backend image at the end | **identical to the start** |

Stage 5, in order, every one exit 0:
`gate_phase2` · `gate_phase3` (VERDICT: PASS) · `gate_phase4` (VERDICT:
PASS) · `gate_phase5` (5 sections; "objective score before=0.64
after=0.96; bare total refused (None)") · `gate_phase6a1` ·
`gate_phase6a2` · `gate_phase6b` · `gate_phase6c` · `gate_phase6c2` ·
`gate_phase8` · `gate_phase8b` · `gate_phase9a` (worker removed: the
four Blender-only formats report `unavailable`, ADR-045) ·
`gate_phase11` · `gate_phase13a` · `gate_phase14` (`sections run:
geometry`) · `gate_phase15` · `gate_costing` ("no total, every gap
named, no number invented") · `gate_lf103a` · `gate_pr1` · `gate_pr2` ·
`gate_pr4` · `gate_pr5` · `gate_ffa2` (**63/63**) · **`gate_ffa3`
(55/55)** · `gate_ffa1` (**36/36**, "consumers found: 32 (allowlist
entries: 34)" — FF-A3 added no mass consumer). `gate_ffa1` was run LAST
by design (D-26). No gate was edited at any point in this chain.

#### Stage 7 — Phase 9B FAILED TWICE; both preserved verbatim

**This chain does NOT contain a passing Phase 9B.** Both invocations are
recorded below in full. Neither is described as a pass anywhere.

**INVOCATION 1 — FAILURE, verbatim and complete:**

```
Fontconfig error: Cannot load default config file
==============================================================
Phase 9B auto gate - Blender render worker (offline, $0)
==============================================================
[0] render scratch: /render_scratch
[1] PASS built test mesh (48808 bytes, 3 parts)
[2] queued job 4b56658db2f547ab; waiting for the render worker ...
FAIL [2] render-worker produced no result within 300s — is the render-worker container running? (docker compose ps render-worker)
      Is the render worker running? Start it with:
        docker compose --profile render up -d render-worker
```
`gate_phase9b_auto.py exit=1`. Worker status at that moment, before and
after the gate: `running started=2026-09-14T11:37:02.607157748Z` — the
worker was up the whole time.

**The render itself SUCCEEDED, 15 seconds after the gate gave up.**
`data/render_scratch/4b56658db2f547ab/result.json`, verbatim:

```json
{"bbox": {"max": [1.100000023841858, 1.099658489227295, 1.640000343322754], "min": [-1.100000023841858, -1.0996582508087158, -1.4774880696677428e-07], "size": [2.200000047683716, 2.1993167400360107, 1.6400004625320435]}, "error": null, "ok": true, "total_s": 37.487, "views": [{"bytes": 54547, "elapsed_s": 11.549, "name": "front", "path": "front.png"}, {"bytes": 54572, "elapsed_s": 7.821, "name": "side", "path": "side.png"}, {"bytes": 60958, "elapsed_s": 8.738, "name": "top", "path": "top.png"}, {"bytes": 61013, "elapsed_s": 6.649, "name": "three_quarter", "path": "three_quarter.png"}]}
```

Four PNGs on disk: `front.png` 54,547 B · `side.png` 54,572 B ·
`three_quarter.png` 61,013 B · `top.png` 60,958 B. **`total_s = 37.487`.**

**Timeline (UTC; the host clock is UTC−4, so a raw `ls` reads four hours
earlier — that is why the files first appeared to be from 07:39):**

| time | event |
|---|---|
| 11:37:02 | render worker recreated and started (restarts=0) |
| 11:39:17 | gate wrote `job.json` + `input.glb`, began its fixed 300 s wait |
| 11:43:54 | worker CLAIMED the job — 4 min 37 s after it was queued |
| 11:44:17 | the gate's 300 s deadline expired → FAIL |
| 11:44:32 | worker wrote `result.json`, `ok: true` |

**Cause.** On startup the worker drains every unfinished job in the
shared scratch mount. `data/render_scratch` holds **1,902 job
directories**, and the recreated worker processed **50 stale conversion
jobs** before it reached the gate's job. The gate's wait is a fixed 300
seconds, so it lost a race against a cold worker with a backlog. Nothing
about the render was slow: it took 37.5 s.

**Not caused by FF-A3** — the same risk basis stated above: this slice
changes no rendering, packaging or worker code, and every other piece of
evidence in this chain had already passed.

**Pre-rerun state recorded at 2026-09-14T12:05:23Z, before touching
anything:** backend image `sha256:772e352a34ea…`; worker
`running started=2026-09-14T11:37:02.607157748Z restarts=0`; scratch
directories **1,902**; stale jobs still lacking a `result.json`: **4**;
conversion jobs drained by the recreated worker: **50**; the four PNGs
at the sizes above.

**INVOCATION 2 — the one authorized recovery rerun. ALSO FAILED,**
verbatim and complete (no rebuild, restart, cleanup, deletion or
code/gate modification; warm worker, same image):

```
=== AUTHORIZED RECOVERY RERUN of gate_phase9b_auto.py ===
start 2026-09-14T12:09:57Z
worker BEFORE: running started=2026-09-14T11:37:02.607157748Z restarts=0
image BEFORE:  sha256:772e352a34ea7b3bb6d1fcddab711f2b0348dd5ec4968604e0438ae8fb9013c3
Fontconfig error: Cannot load default config file
==============================================================
Phase 9B auto gate - Blender render worker (offline, $0)
==============================================================
[0] render scratch: /render_scratch
[1] PASS built test mesh (48808 bytes, 3 parts)
[2] queued job e1d5d3be7f2c43bd; waiting for the render worker ...
[2] PASS render worker returned 4 views in 58.1s
[2b] PASS geometry arrived upright, Z up (size [2.2, 2.199, 1.64] m)
    front          stddev= 46.56  mean=  87.2  subject= 29.1%  54547 bytes
    side           stddev= 47.68  mean=  87.4  subject= 29.1%  54572 bytes
    three_quarter  stddev= 58.85  mean=  92.4  subject= 61.7%  61013 bytes
    top            stddev= 31.26  mean= 163.2  subject= 63.2%  60958 bytes
[3] PASS all four views carry real tonal detail
[4] PASS all six view pairs are distinct
FAIL [5] USD reported unavailable: the render worker did not pick up the conversion job within 20s; start it with 'docker compose --profile render up -d render-worker'
EXIT=1
end 2026-09-14T12:16:24Z
worker AFTER: running started=2026-09-14T11:37:02.607157748Z restarts=0
image AFTER:  sha256:772e352a34ea7b3bb6d1fcddab711f2b0348dd5ec4968604e0438ae8fb9013c3
```

It reached further (sections 1, 2, 2b, 3, 4 passed — the render itself
returned four views in 58.1 s, upright, with real tonal detail and six
distinct pairs) and then failed at section 5's **fixed 20-second**
conversion wait. The worker log shows that conversion job,
`conv515aca28338d`, completing at **12:16:28Z — four seconds after the
gate exited at 12:16:24Z**.

**Measured mechanism (timed inside the worker container, read-only):**

| measurement | value |
|---|---|
| directories in `/scratch` | **1,904** |
| `iterdir` + sort | 0.04 s |
| **one full pending-job scan** | **8.89 s** |
| pending jobs found | 0 |

The worker rescans the entire scratch mount on every poll, statting
roughly four paths per directory across a Docker bind mount to NTFS. At
1,904 directories one scan costs 8.89 s, so a 20-second budget allows
about two scan cycles and a newly queued job can miss both. **Pickup
latency scales with the backlog** — which is why raising the timeout is
explicitly NOT the accepted fix (owner ruling).

#### Acceptance of this chain under the risk-based exception (owner, 2026-09-14)

The operator accepted the definitive FF-A3 chain on this precise basis,
recorded verbatim:

1. **FF-A3 changed no rendering, conversion, packaging or worker code.**
2. **The previous closed Phase 9B PASS remains the regression baseline
   for those unchanged bytes.**
3. **The current render and conversion both completed successfully, but
   after their fixed gate deadlines** (render `ok: true`,
   `total_s: 37.487`, four views; conversion `conv515aca28338d -> ok` at
   12:16:28Z).
4. **The measured cause is the 1,904-directory scratch scan taking
   8.89 s per poll, producing queue-pickup latency.**
5. **FF-A3's own gate passed 55/55; the worker-removed suite passed 737;
   all 25 in-container gates, PR-3 static and all host gates passed.**

**This chain is NOT "all gates green" and must never be described that
way.** Phase 9B's current-chain result is **FAIL**, accepted as
unrelated measured infrastructure debt (**D-29**, linked to D-1) under
the risk-based protocol. No scratch artifact was deleted, moved or
modified; Phase 9B was not run a third time.

Full record in `gate_ffa3_visual.md`. Steps 1–5 confirmed by the
operator on the unchanged image `0d4180d2b8d7`, with one recorded
deviation: at the operator's explicit request the Step 3 intake fields
were entered by the session through the same `/api/intake` calls the
Brief tab makes rather than typed in the browser, and the 30 m/s design
wind is a TEST value entered at the operator's instruction, never a
site measurement.

**Step 6 — the one authorized live demonstration ran and halted after
one successful call.** It is recorded here because a truthful failure
report is the deliverable, not a successful-looking demo.

| # | role / side | provider | status | actual |
|---|---|---|---|---|
| 1 | researcher / primary | openai gpt-4o | ok, 490 in / 650 out | $0.007725 |
| 2 | researcher / parallel | kimi kimi-k3 | **ERROR "Connection error."** | $0 billed, reservation UNCERTAIN at $3.268608 |
| 3 | ADR-023 retry of 2 | kimi kimi-k3 | **reservation REFUSED** | — |

```
budget halt: run spend cap would be breached: scope
2a7d3e5b-2b78-42f6-9479-637f0e1feaa6 spent $3.276333 + reserved bound
$3.268608 > run cap $5.000000 — halting, state persisted (halt_and_report)
```

Session `2a7d3e5b-2b78-42f6-9479-637f0e1feaa6` = `halted_budget`,
**0 design specs, 0 arbiter decisions**. The Council never reached the
Designer stage, so it neither selected nor declined `freeform_loop`:
the demonstration did not reach the question. Nothing was rerun and no
prompt was touched. The fabrication attempt was NOT run — the
authorization said stop immediately if a provider call failed, and one
did. **The claim "typed brief → Council selection → sculpture" remains
UNMADE.**

Money: **$0.007725 actually billed**; $3.284036 counted against the
$25.00 UTC-day cap; no safety lock engaged. Reservation
`9077e77a-95ec-4633-b4be-c5a07ad4f74f` is preserved UNCERTAIN at its
full bound by operator instruction — not reconciled.

The cause is arithmetic, not a defect: ADR-061's cap-safe bound is
context window × input rate, and kimi-k3's 1,048,576-token window prices
every one of its three seats at $3.268608 against a $5.00 run cap.
Recorded as **D-28**; the fail-closed rule is not to be weakened.

**Owner ruling, 2026-09-14 (binding).** No second Step 6 attempt now. No
`council.yaml` change, no removal of kimi, no weakening of fail-closed
accounting, no increase to the permanent $5 / $25 caps. **Step 6 remains
NOT ACHIEVED and is never marked PASS**; the halted session is preserved
and **real Council selection of `freeform_loop` remains UNPROVEN**.
FF-A3 may pass its formal gates and close **only** as *"typed-brief/
Council contract implemented and fixture-gated; live end-to-end
selection blocked by D-28 and not claimed."* D-28 becomes the next
separate, rollbackable slice, planned via `/lf-next` and not begun until
FF-A3 closes and its plan is approved. Reservation `9077e77a…` stays
UNRECONCILED until the operator reports the Moonshot/Kimi console for
2026-09-14 08:22–08:23 UTC.

### Affected roster gates, same image, same chain (09:53:44Z → 10:22:39Z)

Run sequentially after `gate_ffa3` (never `gate_ffa1` first after a
rebuild — D-26), render worker UP throughout:

| gate | exit | verdict line |
|---|---|---|
| `gate_phase3_auto.py` (fixture replay + scripted sessions) | 0 | `VERDICT: PASS` |
| `gate_phase4_auto.py` (scripted fabrication loop) | 0 | `VERDICT: PASS` |
| `gate_phase6a2_auto.py` (mapper refusals) | 0 | `PASS — Phase 6 slice A2 auto gate: all sections passed` |
| `gate_phase6b_auto.py` (hydraulic wiring) | 0 | `PASS — Phase 6 slice B auto gate: all sections passed` |
| `gate_pr1_auto.py` (per-axis limits from spec) | 0 | `PASS — PR-1 auto gate: all sections passed` |
| `gate_phase13a_auto.py` (intake/jobs) | 0 | `PASS — Phase 13a auto gate: all sections passed` |
| `gate_ffa2_auto.py` (the lens, exact-eleven registry) | 0 | `PASS -- all 63 checks in every section that ran passed` |
| `gate_pr5_auto.py` (contract + D-10 sweep) | 0 | `growth-collection equalities: 8; structural equalities reviewed (listed, not exempt): 31` → PASS (the new gate's two exact counts carry `D-10-frozen:` reasons and are listed as reviewed) |
| `gate_ffa1_auto.py` (ADR-065 census, 36 checks) | 0 | `consumers found: 32 (allowlist entries: 34)` → PASS — FF-A3 added no mass consumer |

Host: `gate_scope_audit_auto.py` PASS; `gate_pr25_discovery_auto.py
--host-drift` 218/218. Not rerun in this build stage (unaffected by
FF-A3, left to the definitive `/lf-gate` chain): the remaining
in-container gates, `gate_phase9b` (worker up), `gate_pr3` static+live,
`gate_phase14 --frontend-only`.

### Full suite, same image, same chain (10:22:39Z → 12:06:15Z)

`docker compose exec backend python -m pytest -q`, render worker
**running** at the start of the chain and re-verified running at the
end, image `0d4180d2b8d7` identical at both ends:

```
737 passed, 3 warnings in 6202.65s (1:43:22)
```

720 (PR-5) + 17 new FF-A3 tests = 737; zero failures, zero skips
reported by the summary. Run ONCE with the worker up; the worker-removed
state is left to the definitive `/lf-gate` chain (FF-A3 touched no
rendering or packaging code, so PR-4's 707 two-state run remains the
unchanged baseline for the worker-sensitive tests).

---

## PR-5 — one story about lifting: AI contract, gate bases, scorer and documents (CLOSED 2026-09-08, ADR-068: auto gate PASS + operator visual gate PASS 2026-09-08)

`scripts/gate_pr5_auto.py` — 6 sections, 49 checks, exit 0, $0, offline,
no AI call; the real DB+WAL fingerprinted only after the live backend
answered `/api/health` ok and two consecutive identical reads (D-26-safe:
the first run after `up --build` waited 56 polls — ~14 s — for health and
settled on the first fingerprint poll; never an arbitrary sleep).
Operator visual gate `gate_pr5_visual.md` SIGNED 2026-09-08, verbatim:
"Steps 1–6 are all YES. The real design 621d7497… shows the basin pick
weight as the heaviest of 9 modules, 1,472.19 kg versus 11,346.1 kg
element total."

### Definitive chain — operator's risk-based protocol (2026-09-08T12:39:05Z → 14:17:30Z)

| Step | Evidence |
|---|---|
| 1. Rebuild from the signed tree (HEAD `74fc522`, 26 entries) | backend image **`753490ced0af38db…`**, identical at start, stage 1 and end |
| 2. Host/container identity | **26 of 26 PR-5 files byte-identical** (production, tests, gates, documents, `gate_pr5_visual.md`) |
| 3. Focused tests + slice gate | **132 passed** (117.89 s); `gate_pr5_auto` PASS 49/49, DB/WAL `25228669ef28`/`e3b0c44298fc` identical |
| 4. Full suite ONCE, render-worker REMOVED (`rm -sf`, verified absent at start and end of stage 1) | **720 passed, 3 warnings in 3246.54s (0:54:06)** — PR-4's 707 plus PR-5's 13; PR-4's 707 two-state run retained as the unchanged worker-sensitivity baseline (no rendering/packaging code changed) |
| 5. Roster, enumerated from the glob (28) and run in required states | 25 hermetic gates worker-removed all exit 0 (incl. `gate_ffa1` 36/36 — census 32 consumers / 34 entries, 83 legacy manifests clean; `gate_ffa2` 63/63; `gate_pr25` 198; `gate_pr4`; `gate_pr5`; `gate_phase14` container half; `gate_pr3 --static --stdin`); `gate_phase9b` PASS worker-UP (pinned "Up 1 second" → "Up 2 minutes"); host: `gate_pr3 --live` PASS, `gate_scope_audit` PASS ("LF-103A (entry 5) before PR-2.5 (entry 6) — 44 queue entries scanned"), `gate_phase14 --frontend-only` PASS, `gate_pr25 --host-drift` 218/218 |
| 6. Boundaries | compose state and image hash printed at every boundary; no drift |
| 7. Failures | none; no code or gate touched during the chain |

$0; no providers; no downloads. Closed as one commit on main.

### What it makes true

The GEOMETRIST contract, the fabrication gate's `needs_input` bases, the
vision-critique scorer and the operator documents now all say what the
gate has measured since slice C2: the crane picks the **heaviest module
after segmentation**, and `max_module_m` binds **per axis**. The scorer
no longer grades handling by whole mass and no longer invents a lift
limit: the live script's silent `max_lift_kg = 1000.0` default is gone.

### The scorer's five bases, verbatim from the gate (temporary manifests)

```
  9-module basin (complete, segmented)
    score=0.705538  basis=measured_heaviest_module  pick=1472.31  lift=2000.0
    reason: segmentation recorded the heaviest of 9 module(s) at 1472.310 kg (ADR-056)
  single complete element, unsegmented
    score=0.83  basis=single_complete_element  pick=850.0  lift=2000.0
    reason: one complete element, never segmented: its total 850.000 kg is the pick weight
  two elements, unsegmented
    score=None  basis=unavailable  pick=None  lift=2000.0
    reason: handling unavailable: 2 elements with no segmentation record: the assembly total is not what a crane picks
  segmented, NO lift limit declared
    score=None  basis=unavailable  pick=1472.31  lift=None
    reason: handling unavailable: no fabrication max_lift_kg was declared — nothing is defaulted in its place
  free-form, INCOMPLETE mass, segmented
    score=None  basis=unavailable  pick=None  lift=2000.0
    reason: handling unavailable: mass model incomplete: armature mass (FABRICATOR-INPUT-REQUIRED)
```

`None` is `None` — never 0.0, never compared (`score_delta` of an
unavailable score is `None`). The 9-module basin scores on 1,472.31 kg
(handling 0.263845 = 1 − 1472.31/2000), not on its 11,346 kg total.

### The D-10 sweep, now a roster check

`gate_pr5_auto` §5 on all 28 roster gates: **8 growth-collection
equalities, every one carrying a real `D-10-frozen:` reason** (ADR-066
exact-eleven; ADR-065 frozen legacy ten; ADR-066's three declared
inputs; ADR-030 import ceiling; the fixed B-11 reference record ×4);
**25 structural equalities listed as reviewed, not hidden**. Three
checks converted to timeless forms and verified in their new form: 6a2's
derived unknown name (`not_a_primitive_d395047c`, proven outside the
live registry), the scope audit's queue-position order (`LF-103A (entry
5) before PR-2.5 (entry 6) — 44 queue entries scanned`, PASS on the
host), and 6c2's six C2 rate-card paths by name.

### The fact FF-A3 starts from (measured, not assumed)

`PRIMITIVE INDEX offers 11 of 11 registered: … freeform_loop …` — the
fabrication-time contract ALREADY lists `freeform_loop`'s parameters to
the GEOMETRIST, while no brief, Council prompt or `spec_mapper` alias can
request it (LIMITATIONS §11 correction).

### Evidence — build run on image `f1b2d5ece31c`, definitive on `0d1be7cea13b`

| Evidence | Value |
|---|---|
| Focused tests (`test_pr5_contract` 10 new + `test_critique`, `test_mass_consumers`, `test_cascade`, `test_freeform_loop`, `test_costing`) | **132 passed** in 127.37 s |
| Mutation probe (container copy only): loosen "single complete element" to "any element" | exactly `test_multi_element_unsegmented_design_is_unavailable` FAILS (1 failed, 9 passed); restored 10/10 — clarification 2 is enforced by the test that names it |
| `gate_pr5_auto` | **PASS**, 49 checks, DB+WAL `25228669ef28`/`e3b0c44298fc` identical before/after |
| Edited roster gates, each rerun on the PR-5 image | `gate_ffa1` **36/36** (census lists the two new scorer symbols exactly), `gate_phase5` PASS (bare total now refused), `gate_phase6a2` PASS, `gate_phase6c2` PASS, `gate_ffa2` 63/63, `gate_pr25_discovery` 198/198, `gate_costing` PASS, `gate_pr4` PASS, `gate_scope_audit` PASS (host) |
| Host==container sha256 | `gate_pr5_auto.py` `6e31ab857350`, `gate_pr25_discovery_auto.py` `c09b418380af`, `critique.py` `fc596722293e` |
| The gate's OWN first run | FAIL 5/54 — all five my defects (a needle split by a line-wrap, one unmarked B-11 literal, a `len == len` false positive in the sweep rule, a check matching its own comment, a provider scan matching its own token list); fixed, rerun PASS. Recorded because a gate that never failed its author proves less. |

$0 throughout; no providers; no downloads; no schema/config/registry/
geometry change; Phase 2 hash `e1a59fa6…` unaffected.

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
