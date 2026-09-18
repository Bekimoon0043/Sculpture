"""SC-A1: crescent_ring primitive contract — red-first.

The vertical partial-torus crescent: a circular arc swept with a circular
(or elliptically squashed) tube section, standing on its lowest tube point
— the outer form of a mirror-polished "moon crescent" sculpture. What this
file proves: exact thirteenth registration (owner-ordered for SC-A1); the
two-material allowed set (stainless_316l_cast NEW in materials.yaml /
stainless_316l_sheet) with every other material refused by name; the tube
gauge held to the CHOSEN material's wall envelope with real numbers; the
arc_span / oval / nadir floors; gap-azimuth wrap determinism (gap 0 and
gap 360 are the same solid); the photo-replica demo (R=800, tube=350,
span=300, gap=0 -> 1950 mm tall x 1950 mm long x 350 mm deep, the
reference piece read at photo precision: 1.9 m x 2.0 m x 0.4 m) and a slim
full-ish crescent BOTH through the production freeform integrity stack;
swept volume vs analytic torus-segment theory within 2%; two SEPARATE
PROCESSES exporting byte-identical STEP (the FF-A2 determinism pattern);
the measured top anchor pinned against the derived relationship for a
90 deg span; a build time far under the sandbox timeout; a spec mapping
through the ADR-069 mapper rules (height refused as DERIVED, naming the
relationship); and a plinth + crescent stack fusing into one body, with an
honest seat refusal when the joint floor out-runs the seat.

$0, offline, no AI. No reference image is claimed anywhere (there is none
for SC-A1); the photo dimensions are stated as photo-precision readings.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")

from app.geometry.primitives import (  # noqa: E402
    PRIMITIVES,
    crescent_ring,
)
from app.geometry.primitives.base import ConstraintViolation  # noqa: E402

#: The photo-replica demo fixture — the client reference piece
#: (0.4 m deep x 1.9 m tall x 2.0 m long at photo precision).
PHOTO = {
    "centerline_radius_mm": 800,
    "tube_diameter_mm": 350,
    "arc_span_deg": 300,
    "gap_azimuth_deg": 0,
    "material_id": "stainless_316l_cast",
}

#: Slim full-ish crescent fixture.
SLIM = {
    "centerline_radius_mm": 1000,
    "tube_diameter_mm": 120,
    "arc_span_deg": 330,
    "gap_azimuth_deg": 0,
    "material_id": "stainless_316l_cast",
}

#: Small 90 deg-span fixture for the top-anchor derivation pin.
QUARTER = {
    "centerline_radius_mm": 400,
    "tube_diameter_mm": 80,
    "arc_span_deg": 90,
    "gap_azimuth_deg": 0,
    "material_id": "stainless_316l_cast",
}


def validate(**overrides):
    raw = dict(PHOTO)
    raw.update(overrides)
    return crescent_ring.validate(raw, None)


@pytest.fixture(scope="module")
def photo_solid():
    return crescent_ring.build(validate())


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

#: The exact thirteen (owner-ordered for SC-A1 — the roster duplicate,
#: per the D-10 convention, moves with any future widening; the same
#: set is pinned in tests/test_perforated_screen.py).
EXPECTED_THIRTEEN = {
    "tiered_cascade", "basin_round", "plinth", "sculptural_column",
    "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
    "blade_fin_array", "lotus_petal_array", "freeform_loop",
    "perforated_screen", "crescent_ring",
}


class TestRegistry:
    def test_registered_as_the_thirteenth(self):
        assert "crescent_ring" in PRIMITIVES
        assert set(PRIMITIVES) == EXPECTED_THIRTEEN

    def test_declarations(self):
        assert crescent_ring.SUPPORTED_MATERIALS == (
            "stainless_316l_cast", "stainless_316l_sheet")
        assert crescent_ring.SEGMENTATION_MODE == "planar_grid"
        assert crescent_ring.CAN_PARENT_STACK is False
        assert crescent_ring.CAN_PARENT_INSERT is False
        # complete mass: no INCOMPLETE_MASS_INPUTS declaration — the cast
        # tube is the whole mass story
        assert not getattr(crescent_ring, "INCOMPLETE_MASS_INPUTS", ())

    def test_new_material_is_declared(self):
        from app.geometry.primitives.base import load_materials
        mat = load_materials()["stainless_316l_cast"]
        assert mat.density_kg_per_m3 == 8000
        assert mat.min_wall_mm == 3 and mat.max_wall_mm == 500
        assert mat.stock_size_mm is None


# ---------------------------------------------------------------------------
# material rule — the allowed set, everything else by name
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
        assert "stainless_316l_cast" in text

    def test_default_is_cast_316l(self):
        assert validate().material_id == "stainless_316l_cast"

    def test_sheet_material_in_range_is_still_envelope_refused(self):
        """Honest arithmetic pin: the static tube floor (80 mm, the
        ADR-055 handleable-section judgement) sits ABOVE the sheet
        envelope ceiling (20 mm), so every in-range tube refuses the
        sheet process today — the allowed-set membership and the wall
        envelope are separate gates, and the message carries both
        numbers. The sheet process becomes reachable only if a future
        slice moves one of the two (FABRICATOR-INPUT)."""
        with pytest.raises(ConstraintViolation) as exc:
            validate(tube_diameter_mm=80, material_id="stainless_316l_sheet")
        text = str(exc.value)
        assert "tube_diameter_mm=80" in text and "20" in text
        assert "stainless_316l_sheet" in text

    def test_unknown_material_names_the_available_keys(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(material_id="no_such_material")
        assert "no_such_material" in str(exc.value)
        assert "materials.yaml" in str(exc.value)

    def test_tube_above_the_sheet_envelope_refuses_with_numbers(self):
        # tube 350 vs the 316L SHEET wall envelope 3..20 mm
        with pytest.raises(ConstraintViolation) as exc:
            validate(material_id="stainless_316l_sheet")
        text = str(exc.value)
        assert "tube_diameter_mm=350" in text and "20" in text
        assert "stainless_316l_sheet" in text

    def test_tube_above_the_cast_envelope_refuses_with_numbers(self):
        # defence in depth, the perforated_screen precedent: the static
        # ranges (tube max 500 = cast max_wall 500) guarantee this floor,
        # so pin the guarantee AND the runtime message via a
        # construct-bypassed model (materials.yaml is the truth).
        from app.geometry.primitives.base import load_materials
        mat = load_materials()["stainless_316l_cast"]
        p = crescent_ring.CrescentRingParams.model_construct(
            **dict(PHOTO, tube_diameter_mm=600))
        violations: list[str] = []
        crescent_ring.check_wall_envelope(
            "tube_diameter_mm", p.tube_diameter_mm,
            "stainless_316l_cast", mat, violations)
        assert any("600" in v and "500" in v for v in violations), violations


# ---------------------------------------------------------------------------
# validate() refusals — one per signed floor, real numbers in the message
# ---------------------------------------------------------------------------

class TestValidateRefusals:
    def test_arc_span_below_range_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(arc_span_deg=89)
        assert "arc_span_deg" in str(exc.value)

    def test_arc_span_above_range_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(arc_span_deg=331)
        assert "arc_span_deg" in str(exc.value)

    def test_oval_at_or_above_the_tube_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(tube_depth_oval_mm=350)
        text = str(exc.value)
        assert "tube_depth_oval_mm=350" in text
        assert "tube_diameter_mm 350" in text
        assert "squash" in text

    def test_oval_below_the_material_wall_ceiling_refuses(self):
        # the oval is held to the CHOSEN material's wall envelope too:
        # 50 mm is inside the CAST envelope (3..500) but over the SHEET
        # ceiling 20 — real numbers in the message
        with pytest.raises(ConstraintViolation) as exc:
            validate(tube_diameter_mm=80, tube_depth_oval_mm=50,
                     material_id="stainless_316l_sheet")
        text = str(exc.value)
        assert "tube_depth_oval_mm=50" in text and "20" in text

    def test_gap_covering_the_nadir_refuses_with_the_arc_numbers(self):
        # span 90 gap 200 -> swept arc [110 deg, 200 deg] misses 270 deg
        with pytest.raises(ConstraintViolation) as exc:
            validate(**dict(QUARTER, gap_azimuth_deg=200))
        text = str(exc.value)
        assert "nadir" in text and "270" in text
        assert "110" in text

    def test_gap_at_the_nadir_edge_still_stands(self):
        # span 90 gap 0 -> the swept arc STARTS exactly at the nadir
        # (270 deg, inclusive): a point contact at the base plane,
        # allowed — the joint floor refuses to seat on it unsunk
        p = validate(**QUARTER)
        assert p.gap_azimuth_deg == 0
        solid = crescent_ring.build(p)
        assert float(solid.bounding_box().min.Z) == pytest.approx(0.0, abs=1e-3)

    def test_height_key_is_refused_as_derived(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(height=1950)
        text = str(exc.value)
        assert "DERIVED" in text
        assert "2 x centerline_radius_mm + tube_diameter_mm" in text

    def test_monumental_scale_bind_is_guaranteed_by_the_ranges(self):
        """2R + tube <= 5000: the static maxima give 2x1500 + 500 = 3500,
        so the bind can only be broken by a future range edit — pin the
        guarantee here (the range-pinning convention of
        perforated_screen)."""
        t = crescent_ring.PARAMETERS
        assert (2 * t["centerline_radius_mm"]["max"]
                + t["tube_diameter_mm"]["max"]) <= 5000


# ---------------------------------------------------------------------------
# gap azimuth wrap determinism
# ---------------------------------------------------------------------------

class TestGapWrap:
    def test_gap_at_0_and_360_are_the_same_solid(self):
        a = crescent_ring.build(validate(gap_azimuth_deg=0))
        b = crescent_ring.build(validate(gap_azimuth_deg=360))
        assert float(a.volume) == float(b.volume)
        bb_a, bb_b = a.bounding_box(), b.bounding_box()
        assert float(bb_a.min.X) == pytest.approx(float(bb_b.min.X), abs=1e-6)
        assert float(bb_a.max.X) == pytest.approx(float(bb_b.max.X), abs=1e-6)
        assert float(bb_a.min.Z) == pytest.approx(float(bb_b.min.Z), abs=1e-6)
        assert float(bb_a.max.Z) == pytest.approx(float(bb_b.max.Z), abs=1e-6)

    def test_gap_rotation_places_the_opening_deterministically(self):
        """gap 180 moves the opening to the -X side: the swept arc
        [240 deg, 540 deg] still includes the nadir and both side
        azimuths (the envelope is unchanged), but the material at
        azimuth 30 deg — inside the gap for gap 0 — must now be SOLID.
        Probed with a box at the 30 deg centreline point."""
        from build123d import Box, Pos
        x = 800 * math.cos(math.radians(30))
        z = 975 + 800 * math.sin(math.radians(30))
        probe = Pos(x, 0, z) * Box(300, 400, 300)
        solid = crescent_ring.build(validate(gap_azimuth_deg=180))
        assert float((solid & probe).volume) > 0.0
        solid0 = crescent_ring.build(validate(gap_azimuth_deg=0))
        inter0 = solid0 & probe
        # a disjoint boolean returns None on this binding, never an
        # empty solid with a faked zero volume
        assert inter0 is None or float(inter0.volume) == 0.0


# ---------------------------------------------------------------------------
# construction truth (the built solid)
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_one_watertight_solid(self, photo_solid):
        assert len(photo_solid.solids()) == 1
        assert float(photo_solid.volume) > 0.0
        assert bool(photo_solid.is_valid)

    def test_photo_replica_envelope_and_origin(self, photo_solid):
        """The reference piece: 0.4 m deep x 1.9 m tall x 2.0 m long at
        photo precision. The replica measures 350 mm deep x 1950 mm tall
        x 1950 mm long — the photo's "2.0 m" is the length extent read to
        two figures (1.95 m), and "0.4 m" is 350 mm at one figure.

        Pinned relationships (span 300, gap 0 -> swept arc [60, 360]
        includes azimuths 90/180/270/360):
          height = 2R + tube_diameter = 2x800 + 350 = 1950
          length = 2R + tube_diameter = 1950 (both side azimuths swept)
          depth  = tube_diameter = 350
        origin: lowest tube point (nadir azimuth 270 deg) at z = 0.
        """
        bb = photo_solid.bounding_box()
        p = validate()
        assert float(bb.min.Z) == pytest.approx(0.0, abs=1e-3)
        assert float(bb.max.Z) == pytest.approx(1950.0, abs=1e-3)
        assert float(bb.min.X) == pytest.approx(-975.0, abs=1e-3)
        assert float(bb.max.X) == pytest.approx(975.0, abs=1e-3)
        assert float(bb.min.Y) == pytest.approx(-175.0, abs=1e-3)
        assert float(bb.max.Y) == pytest.approx(175.0, abs=1e-3)
        # the derived helpers agree with the measured solid
        assert crescent_ring.top_mm(p) == pytest.approx(1950.0, abs=1e-6)
        assert crescent_ring.length_mm(p) == pytest.approx(1950.0, abs=1e-6)
        assert crescent_ring.anchors(p)["top"] == pytest.approx(1950.0)
        # mass truth: COMPLETE — volume x 8000 kg/m3, nothing hidden
        mass_kg = float(photo_solid.volume) * 1e-9 * 8000.0
        assert 0 < mass_kg < (1950 * 1950 * 350) * 1e-9 * 8000.0

    def test_photo_demo_through_freeform_integrity_stack(self, photo_solid):
        from app.geometry.freeform_validation import run_freeform_integrity
        report = run_freeform_integrity(photo_solid)
        assert report["status"] == "pass", [
            (c["check"], c["status"], c["value"])
            for c in report["checks"] if c["status"] != "pass"]
        by = {c["check"]: c for c in report["checks"]}
        assert by["body_count"]["value"] == 1
        assert by["volume_cross_check"]["status"] == "pass"
        # a partial torus is genus 0 (no through-opening) with one
        # boundary component
        assert by["genus"]["value"] == 0

    def test_slim_fullish_crescent_through_freeform_integrity_stack(self):
        from app.geometry.freeform_validation import run_freeform_integrity
        p = validate(**SLIM)
        solid = crescent_ring.build(p)
        report = run_freeform_integrity(solid)
        assert report["status"] == "pass", [
            (c["check"], c["status"], c["value"])
            for c in report["checks"] if c["status"] != "pass"]
        bb = solid.bounding_box()
        # span 330 gap 0 -> swept [30, 360]: zenith included
        assert float(bb.max.Z) == pytest.approx(2 * 1000 + 120, abs=1e-3)
        assert float(bb.min.Z) == pytest.approx(0.0, abs=1e-3)

    def test_elliptical_section_squashes_the_vertical_only(self):
        p = validate(tube_depth_oval_mm=200)
        solid = crescent_ring.build(p)
        bb = solid.bounding_box()
        # depth stays tube_diameter; the vertical gauge becomes the oval
        assert (float(bb.max.Y) - float(bb.min.Y)) == \
            pytest.approx(350.0, abs=1e-3)
        assert float(bb.max.Z) == pytest.approx(2 * 800 + 200, abs=1e-3)
        # volume follows the elliptical-section theory
        theory = (math.pi * 100 * 175
                  * (2 * math.pi * 800 * 300 / 360))
        assert abs(float(solid.volume) - theory) / theory <= 0.02

    def test_swept_volume_matches_torus_segment_theory(self, photo_solid):
        # V = pi x (tube/2)^2 x 2πR x span/360 (a torus segment)
        theory = crescent_ring.swept_volume_mm3(validate())
        measured = float(photo_solid.volume)
        rel = abs(measured - theory) / theory
        print("swept volume %d mm3 vs theory %d mm3 (rel dev %.2e)"
              % (measured, theory, rel))
        assert rel <= 0.02

    def test_max_outer_diameter_is_the_footprint_diagonal(self):
        """water_wall/ADR-055 pattern: the diagonal of the footprint
        rectangle (length x depth)."""
        p = validate()
        expect = (1950.0 ** 2 + 350.0 ** 2) ** 0.5
        assert crescent_ring.max_outer_diameter_mm(p) == \
            pytest.approx(expect, abs=1e-6)

    def test_base_annulus_is_a_point_until_sunk(self):
        """Un-sunk, the tube meets the seat at a point (zero width), the
        torus_ring precedent; sinking overlap_mm opens a real chord."""
        p = validate()
        assert crescent_ring.base_annulus_mm(p) == (0.0, 0.0)
        out, inner = crescent_ring.base_annulus_at_overlap_mm(p, 3.0)
        # chord 2 x sqrt(3 x (2x175 - 3)) = 2 x 32.26
        assert out == pytest.approx(2 * (3 * (350 - 3)) ** 0.5, abs=1e-6)
        assert inner == 0.0


# ---------------------------------------------------------------------------
# measured top anchor for a 90 deg span — the derived relationship, pinned
# ---------------------------------------------------------------------------

class TestTopAnchor:
    def test_quarter_crescent_top_is_derived_from_the_arc(self):
        """90 deg span, gap 0 -> swept arc [270 deg, 360 deg]: the zenith
        (90 deg) is NOT swept, so the top is NOT 2R + tube — it is the
        highest point of the arc itself, at the 360 deg end.

        Derivation (pinned): the centreline circle's centre sits at
        z_c = R + tube/2 (the nadir tube point rests at z = 0); at
        azimuth 360 deg the radial direction is horizontal (+X), so the
        tube adds NOTHING vertical there — the end face is a horizontal
        ellipse at exactly z_c. Along the arc the surface reaches
        z = z_c + (R + tube/2) x sin(phi), whose max over [270, 360]
        is at 360 deg (sin = 0):
            top = z_c = R + tube/2 = 400 + 40 = 440.
        """
        p = validate(**QUARTER)
        solid = crescent_ring.build(p)
        bb = solid.bounding_box()
        assert float(bb.min.Z) == pytest.approx(0.0, abs=1e-3)
        assert float(bb.max.Z) == pytest.approx(440.0, abs=1e-3)
        assert crescent_ring.top_mm(p) == pytest.approx(440.0, abs=1e-6)
        anchors = crescent_ring.anchors(p)
        assert anchors["base"] == 0.0
        assert anchors["top"] == pytest.approx(440.0)
        assert anchors["seat"] is None
        assert crescent_ring.height_mm(p) == pytest.approx(440.0)

    def test_fullish_span_top_is_2R_plus_tube(self):
        """Spans whose swept arc includes the zenith measure exactly
        2R + tube_diameter — the photo replica relationship."""
        p = validate(**SLIM)
        assert crescent_ring.top_mm(p) == pytest.approx(2120.0, abs=1e-6)


# ---------------------------------------------------------------------------
# determinism: two separate processes, byte-identical STEP
# ---------------------------------------------------------------------------

BUILD_SNIPPET = r"""
import json, os, sys
from app.geometry.primitives import crescent_ring as cr
from app.geometry.exporters import export_step
from app.geometry.kernel import step_timestamp_for
params = json.loads(open(sys.argv[1]).read())
p = cr.validate(params, None)
solid = cr.build(p)
sha = export_step(solid, sys.argv[2], step_timestamp_for(8))
print("pid=%d sha256=%s" % (os.getpid(), sha))
"""


class TestDeterminism:
    def test_two_processes_byte_identical_step(self, tmp_path):
        params_path = tmp_path / "sca1_params.json"
        params_path.write_text(json.dumps(PHOTO))
        results = []
        for i in (1, 2):
            out = str(tmp_path / ("sca1_%d.step" % i))
            proc = subprocess.run(
                [sys.executable, "-c", BUILD_SNIPPET, str(params_path),
                 out],
                capture_output=True, text=True, timeout=900)
            line = (proc.stdout or "").strip().splitlines()
            line = line[-1] if line else ""
            print("run %d: %s (exit %d)" % (i, line, proc.returncode))
            assert proc.returncode == 0, proc.stderr
            results.append(line)
        pids = [r.split()[0] for r in results]
        shas = [r.split("sha256=")[1] for r in results]
        assert pids[0] != pids[1]
        # The load-bearing assertion is cross-PROCESS byte identity (the
        # FF-A2 pattern). Measured on the pinned venv toolchain:
        #   photo replica STEP sha256 =
        #   920d1caaa01a2751b1a6ec1e2804994220958b2fe6bd63e0e5e3bc3a305ef19b
        print("pinned STEP sha256: %s" % shas[0])
        assert shas[0] == shas[1]


# ---------------------------------------------------------------------------
# build time: one revolve, bounded
# ---------------------------------------------------------------------------

class TestBuildTime:
    def test_photo_demo_builds_well_under_the_timeout(self):
        p = validate()
        t0 = time.monotonic()
        solid = crescent_ring.build(p)
        elapsed = time.monotonic() - t0
        print("photo crescent (R=800, tube=350, span=300) built in %.1f s "
              "(sandbox timeout 120 s, assertion < 60 s)" % elapsed)
        assert len(solid.solids()) == 1
        assert elapsed < 60.0


# ---------------------------------------------------------------------------
# spec_mapper (ADR-069 rules)
# ---------------------------------------------------------------------------

class TestSpecMapper:
    def _spec(self):
        from tests.test_design_spec_schema import valid_example_spec
        spec = valid_example_spec()
        spec["massing"]["elements"] = [
            {
                "element_id": "cre1",
                "primitive": "crescent_ring",
                "parameters": {
                    "radius": {"value": 0.8, "unit": "m"},
                    "tube_diameter": {"value": 350, "unit": "mm"},
                    "span": {"value": 300, "unit": "deg"},
                    "opening": {"value": 0, "unit": "deg"},
                },
                "material_id": "stainless_316l_cast",
                "position": {"x_m": 0, "y_m": 0, "z_m": 0},
            },
        ]
        return spec

    def test_spec_element_maps_to_the_registry_keys(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        plan = assembly_plan_from_spec(self._spec())
        assert len(plan) == 1
        params = plan[0]["parameters"]
        assert params["centerline_radius_mm"] == 800    # 0.8 m -> mm
        assert params["tube_diameter_mm"] == 350
        assert params["arc_span_deg"] == 300
        assert params["gap_azimuth_deg"] == 0
        assert params["material_id"] == "stainless_316l_cast"

    def test_every_registry_key_is_reachable_by_a_spec_name(self):
        """ADR-069 anti-drift: proven FROM the registry, never from the
        alias table — no parameter can be spec-unreachable. material_id
        is excluded by the same rule as gate_ffa3: it arrives as the
        element-level material of record, never as a dimension."""
        from app.geometry.spec_mapper import spec_aliases_for
        aliases = spec_aliases_for("crescent_ring")
        dangling = sorted(set(aliases.values())
                          - set(crescent_ring.PARAMETERS))
        assert not dangling, dangling
        unreachable = [k for k in crescent_ring.PARAMETERS
                       if k != "material_id"
                       and k not in set(aliases.values()) | set(aliases)]
        assert not unreachable, unreachable

    def test_height_key_refused_naming_the_derived_relationship(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        spec = self._spec()
        spec["massing"]["elements"][0]["parameters"]["height"] = {
            "value": 1.95, "unit": "m"}
        with pytest.raises(ConstraintViolation) as exc:
            assembly_plan_from_spec(spec)
        text = str(exc.value)
        assert "DERIVED" in text
        assert "2 x centerline_radius_mm + tube_diameter_mm" in text

    def test_bad_unit_for_the_span_refuses(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        spec = self._spec()
        spec["massing"]["elements"][0]["parameters"]["span"] = {
            "value": 300, "unit": "mm"}
        with pytest.raises(ConstraintViolation) as exc:
            assembly_plan_from_spec(spec)
        assert "unit 'mm' cannot map to arc_span_deg" in str(exc.value)

    def test_contradicting_material_refuses(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        spec = self._spec()
        spec["massing"]["elements"][0]["parameters"]["material_id"] = \
            "bronze_cast"
        with pytest.raises(ConstraintViolation) as exc:
            assembly_plan_from_spec(spec)
        assert "contradicts" in str(exc.value)


# ---------------------------------------------------------------------------
# assembly end-to-end: plinth + crescent stacked, one fused body
# ---------------------------------------------------------------------------

class TestAssemblyEndToEnd:
    def test_plinth_and_crescent_stack_into_one_body(self):
        from app.geometry import registry
        # 316L plinth parent; the crescent sinks its joint overlap (3 mm,
        # the cast/sheet floor) into the plinth top: the seat chord
        # 2 x sqrt(3 x (2x175 - 3)) = 64.5 mm is well over the floor.
        spec = {
            "meta": {"seed": 7},
            "fabrication": {"max_lift_kg": 20000,
                            "max_module_m": {"x": 4.0, "y": 4.0, "z": 4.0}},
            "massing": {
                "elements": [
                    {
                        "element_id": "p1",
                        "primitive": "plinth",
                        "parameters": {
                            "top_diameter": {"value": 1200, "unit": "mm"},
                            "height": {"value": 300, "unit": "mm"},
                        },
                        "material_id": "stainless_316l_sheet",
                        "position": {"x_m": 0, "y_m": 0, "z_m": 0},
                    },
                    {
                        "element_id": "cre1",
                        "primitive": "crescent_ring",
                        "parameters": {
                            "radius": {"value": 800, "unit": "mm"},
                            "tube": {"value": 350, "unit": "mm"},
                            "span": {"value": 300, "unit": "deg"},
                            "gap": {"value": 0, "unit": "deg"},
                        },
                        "material_id": "stainless_316l_cast",
                        "position": {"x_m": 0, "y_m": 0, "z_m": 0.3},
                        "parent_id": "p1",
                    },
                ]
            },
        }
        plan = registry.assembly_plan_from_spec(spec)
        by_id = {e["element_id"]: e for e in plan}
        assert by_id["cre1"]["joint"] == {"type": "stack_on", "parent": "p1"}
        solid, manifest = registry.assemble(
            plan, seed=7,
            fabrication=registry.fabrication_limits_from_spec(spec))
        assert manifest["body_count_brep"] == 1
        vc = manifest["volume_conservation"]
        assert vc["delta_pct"] <= vc["tolerance_pct"]
        # mass truth: COMPLETE — volume x 8000, no missing inputs
        crescent = [e for e in manifest["elements"]
                    if e["element_id"] == "cre1"][0]
        assert crescent["mass_model"]["mass_complete"] is True
        assert crescent["mass_model"]["missing_mass_inputs"] == []
        assert crescent["mass_kg"] == pytest.approx(
            crescent["volume_mm3"] * 1e-9 * 8000.0, rel=0.005)

    def test_crescent_on_basalt_parent_respects_the_joint_floor(self):
        from app.geometry import registry
        plan = [
            {"element_id": "p1", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 600, "height_mm": 300,
                            "material_id": "basalt_slab"}},
            {"element_id": "cre1", "primitive": "crescent_ring",
             "parameters": dict(PHOTO),
             "joint": {"type": "stack_on", "parent": "p1",
                       "x_offset_mm": 400.0}},
        ]
        with pytest.raises(ConstraintViolation) as exc:
            registry.assemble(plan, seed=7)
        # the 400 mm lateral offset walks the 350 mm-radius seat off the
        # 600 mm plinth top: the ADR-053 seat check refuses with the
        # real numbers and the cross-material floor (max of 3 and 10)
        text = str(exc.value)
        assert "seat" in text
        assert "10" in text
        assert "basalt_slab" in text
