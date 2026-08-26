# CLAUDE.md — LuxuryForm Studio

You are the sole author of this codebase. Read this file at the start of every session.

## What this is

An internal design platform for LuxuryCon (Addis Ababa), a company that builds monumental fountains, sculptures and water infrastructure. It takes a project brief in plain language and produces fabrication-ready geometry, engineering validation, costed BOMs, renders and export files.

Single operator: the CEO, who has no coding background and directs all development through AI. Explain the **why** alongside the **what**. Give exact copy-paste commands for anything he must run himself.

What is left, in order, with its blockers: `NEXT.md` — the loop state file,
rewritten at the close of every slice. Architecture decisions: `DECISIONS.md`.
Known gaps: `LIMITATIONS.md`. Read all three before your first change in a
session. (`SCOPE.md` is cited throughout this repo and does not exist — see
the note at the end of this file.)

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
- The Hub status file regenerates with `python scripts\generate_hub_status.py --out "E:\Burook platform development\Luxurycon\AI-Team-Hub\luxuryform_status.json"`.

## Build status

Phases 1, 2, 3, 4 CLOSED (gates PASS 2026-08-01 / 08-04 / 08-07 / 08-17).
Phases 5, 6, 7 not started. Operator's stated order: **Phase 6 (primitive
library) before Phase 5 (vision critique)**. Each closed phase has a
`PHASE_N_REPORT.md` with its gate evidence.

> `SCOPE.md` is referenced above but **does not exist in this repository and
> never has** (checked against full git history, 2026-08-17). The same is
> true of `SPEC_PHASE2.md`, `PHASE2_PLAN.md`, the "Master Build Order" and
> the "First Action" document, all cited as authority in the reports and in
> `registry.py`. Until the operator supplies or reconstructs them, the
> authoritative scope is: `DECISIONS.md`, `LIMITATIONS.md`, the phase
> reports, and `luxuryform-claude-code-commands.md`.
