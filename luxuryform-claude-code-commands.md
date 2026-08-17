# LuxuryForm — Claude Code commands, phase by phase

Paste these one at a time into Claude Code in VS Code. Wait for each to complete and be gated before moving on.

---

## SETUP — run this once, first

```
Read SCOPE.md, CLAUDE.md, DECISIONS.md, LIMITATIONS.md, and the PHASE_*_REPORT.md
files. Then run: git log --oneline -15, and git status.

Report back:
  1. Your understanding of this project in your own words
  2. Exactly where the build stands — phase, build step, what is closed
  3. Every open item in LIMITATIONS.md
  4. Anything in the repo that looks half-finished, inconsistent, or wrong
  5. Anything in SCOPE.md you believe is technically wrong or unachievable,
     and what you would do instead

You are taking over as sole author from a previous agent. Do not change any
code yet. I want to know you have the picture before you touch anything.
```

---

## PHASE 4 — finish it (brief → geometry)

**Goal:** the Council's chosen design becomes real geometry with no human writing code.

```
Finish Phase 4. Current state: the loop works end to end — AI writes CAD code,
the AST gate rejects illegal programs, the sandbox executes legal ones, a
bounded repair loop retries on failure. The last known defect was artifact
collection across the container boundary; a fix was pushed but I have not
verified it on my machine.

Do this in order:
  1. git pull, then docker compose up --build -d
  2. Run scripts/gate_phase4_auto.py and show me the verbatim output
  3. Run the live fabrication against session 32e1c68f and show me the result
  4. If it fails, diagnose from the actual error and worker logs — do not guess
  5. Fix, re-gate, commit

Then close the phase: PHASE_4_REPORT.md with the measured first-attempt success
rate and per-repair-round rates, the AST rejection catalogue, and the real cost
of a fabrication including repairs.

Gate: my brief produces a watertight solid that passes the Phase 2 validation
gate, with STEP and GLB I can open, and full lineage from spec to program to
artifact.
```

---

## PHASE 6 — the primitive library *(recommended before Phase 5)*

**Goal:** the platform stops being a fountain configurator and becomes a design platform.

```
Phase 6: the primitive library. This is the phase that makes the platform
general rather than a single-shape configurator.

Plan first, before any code. I want to see:
  1. The order you would build the fourteen primitives in, and why
  2. How the registry surface scales — the GEOMETRIST prompt currently carries
     one primitive's signature; how does it carry fifteen without becoming
     unusable?
  3. How primitives compose. A real fountain is a basin plus a plinth plus a
     column plus a nozzle ring. Does the GEOMETRIST assemble them, and how do
     you validate an assembly rather than a single solid?
  4. Per-material parameter envelopes for each, with the arithmetic behind
     every bound — the ADR-027 pattern, never demo defaults

Primitives: basin (round, elliptical, rectilinear, free-form spline), plinth,
weir edge, nozzle ring, sculptural column, torus/ring form, blade and fin
arrays, lotus and petal arrays, stepped monolith, water wall, reflecting-pool
edge detail, coping profiles, spline-lofted free-form sculptural mass.

Build them in slices — a few primitives, gated, then more. Not fourteen at once.

Gate: a brief that needs three different primitives composed together produces
one watertight assembly that passes validation and exports cleanly.
```

---

## PHASE 5 — the vision critique loop

**Goal:** the platform looks at what it made and corrects it. This is where "imagination plus perfection" lives.

```
Phase 5: the vision critique loop, plus Cycles rendering.

Plan first. Requirements:
  - Render orthographic front/side/top plus three-quarter perspective
  - Send to TWO vision providers (anthropic + openai; kimi is tiebreaker only —
    it measured 2.4x the cost per vision call)
  - Critique must convert to BOUNDED PARAMETER DELTAS restricted to registered
    parameter paths, with magnitude limits and two-provider consensus. Prose
    that cannot be expressed as a delta is recorded as an operator observation,
    never executed.
  - Cap iterations, log every round, keep every intermediate for comparison
  - The Arbiter validates every delta before re-solve

Hardware constraint: I have NO dedicated GPU. i7-8550U, integrated graphics.
Cycles must auto-detect and fall back to CPU at reduced samples for critique
renders. The gate must pass on my machine. Tell me the realistic render time
per iteration before you build it.

Cost constraint: six iterations x two providers per design is where this gets
expensive. Report the projected cost of one full critique loop before I approve
running it live.

Gate: a design measurably improves across at least three critique iterations,
with before/after renders and the parameter deltas that caused each change.
```

---

## COSTING — run this when I supply the rates

```
Wire up the costing layer using the rates I am supplying in config/costing.yaml.

Requirements:
  - Costs derive from validation numbers the platform ALREADY computes — mass,
    surface area, module count, seam length, crane pick weight. Never a parallel
    measurement path.
  - Multi-currency with dated FX
  - Every cost line shows its formula and its source rate. A number I cannot
    trace is a number I cannot defend to a client.
  - NEVER invent or estimate a rate. If one is missing, the report says so
    explicitly and does not guess.
  - The budget constraint check becomes real, not advisory — same treatment as
    the basin_diameter hard constraint

Gate: a completed design produces a BOM I could hand to a client, with every
line traceable to a rate and a formula.
```

---

## PHASE 7 — hardening

```
Phase 7: hardening. Crash-safe resumable jobs, backup, cost dashboard, and
operator documentation with screenshots.

Specific to my situation:
  - My connection drops constantly. Any long-running job must resume, not
    restart.
  - Kill the process mid-design, restart, the job resumes without data loss.
    That is the gate.
  - The operator docs must be written for someone with no coding background —
    exact copy-paste commands, PowerShell syntax, and what every error message
    actually means.
```

---

## STANDING COMMANDS — use any time

**When something breaks:**
```
[paste the verbatim error]

Diagnose from the actual error and the logs. Do not guess and do not write a
fix from recall. If it involves a third-party API, fetch the live docs first
(ADR-009). Show me what you find before you change anything.
```

**Before approving spend:**
```
Before running anything that costs money, tell me the projected cost and what
it buys. My caps are $5 per session and $25 per day.
```

**Weekly:**
```
Regenerate the Hub status and tell me anything that has drifted:
python scripts\generate_hub_status.py --out "E:\Burook platform development\Luxurycon\AI-Team-Hub\luxuryform_status.json"

Then review LIMITATIONS.md against the actual repo state and tell me which
entries are stale.
```
