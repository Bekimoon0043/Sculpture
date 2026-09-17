"""MS-A1: perforated_screen primitive contract — red-first.

The first mesh-class primitive: a flat or single-curved perforated 316L
sheet screen (perforated-skin class, not an open wire lattice). What this
file proves: exact twelfth registration (owner-ordered for MS-A1); 316L-only
refusals by name; every signed floor binds with real numbers in the message
(ligament = min_feature=wall, hole size, margin, grid fit, the 1500-hole
build cap, curvature floors, stock sheet); flat AND curved panels build ONE
watertight solid through the production freeform integrity stack with the
mass = volume x 8000 kg/m3 truth; two SEPARATE PROCESSES export
byte-identical STEP (the FF-A2 determinism pattern); a realistic 1421-hole
panel builds far under the sandbox timeout; a spec maps through the ADR-069
mapper rules; and a plinth + screen stack fuses into one body end-to-end.

$0, offline, no AI. The two-process byte-identity pattern and the
single-boolean construction are the gate's evidence here; no reference
image is claimed anywhere (there is none for MS-A1).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")

from app.geometry.primitives import (  # noqa: E402
    PRIMITIVES,
    perforated_screen,
)
from app.geometry.primitives.base import ConstraintViolation  # noqa: E402

#: Default flat fixture (748 holes) — one build per module, reused by the
#: envelope/origin tests and the two-process determinism runs.
DEFAULTS = {
    "height_mm": 900,
    "arc_width_mm": 1400,
    "sheet_thickness_mm": 6,
    "hole_shape": "circle",
    "hole_pitch_mm": 40,
    "hole_size_mm": 20,
    "edge_margin_mm": 25,
    "material_id": "stainless_316l_sheet",
}

#: Small fixtures (42 holes) for the integrity-stack runs — the FF-A1
#: self-interference check is quadratic in the face count, so the
#: watertight/topology proof runs on the small grid and the envelope/
#: determinism proofs on the default one.
SMALL = {
    "height_mm": 500,
    "arc_width_mm": 600,
    "sheet_thickness_mm": 6,
    "hole_shape": "circle",
    "hole_pitch_mm": 80,
    "hole_size_mm": 30,
    "edge_margin_mm": 25,
    "material_id": "stainless_316l_sheet",
}

#: Curved small fixture (42 holes).
CURVED = dict(SMALL, curvature_radius_mm=800)

#: Hexagon small fixture (42 holes).
HEX = dict(SMALL, hole_shape="hexagon")


def validate(**overrides):
    raw = dict(DEFAULTS)
    raw.update(overrides)
    return perforated_screen.validate(raw, None)


@pytest.fixture(scope="module")
def default_solid():
    return perforated_screen.build(validate())


@pytest.fixture(scope="module")
def curved_solid():
    return perforated_screen.build(validate(**CURVED))


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

#: The exact twelve (owner-ordered for MS-A1 — the roster gate, per the
#: D-10 convention, is gate_ffa2_auto; this duplicate is deliberate for
#: the slice's contract test and moves with any future widening).
EXPECTED_TWELVE = {
    "tiered_cascade", "basin_round", "plinth", "sculptural_column",
    "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
    "blade_fin_array", "lotus_petal_array", "freeform_loop",
    "perforated_screen",
}


class TestRegistry:
    def test_registered_as_the_twelfth(self):
        assert "perforated_screen" in PRIMITIVES
        assert set(PRIMITIVES) == EXPECTED_TWELVE

    def test_declarations(self):
        assert perforated_screen.SUPPORTED_MATERIAL == "stainless_316l_sheet"
        assert perforated_screen.SEGMENTATION_MODE == "planar_grid"
        assert perforated_screen.CAN_PARENT_STACK is True
        assert perforated_screen.CAN_PARENT_INSERT is False
        # complete mass: no INCOMPLETE_MASS_INPUTS declaration (unlike
        # freeform_loop) — the sheet is the whole mass story
        assert not getattr(perforated_screen, "INCOMPLETE_MASS_INPUTS", ())


# ---------------------------------------------------------------------------
# 316L-only
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

    def test_default_is_316l(self):
        assert validate().material_id == "stainless_316l_sheet"

    def test_unknown_material_names_the_available_keys(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(material_id="no_such_material")
        assert "no_such_material" in str(exc.value)
        assert "materials.yaml" in str(exc.value)


# ---------------------------------------------------------------------------
# validate() refusals — one per signed floor, real numbers in the message
# ---------------------------------------------------------------------------

class TestValidateRefusals:
    def test_ligament_under_sheet_floor_refuses(self):
        # pitch 20 - size 16 = 4 mm < t 6
        with pytest.raises(ConstraintViolation) as exc:
            validate(hole_pitch_mm=20, hole_size_mm=16)
        text = str(exc.value)
        assert "ligament" in text and "4" in text and "6" in text
        assert "min_feature" in text

    def test_hole_size_under_sheet_floor_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(hole_size_mm=4)
        text = str(exc.value)
        assert "hole_size_mm=4" in text and "6" in text

    def test_edge_margin_under_sheet_floor_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(edge_margin_mm=3, sheet_thickness_mm=6)
        assert "edge_margin_mm=3" in str(exc.value)

    def test_hole_shape_vocabulary_refuses(self):
        with pytest.raises(ConstraintViolation) as exc:
            validate(hole_shape="diamond")
        text = str(exc.value)
        assert "diamond" in text and "hexagon" in text

    def test_holes_cap_prints_nx_ny_total_and_cap(self):
        # 3000 x 1500 at pitch 10: 296 x 146 = 43216 holes
        with pytest.raises(ConstraintViolation) as exc:
            validate(arc_width_mm=3000, height_mm=1500, hole_pitch_mm=10,
                     hole_size_mm=8, edge_margin_mm=25)
        text = str(exc.value)
        assert "296" in text and "146" in text
        assert "43216" in text and "1500" in text

    def test_curved_wrap_over_270_degrees_refuses(self):
        # R=100 -> wrap limit 2π·100·0.75 = 471 mm
        with pytest.raises(ConstraintViolation) as exc:
            validate(curvature_radius_mm=100, arc_width_mm=1000,
                     height_mm=600)
        text = str(exc.value)
        assert "471" in text and "270" in text

    def test_curvature_under_5x_sheet_refuses(self):
        # Defence in depth, the freeform_loop precedent: the static ranges
        # (R min 100 = 5 x t max 20) guarantee this floor, so below-range
        # values are refused by the pydantic model first; pin the
        # guarantee AND the runtime message via a construct-bypassed model
        # (arc_width kept inside the wrap limit so only the 5x rule fires).
        p = perforated_screen.PerforatedScreenParams.model_construct(
            **dict(SMALL, arc_width_mm=200, curvature_radius_mm=50,
                   sheet_thickness_mm=20))
        msgs = perforated_screen._curvature_violations(p)
        assert any("50" in m and "100" in m for m in msgs), msgs

    def test_margin_fit_floor_is_guaranteed_by_the_ranges(self):
        """Same precedent: margin max 100, hole max 150, span min 400 —
        2·100 + 150 = 350 < 400, so the margin-fit rule can only fire on a
        future range edit. Pin the guarantee and the runtime message."""
        p = perforated_screen.PARAMETERS
        assert (2 * p["edge_margin_mm"]["max"]
                + p["hole_size_mm"]["max"]) < p["arc_width_mm"]["min"]
        m = perforated_screen.PerforatedScreenParams.model_construct(
            **dict(DEFAULTS, arc_width_mm=300, hole_size_mm=200,
                   edge_margin_mm=100))
        msgs = perforated_screen._margin_fit_violations(m)
        assert any("arc width (X)" in v and "100" in v for v in msgs), msgs

    def test_stock_binds_to_the_material_facts(self):
        # the default fixture must sit inside the declared 316L stock
        # 3000 x 1500 — read from the material, never hardcoded
        from app.geometry.primitives.base import load_materials
        mat = load_materials()["stainless_316l_sheet"]
        p = validate()
        assert p.arc_width_mm <= mat.stock_size_mm.length
        assert p.height_mm <= mat.stock_size_mm.width
        # runtime check message, exercised through the material: a
        # construct-bypassed model wider than stock names both numbers
        m = perforated_screen.PerforatedScreenParams.model_construct(
            **dict(DEFAULTS, arc_width_mm=3200))
        msg = perforated_screen._stock_violation(m, mat)
        assert msg is not None
        assert "3200" in msg and "3000" in msg


# ---------------------------------------------------------------------------
# construction truth (the built solid)
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_one_watertight_solid_flat(self, default_solid):
        assert len(default_solid.solids()) == 1
        assert float(default_solid.volume) > 0.0
        assert bool(default_solid.is_valid)

    def test_flat_envelope_and_origin(self, default_solid):
        bb = default_solid.bounding_box()
        p = validate()
        assert float(bb.min.X) == pytest.approx(-p.arc_width_mm / 2, abs=1e-6)
        assert float(bb.max.X) == pytest.approx(p.arc_width_mm / 2, abs=1e-6)
        assert float(bb.min.Z) == pytest.approx(0.0, abs=1e-6)
        assert float(bb.max.Z) == pytest.approx(p.height_mm, abs=1e-6)
        assert (float(bb.max.Y) - float(bb.min.Y)) == \
            pytest.approx(p.sheet_thickness_mm, abs=1e-6)

    def test_curved_envelope(self, curved_solid):
        bb = curved_solid.bounding_box()
        p = validate(**CURVED)
        theta = p.arc_width_mm / p.curvature_radius_mm
        r = p.curvature_radius_mm
        t = p.sheet_thickness_mm
        assert float(bb.min.Z) == pytest.approx(0.0, abs=1e-6)
        assert float(bb.max.Z) == pytest.approx(p.height_mm, abs=1e-6)
        # symmetric about the YZ plane
        assert float(bb.min.X) == pytest.approx(-float(bb.max.X), rel=1e-9)
        # plan extents of the annular sector: half-chord at the OUTER
        # radius; inner face closest at R·cos(theta/2)
        assert float(bb.max.X) == pytest.approx(
            (r + t) * math.sin(theta / 2), abs=0.5)
        assert float(bb.min.Y) == pytest.approx(
            r * math.cos(theta / 2), abs=0.5)
        assert float(bb.max.Y) == pytest.approx(r + t, abs=0.5)

    def test_curved_face_radii_measured_from_the_solid(self, curved_solid):
        """The inner face sits at R and the outer face at R + t — measured
        through the kernel: a thin vertical slab at x = 0 cuts the solid
        in an arc strip whose innermost point is (0, R) and outermost
        (0, R + t) by the +Y symmetry of the construction."""
        from build123d import Box
        p = validate(**CURVED)
        r = float(p.curvature_radius_mm)
        t = float(p.sheet_thickness_mm)
        slab = curved_solid & Box(0.5, 4000.0, p.height_mm)
        bb = slab.bounding_box()
        assert float(bb.min.Y) == pytest.approx(r, abs=0.1)
        assert float(bb.max.Y) == pytest.approx(r + t, abs=0.1)

    def test_flat_through_freeform_integrity_stack(self):
        from app.geometry.freeform_validation import run_freeform_integrity
        solid = perforated_screen.build(validate(**SMALL))
        report = run_freeform_integrity(solid)
        assert report["status"] == "pass", [
            (c["check"], c["status"], c["value"])
            for c in report["checks"] if c["status"] != "pass"]
        # one boundary component pierced by exactly the 42 through-holes
        by = {c["check"]: c for c in report["checks"]}
        assert by["genus"]["value"] == 42

    def test_curved_through_freeform_integrity_stack(self, curved_solid):
        from app.geometry.freeform_validation import run_freeform_integrity
        report = run_freeform_integrity(curved_solid)
        assert report["status"] == "pass", [
            (c["check"], c["status"], c["value"])
            for c in report["checks"] if c["status"] != "pass"]

    def test_hexagon_screen_builds_and_mass_is_complete(self):
        p = validate(**HEX)
        solid = perforated_screen.build(p)
        assert len(solid.solids()) == 1
        # mass truth: volume x 8000 kg/m3, complete, nothing hidden
        vol_mm3 = float(solid.volume)
        mass_kg = vol_mm3 * 1e-9 * 8000.0
        gross_mm3 = (p.arc_width_mm * p.height_mm * p.sheet_thickness_mm)
        assert 0 < mass_kg < gross_mm3 * 1e-9 * 8000.0
        # hexagon across-flats: area = (√3/2)·f² per hole; the single
        # boolean must remove exactly the grid's worth of sheet
        nx, ny = perforated_screen.grid_counts(p)
        expected = (nx * ny * math.sqrt(3) / 2.0 * p.hole_size_mm ** 2
                    * p.sheet_thickness_mm)
        removed = gross_mm3 - vol_mm3
        assert removed == pytest.approx(expected, rel=0.02)


# ---------------------------------------------------------------------------
# determinism: two separate processes, byte-identical STEP
# ---------------------------------------------------------------------------

BUILD_SNIPPET = r"""
import json, os, sys
from app.geometry.primitives import perforated_screen as ps
from app.geometry.exporters import export_step
from app.geometry.kernel import step_timestamp_for
params = json.loads(open(sys.argv[1]).read())
p = ps.validate(params, None)
solid = ps.build(p)
sha = export_step(solid, sys.argv[2], step_timestamp_for(8))
print("pid=%d sha256=%s" % (os.getpid(), sha))
"""


class TestDeterminism:
    def test_two_processes_byte_identical_step(self, tmp_path):
        params_path = tmp_path / "msa1_params.json"
        params_path.write_text(json.dumps(DEFAULTS))
        results = []
        for i in (1, 2):
            out = str(tmp_path / ("msa1_%d.step" % i))
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
        # FF-A2 pattern — a literal pin is not the established convention
        # there). Measured on the pinned venv toolchain, recorded:
        #   default fixture STEP sha256 =
        #   b80b20fd6c0923da942a2ce656f90628190284443f6b33485751fe6dab8db5d1
        print("pinned STEP sha256: %s" % shas[0])
        assert shas[0] == shas[1]


# ---------------------------------------------------------------------------
# build time: one boolean, bounded
# ---------------------------------------------------------------------------

class TestBuildTime:
    def test_realistic_panel_builds_well_under_the_timeout(self):
        # 2000 x 1200, pitch 40, circle d=20, t=6 -> 49 x 29 = 1421 holes
        # through one fused tool and ONE boolean.
        p = validate(arc_width_mm=2000, height_mm=1200)
        nx, ny = perforated_screen.grid_counts(p)
        total = nx * ny
        assert (nx, ny, total) == (49, 29, 1421)
        t0 = time.monotonic()
        solid = perforated_screen.build(p)
        elapsed = time.monotonic() - t0
        print("1421-hole flat panel built in %.1f s "
              "(sandbox timeout 120 s, assertion < 60 s)" % elapsed)
        assert len(solid.solids()) == 1
        # generous margin: measured ~19 s on the pinned venv — a 3x headroom
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
                "element_id": "scr1",
                "primitive": "perforated_screen",
                "parameters": {
                    "height": {"value": 900, "unit": "mm"},
                    "width": {"value": 1.4, "unit": "m"},
                    "sheet_thickness": {"value": 6, "unit": "mm"},
                    "hole_shape": "hexagon",
                    "hole_pitch": {"value": 60, "unit": "mm"},
                    "hole_size": {"value": 30, "unit": "mm"},
                    "edge_margin": {"value": 25, "unit": "mm"},
                },
                "material_id": "stainless_316l_sheet",
                "position": {"x_m": 0, "y_m": 0, "z_m": 0},
            },
        ]
        return spec

    def test_spec_element_maps_to_the_registry_keys(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        plan = assembly_plan_from_spec(self._spec())
        assert len(plan) == 1
        params = plan[0]["parameters"]
        assert params["height_mm"] == 900
        assert params["arc_width_mm"] == 1400     # 1.4 m -> developed width
        assert params["sheet_thickness_mm"] == 6
        assert params["hole_shape"] == "hexagon"
        assert params["hole_pitch_mm"] == 60
        assert params["hole_size_mm"] == 30
        assert params["edge_margin_mm"] == 25
        assert params["material_id"] == "stainless_316l_sheet"

    def test_every_registry_key_is_reachable_by_a_spec_name(self):
        """ADR-069 anti-drift: proven FROM the registry, never from the
        alias table — no parameter can be spec-unreachable. material_id
        is excluded by the same rule as gate_ffa3: it arrives as the
        element-level material of record, never as a dimension."""
        from app.geometry.spec_mapper import spec_aliases_for
        aliases = spec_aliases_for("perforated_screen")
        dangling = sorted(set(aliases.values())
                          - set(perforated_screen.PARAMETERS))
        assert not dangling, dangling
        unreachable = [k for k in perforated_screen.PARAMETERS
                       if k != "material_id"
                       and k not in set(aliases.values()) | set(aliases)]
        assert not unreachable, unreachable

    def test_bad_unit_for_a_dimension_refuses(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        spec = self._spec()
        spec["massing"]["elements"][0]["parameters"]["hole_pitch"] = {
            "value": 60, "unit": "deg"}
        with pytest.raises(ConstraintViolation) as exc:
            assembly_plan_from_spec(spec)
        assert "unit 'deg' cannot map to hole_pitch_mm" in str(exc.value)

    def test_contradicting_material_refuses(self):
        from app.geometry.spec_mapper import assembly_plan_from_spec
        spec = self._spec()
        spec["massing"]["elements"][0]["parameters"]["material_id"] = \
            "bronze_cast"
        with pytest.raises(ConstraintViolation) as exc:
            assembly_plan_from_spec(spec)
        assert "contradicts" in str(exc.value)


# ---------------------------------------------------------------------------
# assembly end-to-end: plinth + screen stacked, one fused body
# ---------------------------------------------------------------------------

class TestAssemblyEndToEnd:
    def test_plinth_and_screen_stack_into_one_body(self):
        from app.geometry import registry
        # 316L plinth: the screen's inscribed base circle IS its sheet
        # thickness (6 mm -> a 3 mm radial seat) — exactly at the 316L
        # 3 mm joint floor, so a same-material parent is required by the
        # ADR-053 seat rule (a basalt parent's 10 mm floor would refuse,
        # which the next test pins).
        spec = {
            "meta": {"seed": 7},
            "fabrication": {"max_lift_kg": 5000,
                            "max_module_m": {"x": 4.0, "y": 4.0, "z": 4.0}},
            "massing": {
                "elements": [
                    {
                        "element_id": "p1",
                        "primitive": "plinth",
                        "parameters": {
                            "top_diameter": {"value": 900, "unit": "mm"},
                            "height": {"value": 300, "unit": "mm"},
                        },
                        "material_id": "stainless_316l_sheet",
                        "position": {"x_m": 0, "y_m": 0, "z_m": 0},
                    },
                    {
                        "element_id": "scr1",
                        "primitive": "perforated_screen",
                        "parameters": {
                            "height": {"value": 600, "unit": "mm"},
                            "width": {"value": 800, "unit": "mm"},
                            "sheet_thickness": {"value": 6, "unit": "mm"},
                            "hole_shape": "circle",
                            "hole_pitch": {"value": 60, "unit": "mm"},
                            "hole_size": {"value": 30, "unit": "mm"},
                            "edge_margin": {"value": 25, "unit": "mm"},
                        },
                        "material_id": "stainless_316l_sheet",
                        "position": {"x_m": 0, "y_m": 0, "z_m": 0.3},
                        "parent_id": "p1",
                    },
                ]
            },
        }
        plan = registry.assembly_plan_from_spec(spec)
        by_id = {e["element_id"]: e for e in plan}
        assert by_id["scr1"]["joint"] == {"type": "stack_on", "parent": "p1"}
        solid, manifest = registry.assemble(
            plan, seed=7,
            fabrication=registry.fabrication_limits_from_spec(spec))
        assert manifest["body_count_brep"] == 1
        vc = manifest["volume_conservation"]
        assert vc["delta_pct"] <= vc["tolerance_pct"]
        # mass truth: COMPLETE — volume x 8000, no missing inputs
        screen = [e for e in manifest["elements"]
                  if e["element_id"] == "scr1"][0]
        assert screen["mass_model"]["mass_complete"] is True
        assert screen["mass_model"]["missing_mass_inputs"] == []
        assert screen["mass_kg"] == pytest.approx(
            screen["volume_mm3"] * 1e-9 * 8000.0, rel=0.005)

    def test_thin_screen_on_basalt_parent_refuses_the_seat_honestly(self):
        from app.geometry import registry
        plan = [
            {"element_id": "p1", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 900, "height_mm": 300,
                            "material_id": "basalt_slab"}},
            {"element_id": "scr1", "primitive": "perforated_screen",
             "parameters": dict(HEX, sheet_thickness_mm=6),
             "joint": {"type": "stack_on", "parent": "p1"}},
        ]
        with pytest.raises(ConstraintViolation) as exc:
            registry.assemble(plan, seed=7)
        # the sheet's 6 mm footprint gives a 3 mm seat — under the 10 mm
        # basalt joint floor — and the refusal names the real numbers
        assert "seat" in str(exc.value)
        assert "3.0" in str(exc.value)
