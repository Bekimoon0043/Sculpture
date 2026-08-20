"""Mesh validation — trimesh reads the exported GLB and reports REAL numbers.

trimesh is used for VALIDATION only (its strength); geometry is built by
build123d and exported natively (ADR-010). Every check prints/persists its
real measured number — never a bare boolean (build order §7).

Cross-check: trimesh's integrated volume must agree with the build123d
solid's exact B-rep volume within VOLUME_CROSSCHECK_TOLERANCE_PCT — this ties
the tessellated preview back to the canonical solid.

NOT in Phase 2: ray-based wall-thickness checks (see LIMITATIONS.md) — the
min-wall guarantee comes from the hard constraints in registry.py.
"""

from __future__ import annotations

from pathlib import Path

import trimesh
from pydantic import BaseModel

from app.core.config import Material

#: |trimesh_volume - brep_volume| / brep_volume must stay under this (%).
VOLUME_CROSSCHECK_TOLERANCE_PCT = 2.0


class VolumeCrossCheck(BaseModel):
    trimesh_volume_mm3: float
    build123d_volume_mm3: float
    delta_pct: float
    tolerance_pct: float
    within_tolerance: bool


class ValidationReport(BaseModel):
    """Every measured number from one mesh validation run."""

    glb_path: str
    material_id: str
    watertight: bool
    winding_consistent: bool
    volume_mm3: float
    surface_area_mm2: float
    euler_number: int
    bounds_mm: list[float]  # [minx, miny, minz, maxx, maxy, maxz]
    degenerate_face_count: int
    face_count: int
    # Slice A1 (plan §4): a mesh can be perfectly watertight and still be
    # TWO disjoint closed bodies — the fatal silent failure of assemblies.
    # None = report persisted before slice A1 recorded body counts (single
    # cascade solids, body count 1 by their builder's own assertion); every
    # new measurement fills it and passed requires exactly 1.
    body_count: int | None = None
    mass_kg: float
    volume_crosscheck: VolumeCrossCheck | None
    passed: bool

    def check_rows(self) -> list[dict[str, object]]:
        """One row per check, for the frontend validation panel / gate print."""
        rows: list[dict[str, object]] = [
            {"check": "watertight", "value": self.watertight,
             "passed": self.watertight is True},
            {"check": "winding_consistent", "value": self.winding_consistent,
             "passed": self.winding_consistent is True},
            {"check": "volume_mm3", "value": round(self.volume_mm3, 3),
             "passed": self.volume_mm3 > 0},
            {"check": "surface_area_mm2", "value": round(self.surface_area_mm2, 3),
             "passed": self.surface_area_mm2 > 0},
            {"check": "euler_number", "value": self.euler_number, "passed": True},
            {"check": "bounds_mm", "value": [round(v, 3) for v in self.bounds_mm],
             "passed": True},
            {"check": "degenerate_face_count", "value": self.degenerate_face_count,
             "passed": self.degenerate_face_count == 0},
            {"check": "mass_kg", "value": round(self.mass_kg, 3),
             "passed": self.mass_kg > 0},
        ]
        if self.body_count is not None:
            rows.insert(2, {"check": "body_count", "value": self.body_count,
                            "passed": self.body_count == 1})
        if self.volume_crosscheck is not None:
            cc = self.volume_crosscheck
            rows.append({
                "check": "volume_crosscheck",
                "value": (
                    f"trimesh {cc.trimesh_volume_mm3:.3f} vs brep "
                    f"{cc.build123d_volume_mm3:.3f} mm3 "
                    f"(delta {cc.delta_pct:.4f}% of {cc.tolerance_pct:g}%)"
                ),
                "passed": cc.within_tolerance,
            })
        return rows


