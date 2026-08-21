# The LUXEXCHANGE package — what you send a fabricator

Phase 9A. This is the file that leaves your machine and lands on someone
else's desk.

---

## Making one

In the Assembly tab: **Build assembly**, then **Build LUXEXCHANGE package**,
then the download link.

Or from PowerShell:

```powershell
$design = (Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/geometry/assembly/build -ContentType 'application/json' -InFile .\request.json).design_id
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/geometry/assembly/$design/exports"
Invoke-WebRequest -Uri "http://localhost:8000/api/geometry/assembly/$design/luxexchange.zip" -OutFile .\luxexchange.zip
```

Note that **building the package is a POST**. Opening the download link
never builds anything — it serves what is already there, or tells you to
build it first. Clicking a link should never change your data.

---

## What is in the box

```
luxexchange_v1.json      the manifest — what this design is
provenance.json          tool versions and platform
CHECKSUMS.sha256         a hash of every file
verify_luxexchange.py    the checker (see below)
README_DWG_SKP.txt       how to get DWG and SketchUp files
assembly_manifest.json   the geometry manifest
validation/*.json        one file per validation gate
costing/bom.json         the bill of materials, when it could be computed
exports/                 the geometry files
```

### The geometry files

**CAD tier — exact geometry, cut from the real surfaces:**

| file | use |
| --- | --- |
| `assembly.step` | **Start here.** Exact solid geometry. Every CAD program opens it. |
| `assembly.brep` | The same solid in OCCT's native format, for CAD rework. |
| `assembly.stl` | Triangulated solid for 3D printing and CAM. |
| `assembly.dxf` | **2D fabrication drawing** — PLAN section, ELEVATION, HIDDEN layers. |
| `assembly.svg` | The same drawing as scalable line art, for client sheets. |

**Mesh tier — triangulated approximations, for looking at:**

`assembly.glb`, `assembly.obj`, `assembly.ply`

> For anything that will be **machined or measured**, use STEP or BREP.
> The mesh files approximate curved surfaces with flat triangles. Every mesh
> entry in the manifest records `derived_from: assembly.glb` so nobody
> mistakes one for the real thing.

---

## Checking a package — including one someone sends back to you

Extract the zip and run:

```powershell
python verify_luxexchange.py
```

It re-hashes every file and compares against what was recorded when the
package was made. It uses **only the Python standard library** — your
fabricator does not need LuxuryForm, or any install beyond Python itself.

```
LUXEXCHANGE VERIFICATION PASSED
  files checked  : 16
  content digest : 18bbfd8c402ff25d3129ee4efa4da389f47f1b3bd53b2ff1a3f169f61cd47449
```

If anything was altered, deleted or added it says which file and exits
non-zero. A checksum nobody outside this office can verify is decoration.

---

## The content digest

One number that identifies the whole package. The same design always
produces the same digest — and the same package bytes.

That is worth stating plainly: **export the same design twice, a week apart,
and you get two identical files.** So if two digests match, the designs are
the same; if they differ, something really changed.

Getting there required fixing two things that had nothing to do with
geometry: OpenCASCADE stamps a counter into STEP that increments per program
run, and ezdxf writes two random IDs and a clock into every DXF. Both are
now normalised. See ADR-035.

`provenance.json` is deliberately **excluded** from the digest — it records
tool versions and platform, and those must not change the identity of a
design.

---

## The four export statuses

| status | meaning |
| --- | --- |
| **in package** | Written and hashed. It is in the zip. |
| **failed** | We tried and it threw. The real error is recorded — this is a bug, report it. |
| **unavailable** | Needs something that is not installed. The reason names it. |
| **not possible** | No open writer exists anywhere. See the workaround. |

Nothing is ever silently left out.

### DWG and SketchUp

Both report **not possible**, and `README_DWG_SKP.txt` travels inside the
package with the workaround, so a fabricator reading it offline still knows
what to do:

- **DWG** — convert `assembly.dxf` with the free ODA File Converter.
- **SketchUp** — SketchUp Pro imports `assembly.step` directly. No
  conversion needed.

### USD, USDZ, FBX, Alembic

These report **unavailable** until the Phase 9B render worker exists. They
need Blender, which is a separate container and a separate download.

### DAE and 3MF

These report **unavailable** naming a missing Python package (`pycollada`
and `networkx`). Both are small. If you want them, add the name to
`pyproject.toml` and rebuild — but that needs a download, so it is your
call, not something done behind your back.

---

## Running the gate yourself

```powershell
docker compose exec backend python scripts/gate_phase9a_auto.py
```

Costs nothing and **needs no internet**. It builds two packages, proves they
are byte-identical, runs the shipped verifier, then flips a single bit and
proves the verifier catches it.
