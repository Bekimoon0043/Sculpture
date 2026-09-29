# CLAUDE.md — LuxuryForm Studio

You are the sole author of this codebase. Read this file at the start of every session.

## What this is

An internal design platform for LuxuryCon (Addis Ababa), a company that builds monumental fountains, sculptures and water infrastructure. It takes a project brief in plain language and produces fabrication-ready geometry, engineering validation, costed BOMs, renders and export files.

Single operator: the CEO, who has no coding background and directs all development through AI. Explain the **why** alongside the **what**. Give exact copy-paste commands for anything he must run himself.

What is left, in order, with its blockers: `NEXT.md` — the loop state file,
rewritten at the close of every slice. Architecture decisions: `DECISIONS.md`.
Known gaps: `LIMITATIONS.md`. Read all three before your first change in a
session. The owner's 30-system scope: `SCOPE.md` (recovered 2026-09-01,
ADR-062 — weights normalize by 112; authoritative once the owner
countersigns `gate_scope_audit_visual.md`); the honest position against it:
`DEVELOPMENT_AUDIT.md` (31.6/100 at `bfa5a77`). Milestone names (ADR-062):
A — Free-form Sculpture Demonstrator; B — Internal Fabrication-Geometry
Beta (what PR-0…PR-9 delivers); C — Production v1 (normalized ≥80% AND
every safety-critical system ≥4/5 — never call anything less Production
v1).

## The core architectural truth

LLMs do not generate geometry. They generate text. **They write the program that draws**; a deterministic CAD kernel (OpenCASCADE via build123d) executes it. Any design that asks a model to output a mesh is wrong.

## Non-negotiable rules

1. **No stubs, no mocks, no placeholders, no TODO.** If a module is written, it works and a test proves it with real data.
2. **No fabricated capability.** If something cannot be done, put it in `LIMITATIONS.md` and build the real alternative. Never simulate an API response to make a demo look complete.
3. **Every phase ends at a hard acceptance gate**, split in two: `gate_phaseN_auto.py` (runs at $0 forever, non-interactive, clear exit codes) and `gate_phaseN_visual.md` (the operator checks by eye).
4. **Vertical slice first.** Depth before breadth.
5. **Determinism from the Design Spec onward.** Identical spec + seed + pinned image = byte-identical STEP. Brief → Spec is non-deterministic by nature. Never write a gate that tests brief-level reproducibility.
6. **Metric, SI, explicit units.** A unitless number is a bug.
7. **Local-first.** No project data leaves the machine except logged AI API calls.
8. **Every AI call logged** — model, prompt, response, tokens, latency, cost — auditable back to the decision it produced.
9. **ADR-009: no third-party endpoint, model string, SDK shape or price from training-data recall.** Fetch from live provider docs, record the fetch date. This rule exists because violating it cost three separate multi-hour failures.
10. **ADR-005: AI-written code executes only in the sandbox** — separate container, non-root, no network, read-only filesystem except one scratch mount, CPU and memory limits, hard timeout. Never in tests, never in the gate.
11. **Parameter ranges derive from material and engineering arithmetic**, per material, with the reasoning recorded. Never from what looked reasonable when the primitive was written.
12. **Report failures honestly and immediately.** A truthful failure report is worth more than a successful-looking demo. Never claim something works without showing the command and its real output.

## The operator's environment — plan around these

- Windows, PowerShell. `curl` is aliased to `Invoke-WebRequest`; give PowerShell-native commands, not cmd syntax.
- **Build machine since 2026-09-25 (ADR-073):** Lenovo 83JJ, i7-13650HX
  (20 threads), 24 GB RAM, RTX 4060 laptop GPU, Windows 11 Pro with a
  **zh-CN system locale** (host-side subprocess decoding must say UTF-8
  explicitly — GBK is the default), Docker Desktop 4.92 on WSL 2
  (engine sees 20 CPUs / ~11.5 GB). The GPU is present but the rule
  stands: **GPU optional, never required** (LIMITATIONS §3) until an
  ADR says otherwise. Windows user is `Lenovo`; the repo folder is
  owned by Administrators — `icacls` granted `Lenovo` full control.
  Historical (2026-08-01 → 09-16): i7-8550U, 12 GB, no GPU, 6 GB Docker
  cap — the constraints the phase reports were measured under.
