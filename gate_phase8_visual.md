# gate_phase8_visual.md — what the operator checks by eye

The auto gate (`scripts/gate_phase8_auto.py`) proves the arithmetic at $0.
This proves the screen tells the truth. Ten minutes.

Start the stack, open http://localhost:5173, choose the **Assembly** tab.

```powershell
docker compose up --build -d
```

---

## 1. A warning must never look like a pass

Press **Build assembly**.

- [ ] The header badge reads **NEEDS INPUT**, not PASS.
- [ ] Under it, a sentence explains that a check could not be evaluated and
      that this is not a pass.
- [ ] `hydraulics` shows **NEEDS INPUT** — no water information was supplied.
- [ ] `structure_static_v1` shows **NEEDS INPUT**.
- [ ] `fabrication` shows **NEEDS INPUT** (lift points are not declared).

**This is the check that matters most.** Before Phase 8 this exact design
displayed a green PASS while the hydraulics had never been evaluated.

## 2. Every limit says where it came from

Expand `fabrication`.

- [ ] Each row shows check, value, limit and verdict.
- [ ] Under each check name there is a small grey `basis:` line.
- [ ] At least one basis names `config/materials.yaml`.
- [ ] At least one basis names `Design Spec fabrication.max_lift_kg`.

Ask yourself of any row: *where did that limit come from?* The answer must
be on screen.

## 3. The gate profile is visible and honest

- [ ] A **gate profile** dropdown lists three profiles.
- [ ] An amber note says the profile is **not signed off**.
- [ ] It lists the thresholds still unset, and names the file to edit.

## 4. NEEDS INPUT names what to supply

Expand `structure_static_v1`.

- [ ] The `overturning_safety_factor` row is NEEDS INPUT.
- [ ] Its message names `design_wind_speed_m_s` and says where to get it
      (wind map or structural engineer).

You should be able to act on this row without asking anyone what it means.

## 5. Supplying the numbers changes the verdict

Edit `config/gate_profiles.yaml`, in the `public_plaza` profile:

```yaml
    design_wind_speed_m_s: 30.0
    overturning_safety_factor: 1.5
    allowable_bearing_kpa: 150.0
```

Save. **No restart needed** — the config is read per request. Press
**Build assembly** again.

- [ ] `structure_static_v1` now shows **PASS**.
- [ ] `overturning_safety_factor` shows a real number well above 1.5.
- [ ] `ground_bearing_pressure_kpa` shows a real kPa figure.
- [ ] `design_wind_pressure_pa` mentions the altitude correction, and says
      sea-level density would overstate it by about 26%.

## 6. A failing design fails visibly, and you can still look at it

In `config/gate_profiles.yaml` set `signed_off: true`, save, and rebuild.
Then in the Assembly tab nothing changes — the design passes.

To see a real failure, the auto gate covers it; to see it by eye, reduce
`max_lift_kg` in the request. The point to confirm:

- [ ] A design that breaches a workshop limit **still renders in the
      viewport** — you see the piece and the number that disqualifies it.
- [ ] The fabrication gate shows **FAIL** with the measured mass and limit.
- [ ] The header badge shows **FAIL**.

## 7. Revert

- [ ] Set `signed_off: false` again unless your engineer has signed the
      values you entered.

---

**PASS** = every box ticked. Any unticked box is a Phase 8 failure; record
it in `LIMITATIONS.md` and report it before closing the phase.
