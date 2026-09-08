# PR-5 Visual Gate — AI contract and document repair (ADR-068)

**What changed, in one sentence:** every surface that describes lifting
and module limits — the instruction sheet the AI reads when it writes a
fabrication program, the gate's own explanation lines, the vision-critique
scorer, and the operator documents — now says the same thing the
fabrication gate has measured since segmentation: the crane picks the
**heaviest module**, the truck envelope binds **per axis**, and a mass
that cannot be justified is **not scored** (the scorer's silent 1,000 kg
lift default is gone; an unavailable score is `None`, never a number).
Four documents that still described built things as unbuilt carry dated
corrections beneath the original sentences — nothing historical was
rewritten. Every frozen list or exact count inside a gate now carries a
written architectural reason, or the sweep fails.

No geometry, schema, config, registry or provider change. Cost: $0.
Time needed: ~10 minutes.

---

## Step 1 — rebuild and run the auto gate

```powershell
docker compose up --build -d
docker compose exec backend python scripts/gate_pr5_auto.py
```

**Check:** the last line is `PASS`. If `FAIL`, stop and report the
transcript.

## Step 2 — read what the AI is told

Section **[1/6]** prints the exact lines of the fabrication contract. Find
the sentence about `max_lift_kg`.

**Check:** it says the lift limit binds on the **heaviest MODULE after
segmentation** and `max_module_m` binds **per axis**. The old sentence
("checked per element") must not appear anywhere in the printed surface.

## Step 3 — the scorer refuses what it cannot justify

Section **[3/6]** prints five scorings with their **basis** line.

**Check:** the 9-module basin scores on **1,472.31 kg** (the heaviest
module), not on its 11,346 kg total; the two-element unsegmented design
reads **unavailable — "2 elements with no segmentation record"** with a
score of `None`; the design with no lift limit reads **unavailable** and
the reason names `max_lift_kg` with no number invented in its place; the
free-form design reads **unavailable** naming the armature. `None` is
printed as `None`, never as 0.

## Step 4 — the gate row on a real design

Open the Designer (http://127.0.0.1:5173), select the 9-module C2 basin
(or any segmented design) and open the **Checks** tab → Fabrication.

**Check:** the `mass_kg` row's basis reads *"pick weight is the heaviest
of N modules (element total … kg)"*. Nowhere does a row say "per-element".

## Step 5 — the documents tell the truth without rewriting history

Open `PHASE_6_REPORT.md` and `PHASE_11_12_13A_REPORT.md`.

**Check:** the original headings/sentences are still there **verbatim**,
each with a dated **Correction 2026-09-08** block immediately beneath it
(Phase 6: auto gates passed, the phase is NOT closed because its live
operator gate is pending; 11/12/13A: Phase 9B was built two days after
that sentence was written). In `LIMITATIONS.md` §11 and §12 the retired
sentences are struck through, not deleted, with the date and evidence.

Then read `docs/operator/07_validation_gates.md` — the lift example now
shows the heaviest-module row and the per-axis envelope.

## Step 6 — the D-10 markers name real reasons

Section **[5/6]** lists every frozen literal in every gate with its
`D-10-frozen` reason.

**Check:** read each reason. Reject any that merely restates "this is
intentional" — every one must name the ADR or record that makes the
literal permanent (the registry's single exact-set, the frozen legacy
mass seam, the sandbox import ceiling, the fixed B-11 reference record).
The three converted checks (6a2's generated unknown name, the scope
audit's queue-position order, 6c2's rate-card paths) are printed with
their new form.

---

## Sign-off

- [x] Step 1 — auto gate PASS
- [x] Step 2 — the AI contract says heaviest module / per axis; old wording gone
- [x] Step 3 — the scorer's five bases read as described; `None` never 0
- [x] Step 4 — a real design's gate row says "heaviest of N modules"
- [x] Step 5 — historical text preserved verbatim with dated corrections beneath
- [x] Step 6 — every D-10 marker states a real architectural reason

Signed (operator): SIGNED — 2026-09-08. The operator's results, verbatim:

> PR-5 visual gate results, 2026-09-08: Steps 1–6 are all YES. The real
> design 621d7497… shows the basin pick weight as the heaviest of 9
> modules, 1,472.19 kg versus 11,346.1 kg element total. Record my
> sign-off verbatim and stop. Do not run /lf-gate, commit, push, or begin
> another slice until authorized.

What PR-5 deliberately does NOT do: it does not make the scorer STEER the
critique loop (D-14 stays open), and it does not give the Council any
vocabulary for `freeform_loop` — the gate prints the fact that the
fabrication-time contract already lists that primitive while no brief can
request it; that is FF-A3's starting point.
