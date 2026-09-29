"""LF-103A — the export boundary enforces the gate verdict.

End-to-end over the real API (hermetic temp DB + temp data dir):

* FAILED: no package may be created; fabrication-capable CAD downloads
  refuse; mesh downloads are marked DIAGNOSTIC; the viewport stream stays.
* PRE-FABRICATION (every real design today): the package seals with
  ENGINEERING_WARRANT.txt, marked entry names, a marked download filename,
  and honest class metadata — canonical bytes untouched.
* LEGACY_UNCLASSIFIED: an old zip without a sealed package_class never
  downloads as if clean; its bytes are never rewritten.
* The builder itself refuses FAILED (internal-call bypass closed).
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.database import reset_default_db  # noqa: E402
from app.db.database import get_default_db  # noqa: E402
from app.db.models import ExportRow, JobRow  # noqa: E402
from app.main import app  # noqa: E402


def valid_assembly_payload() -> dict:
    """Same three-element fixture as test_assembly_api (kept local: sibling
    test-module imports do not resolve under this pytest import mode)."""
    return {
        "seed": 7,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "elements": [
            {
                "element_id": "plinth_01",
                "primitive": "plinth",
                "parameters": {
                    "top_diameter_mm": 2200, "height_mm": 300, "wall_mm": 120,
                },
            },
            {
                "element_id": "basin_01",
                "primitive": "basin_round",
                "parameters": {
                    "diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                    "floor_mm": 160, "min_clearance_mm": 220,
                },
                "joint": {"type": "stack_on", "parent": "plinth_01"},
            },
            {
                "element_id": "column_01",
                "primitive": "sculptural_column",
                "parameters": {
                    "diameter_mm": 360, "height_mm": 900, "bore_mm": 80,
                },
                "joint": {"type": "concentric_insert", "parent": "basin_01"},
            },
        ],
    }


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "boundary_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    with TestClient(app) as test_client:
        yield test_client
    reset_default_db()


def _build(client, payload=None):
    resp = client.post("/api/geometry/assembly/build",
                       json=payload or valid_assembly_payload())
    assert resp.status_code == 200, resp.text
    return resp.json()


def failing_payload() -> dict:
    """A design whose fabrication gate FAILS on an always-binding Design
    Spec limit (ADR-034 strict=False: it builds, and the gate says fail)."""
    payload = valid_assembly_payload()
    payload["fabrication"] = {"max_lift_kg": 50}  # plinth alone is far heavier
    return payload


def _filled_bundle_for_budget_test():
    """Arbitrary in-memory TEST rates: prove the budget boundary only.

    No value here has engineering/commercial meaning and nothing is written
    to config/costing.yaml.
    """
    from app.core.config import CostingConfig, load_config_bundle

    bundle = load_config_bundle()
    raw = bundle.costing.model_dump()
    for m in raw["materials"].values():
        m["buy_price"] = {"amount": 100.0, "currency": "ETB", "per": "kg"}
        m["waste_factor_pct"] = 10.0
        m["fabrication"]["method"] = "hand_carve"
        m["fabrication"]["labor"] = {
            "amount": 200.0, "currency": "ETB", "per": "hour"}
        m["fabrication"]["hours_per_m3"] = 40.0
        m["finishing"] = {"amount": 500.0, "currency": "ETB", "per": "m2"}
        m["seam"] = {"amount": 300.0, "currency": "ETB", "per": "m"}
    raw["workshop"]["overhead_pct"] = 15.0
    raw["install"]["crew_day_rate"] = {
        "amount": 1000.0, "currency": "ETB", "per": "crew_day"}
    raw["install"]["crew_size"] = 4
    raw["install"]["days_per_tonne"] = 0.5
    raw["install"]["transport"] = {
        "amount": 8000.0, "currency": "ETB", "per": "trip"}
    raw["install"]["truck_payload_kg"] = 12000.0
    raw["install"]["modules_per_trip"] = 4
    raw["contingency_pct"] = 10.0
    raw["markup_pct"] = 20.0
    raw["joints"] = {"cross_material_owner": "parent"}
    raw["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "2026-09-28"}
    return bundle.model_copy(update={"costing": CostingConfig(**raw)})


# ---------------------------------------------------------------------------
# REFUSED
# ---------------------------------------------------------------------------

def test_failed_design_builds_but_cannot_package(client):
    built = _build(client, failing_payload())
    design_id = built["design_id"]
    assert built["overall_status"] == "fail"  # ADR-034: visible, not hidden

    resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "fail" in detail
    assert "max_lift_kg" in detail or "mass" in detail  # names the check


def test_failed_design_refuses_fabrication_capable_downloads(client):
    built = _build(client, failing_payload())
    design_id = built["design_id"]

    # /latest.step serves the same fabrication-capable bytes with no
    # ExportRow at all — it must refuse too.
    resp = client.get("/api/geometry/assembly/latest.step")
    assert resp.status_code == 409
    assert "fail" in resp.json()["detail"]

    for fmt in ("STEP", "BREP", "DXF"):
        resp = client.get(
            f"/api/geometry/assembly/{design_id}/exports/{fmt}/download")
        assert resp.status_code == 409, fmt
        assert "fail" in resp.json()["detail"], fmt


def test_failed_design_keeps_diagnostic_viewing(client):
    built = _build(client, failing_payload())
    design_id = built["design_id"]

    # The viewport stream is untouched (ADR-034's viewing right).
    resp = client.get(f"/api/geometry/assembly/{design_id}/scene.glb")
    assert resp.status_code == 200

    # The GLB attachment stays available but is explicitly marked.
    resp = client.get(f"/api/geometry/assembly/{design_id}.glb")
    assert resp.status_code == 200
    disposition = resp.headers.get("content-disposition", "")
    assert "DIAGNOSTIC-NOT-FOR-FABRICATION" in disposition


# ---------------------------------------------------------------------------
# PRE-FABRICATION
# ---------------------------------------------------------------------------

def test_confirmed_over_budget_design_writes_no_export_or_package(
        client, monkeypatch):
    """PR-6/D-19: budget binds BEFORE job, geometry rebuild or file writes."""
    intake = client.post("/api/intake", json={
        "brief_text": "Fountain with a deliberately tiny budget ceiling.",
        "fields": {
            "project.project_type": "fountain",
            "dimensions.height_m": 2.4,
            "dimensions.footprint_m": 3.0,
            "site.indoor": False,
            "site.design_wind_speed_m_s": 30.0,
            "water.has_water": True,
            "budget.amount_max": 1.0,
            "budget.currency": "ETB",
        },
    })
    assert intake.status_code == 201, intake.text
    intake_id = intake.json()["id"]
    confirmed = client.post(f"/api/intake/{intake_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text

    payload = valid_assembly_payload()
    payload["intake_id"] = intake_id
    built = _build(client, payload)
    design_id = built["design_id"]

    import app.api.routes_costing as costing_routes
    monkeypatch.setattr(costing_routes, "load_config_bundle",
                        _filled_bundle_for_budget_test)

    db = get_default_db()
    with db.get_session() as session:
        assert session.execute(select(ExportRow).where(
            ExportRow.design_id == design_id)).scalars().all() == []
        assert session.execute(select(JobRow).where(
            JobRow.session_id == design_id,
            JobRow.job_type == "export")).scalars().all() == []

    from app.api.routes_assembly import PACKAGE_NAME, _package_dir
    package_path = _package_dir(design_id) / PACKAGE_NAME
    assert not package_path.exists()

    resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "budget_exceeded"
    assert detail["source"] == "confirmed brief intake"
    assert detail["total_usd"] > detail["ceiling_usd"]

    with db.get_session() as session:
        assert session.execute(select(ExportRow).where(
            ExportRow.design_id == design_id)).scalars().all() == []
        assert session.execute(select(JobRow).where(
            JobRow.session_id == design_id,
            JobRow.job_type == "export")).scalars().all() == []
    assert not package_path.exists()

def test_pre_fabrication_package_is_marked_warranted_and_verifiable(
        client, tmp_path):
    built = _build(client)
    design_id = built["design_id"]
    assert built["overall_status"] == "needs_input"  # every real design today

    resp = client.post(f"/api/geometry/assembly/{design_id}/exports")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["package_class"] == "pre_fabrication"

    # The zip: warrant present, entry names marked, manifest classified.
    zip_resp = client.get(
        f"/api/geometry/assembly/{design_id}/luxexchange.zip")
    assert zip_resp.status_code == 200
    assert "PRE-FABRICATION" in zip_resp.headers.get("content-disposition", "")

    pkg = tmp_path / "pkg.zip"
    pkg.write_bytes(zip_resp.content)
    with zipfile.ZipFile(pkg) as zf:
        names = set(zf.namelist())
        assert "ENGINEERING_WARRANT.txt" in names
        assert "exports/assembly.PRE-FABRICATION.step" in names
        assert "exports/assembly.step" not in names
        manifest = json.loads(zf.read("luxexchange_v1.json"))
        assert manifest["package_class"] == "pre_fabrication"
        warrant = zf.read("ENGINEERING_WARRANT.txt").decode("utf-8")
        assert "NOT" in warrant and "fabrication-ready" in warrant
        assert design_id in warrant

    # The shipped verifier still passes on a marked package.
    extract_dir = tmp_path / "extracted"
    with zipfile.ZipFile(pkg) as zf:
        zf.extractall(extract_dir)
    proc = subprocess.run(
        [sys.executable, str(extract_dir / "verify_luxexchange.py")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_pre_fabrication_cad_download_is_marked_but_bytes_are_canonical(
        client):
    built = _build(client)
    design_id = built["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    resp = client.get(
        f"/api/geometry/assembly/{design_id}/exports/STEP/download")
    assert resp.status_code == 200
    assert "PRE-FABRICATION" in resp.headers.get("content-disposition", "")

    # Marking is filename-only: the bytes are the canonical STEP, untouched.
    manifest = client.get(
        f"/api/geometry/assembly/{design_id}/manifest").json()
    step_path = Path(manifest["artifacts"]["step_path"])
    assert resp.content == step_path.read_bytes()


def test_pre_fabrication_package_is_still_byte_reproducible(client):
    built = _build(client)
    design_id = built["design_id"]
    a = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
    b = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
    assert a["content_digest"] == b["content_digest"]
    zip_a = client.get(
        f"/api/geometry/assembly/{design_id}/luxexchange.zip").content
    zip_b = client.get(
        f"/api/geometry/assembly/{design_id}/luxexchange.zip").content
    assert zip_a == zip_b


def test_exports_status_reports_both_classes(client):
    built = _build(client)
    design_id = built["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")
    status = client.get(
        f"/api/geometry/assembly/{design_id}/exports").json()
    assert status["design_class"] == "pre_fabrication"
    assert status["package_class"] == "pre_fabrication"


# ---------------------------------------------------------------------------
# The builder refuses on its own — internal-call bypass closed
# ---------------------------------------------------------------------------

def test_builder_refuses_failed_reports_directly(tmp_path):
    from app.geometry.luxexchange import build_luxexchange_package
    from app.geometry.package_class import PackageRefused

    failing_reports = {
        "assembly_mesh": {"passed": True, "watertight": True},
        "structure_static_v1": {
            "schema": "layered_validation_report_v2",
            "gate_name": "structure_static_v1", "status": "fail",
            "gate_profile_id": "public_plaza", "gate_profiles_version": 1,
            "profile_signed_off": False, "checks": [],
        },
    }
    with pytest.raises(PackageRefused):
        build_luxexchange_package(
            tmp_path / "refused.zip", seed=1,
            design={"design_id": "d-refused", "seed": 1},
            request_payload={}, assembly_manifest={},
            validation_reports=failing_reports, exports=[],
        )
    assert not (tmp_path / "refused.zip").exists()


def test_builder_with_no_reports_seals_pre_fabrication_never_clean(tmp_path):
    from app.geometry.luxexchange import build_luxexchange_package

    path, manifest, _ = build_luxexchange_package(
        tmp_path / "bare.zip", seed=1,
        design={"design_id": "d-bare", "seed": 1},
        request_payload={}, assembly_manifest={},
        validation_reports={}, exports=[],
    )
    assert manifest["package_class"] == "pre_fabrication"
    with zipfile.ZipFile(path) as zf:
        assert "ENGINEERING_WARRANT.txt" in zf.namelist()


# ---------------------------------------------------------------------------
# LEGACY_UNCLASSIFIED — old zips fail closed, bytes untouched
# ---------------------------------------------------------------------------

def test_legacy_package_without_class_refuses_download_and_is_untouched(
        client):
    built = _build(client)
    design_id = built["design_id"]

    # Hand-seal an old-style package (no package_class) where the route
    # expects it — exactly what every pre-LF-103A zip on disk looks like.
    from app.api.routes_assembly import PACKAGE_NAME, _package_dir
    from app.geometry.luxexchange import PackageBuilder

    builder = PackageBuilder(seed=7)
    builder.add_json("luxexchange_v1.json", {"schema": "luxexchange_v1"})
    pkg_path = _package_dir(design_id) / PACKAGE_NAME
    builder.seal(pkg_path, provenance={})
    before = pkg_path.read_bytes()

    resp = client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "unclassified" in detail.lower()
    assert "re-export" in detail or "POST" in detail  # the one exact action

    assert pkg_path.read_bytes() == before  # never rewritten
