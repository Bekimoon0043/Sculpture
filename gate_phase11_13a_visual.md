# gate_phase11_13a_visual.md — what the operator checks by eye

Covers the Phase 11 (Library), Phase 12 (Brief), Phase 13a (Operations)
screens and the new app shell. The auto gates prove the arithmetic; this
proves the software is usable and honest on screen. About twenty minutes.

```powershell
docker compose up --build -d
```

Open http://localhost:5173 and **hard-refresh (Ctrl+Shift+R)**.

---

## 1. The shell orients you

- [ ] A top bar shows the brand, then a **pipeline**: Brief → Council →
      Build → Validate → Export → Library.
- [ ] Each step has a glyph (`✓` done, `!` attention, `●` active, `○`
      pending) **and** a line of text under it — the state is readable
      without relying on colour.
- [ ] Cascade and Operations sit apart on the right, not in the pipeline.
      They are tools, not stages of the job.
- [ ] A status bar runs along the bottom: a green dot and "backend
      connected", spend, precedent count.
- [ ] Clicking any pipeline step navigates to the view that owns it.

**Now test that the dot tells the truth.** In a terminal:

```powershell
docker compose stop backend
```

- [ ] Within ~15 seconds the dot turns red and reads "backend unreachable"
      **without you clicking anything**.

```powershell
docker compose start backend
```

- [ ] It returns to green on its own.

## 2. Brief — provenance is visible on every field

Go to **Brief**. Paste:

> A basalt fountain for the hotel forecourt in Addis Ababa, about two and a
> half metres tall, with a gentle central jet.

Press **Start intake**.

- [ ] The Readiness card shows **NOT READY** and lists missing fields
      grouped by tier, each with a reason.
- [ ] Tier 1 and 2 chips are red; tier 3 is amber.
- [ ] Every form field shows a grey **UNKNOWN** chip.
- [ ] **Confirm intake** is disabled.

Type a height of `2.4` by hand.

- [ ] That field's chip turns green and reads **OPERATOR**.

### If you have API keys configured

Press **Parse brief ($)**.

- [ ] Fields the brief mentions gain blue **PARSED** chips.
- [ ] Hovering a PARSED chip shows the client's sentence it came from, and
      the sentence appears in italics under the field.
- [ ] **Your typed height of 2.4 is unchanged**, still OPERATOR, even though
      the brief says "two and a half metres".
- [ ] The notice reports something like "3 fields filled, 1 of yours kept,
      $0.0021".

If you have no keys:

- [ ] The notice says the provider is unavailable and that the form still
      works by hand. Nothing crashes.

### Readiness and confirmation

Fill in: project type, footprint, indoor = no, water = yes.

- [ ] Mark **Indoor = yes** briefly — the wind-speed field stops being
      listed as missing (there is no wind case indoors). Set it back to no.
- [ ] With tiers 1 and 2 answered, Readiness flips to **READY**.
- [ ] Press **Confirm intake** — the badge shows CONFIRMED and you land on
      Assembly.
- [ ] The pipeline's Brief step now shows `✓` and "confirmed".

Go back to **Brief** and change any field.

- [ ] The status returns to draft — the confirmation covered the old
      content.

## 3. The intake actually changes validation

Re-confirm the intake, then go to **Assembly**.

- [ ] A **site context** row appears with a checked box reading
      "use intake <id>".
- [ ] Press **Build assembly**.
- [ ] In Validation, expand `hydraulics`. It is **no longer NEEDS INPUT** —
      it shows real rows: reservoir capacity in litres, freeboard in mm, and
      a nozzle bore judged against a derived band.
- [ ] Expand `structure_static_v1`. There is a **site_overrides** row at the
      top listing the values you supplied *and their source* (`operator`).
- [ ] `design_wind_pressure_pa` shows a real number, and its basis mentions
      the ISA altitude correction.
- [ ] `ground_bearing_pressure_kpa` gives a real verdict against your
      allowable value.
