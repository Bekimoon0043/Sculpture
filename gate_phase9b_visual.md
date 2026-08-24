# Phase 9B Visual Gate — Blender Render Worker

**Operator check:** the render worker turns a real design into four views that
look like the design, at the right size and the right way up.

The auto gate (`gate_phase9b_auto.py`) already proves this numerically. This
one exists because a picture can satisfy every statistic and still be wrong in
a way only a person notices.

---

## 1. Start the worker

The render worker sits behind a compose profile, so it does not start with a
plain `docker compose up -d`. Start it explicitly:

```bat
docker compose --profile render up -d render-worker
docker compose ps render-worker
```

You should see `luxuryform-render-worker-1` with status `Up`.

If the build has never run on this machine it needs
`docker\render\blender-4.5.12-linux-x64.tar.xz` present first (about 360 MB,
fetched host-side so a dropped connection resumes). The image build itself
then needs no further downloads beyond 17 small system packages.

## 2. Run the auto gate

```bat
docker compose exec backend python scripts\gate_phase9b_auto.py
```

Expect `Phase 9B auto gate PASS` and a per-view table. On the operator's
machine this takes about 30 seconds.

## 3. Look at the pictures

The gate leaves its renders in the job directory it names in its output:

```
data\render_scratch\<job_id>\
    front.png  side.png  top.png  three_quarter.png
    blender.log      (the full Blender output, if you want it)
    views.json       (per-view timings and the bounding box)
```

The gate's own test object is a three-part stepped solid: a wide low plinth,
a narrower bowl above it, and a slim vertical stem on top. It is 2.2 m across
and 1.64 m tall.

## Pass criteria

- [ ] Four PNGs, each 256x256, one per view.
- [ ] `three_quarter.png` shows the stem standing **vertically**, on top of
      two stacked discs. If the object is lying on its side, fail this gate.
- [ ] `front.png` and `side.png` show the same silhouette as each other (the
      object is round), differing only in shading.
- [ ] `top.png` looks down on concentric circles.
- [ ] The object sits on a visible ground plane and casts a shadow onto it.
- [ ] Surfaces are mid-grey with readable shading — not flat white, not
      near-black, not a coloured material.
- [ ] The object fills most of the frame without being cropped.

## Then try it on a real design

Render one of your own designs rather than the gate's test object:

```bat
curl.exe -s -X POST http://localhost:8000/api/render/jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"design_id\": \"<a design id>\"}"
```

That returns a job id. Poll it:

```bat
curl.exe -s http://localhost:8000/api/render/jobs/<job_id>
```

and open the PNGs from `data\render_scratch\<job_id>\`, or fetch one directly:

```
http://localhost:8000/api/render/jobs/<job_id>/views/three_quarter
```

- [ ] The rendered design matches what the 3D viewport shows for that design.

## Known limitations

- **Cycles CPU only.** Your machine has no dedicated GPU, and this container
  installs no GL vendor at all, so EEVEE cannot run here. Renders are
  therefore minutes, not seconds: four views at 512x512 with 32 samples take
  about two minutes.
- **Clay render, deliberately.** Every part is the same neutral matte grey.
  This is what the vision critique needs in order to judge proportion and
  silhouette; it is not a presentation render and is not meant to look like
  the finished fountain in stone or bronze.
- **The renderer reads the GLB, not the STEP.** Blender cannot import STEP.
  The GLB is the same tessellation the browser viewport shows, so the render
  matches the viewport rather than the exact CAD surface.
- **PNG bytes are not guaranteed identical between runs.** The seed and thread
  count are pinned, which makes rounds comparable, but byte-level
  reproducibility is a promise made for STEP only (LIMITATIONS.md).
