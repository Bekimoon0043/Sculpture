"""FF-A1 (ADR-065): production free-form geometry-integrity validation.

The independent check stack the PR-2.5 discovery proved (ADR-064),
promoted into reviewed production code — NOT an import of the discovery
probe script (`scripts/probes/validate_freeform.py` stays evidence).
Runs in the backend as analysis of a solid the trusted kernel already
built, exactly like `validate.validate_assembly` does; ADR-005 is not in
play (no AI-loop code executes here).

Verdict vocabulary and the fail-closed rule (owner ruling 2026-09-03):

  * ``pass``        — every check passed.
  * ``fail``        — at least one check failed.
  * ``needs_input`` — the stack could not reach a verdict: OCC's
    BRepAlgoAPI_Check can return IsValid()=False with HasErrors()=False
    (measured 2026-09-02 on the installed binding), which is
    INDETERMINATE and fails closed under its own honest label.

For a design whose persisted manifest requires this gate, classification
REFUSES export on a missing, failed OR indeterminate row — see
`package_class.classify_reports` and ADR-065.

Checks (all values printed into the report, mm/mm^3):
  occ_analyzer_valid       BRepCheck_Analyzer
  occ_self_interference    BRepAlgoAPI_Check(shape, testSE, testSI)
  tessellation_watertight  1.0 mm deflection, exact-weld, trimesh
  tessellation_winding     winding consistency
  boundary_or_nonmanifold  edge-incidence != 2 count (networkx-free)
  duplicate_faces          duplicate face pairs
  volume_cross_check       |kernel - mesh| / kernel <= REL_VOL_TOL
  body_count               kernel solid count == 1
  genus                    Euler-characteristic genus (informational
                           value; pass = computable on a closed mesh)

Minimum-thickness sampling is NOT part of this stack: the pinned image
lacks `rtree` (LIMITATIONS 22); pretending otherwise would be a silent
lie. It joins when that dependency decision is made.
"""

from __future__ import annotations

from typing import Any

#: Kernel-vs-tessellation relative volume tolerance. Carried from the
#: discovery (ADR-064); a printed judgement value.
REL_VOL_TOL = 0.02

FREEFORM_INTEGRITY_GATE = "freeform_integrity_v1"

_SCHEMA = "freeform_integrity_report_v1"


def _check(check: str, *, status: str, value: Any, limit: Any,
           units: str | None, basis: str, message: str) -> dict[str, Any]:
    return {
        "check": check, "status": status, "on_violation": "fail",
        "value": value, "limit": limit, "units": units,
        "basis": basis, "message": message,
    }


def occ_self_interference(wrapped) -> dict[str, Any]:
    """BRepAlgoAPI_Check with self-interference testing against the
    INSTALLED binding — the working call pattern was established by
    runtime inspection on 2026-09-02 (ADR-064), and unavailability is
    reported, never papered over."""
    try:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    except Exception as exc:  # pragma: no cover — binding present on image
        return {"available": False, "error": f"import failed: {exc}"}
    for pattern, make in (
        ("ctor(shape, testSE=True, testSI=True)",
         lambda: BRepAlgoAPI_Check(wrapped, True, True)),
        ("ctor(shape)", lambda: BRepAlgoAPI_Check(wrapped)),
    ):
        try:
            chk = make()
            chk.Perform()
            return {"available": True, "pattern": pattern,
                    "has_errors": bool(chk.HasErrors()),
                    "is_valid": bool(chk.IsValid())}
        except Exception:
            continue
    return {"available": False,
            "error": "no constructor pattern accepted by the installed "
                     "OCP binding"}


