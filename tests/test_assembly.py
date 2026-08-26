"""Phase 6 slice A1 — registry.assemble: joints, interference, honesty.

The canonical composition here IS the operator's gate shape (three different
primitives, one watertight assembly) proven offline at $0; the gate script
re-proves it across two processes with STEP hashes.
"""

from __future__ import annotations

import pytest

from app.core.config import load_config_bundle
from app.geometry.assembly import assemble
from app.geometry.primitives.base import ConstraintViolation


def _materials():
    return load_config_bundle().materials.materials


# The canonical slice-A composition: plinth, basin stacked on it, column
# inserted into the basin. Floor 60 mm hosts BOTH joints: the basin sinks
# 10 into the plinth and the column sinks 10 into the floor, leaving 40 mm
# of clear stone between column base and plinth top.
def _gate_plan():
    return [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 700, "height_mm": 300,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 600, "height_mm": 300, "wall_mm": 25,
                        "floor_mm": 60, "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
        {"element_id": "c1", "primitive": "sculptural_column",
         "parameters": {"diameter_mm": 100, "height_mm": 400,
                        "material_id": "basalt_slab"},
         "joint": {"type": "concentric_insert", "parent": "b1"}},
    ]


def test_three_primitives_fuse_to_one_watertight_assembly(tmp_path):
    from app.geometry.exporters import export_glb
    from app.geometry.validate import validate_assembly

    solid, manifest = assemble(_gate_plan(), seed=7)
    assert len(solid.solids()) == 1
    assert manifest["body_count_brep"] == 1
    assert len(manifest["elements"]) == 3
    assert len(manifest["joints"]) == 2
    for j in manifest["joints"]:
        assert j["intersection_volume_mm3"] > 0, j
        assert j["overlap_mm"] >= j["floor_mm"]
    vc = manifest["volume_conservation"]
    assert vc["delta_pct"] <= vc["tolerance_pct"]

    out = tmp_path / "assembly.glb"
    export_glb(solid, out)
    report = validate_assembly(out, manifest)
    assert report.watertight and report.winding_consistent
    assert report.body_count == 1
    assert report.element_count == 3 and report.joint_count == 2
    assert report.volume_crosscheck.within_tolerance
    assert report.passed
    # per-element masses come from each element's OWN material density
    assert set(report.element_masses_kg) == {"p1", "b1", "c1"}
    assert report.total_mass_kg == pytest.approx(
        sum(report.element_masses_kg.values()))


def test_assembly_step_export_is_deterministic_in_process(tmp_path):
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for

    shas = []
    for run in ("a", "b"):
        solid, manifest = assemble(_gate_plan(), seed=42)
        shas.append(export_step(solid, tmp_path / f"{run}.step",
                                step_timestamp_for(42)))
    assert shas[0] == shas[1]


def test_default_overlap_is_the_material_floor():
    _, manifest = assemble(_gate_plan(), seed=0)
    for j in manifest["joints"]:
        assert j["overlap_mm"] == 10.0  # basalt on basalt


def test_overlap_below_floor_refused_constraint_9():
    plan = _gate_plan()
    plan[1]["joint"]["overlap_mm"] = 5
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "overlap_mm=5 < the 10 mm floor" in str(exc.value)
    assert "ADR-029" in str(exc.value)


def test_cross_material_joint_takes_the_max_floor():
    # bronze (floor 5) into a basalt basin (floor 10): the joint floor is 10.
    plan = _gate_plan()
    plan[2]["parameters"]["material_id"] = "bronze_cast"
    plan[2]["joint"]["overlap_mm"] = 7
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "overlap_mm=7 < the 10 mm floor" in str(exc.value)


def test_insert_into_plinth_refused():
    plan = _gate_plan()
    plan[2]["joint"]["parent"] = "p1"
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "no interior seat" in str(exc.value)


def test_stack_on_cascade_refused():
    plan = [
        {"element_id": "f1", "primitive": "tiered_cascade",
         "parameters": {"tiers": 1, "tier_top_diameter_mm": 200,
                        "basin_diameter_mm": 400, "basin_height_mm": 200,
                        "column_diameter_mm": 80, "dish_depth_mm": 40, "bore_diameter_mm": 25,
                        "min_clearance_mm": 40, "lip_fillet_mm": 8,
                        "material_id": "basalt_slab"}},
        {"element_id": "x1", "primitive": "sculptural_column",
         "parameters": {"diameter_mm": 100, "height_mm": 300,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "f1"}},
    ]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "no stackable top face" in str(exc.value)


