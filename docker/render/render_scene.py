"""Blender-side scene builder and renderer (Phase 9B).

Runs INSIDE the render-worker container, under Blender's bundled Python:

    blender -b --factory-startup --python render_scene.py -- <spec.json>

It is deliberately a separate file from render_worker.py: the worker runs
under the container's system CPython and must never import bpy, while this
file only ever runs under Blender and may import nothing else.

INPUT MESH FORMAT
-----------------
Blender has no STEP importer, and there is no OCCT in this image (that is the
backend's stack, kept out of here on purpose -- see the Dockerfile header).
So the backend hands over the tessellated mesh it already produces for the
viewport, `assembly.glb` (app.geometry.exporters.export_glb). GLB is Blender's
best-supported import path and carries the assembly's part structure.

WHY CYCLES CPU
--------------
The operator's machine has integrated graphics and no dedicated GPU, and this
container has no GL vendor installed at all (debs.txt explains why). EEVEE
needs a real GPU context and would fail here. Cycles CPU is the only engine
that renders correctly headless on this hardware.

CLAY RENDER, NOT A PHOTOREAL ONE
--------------------------------
Every part gets the same neutral matte material. The vision critique judges
proportion, silhouette and composition (gate_phase5_visual.md), and colour or
material realism actively works against that -- it gives the model something
to comment on that the geometry pipeline cannot act on. A uniform clay shader
is the standard way to read form, and it also renders far faster.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import bpy
import mathutils


# Camera rig. MUST stay in step with backend/app/render/scene.py
# CAMERA_DESCRIPTIONS -- the backend documents the same rig for the API, and
# the two drifting apart would silently mislabel views.
#   dir = the way the camera LOOKS (so it sits at center - dir * distance)
CAMERAS = {
    "ortho_front":    {"type": "ORTHO", "dir": (0.0, -1.0, 0.0), "up": (0.0, 0.0, 1.0)},
    "ortho_side":     {"type": "ORTHO", "dir": (-1.0, 0.0, 0.0), "up": (0.0, 0.0, 1.0)},
    "ortho_top":      {"type": "ORTHO", "dir": (0.0, 0.0, -1.0), "up": (0.0, -1.0, 0.0)},
    "perspective_3q": {"type": "PERSP", "dir": (1.0, -1.0, -0.6), "up": (0.0, 0.0, 1.0)},
}

#: Framing margin around the bounding box, both camera types.
FRAME_MARGIN = 1.12


def log(msg):
    print("[render_scene] %s" % msg, flush=True)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def clear_scene():
    """Empty the factory startup scene (cube, camera, light)."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                  bpy.data.lights):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def import_mesh(path):
    """Import the design and return the mesh objects it produced.

    glTF is authored Y-up by spec; Blender's importer converts to its own
    Z-up on the way in, so a Z-up assembly exported through trimesh arrives
    upright. The worker asserts this rather than trusting it: it checks the
    reported bbox against the bbox the backend already knows.
    """
    suffix = path.suffix.lower()
    before = set(bpy.data.objects)
    if suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise SystemExit(
            "unsupported mesh format %r -- the render worker accepts "
            ".glb/.gltf/.stl/.obj/.ply (Blender cannot read STEP)" % suffix
        )
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not new:
        raise SystemExit("import of %s produced no mesh objects" % path)
    log("imported %d mesh object(s) from %s" % (len(new), path.name))
    return new


def world_bbox(objects):
    """Axis-aligned bounding box of `objects` in world space."""
    lo = mathutils.Vector((float("inf"),) * 3)
    hi = mathutils.Vector((float("-inf"),) * 3)
    for obj in objects:
        for corner in obj.bound_box:
            p = obj.matrix_world @ mathutils.Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    return lo, hi


# ---------------------------------------------------------------------------
# Look
# ---------------------------------------------------------------------------