- **The connection is slow and drops.** Measured 2026-09-28 on this
  machine: **~31 kB/s to files.pythonhosted.org** (the old line was
  ~320 kB/s), frequent resets. Anything that downloads must retry,
  resume, and be cached in its own Docker layer. This has cost more
  time than any code defect. The Dockerfile's `PIP_INDEX_URL` build
  arg exists for exactly this: `https://pypi.tuna.tsinghua.edu.cn/simple`
  served the pinned OCCT wheel at ~1 MB/s here (mirror = transport only;
  pip hash-checks every pinned wheel). Mirrors are location-dependent —
  re-measure before relying on one (ADR-017 caveat).
- Repo: `C:\Users\burook\luxuryform` → `github.com/Bekimoon0043/Sculpture`
  (historical: `C:\Users\buroo\luxuryform` → `burook-Luxury/luxuryform`).
- **`data/` on this machine started EMPTY (2026-09-28).** The previous
  machine's designs, the preserved scratch backlog (D-29), the
  uncertain reservation `9077e77a…` and the 16 operator-local free-form
  reference images are NOT here until the operator copies them.

## The loop

Work runs as repeating gated slices, driven by the slash commands in
`.claude/commands/`: `/lf-orient` → `/lf-next` (plan, stop for approval) →
`/lf-build` → `/lf-gate` → `/lf-close` (docs + one commit + push), plus
`/lf-broke`, `/lf-spend` and `/lf-drift` as standing commands. Each command
carries the rules above so they do not depend on recall. The operator's guide
to the loop is `docs/operator/06_the_loop.md`; the queue itself is `NEXT.md`.

## Working method

