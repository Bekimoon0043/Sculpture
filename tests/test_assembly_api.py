"""Assembly API — Phase 7A build/persist, Phase 8 gates, Phase 9A exports.

Beyond the happy path, these lock in the three behaviours the foundation
slice got wrong:

* GET never mutates. Polling the exports endpoint used to insert DB rows.
* One row per (design, format). Three downloads used to produce nine rows.
* A warning is never reported as a pass, at any layer of the response.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import zipfile

import pytest

build123d = pytest.importorskip("build123d", reason="build123d not installed")
trimesh = pytest.importorskip("trimesh", reason="trimesh not installed")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.database import reset_default_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "api_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    with TestClient(app) as test_client:
        yield test_client
    reset_default_db()


def valid_assembly_payload() -> dict:
    return {
        "seed": 7,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "elements": [
            {
                "element_id": "plinth_01",
                "primitive": "plinth",
                "parameters": {
                    "top_diameter_mm": 2200,
                    "height_mm": 300,
                    "wall_mm": 120,
                },
            },
            {
                "element_id": "basin_01",
                "primitive": "basin_round",
                "parameters": {
                    "diameter_mm": 2000,
                    "height_mm": 450,
                    "wall_mm": 40,
                    "floor_mm": 160,
                    "min_clearance_mm": 220,
                },
                "joint": {"type": "stack_on", "parent": "plinth_01"},
            },
            {
                "element_id": "column_01",
                "primitive": "sculptural_column",
                "parameters": {
                    "diameter_mm": 360,
                    "height_mm": 900,
                    "bore_mm": 80,
                },
                "joint": {"type": "concentric_insert", "parent": "basin_01"},
            },
        ],
    }


# ---------------------------------------------------------------------------
# Registry surface
# ---------------------------------------------------------------------------

def test_assembly_defaults_expose_live_registry_profiles_and_formats(client):
    resp = client.get("/api/geometry/assembly/defaults")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "assembly_defaults_v1"
    assert set(body["primitives"]) >= {
        "basin_round", "plinth", "sculptural_column", "tiered_cascade",
    }
    assert "tiers" in body["primitives"]["tiered_cascade"]["parameters"]
    assert body["primitives"]["basin_round"]["can_parent_insert"] is True
    assert "basalt_slab" in body["materials"]
    assert body["joint_types"] == ["stack_on", "concentric_insert"]

    # Phase 8: the UI must be able to say which thresholds are unset rather
    # than only showing needs_input rows with no remedy.
    profiles = body["gate_profiles"]
    assert profiles["default"] == "public_plaza"
    plaza = profiles["profiles"]["public_plaza"]
    assert plaza["signed_off"] is False
    assert "design_wind_speed_m_s" in plaza["unset_thresholds"]

    # Phase 9A: the format catalogue is visible before anything is exported.
    formats = {f["format"] for f in body["export_formats"]}
    assert {"STEP", "DXF", "STL", "OBJ", "DWG"} <= formats


# ---------------------------------------------------------------------------
# Build + validate
# ---------------------------------------------------------------------------

def test_assembly_build_persists_manifest_artifacts_and_gate_statuses(client, tmp_path):
    resp = client.post("/api/geometry/assembly/build", json=valid_assembly_payload())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    design_id = body["design_id"]

    assert body["manifest"]["schema"] == "assembly_manifest_v1"
    assert body["manifest"]["body_count_brep"] == 1
    assert len(body["manifest"]["elements"]) == 3
    # Phase 8 needs real centroids and world-space extents, not placements.
    for element in body["manifest"]["elements"]:
        assert set(element["centroid_mm"]) == {"x", "y", "z"}
        assert len(element["bbox_min_mm"]) == 3
        assert len(element["bbox_max_mm"]) == 3
    assert len(body["manifest"]["assembly_bbox_min_mm"]) == 3

    assert body["validation"]["passed"] is True
    assert set(body["validation_gates"]) == {
        "structure_static_v1", "hydraulics", "fabrication",
    }
    assert body["gate_profile_id"] == "public_plaza"
    assert len(body["step_sha256"]) == 64

    # With no water context and an unsigned profile, the honest answer is
    # needs_input — NOT a pass.
    assert body["overall_status"] == "needs_input"
    assert body["passed"] is False

    latest = client.get("/api/geometry/assembly/latest/manifest").json()
    assert latest["design_id"] == design_id
    assert latest["artifacts"]["step_sha256"] == body["step_sha256"]

    glb = client.get("/api/geometry/assembly/latest.glb")
    assert glb.status_code == 200 and glb.content[:4] == b"glTF"
    step = client.get("/api/geometry/assembly/latest.step")
    assert step.status_code == 200 and b"ISO-10303-21" in step.content

    db = sqlite3.connect(str(tmp_path / "api_test.db"))
    gate_rows = db.execute(
        "SELECT gate_name, status, passed FROM validation_reports "
        "WHERE design_id = ? ORDER BY gate_name", (design_id,)
    ).fetchall()
    db.close()
    by_gate = {name: (status, passed) for name, status, passed in gate_rows}
    assert set(by_gate) == {
        "assembly_mesh", "structure_static_v1", "hydraulics", "fabrication",
    }
    # `passed` is now defined as status == "pass". A needs_input row is not
    # a pass, which is exactly what the old `!= fail` definition got wrong.
    for status, passed in by_gate.values():
        assert passed == (1 if status == "pass" else 0)


def test_a_warned_design_is_never_reported_as_passing(client):
    """Regression: `passed = status != "fail"` made a warned design green."""
    payload = valid_assembly_payload()
    # Real water context: the pump turns this basin over far too fast, which
    # is a warning under an unsigned profile.
    payload["water"] = {
        "has_water": True,
        "flow_l_per_min": 2000,
        "operating_depth_mm": 200,
        "nozzle_bore_mm": 80,
    }
    body = client.post("/api/geometry/assembly/build", json=payload).json()
    hydraulics = body["validation_gates"]["hydraulics"]
    assert hydraulics["status"] in {"warn", "fail"}

    validation = client.get("/api/geometry/assembly/latest/validation").json()
    assert validation["overall_status"] != "pass"
    assert validation["passed"] is False
    assert validation["gate_statuses"]["hydraulics"] == hydraulics["status"]


def test_water_context_drives_real_hydraulic_numbers(client):
    payload = valid_assembly_payload()
    payload["water"] = {
        "has_water": True,
        "flow_l_per_min": 120,
        "operating_depth_mm": 200,
        "nozzle_bore_mm": 20,
    }
    body = client.post("/api/geometry/assembly/build", json=payload).json()
    rows = {r["check"]: r for r in body["validation_gates"]["hydraulics"]["rows"]}
    assert rows["basin_01.reservoir_capacity_l"]["value"] > 0
    assert rows["basin_01.freeboard_mm"]["status"] == "pass"
    # The bore band is DERIVED from the declared flow, not a magic range.
    assert "sqrt(4Q/(pi*v))" in rows["nozzle_bore_mm"]["basis"]
    assert rows["nozzle_bore_mm"]["status"] == "pass"


def test_diagnostic_build_returns_geometry_for_an_overweight_element(client):
    """ADR-034: the operator sees the piece and the number that disqualifies it.

    The old behaviour was a 422 with nothing to look at.
    """
    payload = valid_assembly_payload()
    payload["fabrication"] = {"max_lift_kg": 50, "max_module_m": 4.0}

    resp = client.post("/api/geometry/assembly/build", json=payload)
    assert resp.status_code == 200, "a limit breach must still produce geometry"
    body = resp.json()
    assert body["manifest"]["fabrication_limit_violations"], (
        "the breach must be recorded on the manifest"
    )
    fabrication = body["validation_gates"]["fabrication"]
    assert fabrication["status"] == "fail"
    heavy = [r for r in fabrication["rows"]
             if r["check"].endswith(".mass_kg") and r["status"] == "fail"]
    assert heavy, "the gate must name the overweight element"
    assert heavy[0]["limit"] == 50.0
    assert body["overall_status"] == "fail"

    glb = client.get("/api/geometry/assembly/latest.glb")
    assert glb.status_code == 200, "the operator must be able to look at it"


def test_strict_build_still_refuses_an_overweight_element(client):
    """The AI fabrication loop needs a hard refusal — unchanged."""
    payload = valid_assembly_payload()
    payload["fabrication"] = {"max_lift_kg": 50, "max_module_m": 4.0}
    payload["strict"] = True

    resp = client.post("/api/geometry/assembly/build", json=payload)
    assert resp.status_code == 422
    joined = " ".join(resp.json()["detail"]["violations"])
    assert "max_lift_kg" in joined


def test_assembly_unknown_primitive_fails_before_artifacts(client):
    payload = valid_assembly_payload()
    payload["elements"][1]["primitive"] = "lotus_crown"
    resp = client.post("/api/geometry/assembly/build", json=payload)
    assert resp.status_code == 422
    joined = " ".join(resp.json()["detail"]["violations"])
    assert "primitive 'lotus_crown' is not in the registry" in joined


def test_unknown_gate_profile_is_refused(client):
    payload = valid_assembly_payload()
    payload["gate_profile_id"] = "atlantis"
    resp = client.post("/api/geometry/assembly/build", json=payload)
    assert resp.status_code == 422
    assert "unknown gate profile" in " ".join(resp.json()["detail"]["violations"])


# ---------------------------------------------------------------------------
# Export jobs
# ---------------------------------------------------------------------------

def test_export_is_a_post_and_reading_status_never_writes(client, tmp_path):
    """Regression: the old GET download wrote files AND inserted rows."""
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]

    db_path = str(tmp_path / "api_test.db")

    def export_row_count() -> int:
        db = sqlite3.connect(db_path)
        n = db.execute("SELECT COUNT(*) FROM exports").fetchone()[0]
        db.close()
        return n

    assert export_row_count() == 0

    # Before any export job, the package does not exist and the download
    # says so instead of quietly building one.
    before = client.get(f"/api/geometry/assembly/{design_id}/exports").json()
    assert before["package_built"] is False
    assert export_row_count() == 0
    assert client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip").status_code == 409

    first = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
    after_first = export_row_count()
    assert after_first > 0

    # Polling status and downloading must not add rows.
    for _ in range(3):
        client.get(f"/api/geometry/assembly/{design_id}/exports")
        client.get("/api/geometry/assembly/latest/exports")
        client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip")
    assert export_row_count() == after_first

    # Re-exporting UPDATES in place rather than appending.
    second = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
    assert export_row_count() == after_first
    assert second["content_digest"] == first["content_digest"]


def test_export_package_is_reproducible_and_self_verifying(client, tmp_path):
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]

    first = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
    package_a = client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip").content
    second = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
    package_b = client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip").content

    assert first["content_digest"] == second["content_digest"]
    assert package_a == package_b, "the same design must export to the same bytes"

    zip_path = tmp_path / "pkg.zip"
    zip_path.write_bytes(package_a)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        zf.extractall(extracted)
        manifest = json.loads(zf.read("luxexchange_v1.json"))

    assert "verify_luxexchange.py" in names
    assert "CHECKSUMS.sha256" in names
    assert "README_DWG_SKP.txt" in names
    assert "exports/assembly.dxf" in names
    assert "validation/structure_static_v1.json" in names
    assert manifest["schema"] == "luxexchange_v1"
    assert manifest["design"]["overall_status"] == "needs_input"

    proc = subprocess.run(
        [sys.executable, str(extracted / "verify_luxexchange.py")],
        capture_output=True, text=True, cwd=str(extracted),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert first["content_digest"] in proc.stdout


def test_export_status_reports_four_honest_statuses(client):
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    body = client.get(f"/api/geometry/assembly/{design_id}/exports").json()
    by_format = {row["format"]: row for row in body["exports"]}
    assert by_format["STEP"]["status"] == "included"
    assert by_format["DXF"]["status"] == "included"
    assert by_format["STL"]["status"] == "included"
    assert by_format["DWG"]["status"] == "impossible"
    assert by_format["USD"]["status"] == "unavailable"
    assert body["package_built"] is True
    assert body["last_job"]["status"] == "completed"
    # Hashes are stored, not recomputed on every poll.
    assert len(by_format["STEP"]["sha256"]) == 64


def test_validation_reports_persisted_with_the_package_parse_as_strict_json(client):
    """No `Infinity`, no `NaN` — a fabricator's parser must not choke."""
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")
    raw = client.get(f"/api/geometry/assembly/{design_id}/luxexchange.zip").content

    def _reject(value):  # parse_constant fires on Infinity / -Infinity / NaN
        raise AssertionError(f"non-finite constant in package JSON: {value}")

    import io

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in zf.namelist():
            if name.endswith(".json"):
                json.loads(zf.read(name).decode("utf-8"), parse_constant=_reject)


