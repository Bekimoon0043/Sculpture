# PR-4 Visual Gate — honest module transport costing (ADR-067)

**What changed, in one sentence:** the transport line on a BOM no longer
prints a lower-bound formula dressed up as a trip count — it LOADS the
trucks module by module (heaviest first, both limits checked with
unrounded numbers) and shows you every trip: which modules, their masses,
the load, and the capacity left over. It calls itself *a deterministic
conservative feasible allocation* — never "minimal", because a cleverer
packing might use fewer trucks, and the platform does not claim what it
did not prove.

Your rate card was not touched. `install.transport`,
`install.truck_payload_kg` and `install.modules_per_trip` are still null
in `config/costing.yaml` and still yours to supply — every transport
number below is an in-memory test value.

Time needed: ~10 minutes. Cost: $0.

---

## Step 1 — rebuild and run the auto gate

```powershell
docker compose up --build -d
docker compose exec backend python scripts/gate_pr4_auto.py
```

**Check:** the last line is `PASS`. If it is `FAIL`, stop here and report
the transcript.

## Step 2 — read the loading in the gate's own transcript

In the output of Step 1, find section **[3/9] THE DISPROOF** and section
**[5/9] PER-TRIP TRUTH**.

**Check (the disproof):** four 6,000 kg modules at a 10,000 kg payload —
the retired arithmetic says **3** trips, the loaded trucks say **4**.
Both numbers are printed side by side. This is the case that proves why
the old formula had to go: three trucks cannot legally carry four 6 t
modules at 10 t each.

**Check (the loading):** section 5 prints three trips for a 10-module,
13,721 kg test design at a 12,000 kg / 4-per-bed test card:

- trip 1: the 2,375.044 kg module plus three 1,300 kg modules =
  6,275.044 kg, bed full (0 slots spare);
- trip 2: four 1,300 kg modules = 5,200.000 kg, bed full;
- trip 3: 1,300 kg + 946.137 kg = 2,246.137 kg, 2 slots and
  9,753.863 kg payload spare.

Add any trip up by hand — the loads must match the module masses exactly,
every module must appear exactly once, and no load may exceed 12,000 kg.

**Check (the wording):** the line describes itself as *"a deterministic
conservative feasible allocation"* and nowhere claims the count is
minimal or optimal.

## Step 3 — a REAL design still refuses honestly

Pick any segmented design in the Designer (the 9-module C2 basin is the
canonical one) and open its BOM document:

```powershell
# replace <design_id> with the id from the Designer's Recent Builds strip
Invoke-WebRequest "http://localhost:8000/api/costing/bom/<design_id>.txt" | Select-Object -ExpandProperty Content
```

**Check:** the transport line reads `[RATE MISSING]` and the blocker names
`install.truck_payload_kg` — your number, still yours. **No trip count
appears anywhere on a real design**, because no real payload exists yet.
Nothing was invented to make the page look finished.

## Step 4 — your rate card is untouched

```powershell
Select-String -Path config\costing.yaml -Pattern "transport|truck_payload_kg|modules_per_trip"
```

**Check:** all three entries are still `null` (the `transport:` block's
`amount: null`). The gate transcript's section [9/9] also prints the
file's sha256 before and after — the two hashes must be identical.

---

## Sign-off

- [x] Step 1 — auto gate PASS
- [x] Step 2 — the disproof (3 vs 4) and the per-trip loading add up by hand
- [x] Step 3 — a real design's transport line is RATE MISSING, no invented trips
- [x] Step 4 — costing.yaml untouched, hashes identical

Signed (operator): SIGNED — 2026-09-07. The operator's results, verbatim:

> PR-4 visual gate results, 2026-09-07:
> - Step 1: YES — auto gate PASS.
> - Step 2: YES — 3-versus-4 disproof confirmed; trip allocations and
>   masses add up; wording is conservative feasible allocation.
> - Step 3: YES — real design reports [RATE MISSING], names
>   install.truck_payload_kg, and shows no invented trip count.
> - Step 4: YES — all three costing entries remain null and the hashes
>   match.
> Record this sign-off verbatim and stop. Do not run /lf-gate, commit,
> or push until I authorize it.

When you sign this, PR-4 closes with `/lf-close`. What the allocation does
NOT model — module ROTATION (a piece that would fit rotated is still
counted by mass and bed slots only) and mixed-fleet trucks (one payload,
one bed count for the whole job) — is recorded in `LIMITATIONS.md`.
