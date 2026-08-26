# Phase 6 visual gate — the operator's gate, live (slice A2)

**This is the gate the phase was named for** (PHASE_6_PLAN.md, verbatim):
*"a brief that needs three different primitives composed together produces
one watertight assembly that passes validation and exports cleanly."*

**Cost before you spend (Rule: say it first):** one live Council session
≈ **$0.84** (Phase 3 measured $0.843842) + one assembly fabrication
≈ **$0.05–0.25** (Phase 4 measured $0.046777 for a single primitive; the
plan budgets repair-attempt headroom). Projected total ≈ **$0.90–1.10**
against the $5.00 session cap. Everything before step 2 is $0.

Run the $0 auto gate first; do not spend money on a red build:

```powershell
docker compose exec backend python scripts/gate_phase6a2_auto.py
```

Expected: `PASS — Phase 6 slice A2 auto gate` and exit code 0.

---

## 0. Rebuild (backend code changed)

If another Claude session is live in this repo, check with it before
rebuilding — containers are shared.

```powershell
docker compose up --build -d
```

## 1. Run a live Council session with a three-primitive brief

Open the UI at **http://localhost:5173** → **Council** → paste this brief
(or your own — it must need a plinth, a basin and a column):

> A ceremonial fountain for a hotel forecourt in Addis Ababa: a round
> carved basalt basin about 2 m across standing on a low basalt plinth,
> with a single sculptural basalt column rising from the centre of the
> basin. Site crane limit 2000 kg, largest transportable piece 3 m.

Start the session and wait for the Arbiter's decision (as in
`docs/operator/04_first_live_council.md`).

## 2. Fabricate the winning spec

Replace `SESSION` with the 8-character session id shown in the UI:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/council/sessions/SESSION/fabricate -Method Post -Body '{}' -ContentType 'application/json' | ConvertTo-Json -Depth 5
```

**Check in the response:**
- [ ] `success` is `true`
- [ ] `design_id` is present and NOT null — this is new in slice A2: the
      fabricated assembly is now a real design record
- [ ] `attempts` — note the number for the report (1 = first-attempt pass)

If `design_id` is null while `success` is true, the response's
`artifacts.design_bridge_error` says exactly why — that is a slice defect;
report it verbatim.

## 3. The assembly is VIEWABLE

Open the **Designer** view.

- [ ] The fabricated design appears in the builds strip (under
      **Ungrouped builds** — fabrications carry no project yet)
- [ ] The outliner lists the elements by name (e.g. a plinth, a basin, a
      column — the ids the Council's spec used), not one fused blob
- [ ] Orbit it: one coherent object, column centred in the basin, basin
      seated on the plinth — no floating parts, no interpenetrating mess

## 4. The assembly passed validation honestly

Open the **Checks** tab for that design.

- [ ] `assembly_mesh` is a PASS (watertight, body_count 1)
- [ ] The structure/fabrication gates show real measured rows
- [ ] Hydraulics may honestly read `needs_input` if no intake was
      confirmed — that is correct behaviour, not a failure. A green
      "pass" on hydraulics with no water context would be the lie.

## 5. The assembly is EXPORTABLE

Open the **Output** tab for that design.

- [ ] Download the LUXEXCHANGE package; the ZIP opens and contains
      `assembly.step`, `luxexchange_v1.json`, `CHECKSUMS.sha256`,
      `verify_luxexchange.py`
- [ ] (Optional, proves it end-to-end) In the extracted folder:
      `python verify_luxexchange.py` → exit 0, every checksum OK
- [ ] Open the STEP in your CAD program: one solid, three recognisable
      members

## 6. Determinism evidence across the two containers

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/geometry/assembly/latest/manifest | Select-Object -ExpandProperty artifacts | ConvertTo-Json
```

- [ ] `step_sha256` (backend rebuild) and `sandbox_step_sha256` (what the
      ADR-005 sandbox exported for the same program) are **identical**.
      If they differ, the two images have drifted — report both hashes;
      the record was designed to make exactly this visible.

## 7. The money is accounted for

Open **Operations** (or the Council session's cost panel).

- [ ] The session's fabrication calls are listed with real token counts
      and cost; the two ledgers agree (no LEDGER MISMATCH badge)
- [ ] Total live spend for this gate is within the projection above

---

**PASS** = every box ticked. Record the session id, design id, attempt
count and measured cost in PHASE_6_REPORT.md. **FAIL** on any box = stop,
report exactly what you saw (screenshot + the response JSON), spend
nothing further.