- [ ] `overturning_safety_factor` still reports NEEDS INPUT — its message
      shows the **computed** safety factor and names the one remaining field
      (`overturning_safety_factor`), which your engineer signs in
      `config/gate_profiles.yaml`. This is correct, not a bug.
- [ ] `assembly_mesh` shows **PASS**, not NEEDS INPUT. (It has no threshold
      rows of its own — it is a whole-body watertight check — but it must
      still show its real verdict.)

### The profile notice must match what the gates received

With **use intake** on, look at the text under the gate profile dropdown:

- [ ] A green line reads "Supplied by intake <id>:
      `allowable_bearing_kpa, design_wind_speed_m_s`".
- [ ] The amber line lists **only** `overturning_safety_factor` as still
      unset, and explains it is a policy value your engineer signs — not
      something to enter in the brief.
- [ ] It does **not** tell you to edit `config/gate_profiles.yaml` for the
      two values you already typed into the Brief screen.

Now uncheck **use intake** and rebuild.

- [ ] The green line disappears and all three thresholds are listed as unset
      again — the notice tracks what the build will actually use.
- [ ] Hydraulics returns to NEEDS INPUT. The difference the intake makes is
      visible and reversible.

Re-check it and rebuild before continuing.

## 4. Library — accepting and searching

Go to **Library** before exporting anything.

- [ ] It says a precedent is the accepted deliverable and that the export
      package must exist first. It does not offer a broken button.

Go to **Assembly** → **Build export package**, then back to **Library**.

- [ ] The accept form appears with "Accepted by" and "Why is this design
      good?".
- [ ] **Accept as precedent** is disabled until the note is filled in.

Write a real sentence and accept.

- [ ] A precedent card appears with the acceptance note in quotes, the
      materials, size, mass, water flag and validation badge.
- [ ] The status bar precedent count increments.
- [ ] The pipeline's Library step turns `✓`.
- [ ] Trying to accept the same design again says it is already in the
      library.

### Search explains itself

Type `basalt_slab` in the material box, set water to **yes**, press Search.

- [ ] The precedent appears with green reason pills: "material
      basalt_slab", "water design".
- [ ] Set water to **no** and search again — **no results**. The filter is
      AND, not a similarity score.

### Archive and delete differ

- [ ] Press **archive**. The card disappears from the list.
- [ ] Tick **show archived** — it reappears, dimmed, with an ARCHIVED badge.
- [ ] Press **delete** and confirm the dialog.
- [ ] The card becomes a dashed **DELETED** tombstone that still shows its
      id and explains the payload is gone.

## 5. Operations — the spend you can trust

Go to **Operations**.

- [ ] A **Jobs** table lists your export jobs with status `completed` and
      checkpoint `sealed`.
- [ ] The **Spend** card shows a reconciliation panel with a green left edge
      reading "Ledgers reconcile", and how many sessions were checked.
- [ ] If you ran a parse or a Council session, a per-purpose table shows
      calls and cost, with `intake_parse` as its own line.
- [ ] The backup commands are shown ready to copy.

## 6. Backup actually restores

In PowerShell:

```powershell
docker compose exec backend python scripts/backup_restore.py backup --out data/backups/test.zip
docker compose exec backend python scripts/backup_restore.py restore --archive data/backups/test.zip --into data/restored-test
```

- [ ] Backup prints table counts and an artifact count.
- [ ] Restore prints **RESTORE VERIFICATION PASSED** and a line saying the
      LUXEXCHANGE package **re-verified OK**.
- [ ] Running the same restore again is refused because the target is not
      empty.

Clean up when done:

```powershell
docker compose exec backend rm -rf data/restored-test data/backups/test.zip
```

## 7. Nothing hides, nothing lies

- [ ] Scroll every new screen. No panel is clipped or crushed; the page
      scrolls instead.
- [ ] No raw JSON is displayed anywhere an operator reads.
- [ ] No number appears without a unit or a label.
- [ ] Every disabled button has a visible reason next to it.

---

**PASS** = every box ticked. Any unticked box is a failure for its phase;
record it in `LIMITATIONS.md` and report it before closing.
