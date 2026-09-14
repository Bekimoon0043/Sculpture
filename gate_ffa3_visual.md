# FF-A3 Visual Gate — a typed brief can ask for the ref-08 loop (ADR-069)

**What changed, in one sentence:** the brief you type into the Brief tab
can now reach the free-form lens: the Council's designers are told the
lens exists **and what its parameters are called** (generated from the
registry, never typed), the trusted translator maps a Design Spec naming
`freeform_loop` onto the kernel's 13 registry keys (12 scalars +
`material_id`), every Design Spec is now checked at the Designer's desk
against the mapper and the primitive's own arithmetic before it is
persisted, a dry design no longer has to invent a pipe network, and a
ratio must be a plain number — a ratio carrying any unit is refused.

**What this does NOT claim.** One ref-08 family, one primitive, scalar
controls. 316L only. Total mass stays INCOMPLETE until the armature is
designed. Forming radius and wall approval stay the fabricator's.
Integrity-gated, PRE-FABRICATION at best. **The synthetic hand-authored
Council alternatives in the fixture prove replay and pipeline
compatibility only — not that an AI selected the primitive from prose.**
Steps 1–5 are $0. Step 6 is the only real demonstration of "typed brief →
Council selection → sculpture" and spends money; it needs its own
approval and is not authorized by the build approval.

Cost of steps 1–5: $0. Time: ~20 minutes.

---

## Step 1 — rebuild and run the auto gate

```powershell
docker compose up --build -d
docker compose exec backend python scripts/gate_ffa3_auto.py
```

**Check:** the last line is `PASS`. If `FAIL`, stop and report the
transcript.

## Step 2 — read what the DESIGNER is now told

In the gate transcript, section **[1 vocabulary truth …]** prints the
`freeform_loop` block of the Designer index.

**Check:** it lists twelve scalar parameters each with a unit and a
`[min..max]` range, the three ratio/fraction keys say **PLAIN number**,
the material line says **ONLY material_id='stainless_316l_sheet'**, the
mass line names the three armature inputs, and the status line says
**PRE-FABRICATION**. Nothing there is typed by hand — if you change the
registry, the block changes with it.

## Step 3 — type and confirm the brief through the Designer's Brief tab

Open the Designer (http://127.0.0.1:5173) → **Brief** tab. Paste the
brief text from `tests/fixtures/intake_ffa3_v1.json` (`brief_text`) into
the brief box and press **Start**. Do **not** press *Parse brief ($)*.
Fill the form by hand from the fixture's `fields` (sculpture, public,
Addis Ababa, outdoor, altitude 2355 m, **your real site's 3-second gust
in place of the fixture's 30 m/s**, height 4.25 m, footprint 2.6 m,
**water: no**, material 316L sheet, ETB 6,000,000). Press **Confirm
intake**.

**Check:** every filled field carries the **OPERATOR** chip; the intake
confirms (no tier 1/2 field missing); water reads **no**. Note the intake
id shown on the screen — Step 6 uses it.

## Step 4 — read the replayed synthetic transcript at $0

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/council/demo-session -ContentType "application/json" -Body '{"fixture": "council_session_ffa3_v1"}'
```

Then open the **Council** tab and select the session whose brief begins
with `=== BEGIN NORMALIZED INTAKE`.

**Check:** the response says `synthetic: true` and its note says the
dollar figure **was never spent**; the transcript shows six designer
alternatives, every one naming `freeform_loop` with all twelve scalars
and `material_id` stated explicitly, and an arbiter decision whose rank 1
is the FF-A2 acceptance lens. Read the researcher, geometrist, engineer
and arbiter texts: each begins with `[synthetic …]` (the critic's reply
is a JSON defect list; its provenance is the session note). This is a
replay, not an AI decision.

## Step 5 — the built lens is the FF-A2 lens

Section **[6 trusted build …]** prints two process ids and two STEP
digests.

**Check:** the two digests are identical and the two PIDs differ. Then
open the Designer, build a `freeform_loop` at its defaults (the same
numbers as the fixture's rank 1), and open **Checks**: mass reads
**NEEDS INPUT** naming the armature; `freeform_integrity_v1` reads
**pass**; hydraulics say the design carries no water. Compare the
viewport with the lens you signed on 2026-09-07 — it is the same object.

## Step 6 — the live demonstration (SEPARATE cost approval required)

**Do not run this step until you have approved its spend in writing.**
Measured live sessions cost $0.843842 (2026-08-07) and $0.6778
(2026-08-28); the Designer prompt is now larger, so expect more; one
fabrication attempt measured $0.046777 (2026-08-17). Caps: $5 per run,
$25 per day.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/council/sessions -ContentType "application/json" -Body '{"brief_text": "<the brief text from Step 3>", "intake_id": "<the intake id from Step 3>"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/council/sessions/<session_id>/fabricate -ContentType "application/json" -Body '{}'
```

