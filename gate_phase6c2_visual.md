# gate_phase6c2_visual.md — Phase 6 slice C2, the operator's eye gate

**Cost: $0.** Nothing here spends money. No AI call is made.

**Before you start**, the backend image changed, so rebuild:

```powershell
docker compose up --build -d
```

The auto gate (`scripts/gate_phase6c2_auto.py`) has already proved the
arithmetic. What it cannot judge is whether the pieces it produces are
pieces **your workshop would actually cut**. That is this document.

---

## What changed, in one sentence

A fountain bigger than your crane or your truck used to be refused. It now
arrives as numbered modules, and the crane line prices the heaviest
*module* instead of the whole fountain.

---

## 1. The refusal that became a yes

Build a 5 m basalt basin with a module limit your yard actually works to.

```powershell
$body = @{
  elements = @(
    @{ element_id = "b1"; primitive = "basin_round"
       parameters = @{ diameter_mm = 5000; height_mm = 700; wall_mm = 150
                       material_id = "basalt_slab" } }
  )
  seed = 0
  strict = $false
  fabrication = @{ max_module_m = 2.4; max_lift_kg = 2000 }
} | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/geometry/assembly/build `
  -ContentType "application/json" -Body $body |
  ForEach-Object { $_.manifest.segmentation } |
  ConvertTo-Json -Depth 4
```

**Check by eye:**

- [ ] `module_count` is **9** and `heaviest_module_kg` is about **1,472 kg**.
      As one piece this basin is **11,346 kg**. Before this slice the
      platform refused to build it at all.
- [ ] `heaviest_module_kg` is a weight **your crane actually takes**. If
      2,000 kg is not your real limit, say so — the limit is yours, not the
      platform's.

## 2. THE JUDGEMENT CALL — do these look like pieces your masons would cut?

This is the one thing in the slice I could not decide for you, and it is
marked as judgement in ADR-056.

The platform cuts with **axis-aligned saw planes**, so a round basin split
three ways becomes a 3 × 3 waffle: four corner pieces, four edge pieces, one
middle. A stone mason segmenting a circular basin might instead cut **radial
pie segments**, like a millstone.

- [ ] Look at the nine module masses in the output above (they run
      1,083 · 1,083 · 1,083 · 1,083 · 1,125 · 1,472 · 1,472 · 1,472 · 1,472 kg).
      **Would your shop cut a round basin on a square grid, or radially?**

**If the answer is radial, say so and it becomes its own slice.** The grid
is not wrong — it is the only pattern that works for every shape in the
library, including walls, rectangular basins and monoliths — but for round
vessels radial may be the better answer, and only you know how the yard
works.

A second, smaller judgement in the same place: the planes are **evenly
spaced**, which makes the heaviest module as light as possible. If instead
you buy fixed stock and would rather have full-size slabs plus one off-cut,
that is a different rule.

## 3. The crane line stops lying

```powershell
$id = "<design_id from step 1>"
(Invoke-WebRequest "http://localhost:8000/api/costing/bom/$id.txt").Content
```

- [ ] There is a **WHAT SHIPS** block near the top: modules, heaviest single
      pick, seam to join.
- [ ] `heaviest single pick` says **"(a module, not the assembled
      fountain)"** and is the module weight, not the 11-tonne total.
- [ ] **Fabrication — seams** now says `[RATE MISSING]` and names
      `materials.basalt_slab.seam`. Before this slice it said the driver did
      not exist. It is now **your** number to supply, not our code to write.
- [ ] **Install — transport** now says `[RATE MISSING]` and names
      `install.truck_payload_kg`. Same transition.
- [ ] **Material — <name>** still says `[NOT COMPUTABLE]`. **This is
      deliberate and honest.** Read its blocker: it is waiting on a slab
      *thickness* (absent from `materials.yaml`) and on unrolling a curved
      shell onto flat sheet — neither of which segmentation provides.
      Quoting basalt **per m³ or per kg** makes this line, the largest on
      the BOM, compute immediately.

## 4. The refusal did not go away

Put a blade ring over the module limit:

```powershell
$body = @{
  elements = @(
    @{ element_id = "a1"; primitive = "blade_fin_array"
       parameters = @{ hub_diameter_mm = 900; blade_count = 24
                       blade_length_mm = 700
                       material_id = "stainless_316l_sheet" } }
  )
  seed = 0
  strict = $true
  fabrication = @{ max_module_m = 0.8; max_lift_kg = 5000 }
} | ConvertTo-Json -Depth 6
try {
  Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/geometry/assembly/build `
    -ContentType "application/json" -Body $body
} catch { $_.ErrorDetails.Message }
```

- [ ] It is **refused**, and the message names `a1`, says
      `discrete_array`, and explains that saw planes through a blade ring
      produce fragments rather than modules.
- [ ] It does **not** offer you 25 pieces. (A naive grid would: the auto
      gate prints that it would have produced 25 "modules", the lightest
      0.9 kg against a heaviest of 2,685.7 kg — chopped-off blade tips.)

## 5. In the Designer workspace

Open <http://localhost:5173>, build the 5 m basin from step 1, and open the
**Checks** tab.

- [ ] The fabrication gate row `b1.module_split_count` reads like a sentence
      about your workshop: "ships as 9 modules, heaviest 1,472.2 kg, with
      8.42 m of seam to join on site".
- [ ] The row `b1.mass_kg` shows the **module** weight with the element
      total in its basis text, not the element weight.

---

## Known and deliberate, so they are not defects

- **Mixed-material assemblies are refused for costing** with HTTP 409
  naming every material. Per-element costing is the costing tie-off
  (`NEXT.md` W-7).
- **Designs built before 2026-08-27 have no segmentation.** Their BOM asks
  you to rebuild them once rather than guessing a module count. Rebuild any
  older assembly before quoting it.
- **Gate profiles are still unsigned** (`B-5`), so a module breach reports
  **warn**, not **fail**. A green badge on a segmented design is not yet a
  binding pass.

---

## Sign-off

```
Date:
Rebuilt with docker compose up --build -d:   yes / no
Steps 1, 3, 4, 5 all as described:           yes / no

Step 2 — the judgement call:
  Round basins should be cut:   axis-aligned grid  /  radial segments
  Planes should be:             evenly spaced      /  full slabs + off-cut
  Real max_lift_kg for your crane:            ______ kg
  Real max_module_m for your truck/bed:       ______ m

Notes:
```
