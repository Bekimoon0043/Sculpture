#!/usr/bin/env python3
"""PHASE 14 AUTO GATE — designer workspace, $0, offline, non-interactive.

Two toolchains are involved, so the gate is explicit about coverage:

* Geometry + API sections (1-4) need build123d/trimesh/fastapi — run them
  inside the backend container:
      docker compose exec backend python scripts/gate_phase14_auto.py
* The frontend section (5) needs node/npm — run it on the host:
      python scripts\\gate_phase14_auto.py --frontend-only
  (it runs automatically in a full run when npm is on PATH)

A section that CANNOT run in the current environment is reported NOT RUN
with the exact command to run it elsewhere — it is never counted as a pass.
Exit 0 requires: every section that ran passed, and at least one section
group actually ran.

  1. SCENE GLB WRITER — assemble(return_solids=True) on a three-element
     plan; export_scene_glb; parse the emitted binary's JSON chunk and
     PROVE one named node per element (node name == element_id) with
     nonempty geometry. The naming behaviour is proven, not assumed.
  2. API ROUND-TRIP — TestClient against an isolated temp DB/data dir:
     POST /build returns scene_glb_url; GET /{id}/scene.glb serves the
     named-node GLB; GET /{id}.glb, /{id}/manifest and /designs read the
     design back after it is no longer hypothetical.
  3. LAZY BACKFILL — delete scene.glb from disk; GET regenerates it from
     the stored request with the SAME node-name set (pre-Phase-14 designs
     gain pickability without a rebuild).
  4. FUSED ARTIFACTS UNTOUCHED — the same plan built twice yields the
     same STEP sha256 (determinism intact), and assemble() without the new
     flag still returns its Phase 6 two-tuple (no caller broken).
  5. FRONTEND BUILD — `npm run build` (tsc strict + vite) in frontend/,
     offline against the cached node_modules.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS, FAIL = "PASS", "FAIL"

PLAN = [
    {
        "element_id": "plinth_01",
        "primitive": "plinth",
        "parameters": {"top_diameter_mm": 2200, "height_mm": 300, "wall_mm": 120},
    },
    {
        "element_id": "basin_01",
        "primitive": "basin_round",
        "parameters": {
            "diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
            "floor_mm": 160, "min_clearance_mm": 220,
        },
        "joint": {"type": "stack_on", "parent": "plinth_01"},
    },
    {
        "element_id": "column_01",
        "primitive": "sculptural_column",
        "parameters": {"diameter_mm": 360, "height_mm": 900, "bore_mm": 80},
        "joint": {"type": "concentric_insert", "parent": "basin_01"},
    },
]
ELEMENT_IDS = sorted(e["element_id"] for e in PLAN)


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/5] {title}")
    _hline()


def parse_glb_json(path: Path) -> dict:
    """Return the JSON chunk of a GLB, verifying the container structure."""
    blob = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF":
        raise ValueError(f"{path}: not a GLB (magic {magic!r})")
    if length != len(blob):
        raise ValueError(f"{path}: header length {length} != file size {len(blob)}")
    chunk_len, chunk_type = struct.unpack_from("<I4s", blob, 12)
    if chunk_type != b"JSON":
        raise ValueError(f"{path}: first chunk is {chunk_type!r}, expected JSON")
    return json.loads(blob[20 : 20 + chunk_len].decode("utf-8"))


def named_mesh_nodes(gltf: dict) -> dict[str, int]:
    """node name -> mesh index, for nodes that reference a mesh."""
    return {
        n["name"]: n["mesh"]
        for n in gltf.get("nodes", [])
        if "mesh" in n and n.get("name")
    }


def geometry_backend_available() -> bool:
    try:
        import build123d  # noqa: F401
        import trimesh  # noqa: F401
        import fastapi  # noqa: F401
        return True
    except ImportError:
        return False


def run_geometry_sections(failures: list[str]) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="luxform_gate14_"))
    os.environ["LUXURYFORM_DB"] = str(workdir / "gate14.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(workdir / "data")

    from app.geometry.assembly import assemble
    from app.geometry.scene_glb import export_scene_glb

    # -- 1 ------------------------------------------------------------------
    _section(1, "SCENE GLB WRITER — one named node per element, proven")
    fused, manifest, solids = assemble(PLAN, seed=42, return_solids=True)
    if sorted(solids) != ELEMENT_IDS:
        failures.append(f"return_solids keys {sorted(solids)} != {ELEMENT_IDS}")
        print(f"{FAIL} — solids keys: {sorted(solids)}")
    scene_path = workdir / "scene.glb"
    sha = export_scene_glb(solids, scene_path)
    gltf = parse_glb_json(scene_path)
    nodes = named_mesh_nodes(gltf)
    print(f"scene.glb written: {scene_path.stat().st_size} bytes, sha256 {sha[:16]}…")
    print(f"named mesh nodes: {sorted(nodes)}")
    missing = [e for e in ELEMENT_IDS if e not in nodes]
    if missing:
        failures.append(f"scene.glb lacks named nodes for {missing}")
        print(f"{FAIL} — missing nodes: {missing}")
    else:
        # Every element's mesh must carry real geometry.
        accessors = gltf.get("accessors", [])
        meshes = gltf.get("meshes", [])
        for eid in ELEMENT_IDS:
            prim = meshes[nodes[eid]]["primitives"][0]
            count = accessors[prim["attributes"]["POSITION"]]["count"]
            print(f"  {eid}: {count} vertices")
            if count < 4:
                failures.append(f"{eid}: only {count} vertices in scene.glb")
        print(f"ok — {len(ELEMENT_IDS)} elements, each a named node with geometry")

    # -- 2 ------------------------------------------------------------------
    _section(2, "API ROUND-TRIP — build, then read the design back by id")
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/geometry/assembly/build",
            json={"elements": PLAN, "seed": 42,
                  "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0}},
        )
        if resp.status_code != 200:
            failures.append(f"POST /build -> {resp.status_code}: {resp.text[:300]}")
            print(f"{FAIL} — build: {resp.status_code}")
            return
        build = resp.json()
        design_id = build["design_id"]
        print(f"built design {design_id} (overall {build['overall_status']})")
        if "scene_glb_url" not in build:
            failures.append("build response lacks scene_glb_url")
        checks = [
            (f"/api/geometry/assembly/{design_id}/scene.glb", "model/gltf-binary"),
            (f"/api/geometry/assembly/{design_id}.glb", "model/gltf-binary"),
            (f"/api/geometry/assembly/{design_id}/manifest", "application/json"),
            ("/api/geometry/assembly/latest/scene.glb", "model/gltf-binary"),
            ("/api/geometry/assembly/designs", "application/json"),
        ]
        for url, want_type in checks:
            r = client.get(url)
            ok = r.status_code == 200 and want_type in r.headers.get("content-type", "")
            print(f"  GET {url} -> {r.status_code} {r.headers.get('content-type', '')}")
            if not ok:
                failures.append(f"GET {url} -> {r.status_code}")
        listing = client.get("/api/geometry/assembly/designs").json()
        ids = [d["design_id"] for d in listing["designs"]]
        if design_id not in ids:
            failures.append(f"/designs does not list {design_id}")
        else:
            entry = next(d for d in listing["designs"] if d["design_id"] == design_id)
            print(f"  listed: {entry['element_count']} elements, "
                  f"{entry['primitives']}, status {entry['overall_status']}, "
                  f"{entry['total_mass_kg']:.1f} kg")
            if sorted(entry["element_ids"]) != ELEMENT_IDS:
                failures.append(f"/designs element_ids {entry['element_ids']}")
        served = client.get(f"/api/geometry/assembly/{design_id}/scene.glb")
        api_scene = workdir / "api_scene.glb"
        api_scene.write_bytes(served.content)
        api_nodes = sorted(named_mesh_nodes(parse_glb_json(api_scene)))
        print(f"  served scene nodes: {api_nodes}")
        if [e for e in ELEMENT_IDS if e not in api_nodes]:
            failures.append(f"served scene.glb nodes {api_nodes} != {ELEMENT_IDS}")

        # -- 3 --------------------------------------------------------------
        _section(3, "LAZY BACKFILL — scene.glb deleted, GET regenerates it")
        manifest_resp = client.get(
            f"/api/geometry/assembly/{design_id}/manifest"
        ).json()
        stored_scene = Path(manifest_resp["artifacts"]["scene_glb_path"])
        if not stored_scene.exists():
            failures.append(f"artifact scene_glb_path missing on disk: {stored_scene}")
            print(f"{FAIL} — {stored_scene} not on disk")
        else:
            stored_scene.unlink()
            print(f"deleted {stored_scene}")
            r = client.get(f"/api/geometry/assembly/{design_id}/scene.glb")
            if r.status_code != 200:
                failures.append(f"backfill GET -> {r.status_code}: {r.text[:200]}")
                print(f"{FAIL} — regeneration returned {r.status_code}")
            else:
                back = workdir / "backfilled.glb"
                back.write_bytes(r.content)
                back_nodes = sorted(named_mesh_nodes(parse_glb_json(back)))
                print(f"regenerated nodes: {back_nodes}")
                if back_nodes != api_nodes:
                    failures.append(
                        f"backfilled nodes {back_nodes} != original {api_nodes}"
                    )
                else:
                    print("ok — regenerated scene has the identical node set")

        # -- 4 --------------------------------------------------------------
        _section(4, "FUSED ARTIFACTS UNTOUCHED — determinism + back-compat")
        resp2 = client.post(
            "/api/geometry/assembly/build",
            json={"elements": PLAN, "seed": 42,
                  "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0}},
        )
        build2 = resp2.json()
        same = build2.get("step_sha256") == build.get("step_sha256")
        print(f"STEP sha256 build 1: {build['step_sha256'][:16]}…")
        print(f"STEP sha256 build 2: {str(build2.get('step_sha256'))[:16]}…")
        if not same:
            failures.append("same plan+seed no longer yields the same STEP sha256")
        else:
            print("ok — byte-identical STEP across rebuilds (Rule 5 intact)")
        two = assemble(PLAN, seed=42)
        if not (isinstance(two, tuple) and len(two) == 2):
            failures.append("assemble() without return_solids no longer returns 2-tuple")
        else:
            print("ok — assemble() default return shape unchanged (Phase 6 callers safe)")


def run_frontend_section(failures: list[str], ran: dict[str, bool]) -> None:
    _section(5, "FRONTEND BUILD — tsc strict + vite, offline")
    npm = shutil.which("npm")
    if npm is None:
        print("NOT RUN — npm is not on PATH in this environment.")
        print("Run on the host:  python scripts\\gate_phase14_auto.py --frontend-only")
        return
    ran["frontend"] = True
    # Explicit UTF-8 (2026-09-28): `text=True` alone decodes with the HOST
    # locale codec — on a zh-CN Windows host that is GBK, and Vite's UTF-8
    # arrows/ellipses raised UnicodeDecodeError inside the reader thread,
    # leaving proc.stdout None and crashing the gate before its verdict.
    # npm/vite emit UTF-8 regardless of locale; undecodable bytes are
    # replaced, never allowed to hide the build's real exit code.
    proc = subprocess.run(
        [npm, "run", "build"],
        cwd=REPO_ROOT / "frontend",
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-6:]
    for line in tail:
        print(f"  {line}")
    if proc.returncode != 0:
        failures.append(f"npm run build exited {proc.returncode}")
        print(f"{FAIL} — frontend build failed")
    else:
        print("ok — typecheck and production build pass")


def main() -> int:
    frontend_only = "--frontend-only" in sys.argv
    failures: list[str] = []
    ran = {"geometry": False, "frontend": False}

    print("PHASE 14 AUTO GATE — designer workspace")
    print(f"repo: {REPO_ROOT}")

    if not frontend_only:
        if geometry_backend_available():
            ran["geometry"] = True
            run_geometry_sections(failures)
        else:
            print()
            print("Sections 1-4 NOT RUN — build123d/trimesh/fastapi not importable here.")
            print("Run them in the backend container:")
            print("  docker compose exec backend python scripts/gate_phase14_auto.py")

    run_frontend_section(failures, ran)

    print()
    _hline()
    print("VERDICT")
    _hline()
    covered = [k for k, v in ran.items() if v]
    skipped = [k for k, v in ran.items() if not v]
    print(f"sections run: {', '.join(covered) or 'none'}")
    if skipped:
        print(f"NOT covered in this run: {', '.join(skipped)} — see commands above.")
    if not covered:
        print(f"{FAIL} — nothing could run in this environment")
        return 1
    if failures:
        print(f"{FAIL} — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{PASS} — all sections that ran passed at $0 with no network")
    return 0


if __name__ == "__main__":
    sys.exit(main())