def test_cascade_composes_as_a_child_on_a_plinth(tmp_path):
    from app.geometry.exporters import export_glb
    from app.geometry.validate import validate_assembly

    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 500, "height_mm": 200,
                        "material_id": "basalt_slab"}},
        {"element_id": "f1", "primitive": "tiered_cascade",
         "parameters": {"tiers": 1, "tier_top_diameter_mm": 200,
                        "basin_diameter_mm": 400, "basin_height_mm": 200,
                        "column_diameter_mm": 80, "dish_depth_mm": 40, "bore_diameter_mm": 25,
                        "min_clearance_mm": 40, "lip_fillet_mm": 8,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    solid, manifest = assemble(plan, seed=1)
    assert len(solid.solids()) == 1
    # the cascade's canonical params carry the resolved per-member wall
    f1 = next(e for e in manifest["elements"] if e["element_id"] == "f1")
    assert f1["parameters"]["column_wall_mm"] == f1["parameters"]["basin_wall_mm"]

    out = tmp_path / "cascade_on_plinth.glb"
    export_glb(solid, out)
    assert validate_assembly(out, manifest).passed


def test_insert_punching_through_the_floor_refused():
    plan = _gate_plan()
    plan[2]["joint"]["overlap_mm"] = 70   # basin floor is 60
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "punch through" in str(exc.value)


def test_insert_that_does_not_fit_refused():
    plan = _gate_plan()
    plan[2]["parameters"]["diameter_mm"] = 500  # 500 + 100 clearance > 550
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "does not fit inside" in str(exc.value)
    assert "min_clearance_mm" in str(exc.value)


def test_tangent_contact_through_the_floor_refused_adr029():
    # basin base sits at z=290 (10 into the plinth); its seat is at 350.
    # overlap 50 puts the column base at exactly z=300 — the plinth's top
    # plane. Distance 0, intersection 0: the ADR-029 knife edge, refused.
    plan = _gate_plan()
    plan[2]["joint"]["overlap_mm"] = 50
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "TANGENT" in str(exc.value) and "ADR-029" in str(exc.value)


def test_undeclared_interference_refused():
    # overlap 55 pushes the column 5 mm into the plinth — a real overlap
    # with no declared joint between c1 and p1.
    plan = _gate_plan()
    plan[2]["joint"]["overlap_mm"] = 55
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "WITHOUT a declared joint" in str(exc.value)


def test_floating_body_refused_with_real_numbers():
    # A 100 mm column centred over a hollow plinth's 300 mm hole. Before
    # ADR-053 this fell through to the B-rep interference proof ("does NOT
    # interfere"); the bearing check now refuses it EARLIER and cheaper,
    # with the seat arithmetic (-100.0 mm: the hole edge is 150 mm out,
    # the column reaches only 50). Same intent, better refusal. The B-rep
    # interference proof remains in place as the construction-level
    # backstop for shapes the annulus arithmetic cannot foresee.
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 500, "height_mm": 300,
                        "wall_mm": 100, "material_id": "cast_concrete_c35_45"}},
        {"element_id": "c1", "primitive": "sculptural_column",
         "parameters": {"diameter_mm": 100, "height_mm": 300,
                        "material_id": "bronze_cast"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    text = str(exc.value)
    assert "-100.0 mm radial seat" in text
    assert "15 mm floor" in text  # bronze on concrete: cross-material MAX


def test_plan_structure_violations_are_aggregated():
    plan = [
        {"element_id": "a", "primitive": "no_such_primitive",
         "parameters": {}},
        {"element_id": "a", "primitive": "plinth", "parameters": {}},
        {"element_id": "b", "primitive": "plinth", "parameters": {},
         "joint": {"type": "weld", "parent": "ghost"}},
    ]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    msg = str(exc.value)
    assert "duplicated" in msg
    assert "no_such_primitive" in msg
    assert "weld" in msg and "ghost" in msg


def test_joint_cycle_refused():
    plan = [
        {"element_id": "a", "primitive": "plinth", "parameters": {},
         "joint": {"type": "stack_on", "parent": "b"}},
        {"element_id": "b", "primitive": "plinth", "parameters": {},
         "joint": {"type": "stack_on", "parent": "a"}},
    ]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    msg = str(exc.value)
    assert "cycle" in msg or "exactly ONE root" in msg


def test_element_parameter_violations_carry_the_element_id():
    plan = _gate_plan()
    plan[1]["parameters"]["wall_mm"] = 5   # below basalt's 20 mm floor
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan)
    assert "b1: wall_mm=5 < material minimum 20" in str(exc.value)


# ---------------------------------------------------------------------------
# fabrication limits — the dead schema fields become load-bearing (plan §5)
# ---------------------------------------------------------------------------

def test_max_lift_refused_with_hollowing_hint():
    # The signed sheet's own worked example: 1.0 x 1.0 m solid basalt
    # plinth = 2,121 kg against a 2,000 kg crane.
    plan = [{"element_id": "p1", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 1000, "height_mm": 1000,
                            "material_id": "basalt_slab"}}]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan, fabrication={"max_lift_kg": 2000})
    msg = str(exc.value)
    assert "> max_lift_kg 2000" in msg
    assert "hollowing" in msg  # the conversation is hollowing, not shrinking