def run_freeform_integrity(shape: Any) -> dict[str, Any]:
    """Validate one kernel solid. Returns the persistable report dict."""
    import numpy as np
    import trimesh
    from OCP.BRepCheck import BRepCheck_Analyzer
    from trimesh import grouping

    checks: list[dict[str, Any]] = []

    analyzer_ok = bool(BRepCheck_Analyzer(shape.wrapped).IsValid())
    checks.append(_check(
        "occ_analyzer_valid",
        status="pass" if analyzer_ok else "fail",
        value=analyzer_ok, limit=True, units=None,
        basis="OpenCASCADE BRepCheck_Analyzer on the built solid",
        message="the kernel's own validity analyzer must accept the shape"))

    sc = occ_self_interference(shape.wrapped)
    if not sc.get("available"):
        checks.append(_check(
            "occ_self_interference", status="needs_input",
            value=sc.get("error"), limit=None, units=None,
            basis="OCP BRepAlgoAPI_Check (self-interference test)",
            message="the self-interference check could not run on this "
                    "binding — indeterminate, fails closed"))
    elif sc["has_errors"]:
        checks.append(_check(
            "occ_self_interference", status="fail",
            value="HasErrors=True", limit="no errors", units=None,
            basis=f"BRepAlgoAPI_Check pattern {sc['pattern']}",
            message="OCC reports interference/errors on the shape"))
    elif sc["is_valid"] is False:
        checks.append(_check(
            "occ_self_interference", status="needs_input",
            value="IsValid=False, HasErrors=False", limit="IsValid=True",
            units=None,
            basis=f"BRepAlgoAPI_Check pattern {sc['pattern']}",
            message="INDETERMINATE verdict (measured possible on this "
                    "binding, ADR-064) — fails closed, not read as proof "
                    "of self-intersection"))
    else:
        checks.append(_check(
            "occ_self_interference", status="pass",
            value="IsValid=True, HasErrors=False", limit="IsValid=True",
            units=None,
            basis=f"BRepAlgoAPI_Check pattern {sc['pattern']}",
            message="no self-interference reported"))

    solid_count = len(shape.solids())
    checks.append(_check(
        "body_count", status="pass" if solid_count == 1 else "fail",
        value=solid_count, limit=1, units="bodies",
        basis="kernel solid census",
        message="a free-form element must be one solid body"))

    kernel_volume = float(shape.volume)
    verts, tris = shape.tessellate(tolerance=1.0, angular_tolerance=0.1)
    mesh = trimesh.Trimesh(
        vertices=np.array([[v.X, v.Y, v.Z] for v in verts]),
        faces=np.array(tris), process=True)
    mesh.merge_vertices()

    watertight = bool(mesh.is_watertight)
    checks.append(_check(
        "tessellation_watertight",
        status="pass" if watertight else "fail",
        value=watertight, limit=True, units=None,
        basis="1.0 mm deflection tessellation, exact-merge weld, trimesh",
        message="the welded tessellation must close"))
    winding = bool(mesh.is_winding_consistent)
    checks.append(_check(
        "tessellation_winding",
        status="pass" if winding else "fail",
        value=winding, limit=True, units=None,
        basis="trimesh winding consistency",
        message="face winding must be consistent"))

    _, edge_counts = np.unique(np.sort(mesh.edges, axis=1), axis=0,
                               return_counts=True)
    bad_edges = int((edge_counts != 2).sum())
    checks.append(_check(
        "boundary_or_nonmanifold_edges",
        status="pass" if bad_edges == 0 else "fail",
        value=bad_edges, limit=0, units="edges",
        basis="edge-incidence census (networkx-free)",
        message="every edge must belong to exactly two faces"))

    dup_pairs = int(len(grouping.group_rows(np.sort(mesh.faces, axis=1),
                                            require_count=2)))
    checks.append(_check(
        "duplicate_faces", status="pass" if dup_pairs == 0 else "fail",
        value=dup_pairs, limit=0, units="face pairs",
        basis="sorted-face duplicate census",
        message="no coincident duplicate faces"))

    if kernel_volume > 0:
        rel = abs(float(mesh.volume) - kernel_volume) / kernel_volume
        checks.append(_check(
            "volume_cross_check",
            status="pass" if rel <= REL_VOL_TOL else "fail",
            value=round(rel, 5), limit=REL_VOL_TOL, units="relative",
            basis=f"|kernel {kernel_volume:.1f} - mesh "
                  f"{float(mesh.volume):.1f}| / kernel (mm^3)",
            message="independent tessellation volume must agree with the "
                    "kernel"))
    else:
        checks.append(_check(
            "volume_cross_check", status="fail",
            value=round(kernel_volume, 3), limit="> 0", units="mm^3",
            basis="kernel volume",
            message="a zero/negative kernel volume is a silent boolean "
                    "failure (measured class, ADR-064)"))

    genus = None
    if watertight:
        genus = int((2 * int(mesh.body_count) - int(mesh.euler_number)) // 2)
    checks.append(_check(
        "genus", status="pass" if genus is not None else "needs_input",
        value=genus, limit=None, units=None,
        basis="Euler characteristic of the welded tessellation",
        message="void topology (informational value; computable only on a "
                "closed mesh)"))

    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        status = "fail"
    elif "needs_input" in statuses:
        status = "needs_input"
    else:
        status = "pass"
    return {
        "schema": _SCHEMA,
        "gate_name": FREEFORM_INTEGRITY_GATE,
        "status": status,
        "checks": checks,
    }