def validate_mesh(
    glb_path: str | Path,
    material: Material,
    material_id: str = "",
    reference_volume_mm3: float | None = None,
) -> ValidationReport:
    """Load the GLB with trimesh and measure everything.

    GLB frame (verified against the installed build123d 0.11.1 exporter):
    glTF is always METERS and Y-up. This function converts back to the CAD
    frame (mm, Z-up) before measuring, so every reported number is in the
    same units as the rest of the platform (Rule 6).

    merge_vertices() is applied after loading: the exporter writes one mesh
    patch per B-rep face with DUPLICATED vertices along shared edges (a
    tessellation-storage artifact), which would make trimesh's edge-manifold
    watertight check meaningless. Deduplicating coincident vertices is not
    geometry repair — no vertex moves, no face changes; the underlying solid
    is watertight by construction (Rule 6) and the check stays honest.

    reference_volume_mm3: the build123d B-rep volume; when given, the 2%
    volume cross-check is computed and included with BOTH numbers.
    """
    glb_path = Path(glb_path)
    mesh = _load_measured_mesh(glb_path)

    volume_mm3 = float(mesh.volume)
    # mm3 -> m3 is 1e-9; mass = volume[m3] * density[kg/m3]
    mass_kg = volume_mm3 * 1e-9 * material.density_kg_per_m3
    degenerate = int((mesh.area_faces <= 1e-9).sum())

    # Bounds in the CAD frame: glTF (x, y, z) = CAD (X, Z, -Y).
    g = mesh.bounds  # glTF frame, now in mm
    bounds_mm = [
        float(g[0][0]), float(-g[1][2]), float(g[0][1]),  # CAD min: X, Y, Z
        float(g[1][0]), float(-g[0][2]), float(g[1][1]),  # CAD max: X, Y, Z
    ]

    crosscheck: VolumeCrossCheck | None = None
    if reference_volume_mm3 is not None:
        delta_pct = abs(volume_mm3 - reference_volume_mm3) / reference_volume_mm3 * 100
        crosscheck = VolumeCrossCheck(
            trimesh_volume_mm3=volume_mm3,
            build123d_volume_mm3=float(reference_volume_mm3),
            delta_pct=delta_pct,
            tolerance_pct=VOLUME_CROSSCHECK_TOLERANCE_PCT,
            within_tolerance=delta_pct <= VOLUME_CROSSCHECK_TOLERANCE_PCT,
        )

    body_count = int(mesh.body_count)
    passed = (
        bool(mesh.is_watertight)
        and bool(mesh.is_winding_consistent)
        and volume_mm3 > 0
        and degenerate == 0
        and body_count == 1
        and (crosscheck is None or crosscheck.within_tolerance)
    )

    return ValidationReport(
        glb_path=str(glb_path),
        material_id=material_id,
        watertight=bool(mesh.is_watertight),
        winding_consistent=bool(mesh.is_winding_consistent),
        volume_mm3=volume_mm3,
        surface_area_mm2=float(mesh.area),
        euler_number=int(mesh.euler_number),
        bounds_mm=bounds_mm,
        degenerate_face_count=degenerate,
        face_count=int(len(mesh.faces)),
        body_count=body_count,
        mass_kg=mass_kg,
        volume_crosscheck=crosscheck,
        passed=passed,
    )


