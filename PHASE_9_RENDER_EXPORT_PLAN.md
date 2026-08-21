# PHASE_9_RENDER_EXPORT_PLAN.md — L7 Render and Export Package

Original draft 2026-08-21. **Remade 2026-08-21** after reviewing the shipped
foundation slice and probing the installed toolchain live (ADR-009: capability
claims below come from the running container, not from recall).

Phase 9 makes a final design package real: deterministic exports, verifiable
checksums, a portable manifest, and renders.

---

## Part 1 — Review of the shipped foundation slice

Working today: a LUXEXCHANGE v1 ZIP is produced, contains the manifest,
validation reports, STEP and GLB, and the Assembly tab links it. Real, tested
code. Seven design defects.

### E1 — The package is not reproducible, and nothing verifies it

`zipfile.writestr` stamps every entry with wall-clock local time, `zf.write`
uses file mtime, and `_luxexchange_manifest` injects
`datetime.now(timezone.utc)`. Downloading the same design twice yields two
different ZIPs with two different hashes.

The plan's own gate says "The package can be re-opened and its hashes
verified." No code verifies anything, no checksum file exists at a stable
path, and the manifest carries no digest of itself. This is the central
defect: a determinism-first project shipped a non-deterministic deliverable.

Reproduced in `luxuryform-backend-1` — one build at seed 7, three downloads:

```
download 0  200  bytes 27563  sha 8f7e03bdcea0edf6...
download 1  200  bytes 27564  sha 621ae78c9424bcb0...
download 2  200  bytes 27564  sha 4ee43b1531f80fe1...
```

Three different packages for one design. Even the byte length moves.

### E2 — `GET` mutates state

`GET /latest/luxexchange.zip` writes files to disk **and inserts DB rows** on
every request. A browser prefetch, a double-click, or a refresh each append a
new set of `exports` rows. `_persist_export_rows` has no uniqueness or upsert.
Same run as E1, after three downloads:

```
export rows: [('GLB', 3), ('LUXEXCHANGE', 3), ('STEP', 3)]
```

Nine rows for one design, and STEP/GLB rows are only ever created by the
*download* handler even though those artifacts exist from build time.

The plan asked for an export job table with status and logs; there is no job,
no status, no log.

### E3 — Two different manifests, one name

`_write_luxexchange_package` calls `_luxexchange_manifest(row)` once to embed
in the ZIP and again to return. The returned one lists a `LUXEXCHANGE` entry
with the package hash; the embedded one does not, and both carry different
`created_at` values. The thing persisted to `exports` is not the thing inside
the file.

### E4 — Dead branch presenting as completeness

```python
reason = ("DWG/SKP are intentionally not native exports; see LIMITATIONS.md"
          if fmt in {"DWG", "SKP"} else "not implemented ...")
```

`PRACTICAL_EXPORT_FORMATS` contains neither `DWG` nor `SKP`, so that branch
never executes. The package looks like it handles DWG honestly; it never
mentions DWG at all.

### E5 — Eight formats reported "not implemented" that the container can write today

Probed in `luxuryform-backend-1`:

```
build123d 0.11.1  → export_step, export_stl, export_brep, ExportDXF, ExportSVG
trimesh   5.0.0   → 3mf, dae, glb, gltf, obj, off, ply, stl
ezdxf     1.4.4   → installed
```

STL, OBJ, DAE, PLY, 3MF, BREP, DXF and SVG are all reachable **now, with zero
new dependencies and zero bandwidth**. Marking them "not implemented in this
Phase 9 foundation slice" understates the truth in the opposite direction from
Rule 2 — it under-claims, which still misinforms the operator about what he
can send a fabricator this afternoon.

### E6 — Re-hashing on every poll

`_available_export_rows` calls `_sha256_file` on STEP and GLB every time
`/latest/exports` is hit. That endpoint is UI-facing. Hashes belong in the
`exports` row, computed once at export time.

### E7 — The Blender risk is not addressed anywhere

The headline scope was "headless Blender/Cycles CPU render worker". None
exists. More importantly the plan is silent on the constraint CLAUDE.md flags
as having cost more time than any code defect: **~320 kB/s, frequent resets,
6 GB Docker cap, no GPU**. Blender is a large download. Putting it into the
backend image would put the expensive, hard-won OCCT/build123d layer at risk
on every rebuild.

