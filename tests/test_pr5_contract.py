"""PR-5 (ADR-068): the AI contract, the gate bases and the critique scorer
say the same thing the fabrication gate measures — and nothing scores a
mass it cannot justify.

Operator clarifications, binding:
  1. Missing lift limits or incomplete mass make the handling component
     GENUINELY unavailable (None), never a numeric 0.0; the composite is
     None; an unavailable score is never compared.
  2. segmentation.heaviest_module_kg is used only when the mass model is
     complete; a legacy unsegmented total is a pick weight only for a
     single complete element; a multi-element unsegmented design is
     unavailable.
  3. facts_from_manifest() states the basis it selected explicitly.
"""

from __future__ import annotations

import pytest

from app.council.critique import (
    MASS_BASIS_MEASURED,
    MASS_BASIS_SINGLE,
    MASS_BASIS_UNAVAILABLE,
    facts_from_manifest,
    objective_score,
    objective_score_detail,
    score_delta,
)
from app.council.prompts import registry_surface
from app.geometry.gates import validate_fabrication_gate
from app.geometry.mass_model import LEGACY_COMPLETE_MASS_PRIMITIVES


# ---------------------------------------------------------------------------
# manifests — real shapes, no mocks
# ---------------------------------------------------------------------------

def _element(eid: str, mass: float, primitive: str = "basin_round") -> dict:
    return {"element_id": eid, "primitive": primitive,
            "material_id": "basalt_slab", "mass_kg": mass,
            "bbox_mm": [2000.0, 2000.0, 800.0],
            "parameters": {"wall_mm": 80.0}}