# ---------------------------------------------------------------------------
# Legacy rows — reports written before the four-status model
# ---------------------------------------------------------------------------

def test_a_legacy_warn_row_is_not_reported_as_a_pass(client, tmp_path):
    """Found live 2026-08-21 on the operator's own database.

    Rows written before the Phase 8 `status` column have status NULL and
    `passed = 1`, because `passed` then meant "did not fail". Falling back to
    `"pass" if row.passed else "fail"` resurrected exactly the lie Phase 8
    exists to stop: a warned gate reported PASS.
    """
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]

    db = sqlite3.connect(str(tmp_path / "api_test.db"))
    # Recreate the legacy shape: NULL column, passed=1, warn inside the JSON.
    db.execute(
        "UPDATE validation_reports SET status = NULL, passed = 1, "
        "numbers_json = ? WHERE design_id = ? AND gate_name = 'hydraulics'",
        (json.dumps({"schema": "layered_validation_report_v1",
                     "gate_name": "hydraulics", "status": "warn",
                     "passed": True, "checks": []}), design_id),
    )
    db.commit()
    db.close()

    body = client.get(f"/api/geometry/assembly/{design_id}/validation").json()
    assert body["gate_statuses"]["hydraulics"] == "warn"
    assert body["overall_status"] != "pass"
    assert body["passed"] is False


