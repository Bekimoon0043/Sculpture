"""FF-A1 (ADR-065): every consumer of mass behaves honestly on an
INCOMPLETE mass — behavioral tests, one per audited consumer.

Two layers:
  * Unit-level: hand-crafted incomplete manifests through the gates,
    drivers, DNA tagger, critique scorer and classifier.
  * Integration: a shim incomplete-mass primitive (a hand-constructed
    test double wrapping the real plinth module — production never
    simulates anything) registered for the test, driven through the REAL
    assemble -> persist -> classify -> export -> costing chain.
"""

from __future__ import annotations

import json
import types

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import (  # noqa: E402
    DEFAULT_GATE_PROFILE_ID,
    load_config_bundle,
)
from app.costing.drivers import (  # noqa: E402
    IncompleteMassError,
    drivers_for_assembly,
)
from app.council.critique import objective_score  # noqa: E402
from app.db.database import get_default_db, reset_default_db  # noqa: E402
from app.db.models import ValidationReportRow  # noqa: E402
from app.dna import store as dna_store  # noqa: E402
from app.geometry import gates as gates_mod  # noqa: E402
from app.geometry.freeform_validation import FREEFORM_INTEGRITY_GATE  # noqa: E402
from app.geometry.mass_model import MassTruth  # noqa: E402
from app.geometry.package_class import (  # noqa: E402
    CLASS_REFUSED,
    classify_reports,
)
from app.geometry.primitives import PRIMITIVES, plinth  # noqa: E402
from app.geometry.validate import AssemblyValidationReport, VolumeCrossCheck  # noqa: E402
from app.main import app  # noqa: E402

MISSING = ("armature mass and centroid (FABRICATOR-INPUT-REQUIRED)",)


def _element(eid: str, mass: float, incomplete: bool) -> dict:
    e = {
        "element_id": eid, "primitive": "plinth", "material_id": "basalt_slab",
        "parameters": {"wall_mm": 120.0},
        "placement_mm": {"x": 0.0, "y": 0.0, "z": 0.0},
        "volume_mm3": mass / 2700.0 * 1e9,
        "mass_kg": mass,
        "bbox_mm": [2000.0, 2000.0, 400.0],
        "bbox_min_mm": [-1000.0, -1000.0, 0.0],
        "bbox_max_mm": [1000.0, 1000.0, 400.0],
        "centroid_mm": {"x": 0.0, "y": 0.0, "z": 200.0},
    }
    if incomplete:
        e["mass_model"] = MassTruth(False, mass, MISSING).wire()
    return e


def incomplete_manifest() -> dict:
    elements = [_element("root_01", 900.0, incomplete=True)]
    return {
        "schema": "assembly_manifest_v1", "seed": 7,
        "elements": elements, "joints": [],
        "fabrication_limits": {"max_lift_kg": 3000.0, "max_module_m": None},
        "fabrication_limit_violations": [], "strict": True,
        "total_mass_kg": None,
        "mass_model": MassTruth(False, 900.0, MISSING).wire(),
        "assembly_bbox_min_mm": [-1000.0, -1000.0, 0.0],
        "assembly_bbox_max_mm": [1000.0, 1000.0, 400.0],
        "body_count_brep": 1,
    }


def _rows(report, check_name):
    return [c for c in report.checks if c.check == check_name]


class TestGatesRefuseToPassOnIncompleteMass:
    def setup_method(self):
        bundle = load_config_bundle()
        self.profiles = bundle.gate_profiles
        self.profile_id = DEFAULT_GATE_PROFILE_ID
        self.profile = self.profiles.profile(self.profile_id)
        self.materials = bundle.materials.materials

    def test_structural_total_centroid_overturning_bearing_needs_input(self):
        report = gates_mod.validate_structural_gate(
            incomplete_manifest(), self.materials, profile=self.profile,
            profile_id=self.profile_id, constants=self.profiles.constants,
            version=self.profiles.version)
        total = _rows(report, "total_mass_kg")[0]
        assert total.status == "needs_input"
        assert "FABRICATOR-INPUT-REQUIRED" in total.message
        stability = _rows(report, "stability")[0]
        assert stability.status == "needs_input"
        # centroid/overturning/bearing must not have been evaluated at all
        assert not _rows(report, "center_of_mass_lever_mm")
        assert not _rows(report, "ground_bearing_pressure_kpa")
        assert report.status in ("needs_input", "fail")
        assert report.status != "pass"

    def test_fabrication_lift_needs_input_named(self):
        report = gates_mod.validate_fabrication_gate(
            incomplete_manifest(), self.materials, profile=self.profile,
            profile_id=self.profile_id, version=self.profiles.version)
        lift = _rows(report, "root_01.mass_kg")[0]
        assert lift.status == "needs_input"
        assert "INCOMPLETE" in lift.message
        assert "FABRICATOR-INPUT-REQUIRED" in lift.message

    def test_rigging_cannot_be_ruled_out_on_incomplete_mass(self):
        m = incomplete_manifest()
        # known-geometry mass BELOW the handling limit — the dangerous case
        m["elements"][0]["mass_kg"] = 10.0
        m["elements"][0]["mass_model"] = MassTruth(False, 10.0, MISSING).wire()
        report = gates_mod.validate_fabrication_gate(
            m, self.materials, profile=self.profile,
            profile_id=self.profile_id, version=self.profiles.version)
        rig = _rows(report, "rigging_declared")
        assert rig and rig[0].status == "needs_input"

    def test_complete_manifest_unchanged(self):
        m = incomplete_manifest()
        m["elements"][0].pop("mass_model")
        m["total_mass_kg"] = 900.0
        m.pop("mass_model")
        report = gates_mod.validate_structural_gate(
            m, self.materials, profile=self.profile,
            profile_id=self.profile_id, constants=self.profiles.constants,
            version=self.profiles.version)
        assert _rows(report, "total_mass_kg")[0].status == "pass"
        assert _rows(report, "center_of_mass_lever_mm")