def _segmented(total: float = 11346.137) -> dict:
    return {
        "schema": "assembly_manifest_v1",
        "elements": [_element("b1", total)],
        "total_mass_kg": total,
        "fabrication_limits": {"max_lift_kg": 2000.0,
                               "max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2}},
        "segmentation": {
            "schema": "assembly_segmentation_v1",
            "module_count": 9, "heaviest_module_kg": 1472.31,
            "not_segmentable": [],
            "elements": {"b1": {"module_count": 9, "modules": [
                {"index": i, "mass_kg": 1472.31 if i == 0 else 1234.23,
                 "bbox_mm": [1700.0, 1700.0, 800.0]} for i in range(9)]}},
            "seams": {"split": {"count": 12, "length_mm": 50112.0,
                                "area_mm2": 3531278.0},
                      "joint": {"count": 0, "length_mm": 0.0,
                                "area_mm2": 0.0, "joints": []},
                      "total_length_mm": 50112.0},
        },
    }


def test_measured_heaviest_module_is_the_pick_weight():
    facts = facts_from_manifest(_segmented())
    assert facts["mass_basis"] == MASS_BASIS_MEASURED
    assert facts["pick_mass_kg"] == pytest.approx(1472.31)
    assert facts["max_lift_kg"] == 2000.0
    assert "9 module" in facts["mass_basis_reason"]
    detail = objective_score_detail(facts)
    assert detail.score is not None
    # scored on the module, not the 11.3 t total: 1 - 1472.31/2000
    assert detail.handling_score == pytest.approx(1.0 - 1472.31 / 2000.0)
    assert detail.handling.kind == MASS_BASIS_MEASURED


def test_single_complete_element_total_is_its_pick_weight():
    m = {"schema": "assembly_manifest_v1",
         "elements": [_element("p1", 850.0, "plinth")],
         "total_mass_kg": 850.0,
         "fabrication_limits": {"max_lift_kg": 2000.0}}
    facts = facts_from_manifest(m)
    assert facts["mass_basis"] == MASS_BASIS_SINGLE
    assert facts["pick_mass_kg"] == 850.0
    assert objective_score(facts) is not None


def test_multi_element_unsegmented_design_is_unavailable():
    """Clarification 2: an assembled total is not what a crane picks."""
    m = {"schema": "assembly_manifest_v1",
         "elements": [_element("p1", 850.0, "plinth"),
                      _element("b1", 3000.0)],
         "total_mass_kg": 3850.0,
         "fabrication_limits": {"max_lift_kg": 2000.0}}
    facts = facts_from_manifest(m)
    assert facts["mass_basis"] == MASS_BASIS_UNAVAILABLE
    assert facts["pick_mass_kg"] is None
    assert "2 elements" in facts["mass_basis_reason"]
    assert objective_score(facts) is None


def test_incomplete_mass_is_unavailable_even_when_segmented():
    """Clarification 2: heaviest_module_kg is used ONLY on a complete mass."""
    from app.geometry.mass_model import MassTruth
    m = _segmented()
    m["elements"][0]["primitive"] = "freeform_loop"
    m["elements"][0]["mass_model"] = MassTruth(
        False, 853.036, ("armature mass (FABRICATOR-INPUT-REQUIRED)",)).wire()
    m["total_mass_kg"] = None
    facts = facts_from_manifest(m)
    assert facts["mass_basis"] == MASS_BASIS_UNAVAILABLE
    assert "armature mass" in facts["mass_basis_reason"]
    detail = objective_score_detail(facts)
    assert detail.score is None
    assert detail.handling.kind == MASS_BASIS_UNAVAILABLE
    assert "armature mass" in detail.handling.reason


def test_missing_lift_limit_never_defaults():
    m = _segmented()
    m["fabrication_limits"] = {"max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2}}
    facts = facts_from_manifest(m)
    assert facts["max_lift_kg"] is None
    detail = objective_score_detail(facts)
    assert detail.score is None
    assert "max_lift_kg" in detail.handling.reason
    assert "1000" not in detail.handling.reason


def test_unavailable_is_never_an_improvement_or_a_deterioration():
    real = objective_score(facts_from_manifest(_segmented()))
    assert real is not None
    assert score_delta(None, real) is None
    assert score_delta(real, None) is None
    assert score_delta(None, None) is None


# ---------------------------------------------------------------------------
# the gate bases say what the gate measures
# ---------------------------------------------------------------------------

def _gate(manifest: dict):
    from app.core.config import DEFAULT_GATE_PROFILE_ID, load_config_bundle
    bundle = load_config_bundle()
    pid = DEFAULT_GATE_PROFILE_ID
    return validate_fabrication_gate(
        manifest, bundle.materials.materials,
        profile=bundle.gate_profiles.profile(pid), profile_id=pid,
        version=bundle.gate_profiles.version)


def test_needs_input_bases_speak_module_and_axis_not_element():
    m = _segmented()
    m["fabrication_limits"] = {}
    rows = {r["check"]: r for r in _gate(m).check_rows()}
    lift, env = rows["b1.mass_kg"], rows["b1.module_bbox_mm"]
    assert lift["status"] == "needs_input" and env["status"] == "needs_input"
    assert "heaviest module" in lift["basis"] and "1472.3" in lift["basis"]
    assert "each axis" in env["basis"]
    for row in (lift, env):
        assert ("per-" + "element") not in row["basis"]
        assert ("per-" + "element") not in row["message"]


def test_lift_row_names_the_heaviest_of_n_modules():
    rows = {r["check"]: r for r in _gate(_segmented()).check_rows()}
    lift = rows["b1.mass_kg"]
    assert lift["status"] == "pass"
    assert lift["value"] == pytest.approx(1472.31, abs=0.01)
    assert "heaviest of 9 modules" in lift["basis"]


# ---------------------------------------------------------------------------
# the AI contract says the same
# ---------------------------------------------------------------------------

def test_geometrist_contract_states_module_lift_and_per_axis_envelope():
    surface = registry_surface()
    assert "heaviest MODULE after" in surface
    assert "binds per axis" in surface
    assert ("checked per" + " element") not in surface
    assert ("bind per" + " element") not in surface
    # the index is registry-driven: every registered primitive is offered,
    # freeform_loop included — the fact FF-A3 starts from
    from app.geometry.primitives import PRIMITIVES
    for pid in PRIMITIVES:
        assert pid in surface, pid


def test_legacy_ten_is_frozen_history_not_a_registry_count():
    from app.geometry.primitives import PRIMITIVES
    assert LEGACY_COMPLETE_MASS_PRIMITIVES < set(PRIMITIVES)