def test_hollow_plinth_passes_the_same_crane():
    plan = [{"element_id": "p1", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 1000, "height_mm": 1000,
                            "wall_mm": 180, "material_id": "basalt_slab"}}]
    _, manifest = assemble(plan, fabrication={"max_lift_kg": 2000})
    assert manifest["elements"][0]["mass_kg"] == pytest.approx(1252, abs=2)


def test_max_module_refused_before_segmentation_exists():
    plan = [{"element_id": "p1", "primitive": "plinth",
             "parameters": {"top_diameter_mm": 1500, "height_mm": 1200,
                            "material_id": "basalt_slab"}}]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan, fabrication={"max_module_m": 1.0})
    assert "exceeds max_module_m 1" in str(exc.value)
    assert "slice C" in str(exc.value)


# ---------------------------------------------------------------------------
# mesh-level body count — the silent two-body failure (plan §8.5)
# ---------------------------------------------------------------------------

def test_validate_assembly_counts_disjoint_bodies(tmp_path):
    """A GLB of two disjoint closed boxes is watertight at every vertex —
    and is NOT one assembly. body_count must fail it."""
    from build123d import Compound, Pos, Solid

    from app.geometry.exporters import export_glb
    from app.geometry.validate import validate_assembly

    b1 = Solid.make_box(100, 100, 100)
    b2 = Pos(500, 0, 0) * Solid.make_box(100, 100, 100)
    two = Compound(children=[b1, b2])
    out = tmp_path / "two_bodies.glb"
    export_glb(two, out)

    manifest = {
        "elements": [], "joints": [],
        "volume_conservation": {"assembly_volume_mm3": 2_000_000.0},
        "total_mass_kg": 1.0,
    }
    report = validate_assembly(out, manifest)
    assert report.body_count == 2
    assert not report.passed


# --- ADR-053: the stack_on seat is a bearing, not a lip ---------------------


def _hollow_plinth_basin_plan(plinth_wall_mm: float):
    """The exact shape the operator built live on 2026-08-26 (design
    a3006a42): basin ⌀2000 stacked on a hollow plinth ⌀2200. At wall 102
    the plinth's inner mouth is ⌀1996 and the basin bears on a 2 mm lip."""
    return [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 2200, "height_mm": 800,
                        "wall_mm": plinth_wall_mm,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                        "floor_mm": 160, "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]


def test_stack_on_knife_edge_seat_refused_with_real_numbers():
    with pytest.raises(ConstraintViolation) as exc:
        assemble(_hollow_plinth_basin_plan(102), seed=7)
    text = str(exc.value)
    assert "2.0 mm" in text            # the measured seat
    assert "10 mm floor" in text       # basalt §2.1 floor
    assert "1996" in text              # the parent's inner mouth, named
    assert "Thicken the parent wall" in text


def test_stack_on_wide_seat_passes_and_fuses():
    # wall 150 -> inner mouth 1900 -> 50 mm seat >= the 10 mm floor
    solid, manifest = assemble(_hollow_plinth_basin_plan(150), seed=7)
    assert manifest["body_count_brep"] == 1
    assert manifest["joints"][0]["intersection_volume_mm3"] > 0
    vc = manifest["volume_conservation"]
    assert vc["delta_pct"] <= vc["tolerance_pct"]


def test_stack_on_offset_child_keeps_full_disc_bearing():
    """A laterally offset child on a SOLID parent keeps full support while
    its base stays inside the parent's top face — the offset must not be
    mistaken for a hole reaching in (solid parent has no hole)."""
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 900, "height_mm": 300,
                        "material_id": "basalt_slab"}},
        {"element_id": "c1", "primitive": "sculptural_column",
         "parameters": {"diameter_mm": 200, "height_mm": 400,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1",
                   "x_offset_mm": 300}},
    ]
    solid, manifest = assemble(plan, seed=7)
    assert manifest["body_count_brep"] == 1
