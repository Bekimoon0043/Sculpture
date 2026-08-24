# PHASE_9A_REPORT.md — L7 Export Package

**Auto gate: PASS, 2026-08-21.** `scripts/gate_phase9a_auto.py`, exit 0, $0,
**no network required**.
**Visual gate: pending operator** — `gate_phase9a_visual.md`.

ADRs: **ADR-035** (byte-canonicalization), **ADR-037** (export as a job).

---

## Why Phase 9 was split

The original plan bundled the export package with a Blender render worker.
That meant one failed download — on a connection CLAUDE.md flags as having
cost this project more time than any code defect — blocked the entire export
deliverable, and Phases 10 and 11 behind it.

**9A ships without downloading anything.** 9B (renders) is the only part
that touches the network, and 9A's gate does not depend on it.

---

## Two formats became ten, at zero bandwidth cost

The foundation slice reported eight formats as "not implemented in this
Phase 9 foundation slice". Probed live in the running image (ADR-009 — not
recalled):

```
build123d 0.11.1  export_step, export_stl, export_brep, ExportDXF, ExportSVG
trimesh   5.0.0   3mf, dae, glb, gltf, obj, off, ply, stl
ezdxf     1.4.4   installed
```

Under-claiming misinforms the operator about what he can send a fabricator
this afternoon. Now produced, hashed and packaged:

| tier | formats |
| --- | --- |
| **CAD** (from the B-rep, exact surfaces) | STEP, BREP, STL, DXF, SVG |
| **Mesh** (from the preview GLB, triangulated) | GLB, OBJ, PLY |

Every mesh entry records `derived_from: assembly.glb` so nobody machines
from a triangulated approximation.

### The DXF is a real drawing

Not an outline dump — a true horizontal section at mid-height plus a
hidden-line front elevation, laid out side by side on named layers:

```
ok  the DXF is a real drawing with named layers
    — {'PLAN': 2, 'ELEVATION': 21, 'HIDDEN': 23}
```

This is what a fabricator actually cuts from. It carries no dimensions or
title block (LIMITATIONS.md §13) — a draughtsman still adds annotation.

---

## The package is byte-reproducible

The foundation slice's package was **not**. Measured before the fix, one
design, three downloads:

```
download 0  bytes 27563  sha 8f7e03bd…
download 1  bytes 27564  sha 621ae78c…
download 2  bytes 27564  sha 4ee43b15…
```

Three different packages for one design, in a project whose central rule is
determinism.

Proving reproducibility surfaced **three defects that had nothing to do with
geometry** (ADR-035), one of them a live breach of Rule 5:

**STEP carried a process-global counter.** OpenCASCADE numbers
`NEXT_ASSEMBLY_USAGE_OCCURRENCE` from a counter that lives for the life of
the *process*. Every gate to date ran one build per process, so it was
always `'1'` and this went unseen for four phases. In the long-running
backend it meant **two builds of the same Design Spec produced two different
`geometry_hash` values.**

**DXF carried two random GUIDs and two wall clocks** (`$FINGERPRINTGUID`,
`$VERSIONGUID`, `$TDCREATE`, `$TDUPDATE`).

**OCCT returned section faces in a varying order** — the same set, a
different sequence — and the DXF writer emits entities in the order given.

All three fixed in `canonicalize.py` and `_stable_order`. **Metadata and
ordering only — never a coordinate, never a topology reference.**

The Phase 2 canonical STEP sha256 `e1a59fa6…`, proven cross-machine
2026-08-04, still reproduces byte-for-byte —
`scripts/gate_phase6a1_auto.py` section 3 re-run after the change and
passed. A file exported first in a fresh process already had `'1'`, so
canonicalization is a no-op on it.

Result:

```
ok  content digest is identical across two exports — 18bbfd8c402ff25d3129ee4efa4da389...
ok  the package ZIP is byte-identical — 106110 bytes
```

Rule 5 now reaches the deliverable, not just the canonical STEP.

---

## The package verifies itself, without us

`verify_luxexchange.py` ships **inside the ZIP** and imports only the Python
standard library. A fabricator with a bare Python install can check what we
sent them. A checksum only this repository can verify is decoration.

```
ok  the shipped verifier passes on an intact package
ok  it reports the same content digest
ok  one flipped bit is caught
ok  the altered file is named
ok  a deleted file is caught
```

