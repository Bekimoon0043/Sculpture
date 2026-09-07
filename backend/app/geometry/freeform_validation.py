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
  tessellation_watertight  0.5 mm deflection, exact-weld, trimesh
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


def _mesh_boundary_topology(mesh) -> dict[str, Any] | None:
    """Per-boundary-component topology of the welded tessellation —
    networkx/scipy-free (neither is on the pinned image, ADR-064).

    Components are edge-connected face groups. Per component:
    Euler characteristic V - E + F, genus (2 - chi)/2, and the SIGNED
    enclosed volume under the mesh's consistent winding — a closed
    internal cavity surface encloses NEGATIVE volume, which is how
    cavities are counted without any point-containment dependency.
    Components are reported sorted by |volume| descending (outer skin
    first). Returns None when the mesh is not watertight (no closed
    topology to speak of)."""
    import numpy as np

    if not mesh.is_watertight:
        return None
    faces = np.asarray(mesh.faces, dtype=np.int64)
    verts = np.asarray(mesh.vertices, dtype=float)
    n_faces = len(faces)
    edges = np.sort(
        np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                        faces[:, [2, 0]]]), axis=1)
    _, edge_ids = np.unique(edges, axis=0, return_inverse=True)
    face_idx = np.tile(np.arange(n_faces), 3)

    parent = np.arange(n_faces)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return int(i)

    first_face: dict[int, int] = {}
    for k in range(len(edge_ids)):
        e = int(edge_ids[k])
        f = int(face_idx[k])
        if e in first_face:
            ra, rb = find(first_face[e]), find(f)
            if ra != rb:
                parent[rb] = ra
        else:
            first_face[e] = f

    roots = np.array([find(i) for i in range(n_faces)])
    components = []
    for root in np.unique(roots):
        fmask = roots == root
        cf = faces[fmask]
        vids = np.unique(cf)
        ce = np.sort(np.concatenate(
            [cf[:, [0, 1]], cf[:, [1, 2]], cf[:, [2, 0]]]), axis=1)
        n_e = len(np.unique(ce, axis=0))
        chi = int(len(vids)) - n_e + int(fmask.sum())
        genus = (2 - chi) // 2
        a = verts[cf[:, 0]]
        b = verts[cf[:, 1]]
        c = verts[cf[:, 2]]
        signed_vol = float(np.einsum(
            "ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
        components.append({
            "faces": int(fmask.sum()), "euler": chi, "genus": int(genus),
            "signed_volume_mm3": round(signed_vol, 1),
        })
    components.sort(key=lambda comp: -abs(comp["signed_volume_mm3"]))
    cavities = sum(1 for comp in components
                   if comp["signed_volume_mm3"] < 0)
    outer_genus = components[0]["genus"] if components else None
    return {
        "boundary_components": len(components),
        "closed_internal_cavities": cavities,
        "per_component_genus": [comp["genus"] for comp in components],
        "per_component_euler": [comp["euler"] for comp in components],
        "through_openings": outer_genus,
        "components": components,
        "basis": ("edge-connected face components of the welded "
                  "tessellation; cavity = negative signed volume under "
                  "consistent winding; through-openings = genus of the "
                  "outer (largest |volume|) component"),
    }


def run_freeform_integrity(
    shape: Any,
    expected_topology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one kernel solid. Returns the persistable report dict.

    ``expected_topology`` (FF-A2, ADR-066): the primitive's declared
    per-component contract, persisted with the manifest and passed back
    from that snapshot. When present, every mismatch is a FAIL — wrong
    topology is defective geometry and refuses export for applicable
    designs (ADR-065 decision 5). When absent, the measured topology is
    reported informationally (FF-A1 behavior unchanged)."""
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
    # Instrument refined (1.0, 0.1 rad) -> (0.5, 0.05 rad) — ADR-066,
    # measured 2026-09-05: the 0.1 rad ANGULAR tolerance dominated on
    # curved shells (~0.6 mm sagitta at R=500), producing a 1-2.5 %
    # kernel-vs-mesh volume gap that did not converge with deflection
    # alone; at (0.5, 0.05) the default lens agrees to 0.23 % and the
    # 5.0 m envelope to well under 1 %. Strictly finer in both knobs —
    # harder to fool; REL_VOL_TOL is untouched.
    verts, tris = shape.tessellate(tolerance=0.5, angular_tolerance=0.05)
    mesh = trimesh.Trimesh(
        vertices=np.array([[v.X, v.Y, v.Z] for v in verts]),
        faces=np.array(tris), process=True)
    mesh.merge_vertices()

    watertight = bool(mesh.is_watertight)
    checks.append(_check(
        "tessellation_watertight",
        status="pass" if watertight else "fail",
        value=watertight, limit=True, units=None,
        basis="0.5 mm deflection tessellation, exact-merge weld, trimesh",
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

    # FF-A2 (ADR-066): the explicit per-boundary-component topology
    # contract. With a declared expectation every mismatch FAILS; with
    # none the measurement is informational (FF-A1 rows unchanged).
    topo = _mesh_boundary_topology(mesh)
    if expected_topology:
        if topo is None:
            checks.append(_check(
                "boundary_component_topology", status="needs_input",
                value=None, limit=expected_topology, units=None,
                basis="per-component topology of the welded tessellation",
                message="topology contract declared but the mesh is not "
                        "closed — indeterminate, fails closed"))
        else:
            for key in ("boundary_components", "closed_internal_cavities",
                        "per_component_genus", "per_component_euler",
                        "through_openings"):
                expected = expected_topology.get(key)
                measured = topo.get(key)
                checks.append(_check(
                    f"topology_{key}",
                    status="pass" if measured == expected else "fail",
                    value=measured, limit=expected, units=None,
                    basis=topo["basis"],
                    message=f"{key} must match the primitive's declared "
                            "topology contract (ADR-066)"))
            extras = max(
                0, topo["boundary_components"]
                - int(expected_topology.get("boundary_components", 0)))
            checks.append(_check(
                "topology_accidental_extra_bodies_or_voids",
                status="pass" if extras == int(expected_topology.get(
                    "accidental_extra_bodies_or_voids", 0)) else "fail",
                value=extras,
                limit=expected_topology.get(
                    "accidental_extra_bodies_or_voids", 0),
                units="components", basis=topo["basis"],
                message="no boundary components beyond the declared "
                        "contract"))
    elif topo is not None:
        checks.append(_check(
            "boundary_component_topology", status="pass",
            value={k: topo[k] for k in (
                "boundary_components", "closed_internal_cavities",
                "per_component_genus", "per_component_euler",
                "through_openings")},
            limit=None, units=None, basis=topo["basis"],
            message="measured per-component topology (informational — "
                    "no contract declared)"))

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
