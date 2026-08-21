# Validation gates — what the four statuses mean, and what you must supply

Phase 8. Read this once; it takes five minutes and it decides whether the
platform can tell you your fountain is safe.

---

## The four statuses

Every check the platform runs ends in exactly one of four states. The
difference between the middle two is the whole point.

| badge | what it means | what to do |
| --- | --- | --- |
| **PASS** | The check ran. The measured value is inside its limit. | Nothing. |
| **WARN** | The check ran. The value is marginal, **or** it breached a threshold you have not signed off yet. | Read the number. Decide if you accept it. |
| **NEEDS INPUT** | The check **could not run**. Something it needs was not supplied. | Supply the missing value — the row names it. |
| **FAIL** | The check ran. The value is outside its limit. | Fix the design. This blocks acceptance. |

**NEEDS INPUT is not a pass.** Before Phase 8 the platform reported "no
water information supplied" as a warning, and a warning was displayed as a
green PASS. A design could show PASS on every layer while the hydraulics had
never been checked at all. That is now impossible: the header badge shows
the worst status across every layer.

---

## Where every limit comes from

Every row carries a **basis** line in small grey text. It names the exact
source of the limit:

```
basis: config/materials.yaml:basalt_slab.min_wall_mm
basis: Design Spec fabrication.max_lift_kg
basis: d = sqrt(4Q/(pi*v)) = 20.60 mm from water_context_v1.flow_l_per_min
       and gate_profiles.yaml:public_plaza.jet_velocity_m_s = 6 m/s
```

If you ever wonder "where did that number come from?", the answer is on the
screen. No limit in this system is a value someone typed because it looked
reasonable.

---

## The four gates

**Mesh** — is the geometry one watertight solid? Automatic, no input needed.

**Structure (`structure_static_v1`)** — rigid-body statics. Will it stand up,
will it tip over in wind, and what pressure does it put on the ground? This
is **not** finite-element analysis: it tells you whether the piece *tips*,
not whether it *cracks*.

**Hydraulics** — is the basin big enough for the pump, is there enough
freeboard to stop it splashing out, and does the nozzle bore match the flow?

**Fabrication** — can your workshop make it, lift it and get it on a truck?

---

## What you must supply, and who supplies it

Open `config/gate_profiles.yaml`. Three thresholds ship **empty on purpose**
because no honest default exists for them.

### 1. `design_wind_speed_m_s` — from your structural engineer

The 3-second gust design wind speed for the actual site, at the height of
the piece. Get it from the local building authority's wind map or from the
project's structural engineer.

Until you supply it, the overturning check reports NEEDS INPUT. It will not
guess.

### 2. `allowable_bearing_kpa` — from a geotechnical survey

How much pressure the ground at the site can carry. This varies by more than
ten times between soft clay and rock, so a default would be dangerous rather
than merely wrong.

The platform still tells you the pressure your piece *applies* — you just
cannot get a verdict until it knows what the ground can take.

### 3. `overturning_safety_factor` — a policy decision your engineer signs

How much margin you require between the restoring moment and the wind
moment. Below 1.0 the piece tips over.

### Everything else is already filled in

Freeboard, turnover, jet velocity, tool aspect ratio, service void and the
manual handling limit ship with values drawn from LuxuryCon's own practice.
They are **yours to change** — same status as the workshop envelopes in
`materials.yaml`. They are not citations of an external standard.

---

## `signed_off` — the switch that makes gates binding

Every profile has this line:

```yaml
signed_off: false
```

While it is `false`:

- every gate still runs
- every real measured number is still shown
- a breach of one of **that profile's** thresholds reports **WARN** instead
  of FAIL

Nothing is blocked on a number nobody has approved. Material limits from
`materials.yaml` and workshop limits from the Design Spec are **always**
binding — those were signed when you entered them.

When you and your engineer have reviewed the values, change it to:

```yaml
signed_off: true
```

From then on a breach is a **FAIL** and blocks acceptance. That is the point
of the switch.

---

## Why altitude appears in a wind calculation

Wind force depends on air density, and air density depends on altitude.
Addis Ababa sits near 2355 m, where air is about **21% thinner** than at sea
level:

```
sea level     1.225 kg/m3
Addis Ababa   0.971 kg/m3   (ISA formula, site_altitude_m: 2355)
```

Using the sea-level figure would overstate every wind moment on every piece
LuxuryCon builds in its own city. Change `site_altitude_m` per project site.

---

## A design that breaches a workshop limit still gets built

If an element comes out heavier than `max_lift_kg`, the platform now
**builds the geometry anyway** and fails the fabrication gate with the real
number:

```
basin_01.mass_kg    1550.02 kg    limit 50 kg    FAIL
```

You can look at the piece in the viewport and see the number that
disqualifies it. Previously this returned an error page with nothing to look
at.

The AI fabrication loop is unaffected — generated code still gets a hard
refusal, because a program that produces an unbuildable part must be
rejected, not discussed.

---

## Running the gate yourself

```powershell
docker compose exec backend python scripts/gate_phase8_auto.py
```

Costs nothing, needs no internet, no API keys. Exit code 0 means pass.