def test_a_legacy_row_with_no_status_anywhere_is_needs_input(client, tmp_path):
    """We genuinely cannot tell whether it passed or warned, so we say so."""
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]

    db = sqlite3.connect(str(tmp_path / "api_test.db"))
    db.execute(
        "UPDATE validation_reports SET status = NULL, passed = 1, "
        "numbers_json = ? WHERE design_id = ? AND gate_name = 'fabrication'",
        (json.dumps({"gate_name": "fabrication", "passed": True}), design_id),
    )
    db.commit()
    db.close()

    body = client.get(f"/api/geometry/assembly/{design_id}/validation").json()
    assert body["gate_statuses"]["fabrication"] == "needs_input"
    assert body["passed"] is False


def test_the_mesh_report_survives_the_legacy_fallback(client, tmp_path):
    """A mesh report has a genuine two-state verdict and must stay a pass."""
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]

    db = sqlite3.connect(str(tmp_path / "api_test.db"))
    db.execute(
        "UPDATE validation_reports SET status = NULL "
        "WHERE design_id = ? AND gate_name = 'assembly_mesh'", (design_id,)
    )
    db.commit()
    db.close()

    body = client.get(f"/api/geometry/assembly/{design_id}/validation").json()
    assert body["gate_statuses"]["assembly_mesh"] == "pass"


