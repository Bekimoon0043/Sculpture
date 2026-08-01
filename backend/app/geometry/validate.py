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
    mesh = trimesh.load(str(glb_path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{glb_path} did not load as a non-empty triangle mesh")
    mesh.apply_scale(1000.0)  # glTF meters -> CAD millimetres
    mesh.merge_vertices()     # dedupe per-face-patch seam vertices (see docstring)

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

    passed = (
        bool(mesh.is_watertight)
        and bool(mesh.is_winding_consistent)
        and volume_mm3 > 0
        and degenerate == 0
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
        mass_kg=mass_kg,
        volume_crosscheck=crosscheck,
        passed=passed,
    )
