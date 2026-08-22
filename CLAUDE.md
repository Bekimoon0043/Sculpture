# CLAUDE.md — LuxuryForm Studio

You are the sole author of this codebase. Read this file at the start of every session.

## What this is

An internal design platform for LuxuryCon (Addis Ababa), a company that builds monumental fountains, sculptures and water infrastructure. It takes a project brief in plain language and produces fabrication-ready geometry, engineering validation, costed BOMs, renders and export files.

Single operator: the CEO, who has no coding background and directs all development through AI. Explain the **why** alongside the **what**. Give exact copy-paste commands for anything he must run himself.

Full scope: `SCOPE.md`. Architecture decisions: `DECISIONS.md`. Known gaps: `LIMITATIONS.md`. Read all three before your first change in a session.

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
- Docker Desktop, WSL2, 6 GB cap. i7-8550U, 12 GB RAM, integrated graphics, **no dedicated GPU**.
- **The connection is slow and drops.** ~320 kB/s, frequent resets. Anything that downloads must retry, resume, and be cached in its own Docker layer. This has cost more time than any code defect.
- Repo: `C:\Users\buroo\luxuryform` → `github.com/burook-Luxury/luxuryform`

## Working method

- **Report the plan before coding** on any new phase. Repo structure, schema, approach, and anything in the order you believe is wrong. Wait for approval.
- **Commit per gate**, with a clear message. One commit that can be rolled back.
- Keep `LIMITATIONS.md`, `DECISIONS.md` and the phase report current in the same commit as the change.
- After any change touching `backend/`, tell the operator to rebuild: `docker compose up --build -d`.
- Gates: `python scripts\gate_phase8_auto.py` and `gate_phase9a_auto.py` run
  at $0 with no network. Both must pass before touching Phase 9B or later.
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

Ten auto gates, all $0 and offline:
`gate_phase2/3/4/6a1/costing/8/8b/9a/11/13a_auto.py`.

Awaiting the operator's visual gates: `gate_phase8_visual.md`,
`gate_phase9a_visual.md`, `gate_phase11_13a_visual.md`.

Not started: **Phase 9B** (Blender render worker — the only remaining part
that needs a download), **Phase 10** (vision critique, blocked on 9B),
**Phase 13 slices B+** (resumable job runner — see LIMITATIONS.md §16).
Phase 6 slices B–D and Phase 5 remain open.

Each closed phase has a `PHASE_N_REPORT.md` with its gate evidence; the
forward plans are `PHASE_8_VALIDATION_GATE_PLAN.md` through
`PHASE_13_RECOVERY_HARDENING_PLAN.md`.

> `SCOPE.md` is referenced above but **does not exist in this repository and
> never has** (checked against full git history, 2026-08-17). The same is
> true of `SPEC_PHASE2.md`, `PHASE2_PLAN.md`, the "Master Build Order" and
> the "First Action" document, all cited as authority in the reports and in
> `registry.py`. Until the operator supplies or reconstructs them, the
> authoritative scope is: `DECISIONS.md`, `LIMITATIONS.md`, the phase
> reports, and `luxuryform-claude-code-commands.md`.
