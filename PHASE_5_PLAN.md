# PHASE_5_PLAN.md — Vision Critique Loop + Cycles Rendering (2026-08-17)

**STATUS: PLAN — reported to the operator before any code, awaiting approval.
Nothing in this document is built. No money has been spent producing it.**

**GATE (operator, verbatim):** a design measurably improves across at least
three critique iterations, with before/after renders and the parameter
deltas that caused each change.

---

## 1. The two numbers you asked for before approving

### 1.1 Cost of a full critique loop — **≈ $0.47**, computed, not estimated

Derived from formulas fetched live today (ADR-009) against the rates in
`config/pricing.yaml` 2026-08-v3:

- **Anthropic** (`platform.claude.com/docs/en/build-with-claude/vision`,
  fetched 2026-08-17): images cost `⌈width/28⌉ × ⌈height/28⌉` visual
  tokens. `claude-sonnet-4-5` is standard tier — max long edge 1568 px,
  max 1568 visual tokens per image.
- **OpenAI** (`developers.openai.com/api/docs/guides/images-vision`,
  fetched 2026-08-17): `detail:high` = 85 base tokens + 170 per 512 px
  tile, after scaling the shortest side to 768 px. `detail:low` = 85 flat.

| item | tokens | cost |
|---|---|---|
| anthropic vision, 4 views @ 1024² + 2k text | 7,476 in / 800 out | $0.034428 |
| openai vision, 4 views @ 1024² + 2k text | 5,060 in / 800 out | $0.020650 |
| arbiter delta validation (text only) | 1,500 in / 400 out | $0.007750 |
| **per round** | | **$0.062828** |
| **6 rounds** | | **$0.376968** |
| + kimi tiebreak on 2 of 6 rounds (K3 always reasons) | | $0.093000 |
| **FULL 6-ITERATION LOOP** | | **≈ $0.470** |

**Full pipeline — Council $0.843842 + fabrication $0.046777 + loop $0.470
= $1.36 against your $5.00 session cap.**

**Why it is far cheaper than you feared.** You wrote that "six iterations ×
two providers is where this gets expensive". It is not, and the reason is
architectural: **a bounded parameter delta needs no model call to apply.**
A delta is a number change on a registered parameter; the re-solve is
`registry` code — trusted, deterministic, $0 in API. The only paid calls per
round are the two vision critiques and one Arbiter validation. Nothing
re-writes a program, so Phase 4's $0.047 GEOMETRIST call does not recur.

**Resolution is chosen from the formulas, not by taste.** At 1024×1024 an
image costs anthropic 1,369 tokens — just under its 1,568 cap, so nothing is
wasted — and gives OpenAI a clean 2×2 tile grid at 765 tokens. Going to
1280² costs anthropic 2,116 tokens, which is **over the cap and gets
downscaled anyway** — you would pay for tokens the model never sees. 1024²
is the efficient point for both providers simultaneously.

### 1.2 Render time — I will not give you a number I cannot verify

I could not obtain a verified Cycles benchmark for the i7-8550U from live
sources today (Blender Open Data has no entry for it; cpu-monkey returned
HTTP 403). **ADR-009 forbids me writing a performance figure from
training-data recall**, and a wrong render-time estimate is exactly the kind
of number that wrecks a phase plan.

So the plan does two things instead, and I think the second is a better
engineering answer than any estimate would have been.

**(a) A $0 measurement spike, before any loop code exists.** Build the
render-worker image, load the STEP that already passed your Phase 4 gate,
and render one view at three sample counts (32 / 64 / 128 spp) at 1024²,
printing wall-clock seconds for each. Cycles time is very close to linear in
`pixels × samples`, so **one measurement calibrates the entire table** —
every other resolution, sample count and view count follows by arithmetic.
Cost: $0 in API, one 357 MB download (§3), roughly 10 minutes of your line.
You get the real number before approving the loop itself.

**(b) Make render time an INPUT, not an outcome.** Critique renders get a
**wall-clock budget** (`critique_render_seconds`, default 120 s per view)
and Cycles' adaptive sampling does what it can inside it, with a noise
threshold and a hard sample ceiling. Time per iteration then becomes a known
constant by construction — `views × budget` — and *quality* is the variable
that flexes with your hardware, rather than the schedule.

That is what makes your gate pass on your machine by definition rather than
by luck: a slower CPU produces a noisier critique image, not a loop that
never finishes. Final presentation renders stay what LIMITATIONS §3 already
calls them — "explicitly long jobs", run deliberately, never inside the loop.

**Honest expectation to set now:** on 4 cores of a 15 W 2017 mobile CPU
(Docker sees 4 CPUs, 5.8 GiB), a 4-view critique round at a 120 s budget is
**~8 minutes of wall clock**, and 6 rounds is **~50 minutes**. That is a
scheduling fact about the loop, not a performance claim about Cycles — the
spike replaces the quality half of it with measurement.

