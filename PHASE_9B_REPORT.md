# PHASE_9B_REPORT.md — Blender Render Worker

**Status:** BUILT, auto gate PASS 2026-08-24. Awaiting the operator's visual
gate (`gate_phase9b_visual.md`).

**Date:** 2026-08-24

**ADR:** ADR-043 (and the correction it records to ADR-042).

Phase 9B was the last piece of the platform that needed a download, and it was
the blocker under Phase 5 (vision critique) and Phase 10 (vision-driven
revision). It is now built and gated.

---

## What was already on disk, and what was actually wrong

Blender 4.5.12 LTS had been fetched (377,902,364 bytes, sha256
`95e3a2df…0120a25`, matching the pin in `docker/render/Dockerfile`) and
extracted. The container had never built. The failure was not the download:

- `debs.txt` listed 57 packages, several with invented pool paths — mesa
  packages under `libg/libglvnd/` instead of `m/mesa/`, a `t/tfonts-ubuntu/`
  directory that does not exist in the Debian pool, and epochs written into
  filenames (`libllvm19_1%3a19.1.7-3+b1`) which pool files never carry.
- `sums.txt` had never been produced, so the build could not verify anything.
- The fetch had died on the fourth package and left three orphaned `.deb`
  files in two scratch directories.

Both of those are ADR-009 failures in a place the ADR does not literally name:
the rule is about third-party endpoints and versions, and a Debian pool path is
one.

## How the deb set was actually determined

1. Extract Blender in a bare `python:3.11-slim-trixie` and run `ldd` on the
   binary. Nine sonames missing: `libGL.so.1`, `libICE.so.6`, `libSM.so.6`,
   `libX11.so.6`, `libXext.so.6`, `libXfixes.so.3`, `libXi.so.6`,
   `libXrender.so.1`, `libxkbcommon.so.0`.
2. Resolve those nine to packages and let apt compute the dependency closure
   against the same dated snapshot the backend pins, taking the real pool
   paths from `apt-get install --print-uris`.
3. Drop the mesa branch. apt's closure pulls `libgl1-mesa-dri` →
   `mesa-libgallium` → `libllvm19` → `libz3-4`, roughly 45 MB, for a GLX
   *vendor* only dlopened when a real GLX context is created. Headless Cycles
   never creates one. Same finding and same `dpkg -i --force-depends` approach
   as the backend at ADR-017.
4. Install the remaining **17**, confirm `ldd` reports nothing missing, and
   render an actual PNG.

Everything else Blender needs it ships itself in `/opt/blender/lib` (libtbb,
OpenEXR, OpenVDB, MaterialX, OpenImageDenoise), found via the binary's RUNPATH.

## What was built

| File | Role |
|---|---|
| `docker/render/debs.txt` | 17 pinned pool paths, with the derivation recorded |
| `docker/render/sums.txt` | sha256 for each, from the bytes actually fetched |
| `docker/render/extract_blender.py` | stdlib-lzma extraction (see below) |
| `docker/render/render_scene.py` | Blender-side: import, clay, lighting, 4 cameras, render |
| `docker/render/render_worker.py` | scratch watcher, drives Blender as a subprocess |
| `docker/render/.dockerignore` | keeps the 1.2 GB extracted tree out of build context |
| `docker-compose.yml` | `render-worker` service behind a `render` profile |
| `scripts/gate_phase9b_auto.py` | the auto gate |
| `gate_phase9b_visual.md` | the operator's visual gate |

Three problems worth naming, because each would have produced a plausible
wrong answer rather than an error:

**The base image has `tar` but no `xz`.** GNU tar shells out to the `xz`
binary for `.tar.xz`. Rather than carry an eighteenth deb solely for build
time, extraction goes through `tarfile.open(..., "r:xz")`, which uses stdlib
lzma already present in the image. It also preserves the symlinked sonames
Blender's bundled libraries need — which a host-side extraction on Windows had
silently dropped.

**Blender cannot import STEP.** ADR-042 specified rendering the STEP artifact.
There is no STEP importer in Blender and no OCCT in this image on purpose. The
worker renders the GLB the viewport already uses, so `RenderJob.input_step`
became `input_mesh` and the API renders `design.glb_path`.