**Check:** in the Council tab, whether the real designers chose
`freeform_loop` and with what numbers — record the answer either way, a
NO is a result; whether the fabrication produced a design and what its
Checks say. Then capture the session as a real fixture:

```powershell
docker compose exec backend python scripts/capture_council_fixture.py <session_id>
```

Until Step 6 has been run and recorded, the claim "typed brief → Council
selection → sculpture" is **not** made anywhere in this repository.

---

## Sign-off

Walked with the operator 2026-09-14 on image `0d4180d2b8d7` (unchanged
since the 2026-09-09 build; four spot-checked files byte-identical host
and container).

- [x] **Step 1 — auto gate PASS.** Operator's result, verbatim:
      "this process pid 8 STEP f3ccb95345d8534ba30aa98e6817d6f0b341a80cf9c8ca36c860f5f54dca4d14 /
      other process pid 36 STEP f3ccb95345d8534ba30aa98e6817d6f0b341a80cf9c8ca36c860f5f54dca4d14 /
      PASS -- all 55 checks passed at $0, offline, with no AI call and no
      production data touched." The operator also observed the existing
      optional-export warnings (`pycollada`, `networkx`) and ruled them
      documented limitations (D-7, LIMITATIONS §9), not FF-A3 artifacts;
      FF-A3 installs nothing.
- [x] **Step 2 — the Designer block.** Operator's results, verbatim:
      "1. Twelve scalar parameter entries with mappings, units, ranges and
      defaults: YES  2. All three ratios/fractions are labeled (ratio,
      PLAIN number) with no unit: YES  3. Material says only
      stainless_316l_sheet: YES  4. Mass line names all three armature
      inputs as FABRICATOR-INPUT-REQUIRED: YES  5. Status says
      PRE-FABRICATION at best: YES  I confirm this vocabulary is
      registry-generated rather than manually duplicated."
- [x] **Step 3 — brief typed and confirmed. DEVIATION RECORDED:** at the
      operator's explicit request ("can you do it this by you self by
      accessing the page"), the 17 intake fields were entered by the
      session through the SAME `/api/intake` calls the Brief tab makes,
      not typed into the browser by the operator; the confirm was issued
      the same way. Intake `4d4fa904-dc7c-49c3-80a4-c53f3cb69a78`,
      status **confirmed**, 17 fields all `source=operator`,
      `water.has_water = false`, `ready_for_council: true`,
      site_overrides `{site_altitude_m: 2355.0, design_wind_speed_m_s:
      30.0}`. **The wind speed 30.0 m/s is a TEST VALUE**, entered at the
      operator's instruction ("i don't have design wind use a test by ur
      self") — it is the figure the intake test suite uses, NOT a site
      measurement, and any real project must replace it before a
      structural verdict means anything.
- [x] **Step 4 — replayed transcript.** Operator confirmed by screenshot:
      the Council tab shows the session with the **synthetic** badge,
      `completed`, `$0.2022`, 9/9/2026, and the normalized intake block
      ahead of the brief. Through the API: 6 alternatives, every one
      `freeform_loop` with 13 parameters stated and
      material `stainless_316l_sheet`; arbiter rank 1 `13b10c0d…`,
      confidence 0.7; researcher text opens `[synthetic …]`; note states
      the dollar figure "was never spent". Recorded as replay evidence
      only — it proves replay and pipeline compatibility, NOT that an AI
      selected the primitive from prose.
- [x] **Step 5 — the built lens is the FF-A2 lens.** Operator: "yes".
      Design `7880aa6b-4321-4e96-b1c9-1accf5a6ac37` built through the
      real API against the confirmed intake, 209 s, STEP
      `f3ccb95345d8534b…` — byte-identical to the FF-A2 acceptance lens
      signed 2026-09-07 and to both gate processes. Checks:
      `freeform_integrity_v1` **pass**; fabrication **needs_input**
      (lift: "element mass is INCOMPLETE — heaviest module known-geometry
      mass 853.0 kg excludes required inputs"; plus
      `geometric_wall_measurement`, `fabrication_wall_approval`,
      `forming_radius_mm`, `rigging_declared`); structure
      **needs_input**; hydraulics **pass**, basis
      `water_context_v1.has_water = false`; `total_mass_kg` null.
