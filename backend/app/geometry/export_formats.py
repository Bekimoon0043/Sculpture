"""Practical export formats — Phase 9A.

Every format here is written by a library ALREADY installed in the backend
image. Nothing in this module downloads anything, and nothing in it is
aspirational: a format is either produced and hashed, or it carries a status
saying exactly why it was not.

Four statuses, mirroring the costing layer's four line statuses (ADR-031):

    included     written, hashed, in the package
    failed       attempted and threw — the real exception text is recorded
    unavailable  needs the render worker (Phase 9B), which is not running
    impossible   no open writer exists anywhere — workaround documented

Capability was verified against the running image, not recalled (ADR-009):

    build123d 0.11.1  export_step, export_stl, export_brep, ExportDXF, ExportSVG
    trimesh   5.0.0   3mf, dae, glb, gltf, obj, off, ply, stl
    ezdxf     1.4.4

Two tiers, and the difference matters to a fabricator:

  * CAD tier — written from the B-rep. Exact curved surfaces, no
    tessellation. This is what a machinist opens.
  * MESH tier — written from the preview GLB. Triangles. Fine for
    visualisation, wrong for machining, and every mesh-tier entry records
    `derived_from` so nobody mistakes one for canonical geometry.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import time
from dataclasses import dataclass, field

from app.geometry.canonicalize import canonicalize_dxf_file
from app.geometry.kernel import step_timestamp_for
from pathlib import Path
from typing import Any, Callable, Literal

log = logging.getLogger("luxuryform.export")

ExportStatus = Literal["included", "failed", "unavailable", "impossible"]

#: Tessellation tolerances for the B-rep-derived STL. Tighter than the
#: preview GLB (1.0 mm, exporters.py) because an STL may be printed or
#: CNC-toolpathed, not just looked at.
STL_LINEAR_TOLERANCE_MM = 0.1
STL_ANGULAR_TOLERANCE_RAD = 0.1


@dataclass
class ExportResult:
    format: str
    status: ExportStatus
    tier: str
    purpose: str
    path: Path | None = None
    sha256: str | None = None
    bytes: int | None = None
    duration_ms: float | None = None
    error: str | None = None
    reason: str | None = None
    derived_from: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)

    def to_manifest_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "format": self.format,
            "status": self.status,
            "tier": self.tier,
            "purpose": self.purpose,
            "path": str(self.path) if self.path else None,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }
        if self.derived_from:
            entry["derived_from"] = self.derived_from
        if self.reason:
            entry["reason"] = self.reason
        if self.error:
            entry["error"] = self.error
        if self.notes:
            entry["notes"] = self.notes
        return entry


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# CAD tier — written from the B-rep
# ---------------------------------------------------------------------------

def _write_brep(solid, out: Path, ctx: dict[str, Any]) -> None:
    from build123d import export_brep

    export_brep(solid, str(out))


def _write_stl(solid, out: Path, ctx: dict[str, Any]) -> None:
    from build123d import export_stl

    export_stl(
        solid, str(out),
        tolerance=STL_LINEAR_TOLERANCE_MM,
        angular_tolerance=STL_ANGULAR_TOLERANCE_RAD,
        ascii_format=False,
    )


#: Gap between the two views on the drawing sheet, as a fraction of the
#: model's plan width. Purely a layout choice.
_SHEET_GAP_FRACTION = 0.25


def _stable_order(shapes: list) -> list:
    """Sort drawing shapes into a deterministic order.

    OCCT returns section results in an order that varies between runs — same
    set of faces, different sequence (measured 2026-08-21: a 3-element
    assembly's PLAN section came back in a different order on every call).
    The DXF writer emits entities in the order given, so unsorted input makes
    the drawing bytes unreproducible even though the drawing is identical.

    Sorting on the bounding box plus area is stable, geometry-derived, and
    independent of how OCCT happened to walk the topology.
    """
    def key(shape):
        bb = shape.bounding_box()
        return (
            round(float(bb.min.X), 6), round(float(bb.min.Y), 6),
            round(float(bb.min.Z), 6), round(float(bb.max.X), 6),
            round(float(bb.max.Y), 6), round(float(bb.max.Z), 6),
            round(float(getattr(shape, "area", 0.0) or 0.0), 6),
            round(float(getattr(shape, "length", 0.0) or 0.0), 6),
        )

    return sorted(shapes, key=key)


def _drawing_shapes(solid, ctx: dict[str, Any]) -> dict[str, list]:
    """Build the 2D content of a fabrication drawing from the B-rep.

    Three layers a fabricator actually uses:
      PLAN      — a true horizontal section at mid-height, so wall
                  thicknesses and bores read as closed profiles.
      ELEVATION — hidden-line front view (visible edges).
      HIDDEN    — the occluded edges of the same view, on its own layer so it
                  can be dashed or switched off.

    Both views are brought into the XY plane and laid out SIDE BY SIDE, the
    way a real drawing sheet reads. DXF and SVG are 2D formats: geometry left
    at its modelled height is not a drawing, it is a warning per entity.
    """
    from build123d import Plane, Pos

    bbox = solid.bounding_box()
    mid_z = (float(bbox.min.Z) + float(bbox.max.Z)) / 2.0
    plan_width = float(bbox.max.X) - float(bbox.min.X)
    layers: dict[str, list] = {"PLAN": [], "ELEVATION": [], "HIDDEN": []}

    # Plan: a real section, then dropped from mid-height onto the sheet.
    section = solid.intersect(Plane.XY.offset(mid_z))
    if section is not None:
        drop = Pos(0, 0, -mid_z)
        layers["PLAN"] = _stable_order([drop * shape for shape in section])

    # Elevation: build123d returns viewport projections already in XY.
    # Looking from -Y gives the front view. Only the direction matters, but
    # the eye must sit outside the solid.
    depth = max(float(bbox.max.Y) - float(bbox.min.Y), 1.0) * 10.0
    visible, hidden = solid.project_to_viewport(
        (0, -depth, mid_z), viewport_up=(0, 0, 1)
    )
    shift = Pos(plan_width * (1.0 + _SHEET_GAP_FRACTION), 0, 0)
    layers["ELEVATION"] = _stable_order([shift * edge for edge in visible])
    layers["HIDDEN"] = _stable_order([shift * edge for edge in hidden])
    return layers


def _write_dxf(solid, out: Path, ctx: dict[str, Any]) -> None:
    from build123d import ExportDXF, Unit

    layers = _drawing_shapes(solid, ctx)
    exporter = ExportDXF(unit=Unit.MM)
    for name, shapes in layers.items():
        if not shapes:
            continue
        exporter.add_layer(name)
        for shape in shapes:
            exporter.add_shape(shape, layer=name)
    exporter.write(str(out))
    # ezdxf stamps two random GUIDs and a wall clock into every save. Neither
    # is drawing content, and both would make the package unreproducible.
    canonicalize_dxf_file(out, int(ctx.get("seed", 0)),
                          step_timestamp_for(int(ctx.get("seed", 0))))
    ctx["dxf_layers"] = {k: len(v) for k, v in layers.items() if v}


def _write_svg(solid, out: Path, ctx: dict[str, Any]) -> None:
    from build123d import ExportSVG, Unit

    layers = _drawing_shapes(solid, ctx)
    exporter = ExportSVG(unit=Unit.MM)
    for name, shapes in layers.items():
        if not shapes:
            continue
        exporter.add_layer(name)
        for shape in shapes:
            exporter.add_shape(shape, layer=name)
    exporter.write(str(out))


# ---------------------------------------------------------------------------
# MESH tier — written from the preview GLB
# ---------------------------------------------------------------------------

def _load_mesh(glb_path: Path):
    """Load the preview GLB as ONE concatenated trimesh mesh."""
    import trimesh

    loaded = trimesh.load(str(glb_path), force="mesh")
    if hasattr(loaded, "geometry") and not hasattr(loaded, "faces"):
        loaded = trimesh.util.concatenate(list(loaded.geometry.values()))
    return loaded


def _mesh_writer(file_type: str) -> Callable[[Any, Path, dict[str, Any]], None]:
    def _write(solid, out: Path, ctx: dict[str, Any]) -> None:
        glb_path = ctx.get("glb_path")
        if glb_path is None or not Path(glb_path).exists():
            raise FileNotFoundError(
                "the preview GLB is required to derive mesh-tier formats"
            )
        mesh = _load_mesh(Path(glb_path))
        data = mesh.export(file_type=file_type)
        if isinstance(data, str):
            data = data.encode("utf-8")
        out.write_bytes(data)

    return _write


class ExportUnavailable(Exception):
    """The format cannot be produced right now, and that is not a defect.

    Distinct from a failure: a failure means the exporter was asked to do its
    job and could not. This means a precondition the OPERATOR controls is not
    met -- here, the optional render worker is not running. write_exports
    turns it into status `unavailable` carrying this message as the reason,
    which is the difference between "something is broken" and "start the
    render worker".
    """


#: MEASURED 2026-08-24: two conversions of the same GLB differ by 2 bytes
#: (USDZ), 27 bytes (FBX) and 1 byte (ABC) -- embedded creation timestamps in
#: the zip directory, the FBX header and Alembic's metadata. USD happened to
#: match, but it comes off the same toolchain and a future Blender could
#: start stamping it too, so the whole tier is marked non-deterministic
#: rather than relying on one lucky format.
#:
#: Byte-patching those fields was considered and rejected: the offsets are
#: undocumented and version-specific, so it would work until a Blender
#: upgrade moved them and then silently produce corrupt files.
#:
#: Shown when the four Blender-only formats cannot be produced. It names the
#: exact command, because "requires the render worker" without it sends the
#: operator reading documentation to find one line.
_RENDER_WORKER_REASON = (
    "requires the Phase 9B render worker (Blender); start it with "
    "docker compose --profile render up -d render-worker"
)


def _blender_writer(fmt: str) -> Callable[[Any, Path, dict[str, Any]], None]:
    """Writer for a format only Blender can produce (USD/USDZ/FBX/ABC).

    ONE BLENDER LAUNCH FOR ALL FOUR
    -------------------------------
    Blender costs several seconds to start and import. Four formats as four
    launches would pay that four times over, on a laptop where the export
    package is already the slowest thing the operator waits for. So the first
    of these writers to run converts EVERY Blender-tier format that this
    export actually asked for, caches the results in the shared ctx, and the
    other three then just collect their file.

    `ctx["blender_formats"]` is the set the caller wants and
    `ctx["blender_cache"]` is the shared mutable dict holding the outcome;
    `write_exports` fills both in. If they are absent this falls back to
    converting just `fmt`, which is correct but slower.
    """

    def _write(solid, out: Path, ctx: dict[str, Any]) -> None:
        from app.render.convert import ConversionUnavailable, convert_via_worker

        glb_path = ctx.get("glb_path")
        if glb_path is None or not Path(glb_path).exists():
            raise FileNotFoundError(
                "the preview GLB is required to derive Blender-tier formats"
            )

        cache = ctx.get("blender_cache")
        if cache is None:          # called outside write_exports
            cache = {}

        # The worker was already found to be unreachable by an earlier writer
        # in this same package. Fail immediately rather than waiting out the
        # pickup timeout once per format.
        if "unavailable" in cache:
            raise ExportUnavailable(cache["unavailable"])

        if "produced" not in cache:
            batch = sorted(ctx.get("blender_formats") or {fmt})
            try:
                cache["produced"] = convert_via_worker(Path(glb_path), batch)
            except ConversionUnavailable as exc:
                cache["unavailable"] = str(exc)
                # Not a failure: the render worker being off is a choice the
                # operator made, and reporting it as a failure would send them
                # hunting a bug that is really one command.
                raise ExportUnavailable(str(exc)) from exc

        produced = cache["produced"].get(fmt)
        if produced is None:
            raise RuntimeError(
                f"the render worker did not produce {fmt}; see "
                "blender_convert.log in the conversion job directory"
            )
        shutil.copyfile(produced, out)

    return _write


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: What a browser should be told a file is. Every one is served as an
#: attachment, so this is about the file the operator ends up with, not
#: about rendering anything in the page.
MEDIA_TYPES: dict[str, str] = {
    ".step": "application/step",
    ".brep": "application/octet-stream",
    ".stl": "model/stl",
    ".dxf": "image/vnd.dxf",
    ".svg": "image/svg+xml",
    ".glb": "model/gltf-binary",
    ".obj": "model/obj",
    ".ply": "application/octet-stream",
    ".dae": "model/vnd.collada+xml",
    ".3mf": "model/3mf",
}


@dataclass(frozen=True)
class FormatSpec:
    format: str
    extension: str
    tier: str
    purpose: str
    writer: Callable[[Any, Path, dict[str, Any]], None] | None = None
    status_without_writer: ExportStatus = "unavailable"
    reason: str | None = None
    derived_from: str | None = None
    #: False when two exports of the SAME design do not produce identical
    #: bytes. Measured, not assumed -- see the Blender-tier entries below.
    #: The LUXEXCHANGE packager reads this: a non-reproducible file is
    #: produced and offered for download, but is NOT sealed into the package,
    #: because the package's whole promise is that the same design yields the
    #: same ZIP (Rule 5, ADR-035).
    deterministic: bool = True

    @property
    def media_type(self) -> str:
        return MEDIA_TYPES.get(self.extension, "application/octet-stream")

    @property
    def filename(self) -> str:
        return f"assembly{self.extension}"


#: Ordered so the package lists CAD first — that is what a fabricator needs.
FORMAT_REGISTRY: tuple[FormatSpec, ...] = (
    FormatSpec(
        "STEP", ".step", "cad",
        "canonical deterministic CAD geometry — the contract artifact",
    ),
    FormatSpec(
        "BREP", ".brep", "cad",
        "lossless OCCT native solid, for CAD rework without a translation step",
        writer=_write_brep,
    ),
    FormatSpec(
        "STL", ".stl", "cad",
        "watertight triangulation from the B-rep, for 3D print and CAM",
        writer=_write_stl,
    ),
    FormatSpec(
        "DXF", ".dxf", "cad",
        "2D fabrication drawing — plan section plus hidden-line elevation",
        writer=_write_dxf,
    ),
    FormatSpec(
        "SVG", ".svg", "cad",
        "the same drawing as scalable line art, for client sheets",
        writer=_write_svg,
    ),
    FormatSpec(
        "GLB", ".glb", "mesh",
        "viewport and validation preview mesh",
    ),
    FormatSpec(
        "OBJ", ".obj", "mesh",
        "universally readable mesh for visualisation and reference",
        writer=_mesh_writer("obj"), derived_from="assembly.glb",
    ),
    FormatSpec(
        "PLY", ".ply", "mesh",
        "compact mesh for scanning and inspection tools",
        writer=_mesh_writer("ply"), derived_from="assembly.glb",
    ),
    FormatSpec(
        "DAE", ".dae", "mesh",
        "COLLADA mesh for SketchUp and older visualisation pipelines",
        writer=_mesh_writer("dae"), derived_from="assembly.glb",
    ),
    FormatSpec(
        "3MF", ".3mf", "mesh",
        "modern 3D print package",
        writer=_mesh_writer("3mf"), derived_from="assembly.glb",
    ),
    FormatSpec(
        "USD", ".usd", "render",
        "USD scene for downstream visualisation",
        writer=_blender_writer("USD"), derived_from="assembly.glb",
        reason=_RENDER_WORKER_REASON, deterministic=False,
    ),
    FormatSpec(
        "USDZ", ".usdz", "render",
        "AR-ready USD package for client presentation",
        writer=_blender_writer("USDZ"), derived_from="assembly.glb",
        reason=_RENDER_WORKER_REASON, deterministic=False,
    ),
    FormatSpec(
        "FBX", ".fbx", "render",
        "FBX for animation and visualisation pipelines",
        writer=_blender_writer("FBX"), derived_from="assembly.glb",
        reason=_RENDER_WORKER_REASON, deterministic=False,
    ),
    FormatSpec(
        "ABC", ".abc", "render",
        "Alembic cache for animation pipelines",
        writer=_blender_writer("ABC"), derived_from="assembly.glb",
        reason=_RENDER_WORKER_REASON, deterministic=False,
    ),
    FormatSpec(
        "DWG", ".dwg", "none",
        "Autodesk's closed CAD format",
        status_without_writer="impossible",
        reason="DWG is closed; no open writer exists. LuxuryForm writes DXF, "
               "which every CAD program opens. See README_DWG_SKP.txt in this "
               "package for the free ODA File Converter workflow.",
    ),
    FormatSpec(
        "SKP", ".skp", "none",
        "SketchUp native format",
        status_without_writer="impossible",
        reason="no working open-source .skp writer exists anywhere. SketchUp Pro "
               "imports the STEP, DXF and OBJ in this package directly. See "
               "README_DWG_SKP.txt.",
    ),
)

FORMATS_BY_NAME: dict[str, FormatSpec] = {f.format: f for f in FORMAT_REGISTRY}

#: Shipped inside every package so a fabricator reading it offline still
#: learns what to do, instead of finding a link to a file they do not have.
DWG_SKP_README = """DWG and SketchUp files — how to get them from this package
==========================================================

LuxuryForm does not write .dwg or .skp, and says so rather than shipping a
file that will not open properly. Both are covered by files that ARE in this
package.

DWG (one-time setup, about 10 minutes)
--------------------------------------
1. Download the free ODA File Converter:
   https://www.opendesign.com/guestfiles/oda_file_converter
   Install it with the default options.
2. Open ODA File Converter.
3. Input folder:  the "exports" folder of this package.
4. Choose the file  exports/assembly.dxf
5. Set the output DWG version to whatever your fabricator asked for.
6. Press Convert, and send the resulting .dwg.

Why: DWG is Autodesk's closed format. DXF is Autodesk's documented
interchange format for the same data, and every CAD program opens it.

SketchUp
--------
No conversion needed. In SketchUp Pro:
    File -> Import -> choose  exports/assembly.step
                       (or  assembly.dxf,  or  assembly.obj)

Use STEP if you want exact solid geometry. Use DXF if you want the 2D
drawing. Use OBJ if you only need the shape for a visual.

What is in exports/
-------------------
  assembly.step   exact solid geometry (the canonical file — start here)
  assembly.brep   the same solid in OCCT's native format
  assembly.stl    triangulated solid, for 3D printing and CAM
  assembly.dxf    2D drawing: PLAN section, ELEVATION, HIDDEN layers
  assembly.svg    the same drawing as scalable line art
  assembly.glb    preview mesh for viewers
  assembly.obj    mesh for visualisation
  assembly.ply    mesh for inspection tools
  assembly.dae    COLLADA mesh
  assembly.3mf    3D print package

The mesh files are triangulated approximations of the real surfaces. For
anything that will be machined or measured, use STEP or BREP.
"""


def write_exports(
    solid,
    out_dir: Path,
    *,
    step_path: Path | None = None,
    glb_path: Path | None = None,
    formats: list[str] | None = None,
    render_worker_available: bool = False,
    seed: int = 0,
) -> list[ExportResult]:
    """Write every requested format. One failure never aborts the rest.

    STEP and GLB are not re-written: they were produced at build time and
    STEP's bytes are the determinism contract (`kernel.step_timestamp_for`).
    Re-exporting STEP here would risk a different timestamp and break Rule 5.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(formats) if formats else {f.format for f in FORMAT_REGISTRY}
    # The Blender-tier writers convert every requested format in ONE worker
    # round trip; this tells the first one to run what the whole batch is.
    blender_wanted = {f.format for f in FORMAT_REGISTRY
                      if f.tier == "render" and f.format in wanted
                      and f.writer is not None}
    ctx: dict[str, Any] = {"glb_path": glb_path, "step_path": step_path,
                           "seed": seed, "blender_formats": blender_wanted,
                           # A MUTABLE dict, shared deliberately. Each writer
                           # gets a shallow copy of ctx, so this same object
                           # reaches all four Blender writers and the first
                           # one's result (or its failure) is seen by the
                           # rest. Without it they would each launch Blender,
                           # or each wait out the worker-missing timeout.
                           "blender_cache": {}}
    prebuilt = {"STEP": step_path, "GLB": glb_path}
    results: list[ExportResult] = []

    for spec in FORMAT_REGISTRY:
        if spec.format not in wanted:
            continue

        # Already produced at build time — adopt, never re-write.
        if spec.format in prebuilt:
            source = prebuilt[spec.format]
            if source and Path(source).exists():
                path = Path(source)
                results.append(ExportResult(
                    format=spec.format, status="included", tier=spec.tier,
                    purpose=spec.purpose, path=path, sha256=sha256_file(path),
                    bytes=path.stat().st_size, duration_ms=0.0,
                    derived_from=spec.derived_from,
                ))
            else:
                results.append(ExportResult(
                    format=spec.format, status="failed", tier=spec.tier,
                    purpose=spec.purpose,
                    error=f"{spec.format} was not produced by the build step",
                ))
            continue

        if spec.writer is None:
            status = spec.status_without_writer
            if spec.tier == "render" and render_worker_available:
                status = "failed"
                reason = None
                error = (
                    "the render worker is running but this format is not wired "
                    "to it yet (Phase 9B.5)"
                )
            else:
                reason, error = spec.reason, None
            results.append(ExportResult(
                format=spec.format, status=status, tier=spec.tier,
                purpose=spec.purpose, reason=reason, error=error,
            ))
            continue

        out = out_dir / f"assembly{spec.extension}"
        t0 = time.perf_counter()
        notes: dict[str, Any] = {}
        try:
            local_ctx = dict(ctx)
            spec.writer(solid, out, local_ctx)
            if not out.exists() or out.stat().st_size == 0:
                raise RuntimeError("writer produced no output")
            if "dxf_layers" in local_ctx:
                notes["layers"] = local_ctx["dxf_layers"]
            results.append(ExportResult(
                format=spec.format, status="included", tier=spec.tier,
                purpose=spec.purpose, path=out, sha256=sha256_file(out),
                bytes=out.stat().st_size,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                derived_from=spec.derived_from, notes=notes,
            ))
        except ExportUnavailable as exc:
            # A precondition the operator controls is not met. Report it as
            # unavailable with the reason, exactly as if there were no writer.
            log.info("export %s unavailable: %s", spec.format, exc)
            if out.exists():
                try:
                    out.unlink()
                except OSError:
                    pass
            results.append(ExportResult(
                format=spec.format, status="unavailable", tier=spec.tier,
                purpose=spec.purpose,
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                derived_from=spec.derived_from, reason=str(exc),
            ))
            continue
        except Exception as exc:  # one bad exporter must not cost the package
            log.warning("export %s failed: %s", spec.format, exc)
            if out.exists():
                try:
                    out.unlink()
                except OSError:
                    pass
            # A missing OPTIONAL library is not a failure of our code, and
            # calling it one would send the operator hunting a bug that is
            # really a one-line install. Report it as unavailable and name
            # the package.
            missing = _missing_dependency(exc)
            if missing:
                results.append(ExportResult(
                    format=spec.format, status="unavailable", tier=spec.tier,
                    purpose=spec.purpose,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                    derived_from=spec.derived_from,
                    reason=(
                        f"needs the optional Python package '{missing}', which is "
                        f"not in the backend image. To add it, put '{missing}' in "
                        f"pyproject.toml and rebuild: docker compose up --build -d"
                    ),
                ))
            else:
                results.append(ExportResult(
                    format=spec.format, status="failed", tier=spec.tier,
                    purpose=spec.purpose,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                    error=f"{type(exc).__name__}: {exc}",
                ))
    return results


def _missing_dependency(exc: BaseException) -> str | None:
    """Name the missing optional package, or None if this was a real failure.

    Three shapes seen from trimesh 5.0.0 in this image:
      ModuleNotFoundError with .name set
      ModuleNotFoundError raised by hand, .name None, message "No module named 'x'"
      ImportError("missing `pip install pycollada`")
    """
    if not isinstance(exc, ImportError):
        return None
    if exc.name:
        return exc.name
    text = str(exc)
    marker = "pip install "
    if marker in text:
        return text.split(marker, 1)[1].strip().strip("`'\"").split()[0]
    match = re.search(r"No module named ['\"]([\w.]+)['\"]", text)
    if match:
        return match.group(1).split(".")[0]
    return None
