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

- [x] HTTP succeeds; there is no `mixed_material_assembly` 409.
      — **measured 2026-09-30: `HTTP=200`.**
- [x] `drivers.materials` names both real materials.
      — **`basalt_slab, bronze_cast`.**
- [x] `elements` has one record per design element.
      — **2 records (`b1` bronze_cast, `p1` basalt_slab`) for 2 elements.**
- [x] Fabrication line IDs begin with their element id, for example
      `p1/material_purchase` and `b1/finishing`.
      — **16 lines, every id prefixed (`b1/…`, `p1/…`).**
- [x] Exactly one each of `install_crane`, `install_crew`, and
      `install_transport` exists.
      — **one each, at assembly level.**
- [x] Because the real rate card is blank, `complete` is false and
      `totals.total_usd` is null—there is no partial total.
      — **`complete=false` and all seven `totals.*` fields null.**

## 2. Text BOM — readable ownership and grouping

```powershell
curl.exe -s "http://localhost:8000/api/costing/bom/$id.txt"
```

- [x] Each element has its own `FABRICATION — <id> (<material>)` heading.
      — **two headings: `b1 (bronze_cast)` and `p1 (basalt_slab)`.**
- [x] The `JOINTS` heading says each joint is billed once.
      — **`JOINTS (each billed ONCE, to the owner named on the line)`.**
- [x] A cross-material joint with no selected owner says `RATE MISSING` and
      names `joints.cross_material_owner`; it does not bill both sides.
      — **`Joint b1 (bronze_cast) onto p1 (basalt_slab): [RATE MISSING]`,
      blocked naming `costing.yaml joints.cross_material_owner is null`; no
      amount printed on either side.**
- [x] `INSTALL (shared — once for the whole assembly)` appears once.
      — **once.**
- [x] The bottom says `NO TOTAL — THIS BOM IS INCOMPLETE`.
      — **verbatim, with the 11-null / 1-driverless census beneath it.**

## 3. Confirmed brief budget binds automatically

Create/confirm a Brief with `budget.amount_max` and `budget.currency`, then
build a design using that intake. Request the BOM **without** adding any
budget query parameter:

```powershell
$bom = Invoke-RestMethod "http://localhost:8000/api/costing/bom/$id"
$bom.budget | Format-List
```

- [x] `source` says `confirmed brief intake`.
      — **`"source": "confirmed brief intake"`.**
- [x] `source_detail` names the intake and field provenance.
      — **`intake dc49cafd-… budget.amount_max (source=operator), currency
      (source=operator)`.**
- [x] With the blank rate card the status is `not_performed`, never `pass`.
      — **`"status": "not_performed"`, reason naming 11 missing rates and 1
      not-computable line.**
- [x] If you edit the confirmed intake (which reopens it as draft), the BOM
      no longer carries that intake budget until it is confirmed again.
      — **operator edit → `status = draft` → the whole `budget` block is
      absent; re-confirm → it returns.**

## 4. Checklist is usable

Open `docs/operator/12_rate_card_checklist.md`.

- [x] It lists 47 required entries.
      — **35 material (7 × 5) + 12 shared = 47, and the live API agrees:
      `missing_count = 47`.**
- [x] The first recommendation is basalt per m3 or kg—not per slab.
      — **"quote `materials.basalt_slab.buy_price` per m3 or kg, not per
      slab".**
- [x] The cross-material owner choices are understandable.
      — **`parent` / `child` / `stronger_rate`, one line each, with the tie
      rule stated. Operator judgement, made PASS 2026-09-30.**
- [x] The B-4 provider-price worksheet contains no invented price.
      — **every cell empty, and it says so: "it intentionally contains
      none".**

## 5. Two conventions to judge (found while preparing this walk)

- [x] The uncut-element seam line reads `element <id> is one module with no
      segmentation cut, so there is nothing to join inside it; any element
      JOINT it takes part in is billed once under JOINTS` — and never claims
      the design has no element joints. (Before 2026-09-29 it said the
      false thing; it is now guarded by a gate check and a test.)
      — **confirmed byte-for-byte in the rendered BOM, and the same page
      bills `joint/b1->p1` once under JOINTS. The guards were verified, not
      assumed: `gate_pr6_auto.py` §2 (43 → 44 checks), the test
      `test_uncut_element_seam_explanation_is_element_scoped` in
      `tests/test_costing_per_element.py`, source
      `backend/app/costing/bom.py:631-634`.**
- [x] `install.crane_day_rate: null` renders as `no crane on this job`. This
      is a stated convention, but a job whose crane rate is merely unfilled
      would then be totalled **without crane**. Keep it, or make `null` mean
      "rate missing — ask me"? Your call; if you change it, it becomes its own
      small slice.
      — **RULED 2026-09-30: KEEP the convention.** The rendered line is
      `Install — crane: not applicable — install.crane_day_rate is null = no
      crane on this job (pick weight would be 1,662.5 kg)`. The risk is real
      and now recorded as **D-30** in `NEXT.md` §2 instead of being fixed
      here: `backend/app/costing/bom.py:398-401` makes the null
      `NOT_APPLICABLE` unconditionally, and `install.crane_day_rate` is
      deliberately outside the 47-entry census
      (`docs/operator/12_rate_card_checklist.md:92-94`), so a card filled in
      every other respect can reach `complete` with no crane cost.

## Sign-off

- [x] **PASS** — both materials are understandable, joints cannot be mistaken
      for double billing, shared install appears once, and the budget source
      is clear.
- [ ] **FAIL** — write the design id and what was misleading below.

Signed (operator): SIGNED — 2026-09-30. The operator's results, verbatim:

> PASS — tick all boxes and sign; keep the `null → no crane` convention and
> add the risk to NEXT.md §2 Debts

That sentence rules both §5 items: box 1 stands as written, and box 2
**keeps** the convention — a null crane rate means "no crane on this job". Its
measured consequence is recorded as **D-30** in `NEXT.md` §2 rather than fixed
here, because changing it is a commercial decision with its own slice.

Notes — what was measured, on the live stack, **$0.00, no provider call**:

- §1 + §2 fixture `620543b0-dd0f-40ed-aa1c-bf0719a9118e`: `HTTP=200` (the
  mixed-material 409 is gone), `drivers.materials = basalt_slab, bronze_cast`,
  2 element records, 16 lines all prefixed by their element id (`b1/…`,
  `p1/…`), exactly one `install_crew` / `install_crane` / `install_transport`,
  and `complete=false` with all seven `totals.*` fields null. The `.txt` route
  was read with `curl.exe` — `Invoke-WebRequest` really does hang on it, as
  this document warns.
- §3 had no fixture on this machine, so one was built for the walk: intake
  `dc49cafd-b5a3-4b9b-a686-415631e547eb` (created with 8 operator-sourced
  fields, then confirmed) → design
  `9aa8be99-c1b0-48c4-bc76-6329d01e5c73`. With **no** budget query parameter
  the BOM returned `source = "confirmed brief intake"` with a `source_detail`
  naming the intake and both field provenances, and `status =
  not_performed`; an operator edit returned the intake to `draft` and the
  `budget` block disappeared entirely, returning on re-confirmation.
  **Side effect, stated:** the walk added one intake (left confirmed, height
  1.25 m) and one design to the live database. They were deliberately **not**
  cleaned up, following the standing rule about test designs.
- §4 was checked against the live API, not the file: `missing_count = 47`.
- §5 box 2's mechanism, for the record: `backend/app/costing/bom.py:398-401`
  and `docs/operator/12_rate_card_checklist.md:92-94`, as cited above.