def test_every_gate_payload_carries_rows_the_ui_can_render(client):
    """Regression: a gate entry with neither `rows` nor `checks` made the
    Validation panel throw and blanked the whole page to black.

    The panel is now defensive, but the API should also not hand it a shape
    it cannot render without special-casing.
    """
    client.post("/api/geometry/assembly/build", json=valid_assembly_payload())
    body = client.get("/api/geometry/assembly/latest/validation").json()

    for name, gate in body["gates"].items():
        if name == "assembly_mesh":
            # The mesh report is surfaced through `validation`, not as a
            # layered gate card — it legitimately has no `checks`.
            continue
        rows = gate.get("rows") or gate.get("checks")
        assert isinstance(rows, list), f"gate {name} has no renderable rows"


# ---------------------------------------------------------------------------
# Per-file downloads (export UI)
# ---------------------------------------------------------------------------

def test_each_included_format_downloads_on_its_own(client):
    """"Just send me the DXF" is the most common real request.

    A format listed in the panel that cannot be fetched on its own is a dead
    end, so every `included` row carries a working download_url.
    """
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    body = client.get(f"/api/geometry/assembly/{design_id}/exports").json()
    included = [r for r in body["exports"]
                if r["status"] == "included" and r["format"] != "LUXEXCHANGE"]
    assert len(included) >= 8

    for row in included:
        assert row["download_url"], f"{row['format']} has no download link"
        resp = client.get(row["download_url"])
        assert resp.status_code == 200, f"{row['format']}: {resp.text[:120]}"
        assert len(resp.content) == row["bytes"]
        # Served as a file to save, not something to render in the page.
        assert "attachment" in resp.headers["content-disposition"]
        assert row["filename"] in resp.headers["content-disposition"]

    step = client.get(f"/api/geometry/assembly/{design_id}/exports/STEP/download")
    assert step.headers["content-type"].startswith("application/step")
    assert b"ISO-10303-21" in step.content
    dxf = client.get(f"/api/geometry/assembly/{design_id}/exports/DXF/download")
    assert dxf.headers["content-type"].startswith("image/vnd.dxf")


