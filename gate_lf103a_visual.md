# gate_lf103a_visual.md — LF-103A, the operator's eye gate

**Cost: $0.** Nothing here spends money. No AI call is made.

**Before you start — do NOT rebuild.** The running containers already
use verified image `9fe4c4328116`, byte-identical to the working tree
(12/12 sha256 file matches, recorded in ADR-063). Only confirm the
services are running:

```powershell
docker compose ps
```

You should see `backend`, `frontend`, `geo-worker` and `render-worker`
all Up. If any is down, coordinate with any live session before
starting it.

**Evidence note (2026-09-02):** the Stage 2 full-suite duration of
59808.04 s recorded in ADR-063 was inflated by overnight host
suspension — the run is valid FUNCTIONAL evidence (`514 passed`), not
performance evidence.

## What changed, in one sentence

Until now a design that failed its own engineering checks sealed exactly
the same professional-looking fabrication package as a perfect one; now a
FAILED design refuses to package at all (while staying viewable), an
unproven design ships only as an unmistakable PRE-FABRICATION deliverable
— marked download name, marked filenames inside, a printed
NOT-FOR-CONSTRUCTION notice on the drawing, and an
`ENGINEERING_WARRANT.txt` naming every unresolved check and whose
professional input it needs — and an old package sealed before this rule
refuses to download until you deliberately re-seal it.

## 1. A failed design cannot ship

In the Designer, build something deliberately over-limit: set
`max_lift_kg` to `50` on any assembly and Build.

- [ ] The build SUCCEEDS and you can see and orbit the geometry (that is
      ADR-034 — you must be able to look at the thing that failed).
- [ ] The Checks tab shows FAIL with the real mass numbers.
- [ ] The Export panel shows a red "validation FAIL" badge, the build
      button is replaced by "Package refused — validation FAIL", and the
      explanation names what stays available.

Then try the raw API (the server, not the panel, is the authority):

```powershell
Invoke-WebRequest http://localhost:8000/api/geometry/assembly/latest.step
```

- [ ] It refuses (HTTP 409) and the error text names the failing check.

## 2. A normal design ships as PRE-FABRICATION, unmistakably

Build a normal assembly (the default library example is fine), then
Export.

- [ ] The panel badge says **PRE-FABRICATION** (amber, never green), and
      the download card says "Download PRE-FABRICATION package (not for
      construction)".
- [ ] The downloaded file itself is named
      `luxexchange_<id>_PRE-FABRICATION.zip`.
- [ ] Extract the zip. Every file under `exports/` says
      `PRE-FABRICATION` in its own filename (e.g.
      `assembly.PRE-FABRICATION.step`).
- [ ] Open `ENGINEERING_WARRANT.txt`. It says the package is NOT
      fabrication-ready, lists every unresolved check with its real
      numbers, and names the professional input each needs (structural
      engineer, MEP/fountain engineer, …).
- [ ] Open `exports/assembly.PRE-FABRICATION.dxf` (or the `.svg` in a
      browser). The drawing carries a printed
      **PRE-FABRICATION - NOT FOR CONSTRUCTION** notice you can actually
      see.
- [ ] Run `python verify_luxexchange.py` inside the extracted folder — it
      still PASSES: marking never breaks integrity.
- [ ] Download the STEP alone from the panel. The saved filename says
      PRE-FABRICATION; the file content is the untouched canonical STEP.

## 3. Old packages fail closed

Pick any design exported before today (e.g. from the Library) and try to
download its package.

- [ ] The download refuses, the message says the package is unclassified
      (sealed before LF-103A), names the exact re-export action, and the
      panel offers "Re-seal package under LF-103A".
- [ ] The old zip file on disk is byte-identical afterwards (nothing
      rewrote it): `Get-FileHash data\exports\<id>\luxexchange_v1.zip`
      before and after.

## 4. Run the auto gate and read its verdict

```powershell
docker compose exec backend python scripts/gate_lf103a_auto.py
```

- [ ] It ends **PASS**, and section [9] proves the gate itself touched
      neither your real database nor your real `data\exports` tree.

## Sign-off

```
Date: 2026-09-02
Step 1 — failed design: viewable, never shippable:      yes
Step 2 — PRE-FABRICATION marking end-to-end:            yes
Step 3 — legacy package refused, bytes untouched:       yes
Step 4 — auto gate PASS incl. hermeticity:              yes

Notes: Signed PASS by the operator, who personally completed all four
visual steps. The confirmation, verbatim:

  "I confirm:
   - FAILED geometry remains viewable but fabrication-capable exports
     are refused.
   - The normal design produced an amber PRE-FABRICATION package.
   - The ZIP and extracted export filenames contain PRE-FABRICATION.
   - ENGINEERING_WARRANT.txt correctly lists unresolved evidence and
     reviewers.
   - The SVG/DXF notice says PRE-FABRICATION — NOT FOR CONSTRUCTION.
   - Standalone CAD downloads expose the correct classification and
     marked filename.
   - Legacy-unclassified package download was refused and its original
     hash remained unchanged.
   - gate_lf103a_auto.py ended PASS."

(A first sign-off sent earlier on 2026-09-02, before the steps were
performed, was withdrawn by the operator and never recorded; this is
the operative sign-off.)
```
