# Phase 6 slice C1 visual gate — the six new masses ($0)

No live spend. Rebuild first (backend code changed); coordinate with any
other live Claude session before rebuilding shared containers:

```powershell
docker compose up --build -d
```

Run the $0 auto gate before looking at pixels:

```powershell
docker compose exec backend python scripts/gate_phase6c_auto.py
```

Expected: `PASS — Phase 6 slice C1 auto gate` and exit code 0.

## 1. The palette knows the new shapes

Open the **Designer** → **Add** palette:

- [ ] Six new entries appear — rectangular basin, stepped monolith, water
      wall, torus ring, blade fin array, lotus petal array — each with a
      REAL kernel preview (built from live registry defaults), not a
      placeholder icon

## 2. Each mass, by eye

Build each one at its defaults and look:

- [ ] **basin_rect** — a rectangular tub; with the section plane on, the
      inner corners are ROUNDED (that radius is your signed tool floor)
- [ ] **stepped_monolith** — three shrinking steps, sharp and even
- [ ] **water_wall** — a slab with the weir crest along its top: crest
      arc, land, drip lip on one face (same profile family as slice B)
- [ ] **torus_ring** — a clean donut resting on the ground plane
- [ ] **blade_fin_array** — count the blades (default 12), evenly spaced,
      every blade meeting the hub with no sliver gaps
- [ ] **lotus_petal_array** — eight tilted petals from a hub disc; petals
      may overlap each other (a lotus does) but nothing floats free

## 3. The gate composition

Build the 24-blade array inside a basin on a plinth (the agent can POST
the gate's C_PLAN, or compose it in the Designer):

- [ ] One coherent object; the Checks tab shows `assembly_mesh` PASS and
      `body_count` 1 — twenty-four fused blades did not split the body
- [ ] Orbit under the array (key `7`, then roll): every blade root is
      buried in the hub — no daylight between blade and hub

**PASS** = every box ticked; record in PHASE_6_REPORT.md. **FAIL** on any
box: stop, screenshot, report the exact parameters.