`CHECKSUMS.sha256` covers every content file; `content_digest` is the sha256
of that file, recorded in `provenance.json` — which is itself excluded from
the checksum set, avoiding circularity and keeping the digest stable across
hosts and tool versions.

Manifest paths are **relative to the package**. An absolute host path would
make the digest depend on where the file was written, and would ship the
operator's filesystem layout to whoever receives it.

---

## Export became a job

`GET /latest/luxexchange.zip` used to **write files and insert DB rows on
every request** — three downloads produced nine export rows:

```
export rows: [('GLB', 3), ('LUXEXCHANGE', 3), ('STEP', 3)]
```

Now: `POST /{design_id}/exports` creates a `JobRow` (`job_type="export"`).
`GET` reads status and serves artifacts, never mutates. A unique index on
`(design_id, format)` with upsert makes re-export idempotent. Hashes are
computed once at export time, not on every UI poll.

This is the first real consumer of the job model Phase 13 must harden, so
Phase 13 inherits a working example instead of a retrofit.

---

## Four honest statuses

Mirroring the costing layer's four line statuses (ADR-031):

| status | example |
| --- | --- |
| `included` | STEP, BREP, STL, DXF, SVG, GLB, OBJ, PLY |
| `failed` | attempted and threw — real exception text recorded |
| `unavailable` | USD/USDZ/FBX/ABC (need 9B); DAE/3MF (need an optional pip package, named) |
| `impossible` | DWG, SKP — no open writer exists |

A missing *optional* library reports `unavailable` naming the package — not
`failed`, which would send the operator hunting a bug that is really a
one-line install.

DWG and SKP now appear in every manifest with the workaround text shipped
**inside** the package as `README_DWG_SKP.txt`, so a fabricator reading the
zip offline needs nothing from us. Previously the DWG/SKP branch was dead
code — `PRACTICAL_EXPORT_FORMATS` contained neither.

One exporter throwing never aborts the package
(`test_one_failing_exporter_does_not_cost_the_other_formats`).

---

## Gate evidence

```
[1/6] FORMATS — 8 formats produced, 531 kB total                 ok
[2/6] HONESTY — what is missing says why                          ok
[3/6] REPRODUCIBILITY — byte-identical across two exports         ok
[4/6] CONTENTS — no absolute host path leaks into the manifest    ok
[5/6] SELF-VERIFICATION — plain Python, no LuxuryForm install     ok
[6/6] TAMPER DETECTION — one flipped bit caught, deletion caught  ok

PASS — Phase 9A auto gate: all sections passed at $0, no network.
```

Full suite: **309 passed**. All other gates re-run and passing.

---

## What is NOT built

**No renders.** The Blender/Cycles worker is Phase 9B, in its own image so a
failed download cannot invalidate the expensive OCCT layer. The package says
it contains no renders rather than shipping an empty folder.

The remade `PHASE_9_RENDER_EXPORT_PLAN.md` carries the 9B design — notably
that **Workbench, not Cycles, is the critique engine**: Cycles CPU on an
i7-8550U with no GPU would make Phase 10's four-views-per-iteration loop
unusable.

Full scope limits: `LIMITATIONS.md` §13.


---

## Amendment 2026-08-24 — the Blender tier, and a regression caught the same day

Phase 9B.5 (ADR-045) wired USD, USDZ, FBX and Alembic to the render worker.
They had been reported `unavailable` since this phase closed.

**That change briefly broke this phase's central guarantee.** A full-suite run
on 2026-08-24, against a backend image built from the work in progress, failed
`gate_phase9a` section 3 and `gate_phase13a` section 3: the content digest and
the package ZIP were no longer byte-identical across two exports of the same
design. Blender embeds creation timestamps (2 bytes in USDZ, 27 in FBX, 1 in
ABC), so sealing those files into the package made the package vary.

Fixed the same day, before the gates were allowed to stay red: the four formats
are produced and downloadable but are NOT sealed into the ZIP, and the manifest
says so per format (`in_package`, `excluded_reason`, `omitted_non_reproducible`).
Excluding them from the digest alone was insufficient — the ZIP contains the
bytes — and moving their per-build hashes to `provenance.json` was insufficient
too, because provenance is digest-excluded but still a file inside the ZIP.

Section 2 of the gate now accepts either honest outcome: `unavailable` naming
the command that starts the worker, or `included` with its exclusion from the
package stated. Both gates PASS. The reproducibility guarantee is unchanged:
what is in the package is byte-identical for the same design, and what cannot
be is not in the package.
