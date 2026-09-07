"""FF-A2 (ADR-066): red-first calibration of the brepextrema_v1 wall
measurement — v4 amendment 5.

The method may report measured thickness ONLY because these controls
prove it reproduces KNOWN walls within the stated tolerance —
max(±0.5 mm, ±5%), the recorded 316L per-face cut/form tolerance — on:
  * a flat-walled hollow box,
  * a CURVED hollow shell (sphere),
  * a closed-end / base-plate condition (box shell fused with a plate
    at the 3 mm embedment, exercising the junction-exclusion rule).
Zero-distance seam/end-face artifacts must degrade to `unavailable`,
never to a number. The nominal construction parameter is never labeled
verified wall thickness anywhere.
"""

from __future__ import annotations

import types

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")

from build123d import Box, Cylinder, Pos, Sphere  # noqa: E402

from app.geometry.primitives import freeform_loop  # noqa: E402


def tolerance_mm(nominal: float) -> float:
    return max(0.5, 0.05 * nominal)


def fake_params(plate_d: float = 600.0, wall: float = 6.0):
    return types.SimpleNamespace(base_plate_diameter_mm=plate_d,
                                 wall_mm=wall)


class TestControls:
    def test_flat_box_shell_wall_6(self):
        shell = Box(400, 400, 400) - Box(388, 388, 388)
        block = freeform_loop.measure_wall(fake_params(plate_d=0.0), shell)
        assert block["status"] == "measured", block
        tol = tolerance_mm(6.0)
        assert abs(block["min_mm"] - 6.0) <= tol, block
        assert abs(block["max_mm"] - 6.0) <= tol, block

    def test_curved_sphere_shell_wall_8(self):
        shell = Sphere(200) - Sphere(192)
        block = freeform_loop.measure_wall(fake_params(plate_d=0.0,
                                                       wall=8.0), shell)
        assert block["status"] == "measured", block
        tol = tolerance_mm(8.0)
        assert abs(block["min_mm"] - 8.0) <= tol, block
        assert abs(block["max_mm"] - 8.0) <= tol, block

    def test_closed_end_plate_condition(self):
        """Box shell standing on a fused plate with 3 mm embedment: the
        junction-exclusion rule must keep the plate out of the max and
        the measured wall must stay the known 6 mm."""
        wall = 6.0
        shell = Pos(0, 0, wall - 3.0 + 200.0) * (
            Box(400, 400, 400) - Box(388, 388, 388))
        plate = Pos(0, 0, wall / 2.0) * Cylinder(300.0, wall)
        fused = shell + plate
        assert len(fused.solids()) == 1
        block = freeform_loop.measure_wall(
            fake_params(plate_d=600.0, wall=wall), fused)
        assert block["status"] == "measured", block
        tol = tolerance_mm(wall)
        assert abs(block["min_mm"] - wall) <= tol, block
        assert abs(block["max_mm"] - wall) <= tol, block
        assert block["junction_excluded"] > 0, (
            "the plate zone must actually exclude samples")


class TestHonestDegradation:
    def test_solid_without_cavity_is_unavailable(self):
        block = freeform_loop.measure_wall(fake_params(), Box(100, 100, 100))
        assert block["status"] == "unavailable"
        assert "component" in block["reason"]

    def test_no_verified_wall_claim_in_the_module(self):
        """The forbidden phrase is asserted ABSENT from the primitive
        and its measurement path (runtime-assembled token so this test
        never trips itself)."""
        import inspect

        forbidden = "verified " + "wall"
        source = inspect.getsource(freeform_loop).lower()
        for line in source.splitlines():
            if forbidden in line and "never" not in line and \
                    "not" not in line:
                raise AssertionError(f"claim found: {line.strip()}")


