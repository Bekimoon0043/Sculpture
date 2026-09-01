# SCOPE.md — the owner's complete LuxuryForm scope

## Authority — read this first

- **Provenance.** This scope was supplied by the owner on **2026-08-28** in a
  working session and was never committed to this repository (blocker B-6:
  every earlier document cited `SCOPE.md` as authority while it did not
  exist). It was recovered **verbatim** from the owner's 2026-08-28 session
  transcript on 2026-09-01 and reproduced below. Only text encoding was
  normalized (em-dashes, arrows, quotation marks — transport artifacts of
  the transcript format); no word was added, removed, or corrected.
- **The weight total is reproduced as supplied.** The 30 stated weights sum
  to **112**, although the document itself says "Total = 100%". This
  contradiction is **preserved, not silently corrected**. Every normalized
  percentage derived from this scope is computed as `raw ÷ 112 × 100`.
- **This file becomes owner-authoritative only when the owner countersigns
  `gate_scope_audit_visual.md`.** Until that signature it is a faithful
  reproduction awaiting confirmation.
  **COUNTERSIGNED 2026-09-01 — this scope is now owner-authoritative**
  (sign-off recorded verbatim in `gate_scope_audit_visual.md`; the owner
  confirmed the recovered scope correctly represents the requested
  product).
- **Future scope changes require an explicit owner ruling**, recorded as an
  ADR in `DECISIONS.md`. No session may reinterpret, extend, or trim this
  scope on its own judgement.

## Product milestone names (owner ruling, 2026-09-01)

These names are used consistently across the repository:

- **Milestone A — Free-form Sculpture Demonstrator**: brief → Council
  alternatives → deterministic watertight free-form geometry → validation →
  segmentation → render → export, demonstrated end-to-end (ADR-060; PR-2.5
  and its implementation slices).
- **Milestone B — Internal Fabrication-Geometry Beta**: Milestone A plus the
  engineering trust core (signed thresholds, gate-blocked packaging, material
  allowables, a real rate card, operator workflow controls, walked visual
  gates). **The approved PR-0…PR-9 program delivers Milestone B, not
  Production v1.**
- **Milestone C — Production v1**: the owner's complete threshold —
  **normalized score ≥ 80% against this scope AND every safety-critical
  system ≥ 4/5**. No document may describe anything short of this as
  Production v1.

## Safety-critical designation

The owner designates gates **G2 (Geometry Integrity), G4 (Structural),
G5 (Hydraulic), G7 (Fabrication)** as safety/engineering critical, and the
critical assessment covers geometry integrity, structural engineering,
hydraulic engineering, foundation/anchors, fabrication and maintainability.
The corresponding scored systems are **#3, #5, #6, #7, #8, #16, #17, #19**.
A failed safety-critical gate must prevent the system from being classified
as production-ready.

---

## The owner's scope, verbatim (2026-08-28)

LuxuryForm — Full Development Scope Audit & Next-Phase Planning

We need to perform a real engineering audit of the current LuxuryForm repository against the complete LuxuryForm Studio scope below.

IMPORTANT RULES

Do NOT judge the project based on:

- documentation alone
- TODO files
- task names
- commit messages
- UI appearance
- claims that something is implemented
- previous AI summaries

Judge the status from the actual current codebase.

You must inspect and, where possible, execute:

- frontend code
- backend code
- APIs
- database/schema
- geometry generation
- engineering calculations
- tests
- validation gates
- exports
- UI workflows
- integrations
- configuration
- actual runtime behavior

If something exists only as a mock, placeholder, hardcoded value, simplified formula, demo, or UI representation, classify it accordingly.

Do not give credit for something merely because a function/file exists.

For every subsystem, determine:

0 — Nonexistent
1 — Concept only
2 — Prototype
3 — Functional
4 — Validated
5 — Production-grade

For every score provide:

- Evidence from the repository
- Relevant files/modules
- Tests proving functionality
- What is missing
- Why it received that score
- What would be required to reach the next level

---

COMPLETE LUXURYFORM SCOPE

LuxuryForm should ultimately convert:

Idea / sketch / image / client brief
→ Concept alternatives
→ Parametric 3D sculpture
→ Engineering validation
→ Water-feature engineering
→ Structural engineering
→ Material engineering
→ Lighting engineering
→ Motion/mechatronics engineering
→ Fabrication engineering
→ BOM + costing
→ Production drawings
→ CNC/fabrication files
→ Installation engineering
→ AquaFlow integration
→ Client visualization/rendering

Critical principle:

Geometry cannot be separated from engineering.

An aesthetically good sculpture that cannot withstand wind, cannot be fabricated, has impossible weld access, inadequate pipe routing, or requires an impractical pump is a failed design.