---

## 2. Rendering: Cycles CPU is the only path, and EEVEE is not a fallback

Fetched today: **EEVEE requires a GPU with OpenGL 4.3 and does not support
headless rendering** on most platforms (Linux only since 3.4). Cycles renders
on CPU in background mode with no GL context at all.

This matters more here than on a normal machine, because **your backend image
deliberately has no Mesa**: ADR-014 and ADR-016 cut the GL stack from 49
packages / 222 MB to 9 packages / 5 MB, precisely to protect your connection.
Reaching for EEVEE would mean putting `libgl1-mesa-dri` and `libllvm19` back —
undoing that work for a renderer that cannot run headless anyway.

**Decision: Cycles, CPU, background mode. EEVEE is out of scope and the
reason is recorded.** This confirms rather than revises LIMITATIONS §3.

---

## 3. How Blender gets onto your machine — the part that usually hurts

**`bpy` — Blender as a Python module — is on PyPI**, and PyPI is the one
large-file source your line handles well (ADR-017: PyPI 1.5 MB/s, while
deb.debian.org is connection-RESET).

Live query today: the newest `bpy` is 5.2.0 but it requires Python 3.13,
and the backend is 3.11. The newest cp311 wheel is:

```
bpy-5.0.1-cp311-cp311-manylinux_2_28_x86_64.whl   356.9 MB   requires_python ==3.11.*
```

`manylinux_2_28` needs glibc ≥ 2.28; trixie ships 2.41. Compatible.