def test_downloading_before_exporting_says_what_to_do(client):
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    resp = client.get(f"/api/geometry/assembly/{design_id}/exports/DXF/download")
    assert resp.status_code == 409
    assert "POST" in resp.json()["detail"]


def test_an_absent_format_refuses_with_its_reason_not_a_broken_file(client):
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    usd = client.get(f"/api/geometry/assembly/{design_id}/exports/USD/download")
    assert usd.status_code == 409
    assert "render worker" in usd.json()["detail"]

    dwg = client.get(f"/api/geometry/assembly/{design_id}/exports/DWG/download")
    assert dwg.status_code == 409
    assert "DXF" in dwg.json()["detail"]

    unknown = client.get(f"/api/geometry/assembly/{design_id}/exports/NOPE/download")
    assert unknown.status_code == 404
    assert "unknown format" in unknown.json()["detail"]


def test_absent_formats_never_offer_a_dead_link(client):
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    body = client.get(f"/api/geometry/assembly/{design_id}/exports").json()
    for row in body["exports"]:
        if row["status"] != "included":
            assert row["download_url"] is None, (
                f"{row['format']} is {row['status']} but offers a download link"
            )


def test_exports_are_listed_in_registry_order_not_alphabetically(client):
    """STEP is the file a machinist opens; it belongs above BREP."""
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    formats = [r["format"] for r in
               client.get(f"/api/geometry/assembly/{design_id}/exports").json()["exports"]]
    assert formats.index("STEP") < formats.index("BREP")
    assert formats.index("DXF") < formats.index("GLB")     # CAD before mesh
    assert formats.index("PLY") < formats.index("DWG")     # real before impossible
    assert formats[-1] == "LUXEXCHANGE"                    # the package last


def test_export_status_carries_what_the_panel_needs_to_group_files(client):
    design_id = client.post(
        "/api/geometry/assembly/build", json=valid_assembly_payload()
    ).json()["design_id"]
    client.post(f"/api/geometry/assembly/{design_id}/exports")

    body = client.get(f"/api/geometry/assembly/{design_id}/exports").json()
    assert body["package_bytes"] > 0
    by_format = {r["format"]: r for r in body["exports"]}
    assert by_format["STEP"]["tier"] == "cad"
    assert by_format["OBJ"]["tier"] == "mesh"
    assert by_format["USD"]["tier"] == "render"
    # Every row explains what it is for, so the panel never shows a bare code.
    for row in body["exports"]:
        assert row["purpose"], f"{row['format']} has no purpose text"
