#!/usr/bin/env python3
"""Phase 9B auto gate — Blender render worker, offline, $0.

Gate: the render worker turns a mesh into four canonical views that are real
images of the geometry, not blank frames, and the four views are genuinely
different from one another.

Run it inside the backend container, with the render worker up:

    docker compose --profile render up -d render-worker
    docker compose exec backend python scripts/gate_phase9b_auto.py

WHY THIS GATE NEEDS A CONTAINER AND THE OTHERS DO NOT
------------------------------------------------------
Every other auto gate is pure Python and proves logic. This one proves that
Blender actually renders, which is exactly the claim that cannot be made
without running Blender. It still costs $0 and touches no network -- the
render worker runs with network_mode: none.

WHAT IT REFUSES TO ACCEPT
-------------------------
A gate that only checked "four PNG files exist" would pass on four identical
black frames, which is the most likely way this breaks (bad camera, no
lighting, geometry off-screen). So it checks that each view has real tonal
variation, that the subject occupies a plausible share of the frame, and that
no two views are near-identical.
"""

from __future__ import annotations

import shutil
import sys
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import numpy as np
from PIL import Image

from app.render import DEFAULT_VIEWS
from app.render.queue import ScratchRenderRunner, scratch_dir, submit_render_job

#: Small enough to keep the gate near a minute on the operator's laptop, big
#: enough that a framing or camera fault is visible in the statistics.
GATE_RESOLUTION = 256
GATE_SAMPLES = 16
GATE_BUDGET_S = 240.0

#: A view whose pixels vary less than this is a flat frame -- black, white, or
#: pure background with the geometry off-camera.
MIN_STDDEV = 6.0

#: The subject must cover at least this fraction of the frame. Catches a
#: camera that technically sees the design but from so far away it is a speck.
MIN_SUBJECT_FRACTION = 0.02

#: Two views differing by less than this mean absolute difference are the same
#: picture, which means the camera rig is not actually moving.
MIN_VIEW_DIFFERENCE = 2.0

#: The four formats only Blender can write, with the magic bytes that prove a
#: file really is that format. Checking the extension would prove nothing --
#: an exporter that silently wrote glTF to assembly.fbx would pass.
#:   USD  -> Blender writes binary USD (usdc) by default
#:   USDZ -> an uncompressed zip package
#:   FBX  -> binary FBX
#:   ABC  -> Alembic's Ogawa backend
BLENDER_FORMATS = {
    "USD": (".usd", b"PXR-USDC"),
    "USDZ": (".usdz", b"PK"),
    "FBX": (".fbx", b"Kaydara FBX Binary"),
    "ABC": (".abc", b"Ogawa"),
}


def fail(step: str, msg: str) -> int:
    print(f"FAIL [{step}] {msg}")
    return 1


#: The test solid's bounding box AS BLENDER SHOULD SEE IT, in metres, Z up.
#: The solid is authored in millimetres (build123d's unit) and export_gltf
#: converts to metres, so 2200 mm of plinth diameter must arrive as 2.2.
#: Asserted after every render: this single check catches both a Y-up/Z-up
#: mix-up (axes permuted) and a millimetre/metre mix-up (everything 1000x off),
#: neither of which makes the picture itself look wrong.
EXPECTED_BBOX = (2.20, 2.20, 1.64)
BBOX_TOLERANCE = 0.02


