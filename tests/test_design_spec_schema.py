"""Design Spec schema tests (Amendments 1, 3, 4).

The schema file is checked as a valid Draft 2020-12 JSON Schema, then a
complete example spec — with hydraulic_network and the currency-aware budget —
is validated against it. Removal of hydraulic_network, the old budget_etb_max
field, and a bad currency pattern must all be REJECTED.
"""

from __future__ import annotations

import copy
import json

import jsonschema
import pytest


@pytest.fixture()
def schema(repo_root):
    path = repo_root / "schemas" / "design_spec_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def valid_example_spec() -> dict:
    """A complete, valid Design Spec v1 (lotus fountain, Hawassa roundabout)."""
    return {
        "meta": {
            "spec_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "schema_version": "1.0.0",
            "project_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "seed": 42,
            "spec_hash": "sha256:9b74c9897bac770ffc029102a200c5de",
            "created_by": "DESIGNER",
            "provider": "anthropic",
            "alternative_no": 1,
            "designdna_precedents": [],
        },
        "form_language": {
            "concept": "Monumental abstracted lotus rising from a still basin",
            "cultural_basis": "Ethiopian lotus motif, abstracted",
            "silhouette": "radial",
            "proportion_system": {"system": "golden", "ratio": 1.618},
            "symmetry": "radial",
            "symmetry_order": 8,
        },
        "massing": {
            "elements": [
                {
                    "element_id": "basin_01",
                    "primitive": "basin_round",
                    "parameters": {
                        "diameter": {"value": 6.0, "unit": "m"},
                        "wall": {"value": 3, "unit": "mm"},
                    },
                    "material_id": "stainless_316l_sheet",
                    "position": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
                },
                {
                    "element_id": "column_01",
                    "primitive": "sculptural_column",
                    "parameters": {
                        "height": {"value": 2400, "unit": "mm"},
                        "diameter": {"value": 600, "unit": "mm"},
                    },
                    "material_id": "bronze_cast",
                    "position": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.8},
                    "parent_id": "basin_01",
                },
            ]
        },
        "materials": [
            {
                "material_id": "stainless_316l_sheet",
                "name": "316L stainless steel sheet",
                "category": "metal",
                "finish": "mirror polish",
            },
            {
                "material_id": "bronze_cast",
                "name": "Cast bronze",
                "category": "metal",
            },
        ],
        "water": {
            "has_water": True,
            "choreography": [
                {
                    "name": "crown_jets",
                    "nozzle_elements": ["column_01"],
                    "flow_L_per_s": 4.0,
                    "jet_height_m": 2.5,
                    "sequence": "programmed",
                }
            ],
            "reservoir_element_id": "basin_01",
            "makeup_water": True,
        },
        "hydraulic_network": {
            "nodes": [
                {
                    "node_id": "pump_01",
                    "type": "pump",
                    "elevation_m": -0.5,
                    "element_id": "basin_01",
                    "pump_curve_ref": "lowara_esv_3_2",
                },
                {
                    "node_id": "nozzle_ring_01",
                    "type": "nozzle",
                    "elevation_m": 2.4,
                    # FF-A3 (ADR-069): the Designer boundary now runs the
                    # trusted mapper, whose slice-B rule (ADR-054) drills
                    # nozzle rings into basin_round floors only. This node
                    # used to target column_01 — a spec the mapper refused,
                    # which every scripted Council test then persisted as
                    # "valid" because nothing checked it before fabrication.
                    "element_id": "basin_01",
                    "nozzle_bore_mm": 12.0,
                },
                {
                    "node_id": "drain_01",
                    "type": "drain",
                    "elevation_m": -0.6,
                    "element_id": "basin_01",
                },
            ],
            "edges": [
                {
                    "edge_id": "riser_01",
                    "from_node": "pump_01",
                    "to_node": "nozzle_ring_01",
                    "diameter_mm": 50.0,
                    "length_m": 3.2,
                    "material": "hdpe_pe100",
                    "fittings": [
                        {"type": "elbow_90", "count": 2},
                        {"type": "valve_check", "count": 1},
                    ],
                    "elevation_change_m": 2.9,
                }
            ],
        },
        "site": {
            "climate_zone": "tropical_highland",
            "design_wind_m_per_s": 12.0,
            "frost_risk": False,
            "seismic_zone": "II",
            "viewing_distance_m": 25.0,
        },
        "fabrication": {
            "method": "hybrid",
            "max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2},
            "max_lift_kg": 800.0,
            "local_capability_notes": "Addis Ababa sheet shop; bronze cast locally",
        },
        "constraints": {
            "budget": {"amount": 4500000.0, "currency": "ETB", "fx_date": "2026-07-15"},
            "hard_constraints": ["no element taller than 6 m", "potable-grade wetted parts"],
        },
        "confidence": 78,
        "assumptions": [
            {
                "statement": "Mains water available at site boundary",
                "sourced": True,
                "source": "Hawassa utility letter, 2026-06",
            },
            {
                "statement": "Soil bearing capacity at least 150 kPa",
                "sourced": False,
            },
        ],
    }


def test_schema_is_valid_json_schema(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_complete_example_validates(schema):
    jsonschema.Draft202012Validator(schema).validate(valid_example_spec())


def test_missing_hydraulic_network_fails(schema):
    spec = valid_example_spec()
    del spec["hydraulic_network"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(spec)


def test_old_budget_etb_max_field_fails(schema):
    """Amendment 4: budget_etb_max is gone; a spec still using it (and not
    the new currency-aware budget) must be rejected."""
    spec = valid_example_spec()
    spec["constraints"] = {
        "budget_etb_max": 4500000.0,
        "hard_constraints": spec["constraints"]["hard_constraints"],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(spec)


def test_bad_currency_pattern_fails(schema):
    spec = valid_example_spec()
    spec["constraints"]["budget"]["currency"] = "etb"  # must be ^[A-Z]{3}$
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(spec)

    spec2 = valid_example_spec()
    spec2["constraints"]["budget"]["currency"] = "ETBR"  # 4 letters
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(spec2)


def test_budget_missing_fx_date_fails(schema):
    spec = valid_example_spec()
    del spec["constraints"]["budget"]["fx_date"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(spec)
