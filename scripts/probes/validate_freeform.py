"""PR-2.5 independent validation of probe artifacts (ANALYSIS-ONLY).

ADR-064: this module OPENS artifacts the sandbox produced and never
constructs design geometry, so it may run in the backend container,
orchestrated by scripts/run_pr25_discovery.py:

    docker compose exec -T backend python \
        /scratch/pr25_discovery/probes/validate_freeform.py <pass_dir> <out_json>

Independent cross-checks (owner amendment 5) applied per artifact:

  STEP artifacts (BREP route):
    * OpenCASCADE BRepCheck_Analyzer validity;
    * OpenCASCADE BRepAlgoAPI_Check with self-interference testing when
      the installed binding exposes a usable call pattern (the pattern
      actually used -- or its unavailability -- is RECORDED in the output;
      nothing is assumed from recall, ADR-009);
    * solid/body count from the kernel;
    * kernel volume vs the sibling GLB's tessellated-mesh volume
      (divergence-theorem volume from trimesh), relative tolerance
      REL_VOL_TOL -- a printed probe-only-judgement value;
    * bounding envelope (mm).

  Mesh artifacts (GLB / canonical OBJ):
    * trimesh watertight / winding-consistency / broken-face checks;
    * connected-body count;
    * duplicate-face detection;
    * Euler characteristic -> genus (void topology) for closed bodies;
    * minimum-thickness sampling: trimesh.proximity.thickness
      (max_sphere) at <=200 DETERMINISTIC sample points (every k-th
      vertex, never random).

An artifact is flagged_invalid when any independent check fails; the
reasons are listed. For fixtures marked expected_invalid the FLAG is the
desired outcome -- the gate fails if such a fixture is NOT flagged and was
not already refused at construction time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Kernel-vs-tessellation relative volume tolerance. probe-only-judgement:
#: the GLB is tessellated at 1.0 mm linear deflection (exporters.py), so a
#: smooth 3.5-5 m body should agree well within 2 %.
REL_VOL_TOL = 0.02

MAX_THICKNESS_SAMPLES = 200


def mesh_report(mesh) -> dict:
    """Independent trimesh-side checks for one loaded mesh.

    NOTE: trimesh.repair.broken_faces needs networkx, which the image
    deliberately does not carry (LIMITATIONS/D-7). The equivalent
    networkx-free check counts edges whose face-incidence is not exactly
    2 (boundary or non-manifold edges) straight from numpy."""
    import numpy as np
    from trimesh import grouping, proximity

    faces_sorted = np.sort(mesh.faces, axis=1)
    dup_groups = grouping.group_rows(faces_sorted, require_count=2)
    _, edge_counts = np.unique(np.sort(mesh.edges, axis=1), axis=0,
                               return_counts=True)
    bad_edge_count = int((edge_counts != 2).sum())
    body_count = int(mesh.body_count)
    euler = int(mesh.euler_number)
    watertight = bool(mesh.is_watertight)
    genus = None
    if watertight:
        genus = int((2 * body_count - euler) // 2)

    step = max(1, len(mesh.vertices) // MAX_THICKNESS_SAMPLES)
    pts = mesh.vertices[::step][:MAX_THICKNESS_SAMPLES]
    try:
        thick = proximity.thickness(mesh, pts, method="max_sphere")
        min_thickness_mm = round(float(min(thick)), 3)
    except BaseException as exc:  # thickness sampling must never kill a run
        min_thickness_mm = None
        thick_err = "%s: %s" % (type(exc).__name__, exc)
    else:
        thick_err = None

    return {
        "watertight": watertight,
        "winding_consistent": bool(mesh.is_winding_consistent),
        "boundary_or_nonmanifold_edges": bad_edge_count,
        "duplicate_face_pairs": int(len(dup_groups)),
        "body_count": body_count,
        "euler_characteristic": euler,
        "genus": genus,
        "volume_mm3": round(float(mesh.volume), 3),
        "bbox_mm": [round(float(x), 3) for x in
                    (mesh.bounds[1] - mesh.bounds[0])],
        "min_thickness_mm": min_thickness_mm,
        "thickness_error": thick_err,
    }


def occ_self_check(wrapped) -> dict:
    """BRepAlgoAPI_Check against the installed OCP binding. Every call
    pattern is attempted at runtime and the one that worked is recorded;
    unavailability is recorded, never papered over."""
    try:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    except Exception as exc:
        return {"available": False, "pattern": None,
                "error": "import failed: %s" % exc}
    for pattern, make in (
        ("ctor(shape, testSE=True, testSI=True)",
         lambda: BRepAlgoAPI_Check(wrapped, True, True)),
        ("ctor(shape)", lambda: BRepAlgoAPI_Check(wrapped)),
        ("default ctor + SetData", None),
    ):
        try:
            if make is None:
                chk = BRepAlgoAPI_Check()
                chk.SetData(wrapped)
            else:
                chk = make()
            chk.Perform()
            return {"available": True, "pattern": pattern,
                    "has_errors": bool(chk.HasErrors()),
                    "is_valid": bool(chk.IsValid())}
        except Exception:
            continue
    return {"available": False, "pattern": None,
            "error": "no constructor/SetData pattern accepted by the "
                     "installed OCP binding"}


def validate_step(step_path: Path) -> dict:
    """OCC-side checks plus an INDEPENDENT tessellation cross-check.

    The probe's sibling GLB is deliberately NOT used here: build123d
    exports GLB in metres and as per-face primitives (unwelded -- loading
    one reports ~10 bodies and watertight=False for a perfectly valid
    solid; measured 2026-09-02 on the installed stack). Instead the
    imported shape is tessellated directly at the same 1.0 mm deflection,
    welded by exact vertex merge (OCC shares each edge's polyline between
    adjacent faces, so boundary vertices coincide bitwise), and checked
    in millimetres end to end."""
    import numpy as np
    import trimesh
    from build123d import import_step
    from OCP.BRepCheck import BRepCheck_Analyzer

    shape = import_step(str(step_path))
    analyzer_valid = bool(BRepCheck_Analyzer(shape.wrapped).IsValid())
    self_check = occ_self_check(shape.wrapped)
    kernel_volume = float(shape.volume)
    bb = shape.bounding_box().size
    out = {
        "occ_analyzer_valid": analyzer_valid,
        "occ_self_check": self_check,
        "kernel_solid_count": len(shape.solids()),
        "kernel_volume_mm3": round(kernel_volume, 3),
        "kernel_bbox_mm": [round(float(bb.X), 3), round(float(bb.Y), 3),
                           round(float(bb.Z), 3)],
    }
    verts, tris = shape.tessellate(tolerance=1.0, angular_tolerance=0.1)
    mesh = trimesh.Trimesh(
        vertices=np.array([[v.X, v.Y, v.Z] for v in verts]),
        faces=np.array(tris), process=True)
    mesh.merge_vertices()
    m = mesh_report(mesh)
    out["tessellation_mesh"] = m
    if kernel_volume > 0:
        rel = abs(m["volume_mm3"] - kernel_volume) / kernel_volume
        out["volume_rel_diff"] = round(rel, 5)
        out["volume_cross_check_ok"] = bool(rel <= REL_VOL_TOL)
        out["volume_rel_tol"] = REL_VOL_TOL
    return out


def flag(checks: dict) -> list[str]:
    reasons = []
    if checks.get("occ_analyzer_valid") is False:
        reasons.append("OCC BRepCheck_Analyzer reports INVALID")
    sc = checks.get("occ_self_check") or {}
    if sc.get("available"):
        if sc.get("has_errors"):
            reasons.append("OCC BRepAlgoAPI_Check reports errors "
                           "(self-interference test pattern: %s)"
                           % sc["pattern"])
        elif sc.get("is_valid") is False:
            # Measured on this stack: IsValid() can return False with
            # HasErrors() False. That verdict is INDETERMINATE -- the
            # binding gives no error detail -- and it fails closed here,
            # honestly labeled, rather than being read as proof of
            # self-intersection.
            reasons.append("OCC BRepAlgoAPI_Check IsValid=False with no "
                           "error details (indeterminate; fail-closed; "
                           "pattern: %s)" % sc["pattern"])
    if checks.get("volume_cross_check_ok") is False:
        reasons.append("kernel vs tessellation volume differ by %.3f%% "
                       "(tol %.3f%%)" % (100 * checks["volume_rel_diff"],
                                         100 * checks["volume_rel_tol"]))
    m = checks.get("tessellation_mesh") or (checks if "watertight" in checks
                                            else {})
    if m:
        if m.get("watertight") is False:
            reasons.append("mesh not watertight")
        if m.get("winding_consistent") is False:
            reasons.append("mesh winding inconsistent")
        if m.get("boundary_or_nonmanifold_edges"):
            reasons.append("%d boundary/non-manifold edges"
                           % m["boundary_or_nonmanifold_edges"])
        if m.get("duplicate_face_pairs"):
            reasons.append("%d duplicate face pairs" % m["duplicate_face_pairs"])
    return reasons


def main(argv) -> int:
    if len(argv) != 3:
        print("usage: validate_freeform.py <pass_dir> <out_json>")
        return 2
    pass_dir = Path(argv[1])
    out_json = Path(argv[2])
    results = sorted(pass_dir.glob("*.results.json"))
    if not results:
        print("no *.results.json in %s" % pass_dir)
        return 2

    validated = []
    for res_path in results:
        payload = json.loads(res_path.read_text(encoding="utf-8"))
        for entry in payload["entries"]:
            if entry["status"] != "constructed":
                continue
            arts = entry["artifacts"]
            checks: dict = {}
            try:
                if "step" in arts:
                    checks = validate_step(pass_dir / arts["step"]["file"])
                elif "obj" in arts or "glb" in arts:
                    import trimesh
                    key = "obj" if "obj" in arts else "glb"
                    mesh = trimesh.load(str(pass_dir / arts[key]["file"]),
                                        force="mesh", process=False)
                    checks = mesh_report(mesh)
                reasons = flag(checks)
            except Exception as exc:
                checks = {"validator_error": "%s: %s"
                          % (type(exc).__name__, exc)}
                reasons = ["validator could not process artifact: %s" % exc]
            validated.append({
                "fixture": entry["fixture"],
                "approach": entry["approach"],
                "expected_invalid": entry["expected_invalid"],
                "checks": checks,
                "flagged_invalid": bool(reasons),
                "reasons": reasons,
            })
            print("[validate] %-28s %-6s flagged=%s %s"
                  % (entry["fixture"], entry["approach"], bool(reasons),
                     ("(" + "; ".join(reasons) + ")") if reasons else ""))

    out_json.write_text(json.dumps({"validated": validated}, indent=2,
                                   sort_keys=True), encoding="utf-8")
    print("validated %d artifacts -> %s" % (len(validated), out_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