def build_test_mesh(path: Path) -> None:
    """A deterministic stepped solid -- plinth, bowl, stem -- Z up.

    Built through build123d and app.geometry.exporters.export_glb, which is
    the SAME path a real design takes. That matters: glTF is a Y-up format, so
    whether the model reaches Blender upright depends entirely on which
    exporter wrote it. An earlier version of this gate built the mesh with
    trimesh's own Scene export instead, which applies its own Y-up flip -- the
    render came out lying on its side while real pipeline GLBs were upright.
    A gate that does not exercise the production exporter cannot catch an
    orientation regression in it.

    It is built here rather than read from data/ so the gate does not depend
    on the operator having produced a design first, and so the geometry under
    test is fixed and known.

    UNITS: build123d geometry is in MILLIMETRES, and export_gltf converts to
    METRES on the way out because that is what glTF specifies. So the numbers
    below are mm and the bounding box Blender reports is the same solid in m
    (2200 mm -> 2.2 m). Getting this wrong does not produce a broken-looking
    render -- the camera rig frames whatever it is given, so a design 1000x
    too small renders as a perfectly nice picture. That is precisely why the
    check below is numeric.
    """
    from build123d import Cylinder, Pos

    from app.geometry.exporters import export_glb

    plinth = Pos(0, 0, 150) * Cylinder(radius=1100, height=300)
    bowl = Pos(0, 0, 520) * Cylinder(radius=850, height=440)
    stem = Pos(0, 0, 1190) * Cylinder(radius=180, height=900)
    export_glb(plinth + bowl + stem, path)


def luminance(png: Path) -> np.ndarray:
    img = Image.open(png).convert("RGB")
    a = np.asarray(img, dtype=np.float64)
    return 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]


