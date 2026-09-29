# PR-6 visual gate — per-element costing and confirmed budget

**Cost:** $0. **Provider calls:** none.

This visual gate checks the operator-facing wording and grouping that an
auto test cannot judge. It does not ask you to approve any rate—the real
rate card is still blank.

## Before you start

```powershell
cd C:\Users\burook\luxuryform
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/api/health
```

Create or open a design with at least two materials (for example a basalt
plinth plus bronze basin) and copy its `design_id` from the URL/status.

## 1. JSON BOM — both materials, no 409

A ready-made two-material design already exists on this machine if you do not
want to build one: `620543b0-dd0f-40ed-aa1c-bf0719a9118e` (plinth `p1` in
basalt, basin `b1` in bronze, one `stack_on` joint). Use its id in the
commands below.

**Use `curl.exe`, not `Invoke-WebRequest`, for the `.txt` route (step 2).**
`Invoke-WebRequest` tries to parse the response as a web page and stops to ask
for permission — it waits forever for an answer and looks like a hang.

```powershell
$id = "PASTE-DESIGN-ID-HERE"
$bom = Invoke-RestMethod "http://localhost:8000/api/costing/bom/$id"
$bom | ConvertTo-Json -Depth 12
```

- [ ] HTTP succeeds; there is no `mixed_material_assembly` 409.
- [ ] `drivers.materials` names both real materials.
- [ ] `elements` has one record per design element.
- [ ] Fabrication line IDs begin with their element id, for example
      `p1/material_purchase` and `b1/finishing`.
- [ ] Exactly one each of `install_crane`, `install_crew`, and
      `install_transport` exists.
- [ ] Because the real rate card is blank, `complete` is false and
      `totals.total_usd` is null—there is no partial total.

## 2. Text BOM — readable ownership and grouping

```powershell
curl.exe -s "http://localhost:8000/api/costing/bom/$id.txt"
```

- [ ] Each element has its own `FABRICATION — <id> (<material>)` heading.
- [ ] The `JOINTS` heading says each joint is billed once.
- [ ] A cross-material joint with no selected owner says `RATE MISSING` and
      names `joints.cross_material_owner`; it does not bill both sides.
- [ ] `INSTALL (shared — once for the whole assembly)` appears once.
- [ ] The bottom says `NO TOTAL — THIS BOM IS INCOMPLETE`.

## 3. Confirmed brief budget binds automatically

Create/confirm a Brief with `budget.amount_max` and `budget.currency`, then
build a design using that intake. Request the BOM **without** adding any
budget query parameter:

```powershell
$bom = Invoke-RestMethod "http://localhost:8000/api/costing/bom/$id"
$bom.budget | Format-List
```

- [ ] `source` says `confirmed brief intake`.
- [ ] `source_detail` names the intake and field provenance.
- [ ] With the blank rate card the status is `not_performed`, never `pass`.
- [ ] If you edit the confirmed intake (which reopens it as draft), the BOM
      no longer carries that intake budget until it is confirmed again.

## 4. Checklist is usable

Open `docs/operator/12_rate_card_checklist.md`.

- [ ] It lists 47 required entries.
- [ ] The first recommendation is basalt per m3 or kg—not per slab.
- [ ] The cross-material owner choices are understandable.
- [ ] The B-4 provider-price worksheet contains no invented price.

## 5. Two conventions to judge (found while preparing this walk)

- [ ] The uncut-element seam line reads `element <id> is one module with no
      segmentation cut, so there is nothing to join inside it; any element
      JOINT it takes part in is billed once under JOINTS` — and never claims
      the design has no element joints. (Before 2026-09-29 it said the
      false thing; it is now guarded by a gate check and a test.)
- [ ] `install.crane_day_rate: null` renders as `no crane on this job`. This
      is a stated convention, but a job whose crane rate is merely unfilled
      would then be totalled **without crane**. Keep it, or make `null` mean
      "rate missing — ask me"? Your call; if you change it, it becomes its own
      small slice.

## Sign-off

- [ ] **PASS** — both materials are understandable, joints cannot be mistaken
      for double billing, shared install appears once, and the budget source
      is clear.
- [ ] **FAIL** — write the design id and what was misleading below.

Operator: ____________________  Date: ____________________

Notes:

______________________________________________________________________________