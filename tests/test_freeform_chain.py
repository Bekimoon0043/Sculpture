"""FF-A2 (ADR-066): the freeform_loop end-to-end chain — red-first.

The REAL product path with the REAL primitive (no shim): spec fixture ->
/build -> persisted freeform_integrity_v1 row (pass, with the topology
contract) -> structural/fabrication/rigging needs_input naming the
armature -> costing 409 incomplete_mass -> segmentation analysis ->
PRE-FABRICATION export whose warrant carries ONLY unresolved rows
(armature mass/centroid/allocation, forming radius, wall approval) while
the PASSING integrity verdict lives in validation/freeform_integrity_v1
.json — plus the three REFUSED negatives: missing, failed AND
indeterminate integrity rows (ADR-065 decision 5, v4 §D.3).
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.database import get_default_db, reset_default_db  # noqa: E402
from app.db.models import ValidationReportRow  # noqa: E402
from app.geometry.freeform_validation import (  # noqa: E402
    FREEFORM_INTEGRITY_GATE,
)
from app.main import app  # noqa: E402

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "freeform_loop_spec_v1.json")
    .read_text())
PAYLOAD = {k: v for k, v in FIXTURE.items() if not k.startswith("_")}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ffa2_chain")
    import os
    old_db = os.environ.get("LUXURYFORM_DB")
    old_data = os.environ.get("LUXURYFORM_DATA_DIR")
    os.environ["LUXURYFORM_DB"] = str(tmp / "ffa2_test.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(tmp / "data")
    reset_default_db()
    with TestClient(app) as test_client:
        yield test_client
    for key, val in (("LUXURYFORM_DB", old_db),
                     ("LUXURYFORM_DATA_DIR", old_data)):
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val
    reset_default_db()


@pytest.fixture(scope="module")
def built(client):
    """One expensive real build shared by the module's read-only tests."""
    resp = client.post("/api/geometry/assembly/build", json=PAYLOAD)
    assert resp.status_code == 200, resp.text
    return resp.json()


def integrity_rows(design_id):
    db = get_default_db()
    with db.get_session() as s:
        return s.execute(
            select(ValidationReportRow).where(
                ValidationReportRow.design_id == design_id,
                ValidationReportRow.gate_name == FREEFORM_INTEGRITY_GATE,
            )).scalars().all()


class TestManifestTruth:
    def test_mass_incomplete_and_snapshot_persisted(self, built):
        manifest = built["manifest"]
        assert manifest["total_mass_kg"] is None
        assert manifest["mass_model"]["mass_complete"] is False
        el = manifest["elements"][0]
        assert el["mass_model"]["total_mass_kg"] is None
        missing = " ".join(el["mass_model"]["missing_mass_inputs"])
        assert "armature mass" in missing
        assert "armature centroid" in missing
        assert "per-module armature allocation" in missing
        assert manifest["required_validation_gates"] == [
            FREEFORM_INTEGRITY_GATE]
        assert manifest["expected_topology"]["per_component_genus"] == [1, 1]

    def test_known_geometry_mass_basis_includes_plate(self, built):
        """v4 §C item 6: known_geometry_mass_kg is ALL modeled 316L —
        loop shell + interface plate — volume x density."""
        import math
        el = built["manifest"]["elements"][0]
        p = el["parameters"]
        known = el["mass_model"]["known_geometry_mass_kg"]
        # MassTruth.wire() rounds to 3 decimals — assert THAT contract
        # exactly, not an unrounded value at an impossible tolerance
        # (the ADR-064 operator-found-red lesson, applied first-hand).
        assert known == round(el["mass_kg"], 3)
        assert known == round(el["volume_mm3"] * 1e-9 * 8000.0, 3)
        plate_kg = (math.pi * (p["base_plate_diameter_mm"] / 2.0) ** 2
                    * p["wall_mm"] * 1e-9 * 8000.0)
        # the plate is a small, real part of the figure (not 483 kg)
        assert 5.0 < plate_kg < 25.0
        assert known > plate_kg

    def test_wall_measurement_block_persisted(self, built):
        wm = built["manifest"]["elements"][0]["wall_measurement"]
        assert wm["method"] == "brepextrema_v1"
        assert wm["status"] in ("measured", "unavailable")
        if wm["status"] == "measured":
            assert wm["min_mm"] > 0

    def test_segmentation_is_analysis_with_conserved_volume(self, built):
        seg = built["manifest"]["segmentation"]["elements"]["loop_01"]
        modules = seg["modules"]
        assert len(modules) >= 1
        total = sum(m["volume_mm3"] for m in modules)
        el_vol = built["manifest"]["elements"][0]["volume_mm3"]
        assert total == pytest.approx(el_vol, rel=1e-6)


