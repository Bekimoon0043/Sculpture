# gate_pr1_visual.md — PR-1, the operator's eye gate

**Cost: $0.** Nothing here spends money. No AI call is made.

**Before you start**, the backend image changed, so rebuild:

```powershell
docker compose up --build -d
```

---

## What changed, in one sentence

Your Design Spec's truck envelope has three numbers — length, width,
height — and until now the platform quietly kept only the biggest one;
each direction now binds on its own number, and a piece too tall for the
truck is cut or refused even when it fits lengthwise.

## 1. The tall piece that used to slip through

Build a column that fits the truck bed but is 10 cm too tall for a
2.2 m height limit:

```powershell
$body = @{
  elements = @(
    @{ element_id = "c1"; primitive = "sculptural_column"
       parameters = @{ diameter_mm = 600; height_mm = 2300
                       material_id = "basalt_slab" } }
  )
  seed = 0
  strict = $false
  fabrication = @{ max_module_m = @{ x = 2.4; y = 2.4; z = 2.2 }
                   max_lift_kg = 20000 }
} | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/geometry/assembly/build `
  -ContentType "application/json" -Body $body |
  ForEach-Object { $_.manifest.segmentation } |
  ConvertTo-Json -Depth 5
```

**Check by eye:**

- [ ] The column is **cut into 2 modules**, stacked in height (`grid`
      shows `z: 2`, x and y stay 1).
- [ ] Every module's `bbox_mm` third number (its height) is **at most
      2200**.
- [ ] The `basis` line names all three limits
      (`x 2.4 m / y 2.4 m / z 2.2 m`), not one number.

## 2. The Designer's single number still works

In the Designer (<http://localhost:5173>) build any design the way you
always have — the fabrication limit there is still one number, and it
honestly means "a cube this size". Nothing about your workflow changes.

- [ ] A normal Designer build completes exactly as before.
- [ ] Its Checks tab module row reads normally (no rebuild warnings).

## 3. Old spec-built designs say "rebuild me" instead of guessing

Any design that was built by the AI fabrication loop **before PR-1**
carries a collapsed limit — its spec said three numbers, the platform
kept one. Such designs now:

- [ ] still open and display normally (viewing is never blocked), and
- [ ] refuse to re-export, with a message that names the spec's true
      three numbers and the exact rebuild command — rather than quietly
      judging the geometry against the wrong envelope.

(If you have no pre-PR-1 spec-built design in the database, this step is
covered by the auto gate's §5 and needs no action from you.)

## 4. In the Checks tab

Open the design from step 1 in the workspace, Checks tab:

- [ ] The `c1.module_bbox_mm` row names the **binding axis** ("binding
      axis z") and shows the module height against **2200 mm** — not
      against 2400.

---

## Sign-off

```
Date:
Rebuilt with docker compose up --build -d:     yes / no
Step 1 — z-split observed, modules <= 2200 mm: yes / no
Step 2 — Designer single-number flow unchanged: yes / no
Step 3 — old spec design refuses with rebuild:  yes / n/a
Step 4 — Checks row names the binding axis:     yes / no

Your REAL truck/transport envelope, per axis:
  max_module_m x (length): ______ m
  max_module_m y (width):  ______ m
  max_module_m z (height): ______ m
(These replace the single blank in gate_phase6c2_visual.md's sign-off.)

Notes:
```