And Cycles CPU on an i7-8550U is the wrong engine for Phase 10's critique
loop — a loop that renders four views per iteration cannot afford minutes per
view.

---

## Part 2 — Remade design

Two independent slices. **9A ships without downloading anything.** 9B is the
only part that touches the network, and 9A's gate does not depend on it.

```
9A  Export package      no new deps, no bandwidth, closes on its own
9B  Render worker       one pinned download, its own image, its own container
```

That split is the core structural change: today, one failed Blender download
blocks the entire export deliverable, and Phases 10–11 behind it.

---

## Slice 9A — Deterministic, verifiable export package

### A1 — Honest format tiers

Every format carries one of four statuses, mirroring the costing layer's
four line statuses (ADR-031):

| status | meaning |
| --- | --- |
| `included` | written, hashed, in the package |
| `failed` | attempted, threw — real exception text recorded |
| `unavailable` | needs the render container, which is not running |
| `impossible` | no open writer exists — workaround documented |

**Tier 1 — CAD-native, from the B-rep (build123d 0.11.1, installed):**

| format | writer | why it matters |
| --- | --- | --- |
| STEP | `export_step` + seed timestamp | canonical, deterministic, the contract artifact |
| BREP | `export_brep` | lossless OCCT native, for CAD rework |
| STL | `export_stl` | from the **B-rep** with declared tolerance, not re-derived from the preview mesh |
| DXF | `ExportDXF` (+ ezdxf 1.4.4) | 2D plan / elevation / section — what a fabricator actually cuts from |
| SVG | `ExportSVG` | drawing sheets and client-facing line art |

**Tier 2 — mesh-derived (trimesh 5.0.0, installed):**
GLB, OBJ, DAE, PLY, 3MF. Each carries `derived_from: assembly.glb` and the
tessellation tolerance in the manifest, so nobody mistakes a mesh for the
canonical geometry.

**Tier 3 — needs 9B:** USD, USDZ, FBX, ABC. `unavailable` with the reason
named until the render container is up.

**Never native:** DWG, SKP → `impossible`, and the LIMITATIONS.md workaround
text is **shipped inside the package** as `README_DWG_SKP.txt`, not merely
linked. A fabricator opening the ZIP offline still learns what to do. This
retires E4 by making DWG/SKP first-class entries instead of a dead branch.

Result: **ten real formats today** instead of two, at zero bandwidth cost.

### A2 — The package becomes byte-reproducible

Rule 5 currently stops at STEP. It should reach the deliverable.

- Every ZIP entry is written with a **fixed** `ZipInfo.date_time` derived from
  the seed — the same trick `kernel.step_timestamp_for` already uses for STEP.
- Entries are added in **sorted name order** at a fixed compression level.
- Wall-clock and host metadata move to `provenance.json`, which is *in* the
  package but *excluded* from the content digest.
- `content_digest` = sha256 over the sorted `(name, sha256)` list of all
  content files. Recorded in `luxexchange_v1.json`.

Same design + same seed ⇒ **byte-identical `luxexchange_v1.zip`**. That turns
E1's aspiration into a one-line $0 gate assertion.

### A3 — The package can verify itself, offline, without LuxuryForm

```
luxexchange_v1.json        manifest + content_digest
provenance.json            wall-clock, tool versions, host  (excluded from digest)
CHECKSUMS.sha256           standard format, one line per file
verify_luxexchange.py      stdlib-only verifier, ~60 lines, SHIPPED IN THE ZIP
assembly_manifest.json
design_spec.json
validation/*.json          one per gate, with gate_profile_id
costing/bom.json           from the existing costing layer (ADR-031)
renders/*.png              when 9B is available
exports/*                  the geometry files
README_DWG_SKP.txt
```

`python verify_luxexchange.py` re-hashes every file, compares against
`CHECKSUMS.sha256`, recomputes `content_digest`, and exits non-zero on any
mismatch. Standard library only, so a fabricator with a bare Python install
can check the package we sent them. This is what "hashes verified" has to mean
to be worth writing down.

Note the two additions the old plan listed but the slice omitted: the
**Design Spec** and the **cost summary**. The costing layer already exists
(`routes_costing.py`); a package without the BOM is not a deliverable.

