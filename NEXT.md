# NEXT.md — the loop state file

**This file is the single source of truth for "what is left".** It is read at
the start of every session (`/lf-orient`) and rewritten at the end of every
slice (`/lf-close`). If this file and a phase plan disagree, this file is
stale and must be corrected in the same commit as the work.

Last updated: 2026-08-26 — derived from the repo, not from memory.

---

## 0. Where the build actually stands

| phase | state | evidence |
|---|---|---|
| 1 — provider layer, spend caps, audit log, gates | **CLOSED** | gate PASS 2026-08-01, `PHASE_1_REPORT.md` |
| 2 — geometry kernel, STEP/GLB, determinism, viewport | **CLOSED** | gate PASS 2026-08-04, `PHASE_2_REPORT.md` |
| 3 — the AI Council | **CLOSED** | gate PASS 2026-08-07, `PHASE_3_REPORT.md`, first live session $0.843842 |
| 4 — fabrication loop (AI writes CAD, sandbox runs it) | **CLOSED** | gate PASS 2026-08-17, `PHASE_4_REPORT.md`, live brief → watertight 2.6 m basalt cascade, $0.046777 |
| costing engine | **BUILT, gated, starved** | `scripts/gate_costing_auto.py`, ADR-031 — machinery honest, rate card empty |
| 6 — primitive library | **PLANNED, APPROVED, BLOCKED** | `PHASE_6_PLAN.md` approved 2026-08-17; blocked on B-1 below |
| 5 — vision critique + Cycles render | **PLANNED, NOT APPROVED** | `PHASE_5_PLAN.md`, 4 rulings outstanding (B-4) |
| 7 — resumable jobs, backup, cost dashboard, docs | **NOT PLANNED** | `luxuryform-claude-code-commands.md` |

Operator's stated order stands: **Phase 6 before Phase 5.**

---

## 1. BLOCKERS — these need the operator, not the agent

Nothing below can be unblocked by writing code. Each one names exactly what
is wanted and what it unblocks.

