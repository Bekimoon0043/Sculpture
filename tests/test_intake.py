"""Phase 12 — brief intake: typed contexts with per-field provenance.

Core honesty chain under test: `unknown` stays distinguishable from
`default`, the operator's word always beats the parser's, and unknowns
propagate to the gates as needs_input instead of quietly becoming numbers.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.db.database import reset_default_db
from app.intake.models import (
    IntakeV1,
    Sourced,
    readiness,
    summary_block,
    to_dna_filters,
    to_site_overrides,
    to_water_context,
)
from app.intake.parser import merge_parsed, parse_prompt


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXURYFORM_DB", str(tmp_path / "intake_test.db"))
    monkeypatch.setenv("LUXURYFORM_DATA_DIR", str(tmp_path / "data"))
    reset_default_db()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_default_db()


def _operator_intake() -> IntakeV1:
    intake = IntakeV1()
    intake.project.project_type = Sourced(value="fountain", source="operator")
    intake.dimensions.height_m = Sourced(value=2.4, source="operator")
    intake.dimensions.footprint_m = Sourced(value=3.0, source="operator")
    intake.site.indoor = Sourced(value=False, source="operator")
    intake.site.design_wind_speed_m_s = Sourced(value=30.0, source="operator")
    intake.water.has_water = Sourced(value=True, source="operator")
    intake.water.flow_l_per_min = Sourced(value=120.0, source="operator")
    intake.water.operating_depth_mm = Sourced(value=200.0, source="operator")
    intake.water.nozzle_bore_mm = Sourced(value=20.0, source="operator")
    return intake


# --- provenance model -------------------------------------------------------

def test_unknown_and_default_are_different_things():
    unknown = Sourced.unknown()
    defaulted = Sourced.default(15.0)
    assert not unknown.known()
    assert defaulted.known()
    assert unknown.source == "unknown" and defaulted.source == "default"


def test_wire_format_keeps_the_schema_key():
    wire = IntakeV1().dump_wire()
    assert wire["schema"] == "intake_v1"
    assert "schema_id" not in wire


# --- parser merge rules -----------------------------------------------------

def test_operator_fields_are_never_overwritten_by_the_parser():
    intake = IntakeV1()
    intake.dimensions.height_m = Sourced(value=2.4, source="operator")
    merged, counts = merge_parsed(intake, {
        "dimensions.height_m": {"value": 9.9, "quote": "nine point nine metres"},
        "water.has_water": {"value": True, "quote": "a water feature"},
    })
    assert merged.dimensions.height_m.value == 2.4
    assert merged.dimensions.height_m.source == "operator"
    assert merged.water.has_water.value is True
    assert merged.water.has_water.source == "parsed"
    assert counts == {"applied": 1, "kept_operator": 1, "dropped": 0}


def test_parser_cannot_invent_fields_or_coerce_types():
    merged, counts = merge_parsed(IntakeV1(), {
        "secret.backdoor": {"value": "x", "quote": "?"},          # not in schema
        "dimensions.height_m": {"value": "tall", "quote": "?"},   # wrong type
        "water.has_water": {"value": None, "quote": "?"},         # null value
        "site.city": {"value": "Addis Ababa", "quote": "in Addis Ababa"},
    })
    assert counts["dropped"] == 3 and counts["applied"] == 1
    assert merged.site.city.value == "Addis Ababa"
    assert merged.site.city.quote == "in Addis Ababa"


def test_parse_prompt_forbids_guessing_and_lists_real_materials():
    prompt = parse_prompt("a marble fountain", ["basalt_slab", "bronze_cast"])
    assert "OMIT any field the brief does not state" in prompt
    assert "basalt_slab" in prompt and "bronze_cast" in prompt
    assert "a marble fountain" in prompt


# --- readiness tiers (R5) ---------------------------------------------------

def test_readiness_ranks_missing_fields_by_what_they_block():
    ready = readiness(IntakeV1())
    assert ready["ready_for_council"] is False
    tier1 = {r["field"] for r in ready["missing_by_tier"]["1"]}
    assert {"project.project_type", "dimensions.height_m",
            "dimensions.footprint_m"} <= tier1


def test_indoor_pieces_are_not_asked_for_a_wind_speed():
    intake = IntakeV1()
    intake.site.indoor = Sourced(value=True, source="operator")
    missing2 = readiness(intake)["missing_by_tier"].get("2", [])
    assert not any(r["field"] == "site.design_wind_speed_m_s" for r in missing2)


def test_tier_3_and_4_do_not_block_council():
    ready = readiness(_operator_intake())
    assert ready["ready_for_council"] is True
    assert "3" in ready["missing_by_tier"]  # budget unknown — allowed, stated


# --- converters -------------------------------------------------------------

def test_unknown_water_fields_map_to_none_never_a_guess():
    ctx = to_water_context(IntakeV1())
    assert ctx == {
        "has_water": None, "flow_l_per_min": None, "operating_depth_mm": None,
        "nozzle_bore_mm": None, "recirculating": None,
    }


def test_site_overrides_carry_values_and_sources():
    overrides = to_site_overrides(_operator_intake())
    assert overrides["design_wind_speed_m_s"] == 30.0
    assert overrides["_source"]["design_wind_speed_m_s"] == "operator"
    assert "allowable_bearing_kpa" not in overrides  # unknown stays absent


def test_indoor_forces_the_wind_case_to_zero():
    intake = _operator_intake()
    intake.site.indoor = Sourced(value=True, source="operator")
    assert to_site_overrides(intake)["design_wind_speed_m_s"] == 0.0


def test_dna_filters_come_from_known_fields_only():
    filters = to_dna_filters(_operator_intake())
    assert filters == {"has_water": True, "height_m": 2.4}


def test_summary_block_marks_unknowns_and_sources():
    block = summary_block(_operator_intake(), "intake-1")
    assert "BEGIN NORMALIZED INTAKE intake-1" in block
    assert "do not invent a value for an UNKNOWN field" in block
    assert "2.4 m (operator)" in block
    assert "UNKNOWN" in block  # budget was never stated


# --- API flow ---------------------------------------------------------------

def test_intake_crud_and_confirmation_flow(client):
    created = client.post("/api/intake", json={
        "brief_text": "A granite fountain for a plaza in Addis Ababa.",
        "fields": {"project.project_type": "fountain"},
    })
    assert created.status_code == 201
    body = created.json()
    intake_id = body["id"]
    assert body["intake"]["project"]["project_type"]["source"] == "operator"
    assert body["readiness"]["ready_for_council"] is False

    # Confirming an unready intake is refused with the missing fields named.
    refused = client.post(f"/api/intake/{intake_id}/confirm")
    assert refused.status_code == 409
    assert "missing_by_tier" in refused.json()["detail"]

    # Operator fills tier 1+2 by hand — free, no provider call.
    updated = client.put(f"/api/intake/{intake_id}", json={"fields": {
        "dimensions.height_m": 2.4, "dimensions.footprint_m": 3.0,
        "site.indoor": False, "site.design_wind_speed_m_s": 30.0,
        "water.has_water": True,
    }}).json()
    assert updated["readiness"]["ready_for_council"] is True

    confirmed = client.post(f"/api/intake/{intake_id}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    # Editing after confirmation reopens the draft — the confirmation
    # covered the OLD content.
    reopened = client.put(f"/api/intake/{intake_id}", json={"fields": {
        "dimensions.height_m": 2.6,
    }}).json()
    assert reopened["status"] == "draft"

    latest = client.get("/api/intake/latest").json()
    assert latest["id"] == intake_id
    assert "summary_block" in latest


def test_unknown_field_names_are_rejected_loudly(client):
    resp = client.post("/api/intake", json={"fields": {"site.mars_base": True}})
    assert resp.status_code == 422
    assert "site.mars_base" in str(resp.json()["detail"])


def test_parse_without_keys_fails_honestly_and_form_still_works(client):
    created = client.post("/api/intake", json={"brief_text": "a fountain"}).json()
    resp = client.post(f"/api/intake/{created['id']}/parse")
    assert resp.status_code == 503
    assert "fill the fields by hand" in resp.json()["detail"]
    # And the form does still work by hand:
    assert client.put(f"/api/intake/{created['id']}", json={
        "fields": {"project.project_type": "fountain"}
    }).status_code == 200
