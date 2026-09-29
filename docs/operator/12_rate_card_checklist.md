# 12 — Costing rate-card checklist (PR-6 / ADR-074)

**Who this is for:** the LuxuryCon operator and whoever supplies real Addis
Ababa purchase, workshop and installation rates.

LuxuryForm does not guess a rate. `config/costing.yaml` currently has
**47 required blank entries**. Until all applicable entries are supplied,
the BOM prints **NO TOTAL — THIS BOM IS INCOMPLETE**. This checklist is the
same list returned by:

```powershell
Invoke-RestMethod http://localhost:8000/api/costing/rate-card
```

## The quickest useful order

1. **Basalt purchase price:** quote `materials.basalt_slab.buy_price` per
   **m3 or kg**, not per slab. Per-slab still needs stock thickness and shell
   unrolling, which the platform honestly does not have.
2. Fill dated `fx_rates.ETB` and the shared install/workshop percentages.
3. Fill the material block(s) used by the current project.
4. Set `joints.cross_material_owner` after deciding who bears a seam where
   two different materials meet: `parent`, `child`, or `stronger_rate`.
5. Fill truck capacities from the real vehicle, never a brochure guess.

## Material entries — 35 total (7 × 5 materials)

For **each** material below, supply these seven paths:

1. `buy_price` — amount, currency, and usable unit (`kg` or `m3` is directly
   computable; `sheet`/`slab` are not yet computable for formed shells)
2. `waste_factor_pct`
3. `fabrication.method` — `cnc_mill`, `hand_carve`, `cast`, or
   `sheet_fabricate`
4. `fabrication.labor`
5. `fabrication.hours_per_m3`
6. `finishing`
7. `seam` — quote `per: m` for seam run or `per: m2` for bedded face

### A. Bronze cast

- [ ] `materials.bronze_cast.buy_price`
- [ ] `materials.bronze_cast.waste_factor_pct`
- [ ] `materials.bronze_cast.fabrication.method`
- [ ] `materials.bronze_cast.fabrication.labor`
- [ ] `materials.bronze_cast.fabrication.hours_per_m3`
- [ ] `materials.bronze_cast.finishing`
- [ ] `materials.bronze_cast.seam`

### B. Basalt slab

- [ ] `materials.basalt_slab.buy_price`
- [ ] `materials.basalt_slab.waste_factor_pct`
- [ ] `materials.basalt_slab.fabrication.method`
- [ ] `materials.basalt_slab.fabrication.labor`
- [ ] `materials.basalt_slab.fabrication.hours_per_m3`
- [ ] `materials.basalt_slab.finishing`
- [ ] `materials.basalt_slab.seam`

### C. Stainless 316L sheet

- [ ] `materials.stainless_316l_sheet.buy_price`
- [ ] `materials.stainless_316l_sheet.waste_factor_pct`
- [ ] `materials.stainless_316l_sheet.fabrication.method`
- [ ] `materials.stainless_316l_sheet.fabrication.labor`
- [ ] `materials.stainless_316l_sheet.fabrication.hours_per_m3`
- [ ] `materials.stainless_316l_sheet.finishing`
- [ ] `materials.stainless_316l_sheet.seam`

### D. Cast concrete C35/45

- [ ] `materials.cast_concrete_c35_45.buy_price`
- [ ] `materials.cast_concrete_c35_45.waste_factor_pct`
- [ ] `materials.cast_concrete_c35_45.fabrication.method`
- [ ] `materials.cast_concrete_c35_45.fabrication.labor`
- [ ] `materials.cast_concrete_c35_45.fabrication.hours_per_m3`
- [ ] `materials.cast_concrete_c35_45.finishing`
- [ ] `materials.cast_concrete_c35_45.seam`

### E. Stainless 316L cast / heavy formed

- [ ] `materials.stainless_316l_cast.buy_price`
- [ ] `materials.stainless_316l_cast.waste_factor_pct`
- [ ] `materials.stainless_316l_cast.fabrication.method`
- [ ] `materials.stainless_316l_cast.fabrication.labor`
- [ ] `materials.stainless_316l_cast.fabrication.hours_per_m3`
- [ ] `materials.stainless_316l_cast.finishing`
- [ ] `materials.stainless_316l_cast.seam`

Machine and mould/pattern amounts may remain null only when the selected
method makes them genuinely not applicable; the BOM prints that fact.
`install.crane_day_rate` may remain null only when the job genuinely uses
no crane. Those three conditional nulls are therefore not in the required
47-entry census.

## Shared workshop / installation / commercial entries — 12 total

- [ ] `workshop.overhead_pct`
- [ ] `install.crew_day_rate`
- [ ] `install.crew_size`
- [ ] `install.days_per_tonne`
- [ ] `install.transport`
- [ ] `install.truck_payload_kg`
- [ ] `install.modules_per_trip`
- [ ] `contingency_pct`
- [ ] `markup_pct`
- [ ] `joints.cross_material_owner`
- [ ] `fx_rates.ETB.rate` — ETB per 1 USD
- [ ] `fx_rates.ETB.as_of` — ISO date, `YYYY-MM-DD`

## Cross-material joint rule

Set exactly one:

- `parent` — the element the child is joined onto bears the seam rate.
- `child` — the joined-on child element bears it.
- `stronger_rate` — the higher seam rate owns it; both rates must use the
  same currency and unit. A tie goes to the parent and the BOM says so.

While this is null, a mixed-material BOM still works, but its joint line is
`RATE MISSING`, no side is billed, and no total is produced.

## B-4 — provider token-price worksheet (separate from construction costs)

Before trusting AI spend forecasts, verify `config/pricing.yaml` against
the three providers' current **first-party** pricing pages (ADR-009):

| Provider | Model(s) in `config/council.yaml` | Input rate verified | Output rate verified | Cache rates verified | Date | First-party source recorded |
|---|---|---:|---:|---:|---|---|
| Anthropic |  | [ ] | [ ] | [ ] |  |  |
| OpenAI |  | [ ] | [ ] | [ ] |  |  |
| Moonshot / Kimi |  | [ ] | [ ] | n/a / [ ] |  |  |

Then bump `pricing_version` in `config/pricing.yaml`. Do not copy numbers
from this document; it intentionally contains none.

## Verify after filling

```powershell
Invoke-RestMethod http://localhost:8000/api/costing/rate-card
docker compose exec backend python scripts/gate_costing_auto.py
docker compose exec backend python scripts/gate_pr6_auto.py
```

The first command must report `missing_count: 0`. The gates prove the
arithmetic and tracing; the rates remain your commercial facts.