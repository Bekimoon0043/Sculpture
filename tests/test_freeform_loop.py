"""FF-A2 (ADR-066): freeform_loop primitive contract — red-first.

The owner-approved hollow-lens + walled-window-bore construction
(2026-09-04 delta): 316L-only refusals, the hard 3500-5000 mm scale,
wall/embedment/ligament arithmetic, bore-corridor refusals with real
numbers, watertight single-solid construction, determinism, and the
hard width/height envelope band. The failed tube-annulus construction
is development evidence in ADR-066, not capability, and is asserted
ABSENT here.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")

from app.geometry.primitives import PRIMITIVES, freeform_loop  # noqa: E402
from app.geometry.primitives.base import ConstraintViolation  # noqa: E402

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "freeform_loop_spec_v1.json")
    .read_text())
DEFAULTS = FIXTURE["elements"][0]["parameters"]

LANDMARKS = json.loads(
    (Path(__file__).parent.parent / "briefs" / "freeform_references"
     / "ref08_landmarks.json").read_text())


def validate(**overrides):
    raw = dict(DEFAULTS)
    raw.update(overrides)
    return freeform_loop.validate(raw, None)


@pytest.fixture(scope="module")
def default_solid():
    return freeform_loop.build(validate())


# ---------------------------------------------------------------------------
# registry + declarations
# ---------------------------------------------------------------------------

class TestRegistryAndDeclarations:
    def test_registered_as_the_eleventh(self):
        # The exact-set assertion lives ONLY in gate_ffa2_auto.py (ADR-066
        # ruling); a duplicate here would expire the day slice D widens the
        # registry (D-10, PR-5 sweep). Here: present, and at least eleven.
        assert "freeform_loop" in PRIMITIVES
        assert len(PRIMITIVES) >= 11

    def test_not_in_the_frozen_legacy_ten(self):
        from app.geometry.mass_model import LEGACY_COMPLETE_MASS_PRIMITIVES
        assert "freeform_loop" not in LEGACY_COMPLETE_MASS_PRIMITIVES
        assert len(LEGACY_COMPLETE_MASS_PRIMITIVES) == 10

    def test_ffa1_declarations_present(self):
        assert freeform_loop.REQUIRES_FREEFORM_INTEGRITY is True
        assert len(freeform_loop.INCOMPLETE_MASS_INPUTS) == 3
        for item in freeform_loop.INCOMPLETE_MASS_INPUTS:
            assert "FABRICATOR-INPUT-REQUIRED" in item

    def test_topology_contract_is_the_approved_values(self):
        assert freeform_loop.EXPECTED_TOPOLOGY == {
            "kernel_solids": 1, "through_openings": 1,
            "boundary_components": 2, "closed_internal_cavities": 1,
            "per_component_genus": [1, 1], "per_component_euler": [0, 0],
            "accidental_extra_bodies_or_voids": 0,
        }

    def test_tube_annulus_construction_is_gone(self):
        """The failed development construction must not survive as
        callable capability (owner ruling, option A)."""
        for name in ("_closed_loop", "_half_loft", "_fold_check",
                     "_centerline_point", "taper_ratio"):
            assert not hasattr(freeform_loop, name), name
        assert "taper_ratio" not in freeform_loop.PARAMETERS
        assert "section_major_mm" not in freeform_loop.PARAMETERS

    def test_bore_center_parameter_renamed(self):
        """Owner clarification 1."""
        assert "bore_center_height_fraction" in freeform_loop.PARAMETERS
        assert "bore_height_fraction" not in freeform_loop.PARAMETERS


# ---------------------------------------------------------------------------
# 316L-only (owner ruling)
# ---------------------------------------------------------------------------

class TestMaterialRule:
    @pytest.mark.parametrize("mat", [
        "basalt_slab", "cast_concrete_c35_45", "bronze_cast"])
    def test_other_materials_refuse_by_name(self, mat):
        with pytest.raises(ConstraintViolation) as exc:
            validate(material_id=mat)
        text = "; ".join(exc.value.violations)
        assert mat in text
        assert "UNBUILT" in text
        assert "prototype manufacturing hypothesis" in text

    def test_316l_is_the_only_supported_material(self):
        assert freeform_loop.SUPPORTED_MATERIAL == "stainless_316l_sheet"
        assert validate().material_id == "stainless_316l_sheet"


# ---------------------------------------------------------------------------
# owner scale + wall arithmetic
# ---------------------------------------------------------------------------

class TestScaleAndWall:
    def test_height_floor_3500_refuses_3499(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(height_mm=3499, width_mm=2100)
        assert "3500" in str(exc.value)

    def test_height_ceiling_5000_refuses_5001(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(height_mm=5001, width_mm=3100)
        assert "5000" in str(exc.value)

    def test_wall_5_999_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(wall_mm=5.999)
        assert "6" in str(exc.value)

    def test_embedment_and_ligament_constants(self):
        assert freeform_loop.EMBEDMENT_MM == 3.0
        assert freeform_loop.MIN_LIGAMENT_MM == 3.0
        assert freeform_loop.PARAMETERS["wall_mm"]["min"] == 6

    def test_width_height_band_hard_low(self):
        # height=5000, width=1680 -> ratio 0.336 < 0.48 (operator case)
        with pytest.raises(ConstraintViolation) as exc:
            validate(height_mm=5000, width_mm=1680)
        assert "0.336" in str(exc.value)

    def test_width_height_band_hard_high(self):
        # height=3500, width=3600 -> ratio 1.029 > 0.72 (operator case)
        with pytest.raises(ConstraintViolation) as exc:
            validate(height_mm=3500, width_mm=3600)
        assert "1.029" in str(exc.value)


# ---------------------------------------------------------------------------
# cross-parameter refusals with real numbers
# ---------------------------------------------------------------------------

class TestCrossConstraints:
    def test_depth_over_width_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(depth_mm=1800, width_mm=1750, height_mm=3500)
        assert "deeper than it is wide" in str(exc.value)

    def test_hollowability_guaranteed_by_the_published_ranges(self):
        """[arith] the ranges themselves guarantee a hollowable waist:
        depth_min 300 > 4 x wall_max 80 — the runtime check is defence
        in depth for future range edits; below the static floor pydantic
        refuses first."""
        pmin = freeform_loop.PARAMETERS
        assert pmin["depth_mm"]["min"] > 4 * pmin["wall_mm"]["max"]
        with pytest.raises(ConstraintViolation) as exc:
            validate(depth_mm=250)
        assert "300" in str(exc.value)

    def test_wobble_bound_is_height_fraction(self):
        # 0.25 x 3500 = 875 < 900 -> refuse, with both numbers printed
        with pytest.raises(ConstraintViolation) as exc:
            validate(height_mm=3500, width_mm=2100, wobble_mm=900)
        assert "875" in str(exc.value)

    def test_bore_corridor_must_fit_the_lens(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(bore_width_mm=2000, bore_height_mm=2500)
        assert "corridor" in str(exc.value)

    def test_bore_offset_can_break_the_corridor(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(plan_skew_ratio=0.30, bore_width_mm=1600)
        assert "corridor" in str(exc.value)

    def test_plate_floor_refuses_small_plate(self):
        # a low waist fattens the tip chord so the derived floor
        # exceeds the static minimum
        p_ok = validate(waist_height_fraction=0.25)
        floor = freeform_loop.plate_diameter_floor_mm(p_ok)
        assert floor > 150.0
        with pytest.raises(ConstraintViolation) as exc:
            validate(waist_height_fraction=0.25,
                     base_plate_diameter_mm=150)
        assert f"{floor:.1f}" in str(exc.value)


# ---------------------------------------------------------------------------
# construction truth (the built solid)
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_one_watertight_solid(self, default_solid):
        assert len(default_solid.solids()) == 1
        assert float(default_solid.volume) > 0.0
        assert bool(default_solid.is_valid)

    def test_shell_is_hollow_not_solid(self, default_solid):
        p = validate()
        outer = freeform_loop._lens_solid(p, 0.0)
        v_total = float(default_solid.volume)
        v_outer = float(outer.volume)
        plate = math.pi * (p.base_plate_diameter_mm / 2.0) ** 2 * p.wall_mm
        assert v_total - plate < 0.35 * v_outer, (v_total, v_outer)

    def test_seated_on_plate_with_exact_embedment(self, default_solid):
        bb = default_solid.bounding_box()
        assert float(bb.min.Z) == pytest.approx(0.0, abs=1e-6)
        p = validate()
        # tip truncation removes wall_mm; measured height within 2%
        assert float(bb.max.Z) == pytest.approx(
            p.height_mm, rel=0.02), float(bb.max.Z)

    def test_width_envelope_within_2pct(self, default_solid):
        bb = default_solid.bounding_box()
        p = validate()
        width = float(bb.max.X - bb.min.X)
        assert width == pytest.approx(p.width_mm, rel=0.02), width

    def test_determinism_same_params_same_volume_and_bbox(self):
        a = freeform_loop.build(validate())
        b = freeform_loop.build(validate())
        assert float(a.volume) == float(b.volume)
        ba, bb_ = a.bounding_box(), b.bounding_box()
        assert (ba.min.X, ba.min.Y, ba.min.Z) == (bb_.min.X, bb_.min.Y,
                                                  bb_.min.Z)
        assert (ba.max.X, ba.max.Y, ba.max.Z) == (bb_.max.X, bb_.max.Y,
                                                  bb_.max.Z)


# ---------------------------------------------------------------------------
# twist vs wobble separation (independent controls)
# ---------------------------------------------------------------------------

class TestTwistWobbleSeparation:
    def test_wobble_bows_the_spine_in_depth(self):
        p0 = validate(wobble_mm=0)
        p3 = validate(wobble_mm=300)
        assert freeform_loop._bow_mm(0.5, p0) == pytest.approx(0.0)
        assert freeform_loop._bow_mm(0.5, p3) == pytest.approx(300.0)
        # tips never displaced
        assert freeform_loop._bow_mm(0.0, p3) == pytest.approx(0.0)
        assert freeform_loop._bow_mm(1.0, p3) == pytest.approx(0.0, abs=1e-9)
        # rotation untouched by wobble
        assert freeform_loop._twist_at(0.75, p0) == \
            freeform_loop._twist_at(0.75, p3)

    def test_twist_rotates_sections_relative_top_vs_bottom(self):
        p = validate(section_twist_deg=40)
        assert freeform_loop._twist_at(0.0, p) == pytest.approx(-20.0)
        assert freeform_loop._twist_at(0.5, p) == pytest.approx(0.0)
        assert freeform_loop._twist_at(1.0, p) == pytest.approx(20.0)

    def test_twist_changes_the_built_geometry_wobble_does_not_rotate(self):
        """Actual frame rotation from geometry: twist narrows the
        silhouette width at the waist (the deep blade turns), while
        wobble alone leaves the silhouette width untouched."""
        p_t = validate(section_twist_deg=90, wobble_mm=0)
        p_0 = validate(section_twist_deg=0, wobble_mm=0)
        s_t = freeform_loop._lens_solid(p_t, 0.0)
        s_0 = freeform_loop._lens_solid(p_0, 0.0)
        w_t = float(s_t.bounding_box().size.X)
        w_0 = float(s_0.bounding_box().size.X)
        assert w_t < w_0, (w_t, w_0)
        p_w = validate(section_twist_deg=0, wobble_mm=600)
        s_w = freeform_loop._lens_solid(p_w, 0.0)
        assert float(s_w.bounding_box().size.X) == pytest.approx(w_0,
                                                                 rel=1e-6)
        assert float(s_w.bounding_box().size.Y) > \
            float(s_0.bounding_box().size.Y)


# ---------------------------------------------------------------------------
# hard landmark band wiring
# ---------------------------------------------------------------------------

class TestLandmarkWiring:
    def test_band_values_match_the_committed_record(self):
        hard = LANDMARKS["bands"]["hard_runtime_constraints"]
        assert list(freeform_loop.WIDTH_HEIGHT_BAND) == \
            hard["width_height_ratio"]["band"]

    def test_landmark_source_image_identity(self):
        src = LANDMARKS["source_image"]
        assert src["sha256"] == ("bfe1662b587807b50e6654e756563fa7b35244"
                                 "15767db3cfb8573a34c3f87a02")
        assert (src["width_px"], src["height_px"]) == (1280, 959)