def _load_measured_mesh(glb_path: Path) -> trimesh.Trimesh:
    """Load a GLB into the CAD frame (mm) with seam vertices deduped.

    merge_vertices() is not repair (see validate_mesh docstring): the
    exporter writes one mesh patch per B-rep face with duplicated seam
    vertices, and only the deduped mesh gives meaningful watertight and
    body-count answers (ADR-029 method note).
    """
    mesh = trimesh.load(str(glb_path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{glb_path} did not load as a non-empty triangle mesh")
    mesh.apply_scale(1000.0)  # glTF meters -> CAD millimetres
    mesh.merge_vertices()     # dedupe per-face-patch seam vertices
    return mesh


class AssemblyValidationReport(BaseModel):
    """Assembly-level validation: the fused mesh PLUS what only an assembly
    needs (plan §4) — body count at mesh level, per-element mass breakdown
    from the manifest (exact B-rep volume x each element's OWN material
    density; a fused mesh has no single material, so a single mass_kg would
    be fiction for mixed-material assemblies), and the cross-check of the
    mesh volume against the manifest's exact fused B-rep volume."""

    glb_path: str
    element_count: int
    joint_count: int
    watertight: bool
    winding_consistent: bool
    body_count: int
    volume_mm3: float
    surface_area_mm2: float
    degenerate_face_count: int
    face_count: int
    element_masses_kg: dict[str, float]
    total_mass_kg: float
    volume_crosscheck: VolumeCrossCheck
    passed: bool

    def check_rows(self) -> list[dict[str, object]]:
        cc = self.volume_crosscheck
        return [
            {"check": "watertight", "value": self.watertight,
             "passed": self.watertight is True},
            {"check": "winding_consistent", "value": self.winding_consistent,
             "passed": self.winding_consistent is True},
            {"check": "body_count", "value": self.body_count,
             "passed": self.body_count == 1},
            {"check": "volume_mm3", "value": round(self.volume_mm3, 3),
             "passed": self.volume_mm3 > 0},
            {"check": "surface_area_mm2", "value": round(self.surface_area_mm2, 3),
             "passed": self.surface_area_mm2 > 0},
            {"check": "degenerate_face_count", "value": self.degenerate_face_count,
             "passed": self.degenerate_face_count == 0},
            {"check": "element_masses_kg",
             "value": {k: round(v, 3) for k, v in self.element_masses_kg.items()},
             "passed": all(v > 0 for v in self.element_masses_kg.values())},
            {"check": "total_mass_kg", "value": round(self.total_mass_kg, 3),
             "passed": self.total_mass_kg > 0},
            {"check": "volume_crosscheck",
             "value": (
                 f"trimesh {cc.trimesh_volume_mm3:.3f} vs brep "
                 f"{cc.build123d_volume_mm3:.3f} mm3 "
                 f"(delta {cc.delta_pct:.4f}% of {cc.tolerance_pct:g}%)"
             ),
             "passed": cc.within_tolerance},
        ]


def validate_assembly(glb_path: str | Path, manifest: dict) -> AssemblyValidationReport:
    """Measure the fused assembly GLB against its manifest.

    ``manifest`` is what registry.assemble returned: per-element exact B-rep
    volumes and masses, the fused B-rep volume, and the joint list. The
    B-rep-level guarantees (per-joint interference, volume conservation,
    fabrication limits) were already enforced INSIDE assemble — this
    function proves the tessellated artifact tells the same story: one
    watertight body whose mesh volume agrees with the exact fused volume.
    """
    glb_path = Path(glb_path)
    mesh = _load_measured_mesh(glb_path)

    volume_mm3 = float(mesh.volume)
    reference = float(manifest["volume_conservation"]["assembly_volume_mm3"])
    delta_pct = abs(volume_mm3 - reference) / reference * 100
    crosscheck = VolumeCrossCheck(
        trimesh_volume_mm3=volume_mm3,
        build123d_volume_mm3=reference,
        delta_pct=delta_pct,
        tolerance_pct=VOLUME_CROSSCHECK_TOLERANCE_PCT,
        within_tolerance=delta_pct <= VOLUME_CROSSCHECK_TOLERANCE_PCT,
    )

    degenerate = int((mesh.area_faces <= 1e-9).sum())
    body_count = int(mesh.body_count)
    element_masses = {
        el["element_id"]: float(el["mass_kg"]) for el in manifest["elements"]
    }

    passed = (
        bool(mesh.is_watertight)
        and bool(mesh.is_winding_consistent)
        and body_count == 1
        and volume_mm3 > 0
        and degenerate == 0
        and crosscheck.within_tolerance
    )

    return AssemblyValidationReport(
        glb_path=str(glb_path),
        element_count=len(manifest["elements"]),
        joint_count=len(manifest["joints"]),
        watertight=bool(mesh.is_watertight),
        winding_consistent=bool(mesh.is_winding_consistent),
        body_count=body_count,
        volume_mm3=volume_mm3,
        surface_area_mm2=float(mesh.area),
        degenerate_face_count=degenerate,
        face_count=int(len(mesh.faces)),
        element_masses_kg=element_masses,
        total_mass_kg=float(manifest["total_mass_kg"]),
        volume_crosscheck=crosscheck,
        passed=passed,
    )
