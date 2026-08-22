# Brief intake — turning a client's words into numbers the platform can check

Phase 12. This is the screen the whole pipeline hangs off: what you enter
here decides whether validation can actually check your fountain, or has to
report "I could not check that".

---

## The screen

**Brief** tab. Paste the client's own words on the left, press
**Parse brief ($)**, and the form fills in. Then correct anything the parser
misread and press **Confirm intake**.

You can also skip the parser entirely and type the form by hand. Editing is
always free — no tokens, no waiting.

---

## The four provenance chips

Every field carries a small chip showing **where its value came from**. This
is the most important thing on the screen.

| chip | meaning |
| --- | --- |
| **OPERATOR** | You typed or confirmed it. Nothing overwrites it — not even the parser. |
| **PARSED** | The AI read it out of the brief. Hover the chip to see the client's exact sentence. |
| **DEFAULT** | Nobody chose it; it is a shipped default. |
| **UNKNOWN** | Nobody knows it. The platform will say so downstream rather than invent a number. |

**UNKNOWN is not a failure.** It is the honest state, and it travels: an
unknown water flow becomes `NEEDS INPUT` on the hydraulic gate, never a
guessed number that quietly passes.

### The parser never overwrites you

If you typed a height and the parser reads a different one from the brief,
**your value wins** and the parse result reports "1 of yours kept". The
client's prose is evidence; your judgement is the decision.

The parser also cannot invent fields, cannot guess, and cannot coerce a
type. If the brief does not state the budget, the budget stays UNKNOWN.

---

## The readiness ladder

Fields are ranked by **what a gap actually blocks**:

| tier | blocks | must answer before Council? |
| --- | --- | --- |
| **1** | geometry — project type, height, footprint | **yes** |
| **2** | a validation gate — indoor/outdoor, water, wind speed | **yes** |
| **3** | costing — currency, budget ceiling | no |
| **4** | design quality — inspiration, material preference | no |

Tiers 1 and 2 must be answered before you spend money on a Council session.
Tiers 3 and 4 may stay unknown — the affected layer will report it.

The platform only asks for what applies. Mark a piece **indoor** and it stops
asking for a wind speed, because there is no wind case.

---

## The three site numbers that unlock validation

These are the fields that turn `NEEDS INPUT` into a real verdict. They are
per-project facts, so they live here rather than in `gate_profiles.yaml`.

**Altitude (m)** — drives air density for the wind calculation. Addis Ababa
at 2355 m has about 21% less air density than sea level, so the same wind
pushes about 21% less hard. Set this per site.

**Design wind (3 s gust, m/s)** — from the local building authority's wind
map, or from the project's structural engineer. There is no universal value,
which is why the platform refuses to invent one.

**Allowable bearing (kPa)** — from the geotechnical survey for the actual
site. This varies by more than ten times between soft clay and rock. Without
it the platform still tells you the pressure your piece *applies* — it just
cannot give you a verdict.

> One threshold is deliberately **not** here: the overturning safety factor.
> That is a policy decision your structural engineer signs, so it lives in
> `config/gate_profiles.yaml`, not in a per-project form.

---

## Confirming

**Confirm intake** freezes it for downstream use. You cannot confirm while
tier 1 or 2 fields are missing — the screen names exactly which.

Editing a confirmed intake reopens it as a draft. That is deliberate: the
confirmation covered the old content, and anything downstream must see that
it changed.

---

## What a confirmed intake then does

**In the Assembly view**, a "site context" toggle appears. With it on, your
build uses the intake's water and site facts:

- hydraulics evaluates freeboard, reservoir turnover and nozzle bore
  against your real flow, instead of reporting NEEDS INPUT
- the structural gate computes real wind pressure and ground bearing
- the validation report records an extra `site_overrides` row naming every
  value you supplied **and its source**, so a report read in a year still
  says where each number came from

**In the AI Council**, the normalized intake is prepended to the brief as a
delimited block, so the Council receives structure, not only prose. Unknown
fields are listed as UNKNOWN with an explicit instruction not to invent
values for them.

---

## Cost

One parse is one logged, budget-capped provider call — the same path and the
same caps as a Council call. Editing and re-confirming afterwards costs
nothing. Without API keys the parse fails honestly and the form still works
by hand.
