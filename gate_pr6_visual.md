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
(Invoke-WebRequest "http://localhost:8000/api/costing/bom/$id.txt").Content
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

## Sign-off

- [ ] **PASS** — both materials are understandable, joints cannot be mistaken
      for double billing, shared install appears once, and the budget source
      is clear.
- [ ] **FAIL** — write the design id and what was misleading below.

Operator: ____________________  Date: ____________________

Notes:

______________________________________________________________________________