**The two containers see the shared directory at different paths.** `/scratch`
on the backend is already the geo-worker's mount, so the render scratch is
`/render_scratch` on the backend and `/scratch` on the worker. The ADR-028
trick of passing absolute paths verbatim is therefore unavailable, and every
filename in the protocol is a basename that each side resolves against its own
view of the job directory.

## Gate evidence

```
$ docker compose exec backend python scripts/gate_phase9b_auto.py
==============================================================
Phase 9B auto gate - Blender render worker (offline, $0)
==============================================================
[0] render scratch: /render_scratch
[1] PASS built test mesh (48808 bytes, 3 parts)
[2] queued job 3cc794816a3d4ca5; waiting for the render worker ...
[2] PASS render worker returned 4 views in 28.8s
[2b] PASS geometry arrived upright, Z up (size [2.2, 2.199, 1.64] m)
    front          stddev= 46.56  mean=  87.2  subject= 29.1%  54547 bytes
    side           stddev= 47.68  mean=  87.4  subject= 29.1%  54572 bytes
    three_quarter  stddev= 58.85  mean=  92.4  subject= 61.7%  61013 bytes
    top            stddev= 31.26  mean= 163.2  subject= 63.2%  60958 bytes
[3] PASS all four views carry real tonal detail
[4] PASS all six view pairs are distinct
==============================================================
Phase 9B auto gate PASS
==============================================================
```

The gate checks more than "four files exist", because four plausible-looking
frames of nothing is the likeliest way this breaks. It asserts real tonal
variation per view, a plausible subject share of the frame, six distinct view
pairs, and the bounding box Blender actually received.

**That bounding-box check caught two real faults on the day it was written.**
Built with trimesh's own Scene export, the test model arrived rotated onto its
side. Rebuilt with metre-valued numbers, it arrived 1000× too small —
build123d works in millimetres and `export_gltf` converts to metres. Both
rendered as perfectly competent pictures, because the camera rig frames
whatever it is given. Neither would have been caught by eye. The gate now
builds its test solid through the production exporter, so it exercises the
same path a real design takes.

An end-to-end run against a real design GLB from `data/designs/` also
succeeded: four views at 512²/32 samples in 122 s, bounding box
2.2 × 2.199 × 0.74 m.

## Full suite after the change

All twelve auto gates pass against a clean `docker compose up --build -d`
backend image:

```
PASS  costing   PASS  phase2   PASS  phase3    PASS  phase4
PASS  phase6a1  PASS  phase8   PASS  phase8b   PASS  phase9a
PASS  phase11   PASS  phase13a PASS  phase5    PASS  phase9b
PASS=12 FAIL=0
```

`pytest tests/` — 361 passed.

## Cost and performance

$0. The worker runs with `network_mode: none` and there is no API call
anywhere in this phase.

Measured on the operator's i7-8550U with 2 threads:

| Job | Time |
|---|---|
| 4 views, 256², 16 samples (the gate) | ~29 s |
| 4 views, 512², 32 samples | ~122 s |

Per-round render cost for the critique loop is therefore minutes, not seconds,
which is what `max_vision_iterations` has to be sized against.

## Honest limitations

- **Cycles CPU only.** No dedicated GPU on the operator's machine and no GL
  vendor in the container, so EEVEE cannot run. This is a deliberate choice,
  recorded in `debs.txt` and ADR-043, not an oversight.
- **PNG bytes are not byte-reproducible.** Seed and thread count are pinned so
  rounds are comparable, but the determinism guarantee remains STEP-only.
- **The render worker renders; it does not convert.** USD, USDZ, FBX and
  Alembic still report `unavailable` in the export package. Blender could now
  produce them, but that path is not wired. It is a wiring job, not a missing
  dependency — recorded in LIMITATIONS.md rather than quietly implied.
- **The Blender tarball is not in the repo.** It is a 360 MB host-side build
  input, gitignored along with the extracted tree. `debs.txt` and `sums.txt`
  are committed, so the image rebuilds from the repo plus one resumable
  download.

## What this unblocks

- **Phase 5** — the render half of the vision critique loop. Its auto gate
  passes; what remains is a live multi-round run, which spends API money and
  is the operator's visual gate.
- **Phase 10** — vision critique of renders, which was blocked on 9B outright.

## For the operator

```bat
docker compose --profile render up -d render-worker
docker compose exec backend python scripts\gate_phase9b_auto.py
```

Then work through `gate_phase9b_visual.md`.