def clay_material():
    """One neutral matte material, shared by every part (see module docstring)."""
    mat = bpy.data.materials.new("luxuryform_clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.62, 0.61, 0.59, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    # Dielectric: a clay surface reads silhouette without throwing highlights
    # that the critique would mistake for form.
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def apply_clay(objects, mat):
    for obj in objects:
        obj.data.materials.clear()
        obj.data.materials.append(mat)


def build_lighting(center, radius):
    """Three-point studio rig plus a ground plane to catch a contact shadow.

    Everything is sized from the design's own bounding sphere, so the rig
    works for a 300 mm maquette and a 12 m monument without retuning.
    """
    d = max(radius, 1e-6)

    def area_light(name, offset, energy, size):
        light = bpy.data.lights.new(name, type="AREA")
        light.energy = energy
        light.size = size
        obj = bpy.data.objects.new(name, light)
        obj.location = center + mathutils.Vector(offset) * d
        direction = center - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        bpy.context.collection.objects.link(obj)
        return obj

    # Energy scales with d^2 so irradiance at the subject stays constant
    # whatever the design's size: exposure does not drift between a small
    # and a large fountain, which is what makes rounds comparable.
    #
    # The absolute numbers are chosen to land the clay in the middle of the
    # range, not near white. Blender area-light `energy` is radiant power in
    # watts, so irradiance at the subject is roughly P / (4*pi*r^2), and a
    # Lambertian surface returns radiance E*albedo/pi. With the three offsets
    # below (r ~ 2.1d to 2.6d) these powers sum to about 2.5 W/m^2, which for
    # the 0.62 clay albedo gives radiance ~0.5 -- mid grey.
    #
    # Tuned against measured renders, not guessed. At roughly six times these
    # values the subject measured a mean luminance of 211-236 of 255 across
    # the four views -- nothing actually clipped, but sitting that close to
    # the top of the range leaves almost no headroom to separate a lit face
    # from a highlight, and that separation is what the critique reads
    # proportion from. These values put the subject at 154-188 instead.
    unit = d * d
    area_light("key", (1.4, -1.6, 1.5), 100.0 * unit, 1.8 * d)
    area_light("fill", (-1.8, -1.0, 0.6), 30.0 * unit, 2.6 * d)
    area_light("rim", (-0.6, 1.8, 1.2), 50.0 * unit, 1.6 * d)

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.05, 0.05, 0.055, 1.0)
    bg.inputs["Strength"].default_value = 1.0

    # Ground at the base of the design, so it sits on something. The contact
    # shadow is the cue that makes proportion legible in a still.
    #
    # Deliberately far larger than the framing needs: at 14x the plane's own
    # corner fell inside the three-quarter view and read as a stray diagonal
    # across the backdrop. At 60x the edge is always outside frame and the
    # horizon reads as a clean line.
    bpy.ops.mesh.primitive_plane_add(
        size=d * 60.0,
        location=(center.x, center.y, center.z - radius),
    )
    ground = bpy.context.active_object
    ground.name = "ground"
    gmat = bpy.data.materials.new("ground")
    gmat.use_nodes = True
    gb = gmat.node_tree.nodes["Principled BSDF"]
    gb.inputs["Base Color"].default_value = (0.20, 0.20, 0.21, 1.0)
    gb.inputs["Roughness"].default_value = 0.9
    ground.data.materials.append(gmat)


# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------

def camera_matrix(position, forward, up):
    """World matrix for a camera at `position` looking along `forward`.

    Built explicitly rather than via to_track_quat, because the top view's up
    vector (0,-1,0) is a case track_quat cannot express: it picks its own roll
    and the plan view comes out rotated by an arbitrary amount.

    A Blender camera looks along its local -Z with local +Y up, so the basis
    columns are (right, true_up, -forward).
    """
    f = forward.normalized()
    right = f.cross(up).normalized()
    true_up = right.cross(f).normalized()
    basis = mathutils.Matrix((
        (right.x, true_up.x, -f.x),
        (right.y, true_up.y, -f.y),
        (right.z, true_up.z, -f.z),
    )).to_4x4()
    basis.translation = position
    return basis


def bbox_span(lo, hi, axis):
    """Extent of the bounding box projected onto `axis`."""
    corners = [mathutils.Vector((x, y, z))
               for x in (lo.x, hi.x)
               for y in (lo.y, hi.y)
               for z in (lo.z, hi.z)]
    proj = [c.dot(axis) for c in corners]
    return max(proj) - min(proj)