def main() -> int:
    print("=" * 62)
    print("Phase 9B auto gate - Blender render worker (offline, $0)")
    print("=" * 62)

    root = scratch_dir()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return fail("0", f"render scratch {root} is not writable: {exc}")
    print(f"[0] render scratch: {root}")

    # 1. Stage a known mesh and queue a real job.
    staging = root / "_gate9b_src"
    staging.mkdir(parents=True, exist_ok=True)
    mesh = staging / "gate_assembly.glb"
    build_test_mesh(mesh)
    if not mesh.exists() or mesh.stat().st_size == 0:
        return fail("1", "failed to build the gate test mesh")
    print(f"[1] PASS built test mesh ({mesh.stat().st_size} bytes, 3 parts)")

    views = []
    for v in DEFAULT_VIEWS:
        views.append(type(v)(name=v.name, camera=v.camera,
                             resolution=GATE_RESOLUTION,
                             samples=GATE_SAMPLES,
                             time_budget_s=GATE_BUDGET_S))

    runner = ScratchRenderRunner()
    job = submit_render_job(design_id="gate-9b", input_mesh=str(mesh),
                            views=views, runner=runner)
    print(f"[2] queued job {job.id}; waiting for the render worker ...")

    result = runner.collect(job.id, timeout_s=GATE_BUDGET_S)
    if not result.ok:
        return fail(
            "2",
            f"{result.error}\n"
            "      Is the render worker running? Start it with:\n"
            "        docker compose --profile render up -d render-worker",
        )
    if len(result.views) != 4:
        return fail("2", f"expected 4 views, got {len(result.views)}: "
                         f"{sorted(result.views)}")
    print(f"[2] PASS render worker returned 4 views in {result.total_s:.1f}s")

    # 2b. Orientation. glTF is a Y-up format and Blender is Z-up, so a wrong
    # importer setting or a change of exporter silently tips the design onto
    # its side -- the render still looks like a competent picture of
    # something, which is exactly why this has to be asserted numerically
    # rather than left to the eye.
    import json as _json

    views_json = scratch_dir() / job.id / "views.json"
    if not views_json.exists():
        return fail("2b", f"worker wrote no views.json at {views_json}")
    bbox = _json.loads(views_json.read_text(encoding="utf-8")).get("bbox", {})
    size = bbox.get("size")
    if not size or len(size) != 3:
        return fail("2b", f"views.json has no usable bbox: {bbox}")
    for axis, got, want in zip("XYZ", size, EXPECTED_BBOX):
        if abs(abs(got) - want) > BBOX_TOLERANCE:
            return fail(
                "2b",
                f"the design reached Blender with {axis} extent {got:.3f}, "
                f"expected {want:.3f} (full size {[round(s, 3) for s in size]}, "
                f"expected {list(EXPECTED_BBOX)}) -- the model is not upright, "
                "so the glTF Y-up/Z-up conversion is wrong",
            )
    print(f"[2b] PASS geometry arrived upright, Z up "
          f"(size {[round(s, 3) for s in size]} m)")

    # 3. Every view must be a real image of something.
    lums: dict[str, np.ndarray] = {}
    for name, png in sorted(result.views.items()):
        if not png.exists():
            return fail("3", f"view {name} missing at {png}")
        with open(png, "rb") as fh:
            if fh.read(8) != b"\x89PNG\r\n\x1a\n":
                return fail("3", f"view {name} is not a PNG")
        lum = luminance(png)
        if lum.shape != (GATE_RESOLUTION, GATE_RESOLUTION):
            return fail("3", f"view {name} is {lum.shape}, expected "
                             f"{(GATE_RESOLUTION, GATE_RESOLUTION)}")
        if lum.std() < MIN_STDDEV:
            return fail("3", f"view {name} is a flat frame "
                             f"(stddev {lum.std():.2f} < {MIN_STDDEV}) -- the "
                             "geometry is probably off camera or unlit")
        # The subject is what stands clear of the darkest background level.
        floor = np.percentile(lum, 5)
        subject = float((lum > floor + 25.0).mean())
        if subject < MIN_SUBJECT_FRACTION:
            return fail("3", f"view {name} shows almost nothing "
                             f"({subject * 100:.2f}% of frame)")
        lums[name] = lum
        print(f"    {name:<14} stddev={lum.std():6.2f}  mean={lum.mean():6.1f}  "
              f"subject={subject * 100:5.1f}%  {png.stat().st_size} bytes")
    print("[3] PASS all four views carry real tonal detail")

    # 4. The four cameras must actually be four different cameras.
    for a, b in combinations(sorted(lums), 2):
        diff = float(np.abs(lums[a] - lums[b]).mean())
        if diff < MIN_VIEW_DIFFERENCE:
            return fail("4", f"views {a} and {b} are near-identical "
                             f"(mean abs diff {diff:.2f}) -- the camera rig is "
                             "not moving between views")
    print("[4] PASS all six view pairs are distinct")

    # 5. Format conversion (Phase 9B.5). USD, USDZ, FBX and Alembic are the
    # four formats nothing else in this stack can write. Before this was
    # wired they reported `unavailable`; the point of the check is that they
    # now report `included` AND that the bytes are really those formats.
    from app.geometry.export_formats import write_exports

    convert_out = staging / "converted"
    if convert_out.exists():
        shutil.rmtree(convert_out)
    results = {r.format: r for r in write_exports(
        None, convert_out, step_path=None, glb_path=mesh,
        formats=list(BLENDER_FORMATS), render_worker_available=True,
    )}

    for fmt, (ext, magic) in BLENDER_FORMATS.items():
        r = results.get(fmt)
        if r is None:
            return fail("5", f"{fmt} was not attempted at all")
        if r.status != "included":
            return fail("5", f"{fmt} reported {r.status}: "
                             f"{r.error or r.reason or 'no reason given'}")
        path = convert_out / f"assembly{ext}"
        if not path.exists() or path.stat().st_size == 0:
            return fail("5", f"{fmt} reported included but wrote no file")
        head = path.read_bytes()[:len(magic)]
        if head != magic:
            return fail("5", f"{fmt} is not really {fmt}: expected magic "
                             f"{magic!r}, file starts {head!r}")
        print(f"    {fmt:<5} {r.bytes:>8} bytes  magic={magic!r}")
    print(f"[5] PASS all four Blender-only formats written and verified")

    # 6. A conversion must carry the design and nothing else. Blender's
    # factory world gets baked to an HDR sidecar by the USD exporter unless
    # it is explicitly dropped, and that folder would ship to a fabricator as
    # a file they did not ask for.
    strays = [p.name for p in convert_out.iterdir()
              if p.name not in {f"assembly{ext}"
                                for ext, _ in BLENDER_FORMATS.values()}]
    if strays:
        return fail("6", f"conversion left files that are not the design: "
                         f"{', '.join(sorted(strays))}")
    print("[6] PASS conversion output contains only the four design files")

    print("=" * 62)
    print("Phase 9B auto gate PASS")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
