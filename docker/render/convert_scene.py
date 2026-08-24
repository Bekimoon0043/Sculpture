"""Blender-side format conversion (Phase 9B.5).

    blender -b --factory-startup --python convert_scene.py -- <spec.json>

Companion to render_scene.py. That one turns a mesh into pictures; this one
turns it into the four formats the export package could not previously
produce -- USD, USDZ, FBX and Alembic -- because they need Blender and
nothing else in the stack can write them.

WHY THIS IS NOT PART OF render_scene.py
---------------------------------------
Rendering and converting share only the import step. Rendering builds a
camera rig, lights and materials that a conversion must NOT bake into the
exported file: a client opening the FBX should get the design, not the
design plus three area lights and a ground plane. Keeping them apart is what
guarantees that.

ONE BLENDER LAUNCH, ALL FORMATS
-------------------------------
Blender takes several seconds to start and import. Converting four formats as
four launches would pay that four times, so the caller sends every format it
wants in one spec and this script loops. A format that fails is recorded and
the rest still run -- the same rule write_exports() applies on the backend:
one bad exporter never costs the package.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy


def log(msg):
    print("[convert_scene] %s" % msg, flush=True)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def drop_world():
    """Remove the world so exporters do not carry Blender's grey background.

    The USD exporter bakes the world colour to an HDR in a `textures/` folder
    beside the output. That folder then travels in the export package as a
    file the fabricator did not ask for and cannot use.
    """
    scene = bpy.context.scene
    if scene.world is not None:
        world = scene.world
        scene.world = None
        try:
            bpy.data.worlds.remove(world)
        except (RuntimeError, ReferenceError):
            pass  # still referenced elsewhere; unlinking from the scene is enough


def import_mesh(path):
    suffix = path.suffix.lower()
    if suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise SystemExit("unsupported mesh format %r" % suffix)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("import of %s produced no mesh objects" % path)
    return meshes


# Each entry: (extension, callable taking the output path).
#
# Every exporter is told to write SELECTED objects only where it supports
# that, and the import leaves exactly the design selected. Without it, a
# stray empty or the glTF importer's scene root can travel into the file and
# show up as a phantom node in the client's viewer.
def export_usd(out: Path, usdz: bool = False) -> None:
    bpy.ops.wm.usd_export(
        filepath=str(out),
        selected_objects_only=True,
        export_materials=True,
        # export_textures=False is NOT sufficient on its own. The USD
        # exporter also writes the WORLD, and Blender's factory-startup world
        # is a plain grey background which it bakes to a one-pixel HDR in a
        # `textures/` folder next to the file (observed: color_121212.hdr).
        # A geometry conversion has no business carrying Blender's default
        # environment, so drop_world() removes it before we get here and the
        # sidecar is never created.
        export_textures=False,
    )


def export_fbx(out: Path) -> None:
    bpy.ops.export_scene.fbx(
        filepath=str(out),
        use_selection=True,
        # Metres. The GLB arrives in metres (glTF's unit) and FBX consumers
        # default to centimetres, which is how a 2.2 m fountain becomes a
        # 220 m one in someone else's scene.
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        object_types={"MESH"},
        use_mesh_modifiers=True,
        bake_anim=False,
    )


def export_abc(out: Path) -> None:
    bpy.ops.wm.alembic_export(
        filepath=str(out),
        selected=True,
        # A fountain is not animated; exporting one frame keeps the file
        # small and avoids a 250-frame cache of identical geometry.
        start=1,
        end=1,
        flatten=False,
    )


EXPORTERS = {
    "USD": (".usd", lambda out: export_usd(out, usdz=False)),
    "USDZ": (".usdz", lambda out: export_usd(out, usdz=True)),
    "FBX": (".fbx", export_fbx),
    "ABC": (".abc", export_abc),
}


def main():
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit("usage: blender -b --python convert_scene.py -- <spec.json>")
    spec = json.loads(Path(argv[argv.index("--") + 1]).read_text(encoding="utf-8"))

    mesh_path = Path(spec["input_mesh"])
    out_dir = Path(spec["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = [f.upper() for f in spec.get("formats", [])]

    unknown = [f for f in wanted if f not in EXPORTERS]
    if unknown:
        raise SystemExit("unknown format(s) %s; known: %s"
                         % (", ".join(unknown), ", ".join(sorted(EXPORTERS))))

    clear_scene()
    meshes = import_mesh(mesh_path)
    log("imported %d mesh object(s)" % len(meshes))
    drop_world()

    # Select exactly the design; every exporter below writes selection only.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]

    results = []
    for fmt in wanted:
        ext, fn = EXPORTERS[fmt]
        out = out_dir / ("assembly%s" % ext)
        t0 = time.time()
        try:
            fn(out)
            if not out.exists() or out.stat().st_size == 0:
                raise RuntimeError("exporter wrote no file")
            results.append({"format": fmt, "ok": True, "path": out.name,
                            "bytes": out.stat().st_size,
                            "elapsed_s": round(time.time() - t0, 3)})
            log("%s -> %s (%d bytes)" % (fmt, out.name, out.stat().st_size))
        except Exception as exc:
            # One failing exporter must not cost the others.
            if out.exists():
                try:
                    out.unlink()
                except OSError:
                    pass
            results.append({"format": fmt, "ok": False,
                            "error": "%s: %s" % (type(exc).__name__, exc),
                            "elapsed_s": round(time.time() - t0, 3)})
            log("%s FAILED: %s" % (fmt, exc))

    (out_dir / "convert.json").write_text(
        json.dumps({"results": results}, sort_keys=True), encoding="utf-8")
    log("CONVERT_SCENE_OK %d/%d" % (sum(1 for r in results if r["ok"]), len(results)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