- **Report the plan before coding** on any new phase. Repo structure, schema, approach, and anything in the order you believe is wrong. Wait for approval.
- **Commit per gate**, with a clear message. One commit that can be rolled back.
- Keep `NEXT.md`, `LIMITATIONS.md`, `DECISIONS.md` and the phase report current in the same commit as the change.
- After any change touching `backend/`, tell the operator to rebuild: `docker compose up --build -d`.
- Gates: every `scripts\gate_*_auto.py` runs at $0 with no network beyond
  the operator's own machine. **The roster is exactly the files matching
  that glob — 23 scripts as of 2026-09-01 (PR-3 added `gate_pr3_auto.py`,
  PR-1 added `gate_pr1_auto.py`, PR-2 added `gate_pr2_auto.py`, the
  Master Scope audit added `gate_scope_audit_auto.py` — pure file checks,
  host or container — and LF-103A added `gate_lf103a_auto.py`, hermetic,
  in the backend container; later slices grew the roster to 29 as of
  2026-09-09 — see `NEXT.md` "Suite and roster state" for the current
  count and each script's required state). Nothing
  discovers or runs them
  automatically: a session lists the glob and runs each one explicitly**,
  before and after any change to `backend/`. Historical counts stand as
  recorded: all 18 pre-PR-3 gates passed on 2026-08-27 (PR-0 evidence:
  17 with the render worker down + `gate_phase9b_auto` with it up; see
  `PRODUCTION_V1_REPORT.md`). Pin the render-worker state
  before a run and re-verify it when the run ENDS — a mid-run manual
  start silently flips results (use `docker compose rm -sf render-worker`
  for a worker-down run, not `stop`).
- The Hub status file regenerates with `python scripts\generate_hub_status.py --out "E:\Burook platform development\Luxurycon\AI-Team-Hub\luxuryform_status.json"`.

## Build status

Phases 1, 2, 3, 4 CLOSED (gates PASS 2026-08-01 / 08-04 / 08-07 / 08-17).
Phase 6 slice A1 (assembly core) CLOSED, auto gate PASS 2026-08-20
(ADR-030, ADR-032). Phase 7A (primitive-agnostic API + manifest
persistence) built.

**Phase 8 (L5 layered validation) auto gate PASS 2026-08-21** — four
statuses, provenanced limits, overturning + ground bearing, derived
hydraulics (ADR-034, ADR-036).
**Phase 9A (export package) auto gate PASS 2026-08-21** — ten formats,
byte-reproducible self-verifying LUXEXCHANGE package (ADR-035, ADR-037).
**Phase 11 (DesignDNA), Phase 12 (brief intake) and Phase 13 slice A
(jobs/costs/backup) auto gates PASS 2026-08-22** (ADR-038 … ADR-041).
**Phase 8b re-gate PASS 2026-08-22** — intake context now drives the
hydraulic and structural gates to real verdicts, closing the Phase 8
dependency.

**Phase 9B (Blender render worker) auto gate PASS 2026-08-24** (ADR-043) —
headless Blender 4.5.12 LTS, Cycles CPU, four canonical views, 17 pinned
system debs and no mesa. This was the last piece needing a download.
**Phase 5 (vision critique loop) auto gate PASS 2026-08-24** — its render
dependency is now closed; what remains is the operator's live-spend gate.

**Phase 14 (Designer Workspace) auto gate PASS 2026-08-24** (ADR-044) —
library / selectable viewport / inspector / history strip, undo-redo,
hide-solo, swatches, measure, section plane, saved views, 2-up compare;
per-element named-node `scene.glb` + per-design read routes backend-side.
**Phase 14b (Blender-familiar controls) 2026-08-24** (ADR-046, frontend
only) — 1/3/7/5 view keys, ortho toggle, axis gizmo, MMB orbit +
Shift+MMB pan, frame-selected, outliner rename, T/N rail collapse, `?`
keymap card; no G/R/S by design (joints + parameters are the only editing
path).

**Phase 15 slice A (Designer UX hierarchy) 2026-08-24** (ADR-047,
frontend only) — viewport-first layout, Scene-first Add palette, compact
Lucide command bar, tabbed Design/Checks/Output rail and collapsible Recent
Builds. Frontend auto gate PASS; visual gate pending. Slices B-E remain open.

**Phase 15 slice B (designer controls) 2026-08-24** (ADR-048, frontend
only) — semantic parameter groups with full registry fallback, plain-language
validation summary with element targeting, and package-first Output. Frontend
auto gate PASS.

**Phase 15 slice C (kernel draft preview) 2026-08-24** (ADR-049) — the
same OpenCASCADE assembly path now returns a non-persisted, unvalidated
named-node GLB after debounced edits; stale responses cannot replace the
current document. Dedicated backend/frontend auto gate PASS.

**Phase 15 slice D (visual judgement) 2026-08-24** (ADR-050) — Studio and
Technical CAD views, bounded lighting/ground/1.7 m scale cues, one focused real
kernel primitive preview, and synchronized A/B views with changed build values.
Auto gate PASS for every registered primitive.

**Phase 15 slice E (project lineage) 2026-08-24** (ADR-051) — project-scoped
variant history, additive nullable project/parent design references, explicit
root-to-branch persistence and cross-project rejection before CAD work. Existing
designs remain Ungrouped. Backend/frontend auto gate PASS; visual gate pending.

Auto gates, all $0 and offline:
`gate_phase2/3/4/5/6a1/6a2/6b/6c/6c2/costing/8/8b/9a/9b/11/13a/14/15_auto.py`
plus `gate_pr3_auto.py` (loopback binding; split like gate 14 — STATIC
in the backend container with the host's live compose file piped in:
`Get-Content docker-compose.yml -Raw | docker compose exec -T backend
python scripts/gate_pr3_auto.py --static --stdin`; LIVE on the host:
`python scripts\gate_pr3_auto.py --live`), `gate_pr1_auto.py`
(per-axis max_module_m, ADR-059; in the backend container) and
`gate_pr2_auto.py` (atomic spend reservations, ADR-061; in the backend
container).
**D-28 (honest reservation bound, ADR-070) and MS-A1 (`perforated_screen`,
the first mesh-class primitive, ADR-071) closed 2026-09-15/16 on the host
chain — the host Docker engine was down, so their in-container suite +
roster re-runs are DEFERRED to engine recovery (recorded in the ADRs and
NEXT.md); MS-A1's gate is `gate_msa1_auto.py` (roster script 30, 54/54).
B-11b stays OPEN: perforated_screen is a perforated SKIN, not an open
lattice, and an owner mesh/lattice reference is still required.**
**SC-A1 (`crescent_ring`, ADR-072) closed the same day: registry 13,
new `stainless_316l_cast` material, `gate_sca1_auto.py` (roster script
31, 63/63); the organic liquid forms of the owner's reference are NOT
claimed. Same deferred in-container caveat.**
**PR-6 (costing tie-off, ADR-074) is BUILT, auto-gated and definitively
chained 2026-09-28/29, visual pending: `gate_pr6_auto.py` is roster script 32
(43/43); on pinned image `e5e5b4ecfa22` the in-container roster is 29/29 gates
PASS with 0 failures, the host gate modes are PASS, the full suite is 860
passed with `geo-worker` UP and 860 passed with it REMOVED, and
`gate_phase9b_auto` is NOT RUN because no render-worker image exists on this
machine — an unrun gate is never reported as PASS. Mixed
materials cost per element; cross-material joints own exactly one rate;
confirmed intake budgets bind at BOM/export; the real card has 47 required
null entries, so no client-ready total exists until B-3 closes.**
Note `gate_phase9b_auto.py` and the Blender-tier sections of
`gate_phase9a_auto.py` need the render-worker container running
(`docker compose --profile render up -d render-worker`); both still cost $0 and
use no network. 9a passes either way — with the worker down the four
Blender-only formats report `unavailable`, with it up they report `included`
but stay OUT of the reproducible package (ADR-045). `gate_phase14_auto.py` runs its geometry/API sections in
the backend container and its frontend section on the host
(`python scripts\gate_phase14_auto.py --frontend-only`); each run prints
which sections it covered.

Awaiting the operator's visual gates: `gate_phase8_visual.md`,
`gate_phase9a_visual.md`, `gate_phase11_13a_visual.md`,
`gate_phase9b_visual.md`, `gate_phase5_visual.md`, `gate_phase14_visual.md`,
`gate_phase14b_visual.md`, `gate_phase15_visual.md`, `gate_phase6_visual.md`
(the live one, ~$1), `gate_phase6b_visual.md`, `gate_phase6c_visual.md`,
`gate_phase6c2_visual.md`.
(`gate_pr3_visual.md` and `gate_pr1_visual.md` were signed by the
operator 2026-08-28; `gate_pr2_visual.md` was signed 2026-09-01 —
$5/run and $25/day retained by explicit ruling.)

**Phase 9B.5 + Phase 5 live run 2026-08-24 (ADR-045)** — USD/USDZ/FBX/ABC
are produced by the render worker (not sealed into LUXEXCHANGE: they are not
byte-reproducible), and the critique loop has been run against real vision
providers: 3 rounds, $0.042916, 5 agreed deltas applied, geometry rebuilt and
measurably changed. Reproduce with `scripts/run_vision_critique.py`; size the
iteration count with `scripts/measure_render.py`.

**Phase 6 slice C2 (segmentation) auto gate PASS 2026-08-27** (ADR-056) —
an element over `fabrication.max_module_m` is CUT by the kernel into
modules and both workshop limits bind on the modules, so an 11,346 kg
basin that was refused now builds as 9 pieces of at most 1,472 kg.
Volume conserved to 0.0000000000%; module counts measured, never
predicted; seams counted once per interface and matched to hand
arithmetic. Two costing lines moved from `not_computable` to
`missing_rate` and `crane_pick_kg` became the heaviest MODULE. It also
fixed three latent defects: costing returned HTTP 500 for every assembly,
the rendered BOM document 404'd for every design, and the LUXEXCHANGE
digest lost reproducibility the moment a real BOM was sealed into it.

Not started: **Phase 10** (vision critique of renders — no longer blocked,
now that 9B is built), **Phase 13 slices B+** (resumable job runner — see
LIMITATIONS.md §16). Phase 6 slice D remains open. Phase 5 is built and
auto-gated; only its live-spend visual gate is outstanding.

Nothing in the project still needs a large download: the Blender tarball is
fetched, and it is the last one.

Each closed phase has a `PHASE_N_REPORT.md` with its gate evidence; the
forward plans are `PHASE_8_VALIDATION_GATE_PLAN.md` through
`PHASE_13_RECOVERY_HARDENING_PLAN.md`.

> `SCOPE.md` EXISTS as of 2026-09-01 (ADR-062): the owner's 30-system
> scope, recovered verbatim from the owner's 2026-08-28 session transcript
> after being cited-but-absent since Phase 1 (B-6, partially resolved). It
> is owner-authoritative once the owner countersigns
> `gate_scope_audit_visual.md`; the honest position against it is
> `DEVELOPMENT_AUDIT.md`. Still missing and still cited in older reports:
> `SPEC_PHASE2.md`, `PHASE2_PLAN.md`, the "Master Build Order" and the
> "First Action" document — for those, the authority remains
> `DECISIONS.md`, `LIMITATIONS.md`, the phase reports, and
> `luxuryform-claude-code-commands.md`.