Evaluate the repository against all of the following:

1. AI Concept Generation
2. Parametric 3D Geometry
3. Geometry Integrity
4. Material Engineering
5. Structural Load Engine
6. Structural/FEA Analysis
7. Foundation/Anchors
8. Hydraulic Engineering
9. Water Simulation
10. Pump/Equipment Selection
11. Lighting Engineering
12. Lighting Simulation
13. Dynamic Lighting
14. Kinetic Engineering
15. Structural Skeleton Generator
16. Panelization
17. Welding Engineering
18. Internal Service Routing
19. Maintainability
20. Fabrication Sequencing
21. BOM
22. Cost/Quotation
23. Engineering AI Copilot
24. Multi-Agent Review
25. Optimization
26. CAD/Manufacturing Export
27. Engineering Documentation
28. Visualization
29. AquaFlow Integration
30. Learning/CogniNet Integration

Use the complete detailed requirements in the supplied scope as the acceptance criteria for each subsystem.

---

REQUIRED AUDIT

First inspect the entire repository and establish the actual architecture.

Then create a table:

#| System| Weight| Score 0–5| Weighted Score| Evidence| Main Gap

Calculate the weighted overall percentage correctly.

The weights are:

1 AI Concept Generation — 4%
2 Parametric Geometry — 7%
3 Geometry Integrity — 5%
4 Material Engineering — 4%
5 Structural Load Engine — 7%
6 Structural/FEA Analysis — 7%
7 Foundation/Anchors — 4%
8 Hydraulic Engineering — 7%
9 Water Simulation — 4%
10 Pump/Equipment Selection — 3%
11 Lighting Engineering — 5%
12 Lighting Simulation — 3%
13 Dynamic Lighting — 3%
14 Kinetic Engineering — 3%
15 Structural Skeleton Generator — 5%
16 Panelization — 4%
17 Welding Engineering — 3%
18 Internal Service Routing — 3%
19 Maintainability — 2%
20 Fabrication Sequencing — 2%
21 BOM — 3%
22 Cost/Quotation — 3%
23 Engineering AI Copilot — 4%
24 Multi-Agent Review — 2%
25 Optimization — 2%
26 CAD/Manufacturing Export — 4%
27 Engineering Documentation — 3%
28 Visualization — 2%
29 AquaFlow Integration — 2%
30 Learning/CogniNet Integration — 2%

Total = 100%.

*(Editorial note, preserved contradiction: the thirty weights above sum to
112, not 100. See the Authority section — percentages normalize by 112.)*

---

CRITICAL ENGINEERING GATES

Separately evaluate these gates:

G0 — Brief Complete
G1 — Concept Approved
G2 — Geometry Valid
G3 — Material Valid
G4 — Structural PASS
G5 — Hydraulic PASS
G6 — Lighting PASS
G7 — Fabrication PASS
G8 — Maintainability PASS
G9 — Cost PASS
G10 — Production Package Approved

For each gate report:

- Current implementation
- Current automated validation
- Current test coverage
- Whether it actually blocks production readiness
- Score/status
- Missing requirements

A failed safety-critical gate must prevent the system from being classified as production-ready.

Pay particular attention to:

G2 Geometry Integrity
G4 Structural
G5 Hydraulic
G7 Fabrication

These are safety/engineering critical.

---

IMPORTANT EXISTING REQUIREMENT

The production sculpture must resolve into one genuinely connected fabrication body, rather than visually overlapping disconnected components.

Verify whether this is actually enforced by code and tests.

Do not give credit if the system only makes objects visually appear connected.

---

TEST THE REAL SYSTEM

Do not only read code.

Run the relevant existing tests and validation gates.

Find:

- total tests
- passing tests
- failing tests
- skipped tests
- relevant gate scripts
- frontend tests
- backend tests
- integration tests
- geometry tests
- engineering tests
- export tests

Where practical, execute representative workflows.

For example:

1. Create/load a sculpture
2. Modify geometry parameters
3. Generate geometry
4. Validate geometry
5. Run engineering calculations
6. Generate hydraulic data
7. Generate material/BOM information
8. Export available formats
9. Run relevant production gates

Record what actually works.

---

TRACEABILITY TEST

For the core requirement:

«Changing a geometry parameter must propagate into engineering consequences.»

Test whether something like:

Height 6m → 8m

actually causes recalculation of relevant:

- geometry
- weight
- structural loads
- structural members
- foundation/anchors
- hydraulic requirements where applicable
- lighting coverage
- materials
- BOM
- costing
- fabrication data

If it does not, identify exactly where the dependency chain breaks.

---

AQUAFLOW

