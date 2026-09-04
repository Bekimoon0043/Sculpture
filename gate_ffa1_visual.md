# gate_ffa1_visual.md — FF-A1, the operator's eye gate

**Cost: $0.** Nothing here spends money or touches the network.

**What you are signing:** that the incomplete-mass truth foundation and
the production free-form validation layer are real, audited and
inactive-by-default — NOT that any free-form or incomplete-mass
capability exists for a user. FF-A1 is an internal foundation slice;
the product cannot create an incomplete-mass design today, and this
gate therefore tests only reachable behavior (owner correction 7,
2026-09-03). The full Designer/warrant demonstration of incomplete
mass on a real free-form element belongs to FF-A2's visual gate.

**Before you start**, the backend and frontend changed, so rebuild once
(coordinate with any live session first):

```powershell
docker compose up --build -d
```

## 1. Run the auto gate and read its verdict

```powershell
docker compose exec -T backend python scripts/gate_ffa1_auto.py
```

- [ ] It ends **PASS** with zero skipped sections, and you can see:
      section 1's census count (28 consumer symbols, all allowlisted),
      section 3's impossible-PASS proof (no mass-dependent check passed
      in any attempt), section 6's legacy sweep (every stored design
      manifest legacy-clean; real DB byte-identical), and section 8's
      hermeticity lines.

## 2. Confirm nothing an operator can see has changed

- [ ] Open any existing design in the Designer: its mass figures,
      checks, BOM behavior and export behavior are exactly as before
      (all existing designs are legacy complete-mass by construction).
- [ ] Re-export one existing design's package and compare digests:

```powershell
# note the content_digest before and after — they must be identical
docker compose exec -T backend python -c "import json,glob;print([p for p in glob.glob('/app/data/exports/*/luxexchange_v1.zip')][:3])"
```

      (or simply re-run the export from the panel and check the digest
      shown matches the previous export of the same design).

## 3. Countersign the consumer census

Open `DECISIONS.md` ADR-065, decision 7.

- [ ] Every consumer of mass in the platform is listed by
      module::symbol with its honest behavior on incomplete mass, and
      the clerical correction is present:
      `package_class::classify_reports` is in the accounting with the
      REFUSED ruling (missing / failed / indeterminate
      `freeform_integrity_v1` for an applicable design ⇒ REFUSED;
      legacy designs untouched).
- [ ] LIMITATIONS §22 records that no user-facing incomplete-mass or
      free-form capability exists and that there is deliberately no
      input contract that makes mass-dependent checks pass.

## Sign-off

```
Date: 2026-09-04
Step 1 — auto gate PASS, zero skipped, census/proofs seen:   YES
Step 2 — existing designs and digests unchanged:             YES
Step 3 — ADR-065 census + scope guards countersigned:        YES

Notes:

Step 1 (operator, verbatim): "PASS — all 35 checks; sections skipped:
none; 28 consumer symbols; impossible-PASS proof completed; 67 legacy
designs verified and DB byte-identical."

Step 2 (operator, verbatim): "Mass figures, checks, BOM and export
behavior looked the same as before." The operator answered "Digests
identical: YES", but the digest value fields arrived as the unfilled
template placeholders (PASTE_FIRST_DIGEST / PASTE_SECOND_DIGEST) — no
actual digest strings were supplied. RECORDED HONESTLY AS SUCH: the
byte-identity claim rests on the operator's YES plus the auto gate's
independent machine evidence (section 6: every stored manifest
legacy-clean, real DB sha byte-identical, data/exports listing
unchanged), not on pasted digest values.

Step 3 verified by the operator 2026-09-04, verbatim:
- 28 mass-consumer symbols are recorded.
- package_class::classify_reports is included.
- Missing/failed/indeterminate applicable freeform_integrity_v1
  => REFUSED.
- LIMITATIONS 22 states that user-facing free-form and
  incomplete-mass capability remain unbuilt.

A partial sign-off sent earlier on 2026-09-04 (Step 3 only) was
recorded as partial and superseded by this completed one.
```