class TestCostingRefusesIncompleteMass:
    def test_drivers_raise_incomplete_mass_error(self):
        m = incomplete_manifest()
        report = AssemblyValidationReport(
            glb_path="x.glb", element_count=1, joint_count=0,
            watertight=True, winding_consistent=True, body_count=1,
            volume_mm3=1e8, surface_area_mm2=1e6, degenerate_face_count=0,
            face_count=100, element_masses_kg={"root_01": 900.0},
            total_mass_kg=None,
            volume_crosscheck=VolumeCrossCheck(
                trimesh_volume_mm3=1e8, build123d_volume_mm3=1e8,
                delta_pct=0.0, tolerance_pct=2.0, within_tolerance=True),
            passed=True)
        with pytest.raises(IncompleteMassError) as err:
            drivers_for_assembly(report, m)
        assert err.value.known_geometry_mass_kg == 900.0
        assert "FABRICATOR-INPUT-REQUIRED" in err.value.missing_mass_inputs[0]


class TestDnaAndCritique:
    def test_dna_tags_carry_null_not_zero(self):
        stored = {"manifest": incomplete_manifest(),
                  "request": {"seed": 7, "water": {}}}
        tags = dna_store.derive_tags(stored, {}, "pass", None)
        assert tags["total_mass_kg"] is None
        assert tags["mass_complete"] is False

    def test_dna_tags_complete_unchanged(self):
        m = incomplete_manifest()
        m["elements"][0].pop("mass_model")
        m.pop("mass_model")
        m["total_mass_kg"] = 900.0
        stored = {"manifest": m, "request": {"seed": 7, "water": {}}}
        tags = dna_store.derive_tags(stored, {}, "pass", None)
        assert tags["total_mass_kg"] == 900.0
        assert tags["mass_complete"] is True

    def test_critique_marks_mass_component_unavailable(self):
        """PR-5 (ADR-068, operator clarification 1): an incomplete mass
        makes the handling component GENUINELY unavailable — the composite
        is None, with the missing basis recorded — never a numeric 0.0
        that could be compared against a real score."""
        from app.council.critique import objective_score_detail
        with_mass = objective_score({"pick_mass_kg": 100.0,
                                     "max_lift_kg": 1000.0,
                                     "mass_basis": "measured_heaviest_module"})
        without = objective_score_detail({"pick_mass_kg": None,
                                          "max_lift_kg": 1000.0,
                                          "mass_basis": "unavailable",
                                          "mass_basis_reason": "armature mass"})
        assert with_mass is not None
        assert without.score is None
        assert without.handling.kind == "unavailable"
        assert "armature mass" in without.handling.reason


class TestClassifierRefusesOnRequiredGate:
    BASE = {
        "assembly_mesh": {"watertight": True, "passed": True},
        "structure_static_v1": {"status": "pass", "checks": [],
                                "gate_profile_id": "p", "profile_signed_off": False,
                                "gate_profiles_version": 1},
        "hydraulics": {"status": "pass", "checks": [],
                       "gate_profile_id": "p", "profile_signed_off": False,
                       "gate_profiles_version": 1},
        "fabrication": {"status": "pass", "checks": [],
                        "gate_profile_id": "p", "profile_signed_off": False,
                        "gate_profiles_version": 1},
    }

    def classify(self, extra_reports=None, required=("freeform_integrity_v1",)):
        reports = dict(self.BASE)
        reports.update(extra_reports or {})
        return classify_reports(reports, required_validation_gates=required)

    def test_missing_required_row_refuses(self):
        result = self.classify()
        assert result.package_class == CLASS_REFUSED
        assert any("MISSING" in r for r in result.reasons)

    def test_failed_required_row_refuses(self):
        result = self.classify({FREEFORM_INTEGRITY_GATE: {
            "status": "fail", "checks": [
                {"check": "occ_analyzer_valid", "status": "fail",
                 "value": False, "limit": True}]}})
        assert result.package_class == CLASS_REFUSED
        assert any("occ_analyzer_valid" in r for r in result.reasons)

    def test_indeterminate_required_row_refuses(self):
        result = self.classify({FREEFORM_INTEGRITY_GATE: {
            "status": "needs_input", "checks": []}})
        assert result.package_class == CLASS_REFUSED
        assert any("INDETERMINATE" in r for r in result.reasons)

    def test_unknown_required_gate_refuses(self):
        result = self.classify(required=("mystery_gate_v9",))
        assert result.package_class == CLASS_REFUSED

    def test_malformed_snapshot_refuses(self):
        result = self.classify(
            required=("__malformed_required_validation_gates__",))
        assert result.package_class == CLASS_REFUSED

    def test_passing_required_row_does_not_refuse(self):
        result = self.classify({FREEFORM_INTEGRITY_GATE: {
            "status": "pass", "checks": []}})
        assert result.package_class != CLASS_REFUSED

    def test_legacy_no_snapshot_unchanged(self):
        result = classify_reports(dict(self.BASE))
        assert result.package_class != CLASS_REFUSED