class TestValidationRows:
    def test_integrity_row_persisted_and_passing(self, built):
        rows = integrity_rows(built["design_id"])
        assert len(rows) == 1
        report = json.loads(rows[0].numbers_json)
        assert report["status"] == "pass", report
        by_name = {c["check"]: c for c in report["checks"]}
        assert by_name["topology_boundary_components"]["value"] == 2
        assert by_name["topology_per_component_genus"]["value"] == [1, 1]
        assert by_name["topology_closed_internal_cavities"]["value"] == 1

    def test_gates_need_input_never_pass_on_incomplete_mass(self, built):
        reports = built["validation_gates"]
        fab = reports["fabrication"]
        checks = {c["check"]: c for c in fab["checks"]}
        lift = checks["loop_01.mass_kg"]
        assert lift["status"] == "needs_input"
        assert "INCOMPLETE" in lift["message"]
        approval = checks["loop_01.fabrication_wall_approval"]
        assert approval["status"] == "needs_input"
        forming = checks["loop_01.forming_radius_mm"]
        assert forming["status"] == "needs_input"
        assert "FABRICATOR-INPUT-REQUIRED" in forming["message"]
        # owner clarification 2: measured clearance row present and real
        bore = checks["loop_01.bore_to_cavity_clearance"]
        assert bore["status"] == "pass", bore
        assert bore["value"] >= 5.5
        structural = reports["structure_static_v1"]
        s_checks = {c["check"]: c for c in structural["checks"]}
        assert s_checks["total_mass_kg"]["status"] == "needs_input"
        assert fab["status"] != "pass"
        assert structural["status"] != "pass"

    def test_costing_refuses_409_incomplete_mass(self, client, built):
        resp = client.get(f"/api/costing/bom/{built['design_id']}")
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["error"] == "incomplete_mass"
        assert any("armature" in m for m in detail["missing_mass_inputs"])


class TestExportBoundary:
    def test_pre_fabrication_package_and_honest_warrant(
            self, client, built, tmp_path):
        design_id = built["design_id"]
        resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
        assert resp.status_code == 200, resp.text
        assert resp.json()["package_class"] == "pre_fabrication"

        zip_resp = client.get(
            f"/api/geometry/assembly/{design_id}/luxexchange.zip")
        assert zip_resp.status_code == 200
        pkg = tmp_path / "pkg.zip"
        pkg.write_bytes(zip_resp.content)
        with zipfile.ZipFile(pkg) as zf:
            names = set(zf.namelist())
            assert "ENGINEERING_WARRANT.txt" in names
            # the PASSING verdict lives in the validation evidence...
            gate_json = f"validation/{FREEFORM_INTEGRITY_GATE}.json"
            assert gate_json in names
            sealed = json.loads(zf.read(gate_json))
            assert sealed["status"] == "pass"
            # ...and the warrant carries ONLY unresolved professional
            # inputs (v4 §D.2 / operator amendment 6 of round 3).
            warrant = zf.read("ENGINEERING_WARRANT.txt").decode("utf-8")
            assert "armature mass" in warrant
            assert "forming radius" in warrant.lower()
            assert "fabrication_wall_approval" in warrant
            assert FREEFORM_INTEGRITY_GATE + "] topology" not in warrant
            for line in warrant.splitlines():
                if "status:" in line:
                    assert "pass" not in line.split("status:")[1], line

    def test_export_determinism_per_design_seed_class(self, client, built):
        design_id = built["design_id"]
        a = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
        b = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
        assert a["content_digest"] == b["content_digest"]


class TestRefusedNegatives:
    """Missing, FAILED and INDETERMINATE rows all refuse (ADR-065 d.5).
    Each negative build gets its own design so the read-only fixtures
    stay untouched."""

    def build(self, client):
        resp = client.post("/api/geometry/assembly/build", json=PAYLOAD)
        assert resp.status_code == 200, resp.text
        return resp.json()["design_id"]

    def _tamper(self, design_id, new_status):
        db = get_default_db()
        with db.get_session() as s:
            for row in s.execute(
                select(ValidationReportRow).where(
                    ValidationReportRow.design_id == design_id,
                    ValidationReportRow.gate_name ==
                    FREEFORM_INTEGRITY_GATE,
                )).scalars().all():
                if new_status is None:
                    s.delete(row)
                else:
                    report = json.loads(row.numbers_json)
                    report["status"] = new_status
                    row.numbers_json = json.dumps(report, sort_keys=True)
                    row.status = new_status
                    row.passed = 0

    def test_missing_row_refuses(self, client):
        design_id = self.build(client)
        self._tamper(design_id, None)
        resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
        assert resp.status_code == 409, resp.text
        assert "MISSING" in resp.text

    def test_failed_row_refuses(self, client):
        design_id = self.build(client)
        self._tamper(design_id, "fail")
        resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
        assert resp.status_code == 409, resp.text

    def test_indeterminate_row_refuses(self, client):
        design_id = self.build(client)
        self._tamper(design_id, "needs_input")
        resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
        assert resp.status_code == 409, resp.text