class TestGateRule:
    """The v4 §3 acceptance rule as the fabrication gate applies it."""

    def setup_method(self):
        from app.core.config import (DEFAULT_GATE_PROFILE_ID,
                                     load_config_bundle)
        bundle = load_config_bundle()
        self.profiles = bundle.gate_profiles
        self.profile = self.profiles.profile(DEFAULT_GATE_PROFILE_ID)
        self.profile_id = DEFAULT_GATE_PROFILE_ID
        self.materials = bundle.materials.materials

    def run_gate(self, wm_block, nominal=6.0):
        from app.geometry import gates as gates_mod
        manifest = {
            "elements": [{
                "element_id": "loop_01", "primitive": "freeform_loop",
                "material_id": "stainless_316l_sheet",
                "parameters": {"wall_mm": nominal},
                "mass_kg": 700.0, "bbox_mm": [2569.0, 2268.0, 4250.0],
                "wall_measurement": wm_block,
                "mass_model": {
                    "mass_complete": False,
                    "known_geometry_mass_kg": 700.0,
                    "missing_mass_inputs": ["armature mass "
                                            "(FABRICATOR-INPUT-REQUIRED)"],
                    "total_mass_kg": None,
                },
            }],
            "joints": [],
            "fabrication_limits": {"max_lift_kg": 3000.0,
                                   "max_module_m": None},
        }
        report = gates_mod.validate_fabrication_gate(
            manifest, self.materials, profile=self.profile,
            profile_id=self.profile_id, version=self.profiles.version)
        return {c.check: c for c in report.checks}

    def test_measured_in_tolerance_passes_geometric_row_only(self):
        rows = self.run_gate({
            "method": "brepextrema_v1", "status": "measured",
            "min_mm": 5.98, "max_mm": 6.03, "samples": 200,
            "junction_excluded": 12, "junction_max_mm": 9.0,
            "junction_basis": "plate zone",
            "bore_to_cavity_mm": 7.978, "bore_face_count": 1,
            "bore_basis": "measured BRepExtrema clearance"})
        geo = rows["loop_01.geometric_wall_measurement"]
        assert geo.status == "pass"
        assert "NEVER fabrication approval" in geo.message
        # owner clarification 2: the measured clearance passes here
        bore = rows["loop_01.bore_to_cavity_clearance"]
        assert bore.status == "pass"
        assert bore.value == 7.978
        # the two professional rows stay unresolved regardless
        assert rows["loop_01.fabrication_wall_approval"].status == \
            "needs_input"
        forming = rows["loop_01.forming_radius_mm"]
        assert forming.status == "needs_input"
        assert "FABRICATOR-INPUT-REQUIRED" in forming.message

    def test_bore_too_close_to_cavity_FAILS_not_needs_input(self):
        """Owner clarification 2: below wall − 0.5 the clearance FAILS."""
        rows = self.run_gate({
            "method": "brepextrema_v1", "status": "measured",
            "min_mm": 5.98, "max_mm": 6.03, "samples": 200,
            "junction_excluded": 0, "junction_max_mm": 0.0,
            "junction_basis": "plate zone",
            "bore_to_cavity_mm": 4.9, "bore_face_count": 1,
            "bore_basis": "measured BRepExtrema clearance"})
        bore = rows["loop_01.bore_to_cavity_clearance"]
        assert bore.status == "fail"
        assert bore.value == 4.9
        assert bore.limit == 5.5

    def test_thin_shell_cannot_pass_on_the_material_floor(self):
        """Operator case: nominal 6 measured 3.1 >= floor 3 must NOT
        pass."""
        rows = self.run_gate({
            "method": "brepextrema_v1", "status": "measured",
            "min_mm": 3.1, "max_mm": 6.0, "samples": 200,
            "junction_excluded": 0, "junction_max_mm": 0.0,
            "junction_basis": "plate zone"})
        geo = rows["loop_01.geometric_wall_measurement"]
        assert geo.status == "needs_input"
        assert "3.1" in geo.basis

    def test_unavailable_is_needs_input(self):
        rows = self.run_gate({"method": "brepextrema_v1",
                              "status": "unavailable",
                              "reason": "zero-distance artifact"})
        geo = rows["loop_01.geometric_wall_measurement"]
        assert geo.status == "needs_input"
        assert "zero-distance artifact" in geo.basis

    def test_legacy_manifest_grows_no_wall_rows(self):
        from app.geometry import gates as gates_mod
        manifest = {
            "elements": [{
                "element_id": "p1", "primitive": "plinth",
                "material_id": "basalt_slab",
                "parameters": {"wall_mm": 120.0},
                "mass_kg": 900.0, "bbox_mm": [2000.0, 2000.0, 400.0],
            }],
            "joints": [],
            "fabrication_limits": {"max_lift_kg": 3000.0,
                                   "max_module_m": None},
        }
        report = gates_mod.validate_fabrication_gate(
            manifest, self.materials, profile=self.profile,
            profile_id=self.profile_id, version=self.profiles.version)
        names = {c.check for c in report.checks}
        assert not any("geometric_wall_measurement" in n for n in names)
        assert not any("fabrication_wall_approval" in n for n in names)
        assert not any("forming_radius" in n for n in names)
