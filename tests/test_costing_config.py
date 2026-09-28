"""costing.yaml template tests (Phase 3 operator amendment).

The rates schema is designed NOW; the operator fills the nulls during the
build. Contract:

- the file LOADS with nulls (template state is valid config);
- material keys match config/materials.yaml ids EXACTLY (cross-file check
  in load_config_bundle — a rate for an unknown material fails at startup);
- every structural rule holds (currency pattern, per-units, fx date);
- missing_entries() names every unfilled rate; require_filled() raises and
  names them (a cost is never guessed — same rule as pricing.yaml);
- a fully-filled copy passes require_filled().
"""

from __future__ import annotations

import copy

import pytest

from app.core.config import (
    ConfigError,
    CostingConfig,
    _load_yaml,
    load_config_bundle,
)


def test_costing_template_loads_and_versions(config):
    costing = config.costing
    # bumped to v2 by slice C2 (ADR-056): the card gained a per-material
    # seam rate and the two truck capacities a trip count needs.
    assert costing.costing_version == "2026-08-v2"
    assert costing.meta["default_currency"] == "USD"


def test_costing_material_keys_match_materials_yaml(config):
    assert set(config.costing.materials) == set(config.materials.materials)
    # D-10-frozen: the material registry grew four -> five when SC-A1
    # (ADR-072, 2026-09-16) added stainless_316l_cast for crescent_ring;
    # found by the first in-container full-suite run 2026-09-28 (D-10
    # instance eight — SC-A1's targeted host run never reached this file).
    assert set(config.materials.materials) == {
        "stainless_316l_sheet", "basalt_slab", "cast_concrete_c35_45", "bronze_cast",
        "stainless_316l_cast",
    }


def test_template_is_unfilled_and_missing_entries_names_everything(config):
    missing = config.costing.missing_entries()
    assert missing, "a freshly committed template must be unfilled"
    # spot-check the named paths exist for each material + the fx block
    for mid in config.costing.materials:
        assert f"materials.{mid}.buy_price" in missing
        assert f"materials.{mid}.fabrication.labor" in missing
        assert f"materials.{mid}.finishing" in missing
    assert "workshop.overhead_pct" in missing
    assert "install.crew_day_rate" in missing
    assert "contingency_pct" in missing
    assert "markup_pct" in missing
    assert "fx_rates.ETB.rate" in missing
    assert "fx_rates.ETB.as_of" in missing


def test_require_filled_raises_naming_missing(config):
    with pytest.raises(ConfigError, match="costing.yaml is not filled in"):
        config.costing.require_filled()


def test_filled_copy_passes_require_filled(config):
    data = copy.deepcopy(_load_yaml("costing.yaml"))

    def fill_amount(a):
        a["amount"] = 1.0

    for m in data["materials"].values():
        fill_amount(m["buy_price"])
        m["waste_factor_pct"] = 10.0
        m["fabrication"]["method"] = "cast"
        fill_amount(m["fabrication"]["labor"])
        m["fabrication"]["hours_per_m3"] = 40.0
        fill_amount(m["finishing"])
        fill_amount(m["seam"])
    data["workshop"]["overhead_pct"] = 15.0
    fill_amount(data["install"]["crew_day_rate"])
    data["install"]["crew_size"] = 3
    data["install"]["days_per_tonne"] = 1.5
    fill_amount(data["install"]["transport"])
    data["install"]["truck_payload_kg"] = 12000.0
    data["install"]["modules_per_trip"] = 4
    data["contingency_pct"] = 10.0
    data["markup_pct"] = 25.0
    data["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "2026-08-04"}

    costing = CostingConfig.model_validate(data)
    assert costing.missing_entries() == []
    costing.require_filled()  # must not raise


def test_bad_currency_and_bad_unit_rejected(config):
    data = copy.deepcopy(_load_yaml("costing.yaml"))
    data["materials"]["bronze_cast"]["buy_price"]["currency"] = "etb"  # lowercase
    with pytest.raises(Exception):
        CostingConfig.model_validate(data)
    data2 = copy.deepcopy(_load_yaml("costing.yaml"))
    data2["materials"]["bronze_cast"]["buy_price"]["per"] = "bucket"
    with pytest.raises(Exception):
        CostingConfig.model_validate(data2)
    data3 = copy.deepcopy(_load_yaml("costing.yaml"))
    data3["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "last Tuesday"}
    with pytest.raises(Exception):
        CostingConfig.model_validate(data3)


def test_bundle_rejects_costing_rates_for_unknown_material(config, monkeypatch):
    """Cross-file honesty: a rate block for a material the library doesn't
    know must fail at startup with a naming error (tested at the checker
    level, not by corrupting the committed files)."""
    import app.core.config as cfg

    real_load = cfg._load_yaml

    def fake_load(name):
        data = real_load(name)
        if name == "costing.yaml":
            data = copy.deepcopy(data)
            data["materials"]["unobtanium"] = copy.deepcopy(
                data["materials"]["bronze_cast"]
            )
        return data

    monkeypatch.setattr(cfg, "_load_yaml", fake_load)
    with pytest.raises(ConfigError, match="unknown material ids"):
        load_config_bundle()