**A separate `render-worker` container, mirroring the geo-worker pattern.**
Not in the backend image, for three reasons: the backend stays 1.36 GB rather
than ~1.9 GB; a failed 357 MB Blender download can never invalidate the
~400 MB of cached pip layers the backend depends on (the ADR-011 lesson); and
the renderer, like the sandbox, is a worker with a scratch handoff we have
already built and gated (ADR-028's probe proves that mechanism works).

Its own layer, its own pin, `--retries 10 --timeout 120`, resumable, exactly
like every other heavy layer since ADR-011.

**Required spike before committing (ADR-016 v3 method, not assumption):**
audit the bpy wheel's shared-library closure — `readelf -d` plus a strings
scan for dlopen-resolved sonames, then resolve the full NEEDED set against
the debuerreotype base manifest. bpy will almost certainly need more X11
libraries than the current 9-package minimal set (libXi, libXxf86vm,
libXrender and friends are the usual additions). **That audit produced a
wrong answer twice before** — ADR-014 shipped without libglx0, ADR-016 v3
found libexpat1 missing — so it gets the corrected method and the ldd guard
from the start, not a second incident.

---

## 4. The loop — honouring ADR-007, which already specified it

ADR-007 was accepted in Phase 1 and already says what you asked for. Phase 5
builds it rather than redesigning it:

```
current design (params + STEP)
  └─ RENDER (render-worker, Cycles CPU, budgeted)
       ortho front / side / top + three-quarter perspective, 1024²
  └─ CRITIQUE — anthropic ‖ openai in parallel, images before text
       each returns: bounded deltas + prose observations, strict JSON
  └─ CONSENSUS — a delta survives only if BOTH providers propose it
       within tolerance on the same parameter path and the same direction.
       Disagreement -> kimi tiebreak (fallback only, per council.yaml)
  └─ ARBITER validates every surviving delta before re-solve
  └─ APPLY (trusted code, $0) -> validate_params -> rebuild -> re-render
  └─ SCORE + persist every intermediate; repeat to max_vision_iterations
```

**Delta contract** — the hard boundary of this phase:

- A delta references a **registered parameter path**. ADR-007's example is
  `cascade_01.tier_height_m` — already `element_id.parameter`, so it is
  **assembly-addressed from the start** and survives Phase 6 unchanged. This
  is why the phase order between 5 and 6 does not force rework either way.
- Every delta carries a **magnitude limit**, and the limit **anneals**: the
  permitted step shrinks each round (e.g. 10% of the parameter's validated
  range in round 1, halving thereafter). Without annealing a critique loop
  oscillates instead of converging — it is the difference between three
  iterations that improve and three that argue.
- Every delta passes `validate_params` **before** any rebuild, so an accepted
  delta can never produce a constraint violation. Rejected deltas are
  persisted with the real numbers, exactly like a Phase 4 repair digest.
- **Prose that cannot be expressed as a delta is recorded as an operator
  observation and never executed** (your requirement, and ADR-007's).
- `max_vision_iterations: 6` is already loaded and validated from
  `budget.yaml` and has been since Phase 1 — Phase 5 is where it finally
  becomes enforcement.

---

## 5. "Measurably improves" — the model must not grade its own homework

The riskiest sentence in the gate is "measurably improves". If the measure is
the vision panel's own score, the loop can report improvement while the
object gets worse, and we would have built a machine for producing
flattering numbers. This is the same failure class as the success-rate metric
I had to correct in Phase 4 (ADR-029 fix 3).

**So improvement is scored objectively, from geometry the platform already
computes**, with the subjective panel scores logged alongside and clearly
labelled as subjective:

| component | source | already exists? |
|---|---|---|
| proportion adherence | deviation from `form_language.proportion_system.ratio` in the spec, measured on the built solid | spec field exists, unused |
| constraint margin | distance from every hard constraint's boundary — a design that improves should not do it by hugging a limit | Phase 2/4 |
| mass vs handling | `mass_kg` against `fabrication.max_lift_kg` | Phase 2 validation + spec |
| silhouette stability | change in projected outline area between rounds — detects oscillation | new, cheap, from the ortho renders |
| defect count | Phase 2 validation failures | Phase 2 |

The gate then means something falsifiable: **the composite score improves
across three rounds, the deltas that caused each change are logged, and the
before/after renders are on disk.** If the objective score does not move
while the panel says it improved, that is a finding to report, not a gate to
pass.

---

## 6. Persistence and repo structure

- **`critique_rounds` already exists** in `schema.sql` — created up front by
  ADR-001 with `design_id`, `round_no`, `critiques_json`, `deltas_json`,
  `consensus`. It needs render paths, scores, the Arbiter verdict and the
  applied parameter set, added through the **ADR-023 additive-patch
  registry** — your live database is ALTERed at next startup, data preserved,
  patch recorded. No v6 rebuild.
- `backend/app/render/` — scene assembly, camera rig, Cycles settings,
  budgeted render driver.
- `backend/app/council/critique.py` — the loop, consensus, annealing.
- `render-worker` compose service + its own Dockerfile.
- Every intermediate kept under `data/critiques/<design_id>/round_<n>/`.

## 7. Slices

**Slice 1 — render only, $0.** render-worker image, GL audit, the four
camera views, budgeted Cycles CPU. **Ends with the measurement spike (§1.2):
real seconds on your machine, reported before anything else is built.**
*Gate: four renders of the Phase 4 STEP, on your machine, with times.*

**Slice 2 — critique + consensus, fixture-replayed at $0.** Vision prompts,
strict-JSON deltas, consensus rule, annealing, Arbiter validation, the
objective score. Developed against recorded critique fixtures so the logic
costs nothing to build — the Phase 3 pattern.
*Gate: fixture replay proves consensus, rejection and annealing offline.*

**Slice 3 — the live loop.** Three or more real iterations on the Phase 4
design. *Gate: the operator's gate.*

## 8. Risks and things I want on the record

1. **Render time is unmeasured.** Mitigated by budgeting time rather than
   estimating it (§1.2), but the spike must run before slice 2.
2. **The bpy library-closure audit has bitten twice before** (§3). Corrected
   method plus the permanent ldd guard from the start.
3. **A critique loop can oscillate.** Annealing magnitudes and the silhouette
   stability term are the defence; if it still oscillates, that is an honest
   finding for LIMITATIONS, not something to tune until the gate passes.
4. **Two-provider consensus may rarely agree** on a specific parameter path,
   making the loop a no-op. If the measured consensus rate is very low, the
   answer is to narrow what we ask for (fewer, larger, more concrete
   parameters), not to weaken the consensus rule.
5. **Vision models cannot judge fabrication.** They see a picture. Every
   engineering fact still comes from the validation gate; the panel's remit
   is proportion, silhouette and composition only, and the prompt says so.
6. **Phase 6 interaction.** Delta paths are element-addressed from day one
   (§4), so either order works. I still recommend **Phase 6 first** — a
   critique loop over a library of composable primitives has real parameters
   to move, while a loop over one primitive can only adjust 13 numbers on a
   single fountain.
7. **6 rounds × 4 views at 120 s is ~50 minutes of laptop time** per full
   loop. Not a cost problem; a patience and thermal one on a 15 W chip.

## 9. What I need from you before slice 1

1. Approval of Cycles-CPU-only, EEVEE explicitly out (§2).
2. Approval of the separate `render-worker` container and the 357 MB
   `bpy==5.0.1` download (§3).
3. A ruling on `critique_render_seconds` — I propose 120 s per view as the
   default budget; you may prefer 60 s for a faster loop at more noise.
4. Confirmation that the objective score (§5) is the right definition of
   "measurably improves", since it is what the gate will be judged on.