Evaluate whether LuxuryForm has a real defined integration boundary with AquaFlow.

LuxuryForm should own:

Sculpture engineering

AquaFlow should own:

Fountain/show control

Evaluate the actual exchange of:

LuxuryForm → AquaFlow:

- fixture coordinates
- nozzles
- lights
- valves
- pumps
- DMX devices
- water zones
- kinetic devices

AquaFlow → LuxuryForm:

- show programming/control information

Determine whether this is a real API/data contract or only conceptual.

---

OUTPUTS

Evaluate actual support for:

3D

STEP
IGES
STL
OBJ
FBX
GLB/glTF
USD/USDZ

Manufacturing

DXF
CNC files
Flat patterns
Panel drawings

Engineering

Structural calculation report
Hydraulic report
Lighting report
Electrical calculations
Foundation design
Equipment schedules

Documentation

BOM
BOQ
Quotation
Fabrication methodology
Installation methodology
Maintenance manual

Drawings

GA
Elevations
Sections
Fabrication drawings
Weld drawings
Hydraulic schematic
Electrical schematic
Lighting layout
Foundation drawing

Only count an output as implemented if the current code can actually generate it.

---

VISUALIZATION

Check whether the same engineering model drives:

- day rendering
- night rendering
- 360°
- animation
- water simulation
- lighting simulation
- kinetic simulation
- site integration

Identify where the visualization model can diverge from the engineering model.

---

AI ARCHITECTURE

Evaluate the actual AI architecture.

Determine whether the system currently has:

- Designer AI
- Structural AI
- Hydraulic AI
- Lighting AI
- Fabrication AI
- Cost AI
- Chief Engineer AI

Determine whether these are genuinely separated agents/reviewers or simply prompts/functions inside one general AI workflow.

---

LEARNING / COGNINET

Check the current repository for any real CogniNet integration.

Do not award points for a future plan.

Determine whether LuxuryForm currently stores and learns from:

- previous geometry
- calculations
- materials
- fabrication hours
- actual costs
- quotations
- supplier prices
- engineering failures
- site problems
- installation problems
- client modifications
- pump performance
- lighting results

---

FINAL REPORT

After the audit, produce these sections:

1. Executive Summary

Give me the honest current state of LuxuryForm.

Example:

«Overall score: XX/100»

«Current maturity: Prototype / Functional / Validated / Production-grade»

Do not inflate the score.

---

2. Complete Scorecard

Provide all 30 systems with evidence and scores.

---

3. Critical Safety/Engineering Assessment

Clearly state the current status of:

- Geometry integrity
- Structural engineering
- Hydraulic engineering
- Foundation/anchors
- Fabrication
- Maintainability

Tell me whether LuxuryForm can currently be trusted to produce a real production sculpture.

---

4. What Is Actually Working

List the strongest implemented capabilities that are demonstrably functional.

---

5. What Is Missing

Group missing work into:

P0 — Critical blockers

Must be solved before production engineering claims.

P1 — Major engineering capabilities

P2 — Manufacturing/production capabilities

P3 — AI/intelligence capabilities

P4 — Optimization/future capabilities

---

NEXT DEVELOPMENT PLAN

Based on the actual audit, create a prioritized implementation roadmap.

Do NOT simply implement the scope in numerical order.

Instead determine dependencies.

For example:

Geometry foundation
→ geometry validation
→ engineering data model
→ material system
→ structural calculations
→ hydraulic calculations
→ fabrication model
→ BOM
→ costing
→ production gates
→ exports
→ AI orchestration

Identify the correct dependency graph for the current repository.

For every next task give:

- Task ID
- Priority
- Goal
- Why it matters
- Current code to modify
- New files/modules required
- Dependencies
- Acceptance criteria
- Tests required
- Production gate affected
- Estimated complexity

---

VERY IMPORTANT: DO NOT START IMPLEMENTING YET

This first task is an AUDIT ONLY.

Do not make code changes.

Do not create speculative implementations.
don't add anyfile to this project just tell me here
Do not modify files.

First give me the complete audit and implementation roadmap.

The objective is to establish:

WHERE LUXURYFORM ACTUALLY IS TODAY

and

EXACTLY WHAT WE SHOULD BUILD NEXT TO MOVE TOWARD THE FULL SCOPE.

At the end give me a concise:

"Recommended Next 10 Tasks"

These must be the highest-value tasks based on the actual repository state and dependencies.     don't add anyfile to this project just tell me here only

---

*(End of the verbatim scope. The "don't add any file" instruction governed
the 2026-08-28 in-chat audit; the owner's 2026-09-01 approval of the Master
Scope Development Audit slice explicitly supersedes it for this file and
`DEVELOPMENT_AUDIT.md`.)*