### A4 — Export becomes a job, not a download side effect

Reuse the existing generic `JobRow` (`job_type="export"`) rather than inventing
a table — this is also the first real consumer of the job model Phase 13 has
to harden, so Phase 13 inherits a working example instead of a retrofit.

```
POST /api/geometry/assembly/{design_id}/exports    → create job, run formats
GET  /api/geometry/assembly/{design_id}/exports    → status, no side effects
GET  /api/geometry/assembly/{design_id}/luxexchange.zip
                                                   → serve built artifact
                                                     409 if no successful job
```

- `exports` gains `sha256`, `bytes`, `duration_ms`, `status`, `error` columns,
  and a **unique index on (design_id, format)** with upsert. Retires E2's
  duplicate rows.
- Hashes are computed once at export time and read from the row afterwards.
  Retires E6.
- One manifest object is built once, embedded, and persisted. Retires E3.
- A format that throws is recorded `failed` with the exception text; the job
  continues and the package still ships with what succeeded. Rule 12: one bad
  exporter must never cost the operator the whole package.
- `/latest/...` aliases are kept for the current UI, delegating to the
  `{design_id}` routes.

### A5 — Slice 9A gate

1. One design produces a LUXEXCHANGE v1 package containing manifest,
   provenance, checksums, verifier, spec, assembly manifest, all validation
   reports, BOM, and ten geometry files.
2. Exporting the same design twice yields **byte-identical** ZIPs
   (`sha256` equal).
3. `python verify_luxexchange.py` inside the extracted package exits 0; a
   deliberately corrupted byte makes it exit non-zero naming the file.
4. STEP inside the package is byte-identical to the STEP from a fresh build at
   the same seed.
5. DWG and SKP appear as `impossible` with the workaround text present in the
   ZIP.
6. Tier 3 formats appear as `unavailable` naming the render container, with
   the package still valid.
7. A forced exporter failure is recorded `failed` with real exception text and
   does not abort the package.
8. Five GETs of the exports endpoint create zero new DB rows.
9. `scripts/gate_phase9a_auto.py` at $0, non-interactive, clear exit code.

**No network access is required to pass this gate.**

---

## Slice 9B — Render worker

### B1 — Its own image, its own container

A new service `render-worker`, built from `Dockerfile.render`, producing image
`luxuryform-render`. It does **not** extend `luxuryform-backend`.

Why this is the load-bearing decision: the backend image carries the OCCT /
build123d layer that cost repeated multi-hour rebuilds on a 320 kB/s link. Any
`RUN` added above it in the same Dockerfile risks invalidating it. A separate
image means a failed or re-pulled Blender layer costs nothing already paid
for, and `docker compose up --build -d backend` stays exactly as fast as it is
today.

Blender acquisition follows the pattern already proven for the pinned Debian
libs (ADR-017/018):

- pinned version, **sha256-pinned** archive
- its own `RUN` layer with nothing else in it, so a resumed pull re-uses cache
- retrying/resuming fetch, not a bare single-shot download
- a documented Plan B donor path if the primary host is unreachable
- `docker compose --profile render` so the service is opt-in and the operator
  can run the whole platform without it

### B2 — Two render tiers, and Cycles is not the default

This is the correction with the largest practical consequence.

| tier | engine | use | budget |
| --- | --- | --- | --- |
| `critique` | Blender **Workbench** | Phase 10 vision loop, package thumbnails | seconds per view |
| `presentation` | **Cycles CPU** | client-facing final images | explicitly a long job, checkpointed |

Phase 10 renders four views per iteration and may run several iterations.
Cycles CPU on an i7-8550U with integrated graphics makes that loop unusable.
Workbench ships inside Blender, is a rasterizer, needs no sampling, and
produces exactly what a vision model needs to judge form, proportion and
silhouette. Cycles stays for the one image a client sees, where minutes are
acceptable.

`presentation` is **optional** — the 9B gate passes without ever running
Cycles. This keeps LIMITATIONS.md §3 ("a GPU is optional, never required")
true in practice rather than in principle.

### B3 — Deterministic framing

Camera position is **derived from the assembly bounding box**, not authored:
fixed FOV, fixed elevation angles, distance solved so the bbox fills a fixed
fraction of frame. Four presets — front, side, plan, perspective.