- [!] **Step 6 — NOT ACHIEVED (never PASS, owner ruling 2026-09-14).**
      The live demonstration ran and HALTED after one successful call;
      the Council never reached the Designer stage, so NO selection of
      any primitive occurred. See the record below. **The claim "typed
      brief → Council selection → sculpture" remains UNMADE, and real
      Council selection of `freeform_loop` remains UNPROVEN.**

### Step 6 record — one live Council session, halted at the second call

Authorized by the operator 2026-09-14 under the platform's standard
$5.00 run cap (replacing an earlier $2.00 authorization after the
session cost the projection below): one live Council session, one
fabrication attempt, no retry, no configuration or Council-composition
change, stop immediately if any provider call fails.

Projection given before dispatch: expected actual **$0.99** (Council
$0.9411 computed from the real FF-A3 prompts × the largest per-role
output sizes measured in live session `32e1c68f`, plus ~$0.05 for one
fabrication attempt). Reservation bounds, which are context window ×
input rate + 8192 × output rate, not prompt estimates: openai
$0.4019, anthropic $0.8729, **kimi $3.2686** (1,048,576-token window).

What happened, 2026-09-14T08:22:32Z → 08:23:18Z (46 s):

| # | role / side | provider | status | tokens | actual cost |
|---|---|---|---|---|---|
| 1 | researcher / primary | openai gpt-4o | **ok** | 490 in, 650 out | $0.007725 |
| 2 | researcher / parallel | kimi kimi-k3 | **ERROR — "Connection error."** | 0 in, 0 out | $0.000000 billed |
| 3 | (ADR-023 retry of call 2) | kimi kimi-k3 | **REFUSED before dispatch** | — | — |

Session `2a7d3e5b-2b78-42f6-9479-637f0e1feaa6`, status
**halted_budget**, `total_cost_usd` $0.007725, degraded 0, corrected 0,
**0 design specs persisted, 0 arbiter decisions**.

The halt, verbatim from the HTTP 402:

```
budget halt: run spend cap would be breached: scope
2a7d3e5b-2b78-42f6-9479-637f0e1feaa6 spent $3.276333 + reserved bound
$3.268608 > run cap $5.000000 — halting, state persisted
(halt_and_report) (spent $3.2763 of $5.00 cap); partial session
2a7d3e5b-2b78-42f6-9479-637f0e1feaa6 is persisted and visible in the
transcript API
```

`budget_events` row `b162e615…` at 08:23:16.798940Z, `event_type`
`cap_breach`, detail `{"attempted_bound_usd": 3.268608, "cap_kind":
"run", "cap_usd": 5.0, "spent_usd": 3.276333}`.

**Reservation state — PRESERVED, NOT RECONCILED** (operator's explicit
instruction: do not reconcile, rerun, or make another provider call):

| reservation | provider | status | reserved | settled |
|---|---|---|---|---|
| `6acb4b04-ed76-4023-b019-bf937c54d7cc` | openai gpt-4o | settled | $0.401920 | $0.007725 |
| `9077e77a-95ec-4633-b4be-c5a07ad4f74f` | kimi kimi-k3 | **uncertain** | **$3.268608** | $0.000000 |

The uncertain row's own note: *"attempt failed; provider may have billed
it (no first-party non-billing proof) — counted at full reserved bound"*.
That is ADR-061 failing closed by design. **Real money actually billed
for this demonstration: $0.007725.** Counted against the UTC-day cap:
$3.284036 of $25.00. No safety lock engaged (`spend_safety_locks` empty).

**Honest answer to the selection question.** The Council did **not**
select `freeform_loop` — and it did not decline to, either. It never
reached the Designer stage: the only completed call was the researcher's
primary, and no Design Spec was ever produced. This is neither a YES nor
an honest NO on selection; it is a demonstration that **did not reach
the question**. Nothing was rerun, no prompt was touched, no selection
was coerced.

**One fabrication attempt: NOT RUN.** The operator's authorization said
stop immediately if any provider call fails. One did.

### Owner ruling on this result (2026-09-14, binding)

Issued after reading the record above:

1. **No second Step 6 attempt now.**
2. **No `council.yaml` change, no removal of kimi, no weakening of
   fail-closed accounting, and no increase to the permanent $5 / $25
   caps.**
