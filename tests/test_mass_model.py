"""FF-A1 (ADR-065): the incomplete-mass truth model — unit contract.

The null/fail-closed contract, asserted literally:
  * total_mass_kg is None when incomplete — NEVER zero.
  * unknown, malformed or inconsistent mass-model data fails closed.
  * absent mass fields mean complete ONLY for the frozen legacy ten.
"""

from __future__ import annotations

import pytest

from app.geometry.mass_model import (
    LEGACY_COMPLETE_MASS_PRIMITIVES,
    MALFORMED_REQUIRED_GATES,
    MassTruth,
    assembly_mass_truth,
    element_mass_truth,
    required_validation_gates,
)


def legacy_element(mass=1200.0, primitive="basin_round"):
    return {"element_id": "e1", "primitive": primitive, "mass_kg": mass}


class TestLegacyInterpretation:
    def test_all_ten_legacy_primitives_are_complete_by_absence(self):
        assert len(LEGACY_COMPLETE_MASS_PRIMITIVES) == 10
        for pid in sorted(LEGACY_COMPLETE_MASS_PRIMITIVES):
            truth = element_mass_truth(legacy_element(500.0, pid))
            assert truth.mass_complete is True
            assert truth.total_mass_kg == 500.0
            assert truth.missing_mass_inputs == ()

    def test_unknown_primitive_without_block_fails_closed(self):
        truth = element_mass_truth(legacy_element(500.0, "freeform_loop"))
        assert truth.mass_complete is False
        assert truth.total_mass_kg is None
        assert "freeform_loop" in truth.missing_mass_inputs[0]

    def test_incomplete_total_is_none_never_zero(self):
        truth = element_mass_truth(legacy_element(0.0, "mystery"))
        assert truth.total_mass_kg is None
        assert truth.total_mass_kg != 0.0


class TestExplicitBlock:
    def test_valid_incomplete_block(self):
        e = legacy_element()
        e["mass_model"] = {
            "mass_complete": False,
            "known_geometry_mass_kg": 708.2,
            "missing_mass_inputs": ["armature mass (FABRICATOR-INPUT-REQUIRED)"],
            "total_mass_kg": None,
        }
        truth = element_mass_truth(e)
        assert truth.mass_complete is False
        assert truth.known_geometry_mass_kg == 708.2
        assert truth.total_mass_kg is None
        assert "armature" in truth.missing_mass_inputs[0]

    def test_valid_complete_block(self):
        e = legacy_element()
        e["mass_model"] = {
            "mass_complete": True,
            "known_geometry_mass_kg": 708.2,
            "missing_mass_inputs": [],
            "total_mass_kg": 708.2,
        }
        truth = element_mass_truth(e)
        assert truth.mass_complete is True
        assert truth.total_mass_kg == 708.2

    @pytest.mark.parametrize("block, defect", [
        ("not a dict", "not an object"),
        ({"mass_complete": "yes", "known_geometry_mass_kg": 1.0,
          "missing_mass_inputs": []}, "not a boolean"),
        ({"mass_complete": True, "known_geometry_mass_kg": -5.0,
          "missing_mass_inputs": []}, "non-negative"),
        ({"mass_complete": True, "known_geometry_mass_kg": 1.0,
          "missing_mass_inputs": ["x"]}, "inconsistent"),
        ({"mass_complete": False, "known_geometry_mass_kg": 1.0,
          "missing_mass_inputs": []}, "inconsistent"),
        ({"mass_complete": True, "known_geometry_mass_kg": 1.0,
          "missing_mass_inputs": [], "total_mass_kg": 2.0}, "inconsistent"),
        ({"mass_complete": False, "known_geometry_mass_kg": 1.0,
          "missing_mass_inputs": ["x"], "total_mass_kg": 1.0},
         "must be null"),
    ])
    def test_malformed_or_inconsistent_fails_closed(self, block, defect):
        e = legacy_element()
        e["mass_model"] = block
        truth = element_mass_truth(e)
        assert truth.mass_complete is False
        assert truth.total_mass_kg is None
        assert any(defect in m for m in truth.missing_mass_inputs), \
            truth.missing_mass_inputs


class TestAssemblyAggregate:
    def test_all_complete_sums(self):
        manifest = {"elements": [legacy_element(100.0), legacy_element(50.0)]}
        truth = assembly_mass_truth(manifest)
        assert truth.mass_complete is True
        assert truth.total_mass_kg == 150.0

    def test_one_incomplete_poisons_the_total(self):
        manifest = {"elements": [
            legacy_element(100.0),
            legacy_element(50.0, "freeform_loop"),
        ]}
        truth = assembly_mass_truth(manifest)
        assert truth.mass_complete is False
        assert truth.total_mass_kg is None
        assert truth.known_geometry_mass_kg == 150.0

    def test_empty_manifest_fails_closed(self):
        truth = assembly_mass_truth({"elements": []})
        assert truth.mass_complete is False
        assert truth.total_mass_kg is None

    def test_wire_block_serializes_null_not_zero(self):
        wire = MassTruth(False, 42.0, ("armature",)).wire()
        assert wire["total_mass_kg"] is None
        assert wire["known_geometry_mass_kg"] == 42.0
        wire_ok = MassTruth(True, 42.0, ()).wire()
        assert wire_ok["total_mass_kg"] == 42.0


class TestRequiredValidationGates:
    def test_absent_key_means_no_extra_gates(self):
        assert required_validation_gates({"schema": "x"}) == ()

    def test_well_formed_list_round_trips(self):
        m = {"required_validation_gates": ["freeform_integrity_v1"]}
        assert required_validation_gates(m) == ("freeform_integrity_v1",)

    @pytest.mark.parametrize("raw", [
        "freeform_integrity_v1", 42, {"gate": "x"}, [42], [""], [None],
    ])
    def test_malformed_snapshot_returns_sentinel(self, raw):
        m = {"required_validation_gates": raw}
        assert required_validation_gates(m) == (MALFORMED_REQUIRED_GATES,)

    def test_non_dict_manifest_is_malformed(self):
        assert required_validation_gates(None) == (MALFORMED_REQUIRED_GATES,)