This matters more than it looks. If framing drifts between iterations, a
Phase 10 critique comparing round N to round N+1 is comparing two different
photographs, and every "improvement" the model reports is noise. Framing must
be a pure function of geometry.

Each critique render also carries a **ground grid at a known module** and the
overall height printed in the corner. A vision model cannot judge whether a
basin is too shallow without a scale reference; without one, Phase 10's
proportion critiques are guesses. Cheap to add, and it decides whether Phase
10 produces signal.

Renders are reproducible within visual tolerance, never byte-identical
(LIMITATIONS.md §2 already says this). The render manifest therefore records
engine, version, samples, resolution and camera solve inputs, so an image can
always be traced to what produced it.

### B4 — Sandbox and mounts reuse the proven pattern

The render worker copies the geo-worker shape (ADR-005 / ADR-028): non-root,
`network_mode: none`, read-only filesystem except one scratch mount, CPU and
memory limits, hard per-job timeout, atomic `result.json` handoff via
`os.replace`. Same host dir at the same container path on both sides, so
artifact paths are valid verbatim — the exact drift that ADR-028 was written
to prevent.

Blender is not AI-written code, so ADR-005 does not strictly compel this. It
is reused because the pattern is already proven here and because a render job
has no business reaching the network.

### B5 — Honest degradation

With `render-worker` absent:

- `/exports` reports renders and Tier 3 formats as `unavailable`, naming the
  container and the command to start it.
- The LUXEXCHANGE package still builds, still verifies, and says in
  `luxexchange_v1.json` that it contains no renders.
- Phase 10 refuses to start with an actionable message rather than critiquing
  nothing.

### B6 — Slice 9B gate

1. `docker compose --profile render up -d` starts the worker without rebuilding
   the backend image.
2. A queued critique job returns four PNGs with geometry-derived framing.
3. Re-running the same design at the same seed produces framing metadata that
   is **byte-identical** even though the pixels are not.
4. A presentation Cycles render completes as a checkpointed long job, or is
   skipped with a recorded reason — either outcome passes.
5. Thumbnails and Tier 3 formats appear `included` in the package once the
   worker is up, without re-running the geometry build.
6. Killing the worker mid-job leaves the job resumable and the package valid.
7. `scripts/gate_phase9b_auto.py` at $0, non-interactive.
8. `gate_phase9_visual.md`: the operator opens the four renders and the ZIP
   and confirms by eye.

---

## Part 3 — Build order and dependencies

```
9A.1  format registry + four statuses + Tier 1/2 writers      (no deps)
9A.2  reproducible ZIP + content_digest + CHECKSUMS + verifier (no deps)
9A.3  export job model, unique index, stored hashes, POST/GET  (no deps)
9A.4  spec + BOM into the package, UI export status            (no deps)
      ── 9A GATE — closes without touching the network ──
9B.1  Dockerfile.render, pinned Blender, compose profile       (one download)
9B.2  worker loop reusing the geo-worker handoff pattern
9B.3  deterministic framing + scale reference, Workbench critique tier
9B.4  Cycles presentation tier as a checkpointed long job
9B.5  Tier 3 exports via Blender, thumbnails into the package
      ── 9B GATE ──
```

Phase 9 depends on Phase 8's corrected report status vocabulary — the package
embeds validation reports, and embedding a report that calls a warning a pass
propagates the lie into the client deliverable. **Do Phase 8 steps C1/C2/C7
before 9A.4.**

Phase 10 depends only on 9B.3. Phase 11 keys DesignDNA dedupe on 9A.2's
`content_digest`. Phase 13 inherits 9A.3's job model rather than retrofitting
one.

## Part 4 — Decisions needing operator approval before build

1. **Separate render image** (B1) — costs one extra Docker image on a 6 GB
   cap; buys immunity for the backend image. Recommended.
2. **Workbench as the critique engine** (B2) — trades photorealism for a
   usable Phase 10 loop. Recommended; Cycles remains for client images.
3. **Blender version and download host** — must be fetched from live docs and
   the fetch date recorded (Rule 9 / ADR-009). Not chosen in this plan on
   purpose.
4. **Ten formats in every package, or an operator-selected subset** — ten
   costs disk and export time per design; a subset costs a decision each time.
   Recommended: all Tier 1/2 by default, configurable.