3. **Step 6 remains NOT ACHIEVED.** The halted session is preserved, and
   **real Council selection of `freeform_loop` remains UNPROVEN.**
4. **Step 6 is never to be marked PASS.** FF-A3 may pass its formal
   gates and close only as: *"typed-brief/Council contract implemented
   and fixture-gated; live end-to-end selection blocked by D-28 and not
   claimed."*
5. **D-28 becomes the next separate, rollbackable slice**, not started
   until FF-A3 is closed and its own plan is approved. Its goal: a
   fail-closed reservation computed from the REAL serialized request
   envelope plus the configured maximum output plus a proven
   conservative margin — never the model's entire unused context window.
   Context size stays an absolute ceiling, not an assumed billable
   request. First-party provider documentation must be fetched and
   recorded under ADR-009, and the slice must test retries, uncertain
   holds, multibyte prompts, maximum output, and reservation-underflow
   safety.
6. **Reservation `9077e77a-95ec-4633-b4be-c5a07ad4f74f` is NOT to be
   reconciled** until the operator reports the Moonshot/Kimi provider
   console for 2026-09-14, 08:22–08:23 UTC.

**Step 6 status: NOT ACHIEVED — never PASS.**

---

## Definitive /lf-gate chain (2026-09-14) — accepted with one FAILING gate

Run under the operator's risk-based protocol on backend image
`sha256:772e352a34ea7b3bb6d1fcddab711f2b0348dd5ec4968604e0438ae8fb9013c3`,
identical at the start and the end. Full transcripts in
`PRODUCTION_V1_REPORT.md`.

**This chain is NOT "all gates green" and is never to be described that
way.**

| result | detail |
|---|---|
| host vs image byte identity | 20 of 20 SAME, 0 DIFF |
| full suite, render worker REMOVED | **737 passed**, exit 0, 1:38:39 |
| in-container roster, worker removed | **25 of 25 exit 0**, incl. `gate_ffa3_auto` **55/55**, `gate_ffa2` 63/63, `gate_ffa1` 36/36 |
| `gate_pr3_auto --static --stdin` | PASS |
| host + split gates | scope audit PASS · Phase 14 `--frontend-only` PASS · PR-2.5 `--host-drift` 218/218 · PR-3 `--live` PASS |
| **`gate_phase9b_auto.py`** | **FAIL — twice. Accepted as unrelated measured infrastructure debt (D-29) under the risk-based exception. NOT a pass.** |

**Basis for accepting the chain with Phase 9B failing** (owner ruling,
recorded verbatim):

1. FF-A3 changed **no rendering, conversion, packaging or worker code**.
2. The **previous closed Phase 9B PASS remains the regression baseline**
   for those unchanged bytes.
3. The current render **and** conversion both **completed
   successfully**, but after their fixed gate deadlines (render
   `ok: true`, `total_s 37.487`, four views; conversion
   `conv515aca28338d -> ok` at 12:16:28Z vs the gate exiting 12:16:24Z).
4. The measured cause is the **1,904-directory scratch scan taking
   8.89 s per poll**, producing queue-pickup latency.
5. **FF-A3's own gate passed 55/55**; the worker-removed suite passed
   **737**; all 25 in-container gates, PR-3 static and all host gates
   passed.

Recorded as **D-29**, linked to D-1: the correction must avoid
rescanning every historical directory on each poll and must provide
bounded, indexed or event-driven pickup plus safe retention/reaping;
raising the timeouts is not an acceptable fix. No scratch artifact was
deleted, moved or modified, and Phase 9B was not run a third time.

**Final FF-A3 status wording, binding:** *typed-brief/Council contract
implemented and fixture-gated; live end-to-end selection blocked by
D-28 and not claimed.*

Signed (operator): **SIGNED — 2026-09-14**, by walking Steps 1–5 with
the session (results recorded verbatim above), ruling Step 6 **NOT
ACHIEVED and never PASS**, accepting the definitive chain under the
risk-based exception with `gate_phase9b_auto.py` FAILING twice and
preserved as FAIL, and authorizing the close with the binding status
sentence above. The operator's closing instruction also stands on the
record: preserve both Phase 9B FAIL transcripts and the D-29
acceptance; keep D-27, D-28 and D-29 open; do not reconcile reservation
`9077e77a-95ec-4633-b4be-c5a07ad4f74f`; do not touch
`data/render_scratch`; do not rerun the suite or Phase 9B during the
close.