# ---------------------------------------------------------------------------
# Integration: the real chain with a shim incomplete-mass primitive
# ---------------------------------------------------------------------------

SHIM_ID = "ffa1_incomplete_plinth"


def _shim_module() -> types.ModuleType:
    shim = types.ModuleType(SHIM_ID)
    for name, value in vars(plinth).items():
        if not name.startswith("__"):
            setattr(shim, name, value)
    shim.PRIMITIVE_ID = SHIM_ID
    shim.INCOMPLETE_MASS_INPUTS = MISSING
    shim.REQUIRES_FREEFORM_INTEGRITY = True
    return shim


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "ffa1_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setitem(PRIMITIVES, SHIM_ID, _shim_module())
    reset_default_db()
    with TestClient(app) as test_client:
        yield test_client
    reset_default_db()


def shim_payload() -> dict:
    return {
        "seed": 11,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "elements": [{
            "element_id": "loop_01", "primitive": SHIM_ID,
            "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                           "wall_mm": 120},
        }],
    }


class TestIncompleteMassEndToEnd:
    def build(self, client):
        resp = client.post("/api/geometry/assembly/build",
                           json=shim_payload())
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_manifest_emits_truth_and_snapshot(self, client):
        body = self.build(client)
        manifest = body["manifest"]
        assert manifest["total_mass_kg"] is None
        assert manifest["mass_model"]["mass_complete"] is False
        assert manifest["mass_model"]["total_mass_kg"] is None
        el = manifest["elements"][0]
        assert el["mass_model"]["mass_complete"] is False
        assert "FABRICATOR-INPUT-REQUIRED" in \
            el["mass_model"]["missing_mass_inputs"][0]
        assert manifest["required_validation_gates"] == [
            FREEFORM_INTEGRITY_GATE]

    def test_integrity_row_is_persisted_by_the_same_operation(self, client):
        body = self.build(client)
        design_id = body["design_id"]
        db = get_default_db()
        with db.get_session() as s:
            rows = s.execute(
                select(ValidationReportRow).where(
                    ValidationReportRow.design_id == design_id,
                    ValidationReportRow.gate_name == FREEFORM_INTEGRITY_GATE,
                )).scalars().all()
        assert len(rows) == 1
        report = json.loads(rows[0].numbers_json)
        assert report["status"] in ("pass", "fail", "needs_input")
        # a real plinth solid passes the integrity stack
        assert report["status"] == "pass", report

    def test_export_refuses_when_required_row_is_missing(self, client):
        body = self.build(client)
        design_id = body["design_id"]
        db = get_default_db()
        with db.get_session() as s:
            for row in s.execute(
                select(ValidationReportRow).where(
                    ValidationReportRow.design_id == design_id,
                    ValidationReportRow.gate_name == FREEFORM_INTEGRITY_GATE,
                )).scalars().all():
                s.delete(row)
        resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
        assert resp.status_code == 409, resp.text
        assert "MISSING" in resp.text

    def test_designs_summary_exposes_null_total(self, client):
        self.build(client)
        resp = client.get("/api/geometry/assembly/designs")
        assert resp.status_code == 200
        entry = resp.json()["designs"][0]
        assert entry["total_mass_kg"] is None
        assert entry["mass_model"]["mass_complete"] is False

    def test_costing_returns_incomplete_mass_409(self, client):
        body = self.build(client)
        resp = client.get(f"/api/costing/bom/{body['design_id']}")
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["error"] == "incomplete_mass"
        assert detail["missing_mass_inputs"]

    def test_legacy_build_emits_no_new_keys(self, client):
        resp = client.post("/api/geometry/assembly/build", json={
            "seed": 11,
            "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
            "elements": [{
                "element_id": "p1", "primitive": "plinth",
                "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                               "wall_mm": 120},
            }],
        })
        assert resp.status_code == 200, resp.text
        manifest = resp.json()["manifest"]
        assert "mass_model" not in manifest
        assert "required_validation_gates" not in manifest
        assert "mass_model" not in manifest["elements"][0]
        assert manifest["total_mass_kg"] is not None
        assert manifest["total_mass_kg"] > 0