- [ ] **B-1 — Sign off `PHASE_6_SLICE_A_ENVELOPES.md`.** *Blocks: all Phase 6
      code.* The sheet is a filled draft with the arithmetic shown; correct
      the numbers or confirm them. Needs a ruling on: §2.1 joint overlap (the
      agent is least sure of concrete's ±5 mm), §2.2 min feature size, §2.3
      min internal tool radius, §3.1–3.3 the basin/plinth/column ranges.
      Confirm the METHOD only for §4 and the hash-protection approach in §5.
- [ ] **B-2 — Fill `config/costing.yaml`.** *Blocks: any client-facing quote.*
      The rate card is all nulls, so no real design can produce a total today
      — by design, not by defect. `GET /api/costing/rate-card` names every
      missing entry. **Biggest single win: quote basalt per m³ or per kg**
      (per-slab defers the largest BOM line to Phase 6 segmentation).
- [ ] **B-3 — Verify token prices** against the three providers' price pages
      and bump `pricing_version` in `config/pricing.yaml`. *Blocks: trusting
      any cost number.* LIMITATIONS §4. Currently `2026-08-v3`.
- [ ] **B-4 — Four rulings before Phase 5 slice 1** (`PHASE_5_PLAN.md` §9):
      Cycles-CPU-only with EEVEE out; the separate `render-worker` container
      and its 357 MB `bpy==5.0.1` download; `critique_render_seconds`
      (120 s proposed, 60 s is the faster/noisier option); and whether the
      objective score in §5 is the right definition of "measurably improves".
- [ ] **B-5 — Supply or retire `SCOPE.md`.** It is cited as authority by
      `CLAUDE.md`, the reports and `registry.py`, and **has never existed in
      this repository** (checked against full git history). Same for
      `SPEC_PHASE2.md`, `PHASE2_PLAN.md`, the "Master Build Order" and the
      "First Action" document.

---

## 2. THE WORK QUEUE — in order

Each entry is one loop iteration: `/lf-next` → approve → `/lf-build` →
`/lf-gate` → `/lf-close`.

### Next up

- [ ] **W-1 — Phase 6 slice A1: the assembly core.** *Blocked by B-1.*
      Entirely offline, $0 to iterate. Registry restructure, three revolved
      masses (`basin_round`, `plinth`, `sculptural_column`), per-member wall
      parameters, `registry.assemble()`, assembly validation, assembly
      determinism, AST whitelist narrowed to `{registry, math}` (ADR-030
      draft). **Gate A1 (auto, $0):** three primitives composed into ONE
      watertight body; `body_count == 1` at B-rep *and* mesh level; every
      declared joint verified to interfere; byte-identical STEP across two
      processes; the Phase 2 canonical hash `e1a59fa6…` unchanged.
- [ ] **W-2 — Phase 6 slice A2: the AI and the surfaces.** Two-tier prompt
      surface (index always, full detail only for the primitives this spec
      uses), spec→assembly mapping, designer primitive index + spec
      validation against the live registry, primitive-agnostic API, frontend
      refactor. **Gate A2 = the operator's Phase 6 gate:** a brief needing
      three different primitives produces one watertight assembly, viewable
      and exportable.
- [ ] **W-3 — Phase 6 slice B: edge treatments + fixtures.** `weir_edge`,
      `coping_profile`, `pool_edge_detail` as profile modifiers (never
      post-hoc booleans); `nozzle_ring` as a fixture family driven by
      `service_voids` and `hydraulic_network`. **Gate B:** a basin whose weir
      depth and nozzle bores come from `hydraulic_network`, not invention.
- [ ] **W-4 — Phase 6 slice C: extrusion and array masses.** `basin_rect`,
      `stepped_monolith`, `water_wall`, `torus_ring`, `blade_fin_array`,
      `lotus_petal_array`. **Gate C:** a 24-element polar array inside a
      3-primitive assembly, byte-identical STEP across two processes.
- [ ] **W-5 — Phase 6 slice D: free-form.** `basin_elliptical`,
      `basin_spline`, `spline_loft_mass`. **Gate D:** a free-form mass
      composed with two library primitives — *or* an honest LIMITATIONS entry
      saying which part of the watertight-by-construction guarantee does not
      hold. Both are acceptable outcomes. Neither is "tune until green".
- [ ] **W-6 — Phase 5 slice 1: render only, $0.** *Blocked by B-4.* Render
      worker image, GL library-closure audit with a permanent `ldd` guard,
      four camera views, budgeted Cycles CPU. **Ends with the measurement
      spike: real seconds on the operator's machine, reported before
      anything else is built.**
- [ ] **W-7 — Phase 5 slice 2: critique + consensus, fixture-replayed at $0.**
- [ ] **W-8 — Phase 5 slice 3: the live loop.** Projected ≈$0.47 for a full
      six-iteration loop; full pipeline ≈$1.36 against the $5.00 session cap.
- [ ] **W-9 — Phase 7: hardening.** Kill-and-resume job runner (the gate is
      literally: kill the process mid-design, restart, it resumes with no
      data loss), backup, cost dashboard, screenshot operator docs.

### Debts — small, real, unscheduled

Pick one up when a slice finishes early. Each is one commit.

- [ ] **D-1 — `data/geo_scratch/` is never reaped.** One directory per sandbox
      job, forever. Harmless today, not a cleanup story. (LIMITATIONS §9)
- [ ] **D-2 — The synthetic demo Council session lies.** `54e12d62` shows
      `completed` with `total_cost_usd $1.2624` and zero `ai_calls` rows.
      Budget enforcement is unaffected (ADR-003) but any spend read from
      `council_sessions` overstates by that amount. Mark it or delete it.
- [ ] **D-3 — Doc drift: LIMITATIONS §4 says `pricing.yaml` ships
      `2026-07-v1`; the file says `2026-08-v3`.** Fix in the same pass as B-3.
- [ ] **D-4 — No `PHASE_6_PLAN` companion for the costing layer.** The engine
      shipped with ADR-031 and a gate but no phase report. Either write one
      or record that the ADR is the report.
- [ ] **D-5 — The repair loop has never rescued a run.** Rounds 2 and 3 are
      diagnostic, not corrective, across four live runs. Not a bug — but it
      needs either a corrective mechanism or an honest "this is a diagnostic
      loop" rename. Revisit after Phase 6 changes the failure surface.

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