def add_camera(name, spec, lo, hi):
    center = (lo + hi) * 0.5
    radius = (hi - lo).length * 0.5

    forward = mathutils.Vector(spec["dir"]).normalized()
    up = mathutils.Vector(spec["up"])
    right = forward.cross(up).normalized()
    true_up = right.cross(forward).normalized()

    cam_data = bpy.data.cameras.new(name)
    if spec["type"] == "ORTHO":
        cam_data.type = "ORTHO"
        # Fit the box as projected on THIS camera's screen axes, not the
        # bounding-sphere diameter: a tall narrow fountain would otherwise
        # render tiny in the middle of a mostly empty frame.
        width = bbox_span(lo, hi, right)
        height = bbox_span(lo, hi, true_up)
        cam_data.ortho_scale = max(width, height) * FRAME_MARGIN
        distance = radius * 3.0          # ortho: only has to clear the geometry
    else:
        cam_data.type = "PERSP"
        cam_data.lens = 50.0             # mild tele; avoids wide-angle distortion
        half_fov = cam_data.angle * 0.5
        distance = (radius * FRAME_MARGIN) / math.tan(half_fov)

    cam_data.clip_start = max(distance * 1e-4, 1e-5)
    cam_data.clip_end = distance * 10.0 + radius * 10.0

    obj = bpy.data.objects.new(name, cam_data)
    obj.matrix_world = camera_matrix(center - forward * distance, forward, up)
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def configure_render(scene, resolution, samples, threads, seed):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.seed = seed
    # Adaptive sampling stops early on converged tiles. On a 4-core laptop
    # that is the difference between a usable loop and an unusable one.
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01

    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False

    # Pin colour management instead of inheriting Blender's default. The
    # default view transform has changed between Blender releases (Filmic ->
    # AgX), and a silent change to it would shift every render's tone at the
    # next version bump -- which the critique loop would read as the design
    # having changed. AgX by name, no creative look, no exposure offset.
    view = scene.view_settings
    view.view_transform = "AgX"
    view.look = "None"
    view.exposure = 0.0
    view.gamma = 1.0
    scene.display_settings.display_device = "sRGB"

    # Fixed thread count: Cycles partitions work by thread, so on AUTO the
    # image depends on how busy the host happened to be. Pinning it is what
    # makes two rounds comparable, which is the whole point of the loop.
    scene.render.threads_mode = "FIXED"
    scene.render.threads = max(1, threads)


def main():
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit("usage: blender -b --python render_scene.py -- <spec.json>")
    spec_path = Path(argv[argv.index("--") + 1])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    mesh_path = Path(spec["input_mesh"])
    out_dir = Path(spec["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    threads = int(spec.get("threads", 2))
    seed = int(spec.get("seed", 0))

    clear_scene()
    objects = import_mesh(mesh_path)
    lo, hi = world_bbox(objects)
    size = hi - lo
    if size.length <= 0.0:
        raise SystemExit("imported geometry has zero extent -- nothing to render")
    center = (lo + hi) * 0.5
    radius = size.length * 0.5
    log("bbox size=(%.4f, %.4f, %.4f) radius=%.4f"
        % (size.x, size.y, size.z, radius))

    apply_clay(objects, clay_material())
    build_lighting(center, radius)

    scene = bpy.context.scene
    results = []
    for view in spec["views"]:
        name = view["name"]
        camera_key = view["camera"]
        if camera_key not in CAMERAS:
            raise SystemExit("unknown camera %r (known: %s)"
                             % (camera_key, ", ".join(sorted(CAMERAS))))
        cam = add_camera("cam_%s" % name, CAMERAS[camera_key], lo, hi)
        scene.camera = cam
        configure_render(scene,
                         int(view.get("resolution", 1024)),
                         int(view.get("samples", 64)),
                         threads, seed)

        out_png = out_dir / ("%s.png" % name)
        scene.render.filepath = str(out_png)
        t0 = time.time()
        log("rendering %s (%s) -> %s" % (name, camera_key, out_png.name))
        bpy.ops.render.render(write_still=True)
        elapsed = time.time() - t0
        if not out_png.exists():
            raise SystemExit("render of view %r wrote no file at %s" % (name, out_png))
        results.append({"name": name,
                        "path": out_png.name,
                        "elapsed_s": round(elapsed, 3),
                        "bytes": out_png.stat().st_size})
        log("done %s in %.2fs (%d bytes)"
            % (name, elapsed, out_png.stat().st_size))

    (out_dir / "views.json").write_text(
        json.dumps({"views": results,
                    "bbox": {"min": list(lo), "max": list(hi),
                             "size": list(size)}},
                   sort_keys=True),
        encoding="utf-8")
    log("RENDER_SCENE_OK %d view(s)" % len(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
