# 13 — Building a sculpture from a file you wrote

**Who this is for:** you, at the machine, without needing to know Python or CAD.
This guide is the path for a sculpture **you** designed — the numbers are yours,
not a provider's. (For the AI path, where the Council writes the design, see
`05_first_fabrication.md`.)

---

## The idea in one paragraph

A sculpture in LuxuryForm is **one JSON file**. It lists the parts, what each is
made of, and how each part sits on the one below it. That file goes into the
real kernel, which fuses the parts into a single watertight solid, checks them
against your workshop's real limits, writes the export files and seals them into
a package for the fabricator. Nothing about the design lives only in a
conversation — if it is not in the file, it is not in the sculpture. That is what
makes the result reproducible: the same file always gives the same geometry,
byte for byte.

A worked example ships with the platform:
`sculptures/entoto_halo/request.json` (**Entoto Halo**, a four-part plaza
fountain). Read it while you read this guide — it is short, and every number in
it is explained below.

---

## Before you start

The stack must be up and healthy (`01_starting_the_platform.md`):

```bat
docker compose up -d
curl http://localhost:8000/api/health
```

If health answers, you are ready. You do not need any API key for this path:
building a sculpture from a file you wrote costs **$0**.

---

## Step 1 — Copy the example and change a number

```bat
copy sculptures\entoto_halo\request.json sculptures\my_piece\request.json
```

Open it. The parts look like this:

```json
{
  "element_id": "b1",
  "primitive": "basin_round",
  "parameters": {
    "diameter_mm": 2400, "height_mm": 400, "wall_mm": 80, "floor_mm": 120,
    "material_id": "basalt_slab"
  },
  "joint": { "type": "stack_on", "parent": "p1" }
}
```

- **`primitive`** — the shape family. The platform has **13**: `plinth`,
  `basin_round`, `basin_rect`, `sculptural_column`, `stepped_monolith`,
  `tiered_cascade`, `torus_ring`, `crescent_ring`, `water_wall`,
  `blade_fin_array`, `lotus_petal_array`, `perforated_screen`, `freeform_loop`.
  To see every parameter a primitive accepts, and its allowed range:

  ```bat
  curl http://localhost:8000/api/geometry/assembly/defaults
  ```

- **`parameters`** — always in millimetres, degrees or a material name. A number
  with no unit is a bug in this platform, by rule.
- **`joint`** — how this part meets its parent. **Exactly one** part carries no
  `joint`: the root, the piece that sits on the ground. Two joint types exist:
  `stack_on` (stands on the parent's top face and sinks `overlap_mm` into it) and
  `concentric_insert` (shares the parent basin's axis and stands on its floor).
- **`material_id`** — one of `basalt_slab`, `cast_concrete_c35_45`,
  `stainless_316l_sheet`, `stainless_316l_cast`, `bronze_cast`.

Leave `seed` alone. It is what makes the build reproducible.

---

## Step 2 — Build it and read the output

```bat
python scripts\build_sculpture.py sculptures\my_piece\request.json
```

Add switches as you need them:

| switch | what it adds |
|---|---|
| `--twice` | builds the identical file a second time and compares the STEP digest (Rule 5) |
| `--exports` | writes every export format and downloads the sealed package |
| `--bom` | fetches the bill of materials (and the readable text version) |
| `--out DIR` | where the captured evidence goes (default `data\sculpture_runs\<design_id>`) |
| `--base URL` | a different API address (default `http://localhost:8000`) |

The full run for the example:

```bat
python scripts\build_sculpture.py sculptures\entoto_halo\request.json --twice --exports --bom
```

---

## Step 3 — Understand a refusal (this is the useful part)

If your file breaks a real rule, the kernel **refuses it and tells you the
numbers**:

```
HTTP 422 — the kernel refused this design:
  t1: stack_on c1 lands on a -282.6 mm radial seat, below the 5 mm floor for
  stainless_316l_cast on bronze_cast (child base annulus ⌀845.109..1074.89 on
  parent top annulus ⌀100..280 mm) — a seat narrower than the fabrication
  tolerance stack can vanish in the workshop (signed sheet §2.1). Thicken the
  parent wall, adjust a diameter, reduce the offset, or make the parent solid
```

That message is not an obstacle; it is the design review you would otherwise pay
for. **A negative or too-small seat has a physical meaning:** the part above is
resting on nothing, or on a ledge too thin to survive the workshop's tolerances.
Fix the numbers it names and run it again. The same applies to a wall thinner
than the material allows, a part that will not fit inside its basin, or a part
heavier than your crane.

---

## Step 4 — Read the verdict honestly

Every build ends with **three gate verdicts**, plus a separate mesh check
("watertight, one body"). Three words matter in those verdicts:

- **`pass`** — checked, with real numbers, and it is fine.
- **`fail`** — checked and it is **not** fine. Fix the design.
- **`needs_input`** — **it could not be checked**, and the message names exactly
  what is missing. This is never a pass.

Right now a public-plaza piece always shows **`needs_input`** on structure and
fabrication, because three things can only come from you or a professional:

| what is missing | who supplies it |
|---|---|
| design wind speed at the piece's height | your local wind map, or your structural engineer |
| allowable ground bearing pressure | a geotechnical survey of the actual site |
| declared lift points (any part over 50 kg) | your rigging reviewer |

Fill those in `config/gate_profiles.yaml` (and mark the profile `signed_off:
true` once the professional has approved them) and the same file rebuilds to a
clean verdict with **no change to the sculpture**. Do not invent these three
numbers, and do not let anyone tell you a design is approved while they are
blank: that is exactly what the `PRE_FABRICATION` warrant on the package is
there to prevent.

---

## Step 5 — Where your sculpture now lives

| what | where |
|---|---|
| the design record + manifest | in the database; visible at http://localhost:5173 |
| the geometry | `data\designs\<spec_hash>\assembly.step` (canonical) and `.glb` (preview) |
| the export files | `data\exports\<design_id>\…` |
| the package for the fabricator | `data\exports\<design_id>\luxexchange_v1.zip` |
| the evidence of your run | `data\sculpture_runs\<design_id>\` (build, exports, BOM, package) |

The `.zip` is self-contained: a fabricator who has never met this platform can
unzip it and run `verify_luxexchange.py` to prove every file is intact and
unedited. Read `README_DWG_SKP.txt` inside it before promising anybody a `.dwg`.

---

## Two honest limits

- **Renders need the Blender worker.** Without it, a render job fails with
  *"render-worker produced no result within 90s"*. You can still see the piece in
  the viewport at http://localhost:5173, and the `SVG` inside the package is a
  real plan and elevation sheet.
- **The BOM has no total until you fill the rate card.** The masses, areas and
  crane pick are measured to the gram; the money is missing, and the BOM lists
  every rate path it needs. It will never invent a price. The checklist is
  `12_rate_card_checklist.md`.

---

## If you only remember one thing

The file is the design. If you want to change the sculpture, change the file and
run the same command — never edit the STEP, the DXF or the package by hand. Those
are outputs, and a hand-edited output is no longer provably yours.
