# Phase 6 slice B visual gate — rim treatments + nozzle ring ($0)

No live spend in this gate. Rebuild first (backend code changed); check with
any other live Claude session before rebuilding shared containers:

```powershell
docker compose up --build -d
```

Run the $0 auto gate before looking at pixels:

```powershell
docker compose exec backend python scripts/gate_phase6b_auto.py
```

Expected: `PASS — Phase 6 slice B auto gate` and exit code 0.

## 1. The three treatments, by eye

In the **Designer**, build a basin (⌀2000, height 450, wall 40, floor 60,
basalt) three times, changing only `rim_treatment`:

- [ ] **weir_edge** — with the section plane on (X key `/` or the section
      control), the rim cross-section reads as a spillway: a rounded inner
      crest, a flat land, and a small square lip overhanging the outer
      face (the drip edge). The outer diameter grows by twice the drip
      edge (status: ⌀2010 at defaults).
      Note: building weir_edge directly in the Designer works (your
      explicit act); through the Council/fabrication path it additionally
      requires the spec's weir node at the crest elevation.
- [ ] **coping** — the rim carries a wider flat cap overhanging outward
      (⌀2120 at overhang 60), and the element got taller by the cap
      thickness (500 at thickness 50)
- [ ] **pool_edge** — both rim edges are rounded (bullnose); no sharp
      arris anywhere on the rim in the section view

## 2. The nozzle ring, by eye

Build the basin with a nozzle fixture (via a spec fabrication, or ask the
agent to POST the gate's B_PLAN):

- [ ] Looking straight down (key `7`), the floor shows the bores — equally
      spaced on a ring, correct count
- [ ] The Checks tab still shows `assembly_mesh` PASS and `body_count` 1 —
      the bores pierced the floor without splitting it
- [ ] In the manifest (Design tab / API), the element's `fixtures` entry
      records the count, bore and ring diameter that were actually cut

## 3. The honesty checks, by eye

- [ ] Set `rim_treatment` to weir_edge on a basin with wall 20 (basalt):
      the build refuses and the message does the arithmetic for you
      (land = wall + drip − crest radius vs the 15 mm feature floor)
- [ ] The refusal messages name real numbers and levers, not error codes

**PASS** = every box ticked. Record it in PHASE_6_REPORT.md. **FAIL** on
any box: stop and report what you saw — screenshot plus the exact
parameters.
