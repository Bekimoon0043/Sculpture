"""FF-A3 (ADR-069): a typed brief can ask for the ref-08 loop — honestly.

What these tests prove at $0 (no provider, no geometry build):

- schema: a DRY design (has_water false) may carry an empty hydraulic
  network; a WET design keeps the Amendment 3 minimums; an ABSENT
  has_water never matches the dry branch (the if-guard is real);
- mapper: every freeform_loop registry key is reachable by a spec-level
  name; lengths convert; a ratio is a PLAIN number and a ratio carrying
  ANY unit is refused; a material contradiction is refused;
- prompt: the Designer index carries the lens vocabulary and its honesty
  lines, all generated from the registry;
- Designer boundary: a spec the registry refuses is re-asked with the
  registry's own text and never persisted; the wrong material is refused;
- fixture: the synthetic FF-A3 Council fixture replays, every spec is
  registry-valid, rank 1 states all 12 scalars + material_id explicitly
  and maps to EXACTLY the FF-A2 acceptance parameters;
- intake: the typed-brief fixture composes the fixture's brief through the
  real intake API and the real _compose_brief;
- demo loader: basenames only — paths, separators, traversal refused.

Synthetic hand-authored Council alternatives prove replay and pipeline
compatibility only — not that an AI selected the primitive from prose.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import jsonschema
import pytest

from app.council.orchestrator import DispatchOutcome, _validate_live_primitives
from app.council.replay import load_fixture, replay_session
from app.db.models import CouncilCallRow, CouncilSessionRow, DesignSpecRow
from app.geometry.primitives import PRIMITIVES, freeform_loop as fl
from app.geometry.primitives.base import ConstraintViolation
from app.geometry.spec_mapper import (
    _UNITLESS_SUFFIXES,
    assembly_plan_from_spec,
    spec_aliases_for,
)
from tests.test_council_orchestrator import (
    MODELS,
    ScriptedDispatcher,
    _arbiter_decision_json,
    _make_orch,
)
from tests.test_design_spec_schema import valid_example_spec

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
COUNCIL_FIXTURE = FIXTURES / "council_session_ffa3_v1.json"
INTAKE_FIXTURE = FIXTURES / "intake_ffa3_v1.json"
FFA2_FIXTURE = FIXTURES / "freeform_loop_spec_v1.json"
SCHEMA = json.loads((REPO / "schemas" / "design_spec_v1.json").read_text("utf-8"))

sys.path.insert(0, str(REPO / "scripts"))


def _rank1_spec() -> dict:
    fx = load_fixture(COUNCIL_FIXTURE)
    chosen = fx["arbiter_decision"]["chosen_spec_ids"][0]
    return next(e["spec"] for e in fx["design_specs"]
                if e["spec"]["meta"]["spec_id"] == chosen)


def _lens_spec(**overrides) -> dict:
    """A dry, single-lens Design Spec built from the fixture's rank 1."""
    spec = copy.deepcopy(_rank1_spec())
    spec["massing"]["elements"][0]["parameters"].update(overrides)
    return spec


# ---------------------------------------------------------------------------
# schema change B (correction 5) + correction 4
# ---------------------------------------------------------------------------

def _validate(spec, schema=SCHEMA):
    jsonschema.Draft202012Validator(schema).validate(spec)


def test_dry_design_may_carry_an_empty_hydraulic_network():
    spec = _rank1_spec()
    assert spec["water"]["has_water"] is False
    assert spec["hydraulic_network"] == {"nodes": [], "edges": []}
    _validate(spec)


def test_wet_design_keeps_the_amendment_3_minimums():
    spec = valid_example_spec()
    assert spec["water"]["has_water"] is True
    _validate(spec)
    for key, empty in (("nodes", []), ("edges", [])):
        broken = copy.deepcopy(spec)
        broken["hydraulic_network"][key] = empty
        with pytest.raises(jsonschema.ValidationError):
            _validate(broken)


def test_absent_has_water_never_matches_the_dry_branch():
    """The if-guard requires has_water to be PRESENT and false. With the
    water.required constraint removed from a schema copy, a water object
    with no has_water plus an empty network must still be REFUSED — the
    else branch (wet minimums) applies whenever the dry condition is not
    positively met."""
    loose = copy.deepcopy(SCHEMA)
    loose["properties"]["water"]["required"] = []
    spec = _rank1_spec()
    spec["water"] = {}
    with pytest.raises(jsonschema.ValidationError):
        _validate(spec, loose)
    # and with the network present, the same spec passes the loose schema —
    # so the refusal above came from the minimums, not from anything else
    spec["hydraulic_network"] = copy.deepcopy(valid_example_spec()["hydraulic_network"])
    _validate(spec, loose)


def test_plain_ratio_is_schema_valid_and_every_unit_on_a_ratio_is_refused():
    spec = _rank1_spec()
    params = spec["massing"]["elements"][0]["parameters"]
    ratio_keys = [k for k in fl.PARAMETERS if k.endswith(_UNITLESS_SUFFIXES)]
    assert ratio_keys == ["plan_skew_ratio", "bore_center_height_fraction",
                          "waist_height_fraction"]
    aliases = spec_aliases_for("freeform_loop")
    for key in ratio_keys:
        names = [n for n, t in aliases.items() if t == key]
        assert names, key
        assert any(isinstance(params.get(n), (int, float)) for n in names), key
    _validate(spec)                       # plain ratios: schema-valid
    assembly_plan_from_spec(spec)         # and mapper-valid
    for key in ratio_keys:
        name = next(n for n, t in aliases.items() if t == key)
        for unit in SCHEMA["$defs"]["dimension"]["properties"]["unit"]["enum"]:
            bad = _lens_spec(**{name: {"value": 0.15, "unit": unit}})
            with pytest.raises(ConstraintViolation) as exc:
                assembly_plan_from_spec(bad)
            assert "dimensionless ratio" in str(exc.value)
            assert key in str(exc.value)


# ---------------------------------------------------------------------------
# mapper
# ---------------------------------------------------------------------------

def test_every_lens_registry_key_is_reachable_and_no_alias_dangles():
    aliases = spec_aliases_for("freeform_loop")
    keys = set(fl.PARAMETERS)
    assert set(aliases.values()) <= keys, set(aliases.values()) - keys
    for key in keys - {"material_id"}:
        assert key in aliases.values(), f"{key} has no spec-level name"


def test_rank1_maps_to_exactly_the_ffa2_acceptance_parameters():
    plan = assembly_plan_from_spec(_rank1_spec())
    assert len(plan) == 1 and plan[0]["primitive"] == "freeform_loop"
    expected = json.loads(FFA2_FIXTURE.read_text("utf-8"))["elements"][0]["parameters"]
    got = plan[0]["parameters"]
    assert set(got) == set(expected) == set(fl.PARAMETERS)
    for key, value in expected.items():
        assert got[key] == pytest.approx(value) if isinstance(value, (int, float)) \
            else got[key] == value, key


def test_rank1_states_all_twelve_scalars_and_material_explicitly():
    """Correction 9: silent defaults may never masquerade as Council
    parameterization — 12 scalar geometry keys + material_id = 13."""
    params = _rank1_spec()["massing"]["elements"][0]["parameters"]
    aliases = spec_aliases_for("freeform_loop")
    stated = {aliases.get(name, name) for name in params}
    assert stated == set(fl.PARAMETERS)
    assert len(fl.PARAMETERS) == 13 and "material_id" in fl.PARAMETERS


def test_material_contradiction_and_wrong_material_are_refused():
    contradiction = _lens_spec(material_id="basalt_slab")
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(contradiction)
    assert "contradicts" in str(exc.value)

    wrong = _rank1_spec()
    wrong["massing"]["elements"][0]["material_id"] = "basalt_slab"
    wrong["massing"]["elements"][0]["parameters"]["material_id"] = "basalt_slab"
    errors = _validate_live_primitives(wrong)
    assert errors and any("only 'stainless_316l_sheet'" in e for e in errors)


def test_unknown_lens_parameter_is_refused_naming_the_keys():
    with pytest.raises(ConstraintViolation) as exc:
        assembly_plan_from_spec(_lens_spec(petal_count=8))
    assert "petal_count" in str(exc.value)
    assert "bore_center_height_fraction" in str(exc.value)


# ---------------------------------------------------------------------------
# prompt vocabulary (registry-driven)
# ---------------------------------------------------------------------------

def test_designer_index_carries_the_lens_vocabulary_and_honesty():
    from app.council.prompts import primitive_index_surface

    text = primitive_index_surface()
    start = text.index("- freeform_loop:")
    rest = text[start + 1:]
    end = rest.find("\n- ")
    block = rest if end == -1 else rest[:end]
    for key, spec in fl.PARAMETERS.items():
        if key == "material_id":
            continue
        assert key in block, key
        assert f"[{spec['min']}..{spec['max']}]" in block, key
        if key.endswith(_UNITLESS_SUFFIXES):
            assert "PLAIN number" in block
    assert fl.SUPPORTED_MATERIAL in block
    for missing in fl.INCOMPLETE_MASS_INPUTS:
        assert missing in block
    assert "PRE-FABRICATION" in block
    # every primitive gets a vocabulary line — nothing is special-cased
    for pid in PRIMITIVES:
        assert f"- {pid}:" in text
    assert text.count("parameters:") == len(PRIMITIVES)


# ---------------------------------------------------------------------------
# Designer boundary
# ---------------------------------------------------------------------------

class _ArbiterAware(ScriptedDispatcher):
    def __init__(self, pricing, base_spec, db):
        super().__init__(pricing, base_spec)
        self._db = db

    def dispatch(self, **kw):
        if kw["role"] == "arbiter" and kw["side"] == "primary" and not self.arbiter_script:
            with self._db.get_session() as s:
                ids = [r.id for r in s.query(DesignSpecRow).all()]
            return DispatchOutcome(
                provider=kw["provider"], model=MODELS[kw["provider"]],
                text=_arbiter_decision_json(ids), tokens_in=2000, tokens_out=900,
                latency_ms=100.0,
                cost_usd=self._pricing.cost_usd(kw["provider"], MODELS[kw["provider"]], 2000, 900),
                pricing_version=self._pricing.pricing_version)
        return super().dispatch(**kw)


def test_designer_boundary_reasks_with_the_registry_text_and_never_persists(db, config):
    base = _rank1_spec()
    bad = copy.deepcopy(base)
    bad["meta"]["spec_id"] = "0f0f0f0f-ffa3-4000-8000-000000000bad"
    bad["massing"]["elements"][0]["parameters"]["wall"] = {"value": 4, "unit": "mm"}
    good = copy.deepcopy(base)
    good["meta"]["spec_id"] = "0f0f0f0f-ffa3-4000-8000-00000000900d"

    d = _ArbiterAware(config.pricing, base, db)
    d.designer_script[("anthropic", 1)] = [json.dumps(bad), json.dumps(good)]
    orch = _make_orch(db, config, d)
    sid = orch.run_session("typed brief (scripted boundary test)")

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "completed" and sess.corrected == 1
        reasks = [c.prompt for c in s.query(CouncilCallRow)
                  .filter_by(session_id=sid, role="designer").all()
                  if "registry refusal" in c.prompt]
        assert len(reasks) == 1
        # the registry's OWN text: the range floor fires first (6 = embedment
        # 3 + ligament 3, recorded in freeform_loop.PARAMETERS)
        assert "wall_mm=4.0: Input should be greater than or equal to 6" in reasks[0]
        persisted = [json.loads(r.spec_json) for r in
                     s.query(DesignSpecRow).filter_by(session_id=sid).all()]
        assert all(sp["massing"]["elements"][0]["parameters"]["wall"]["value"] != 4
                   for sp in persisted)
        assert "0f0f0f0f-ffa3-4000-8000-000000000bad" not in {
            r.id for r in s.query(DesignSpecRow).all()}


def test_boundary_treats_any_exception_as_an_error_never_a_pass(monkeypatch):
    import app.council.orchestrator as orch_mod

    def boom(spec):
        raise RuntimeError("mapper exploded")

    monkeypatch.setattr("app.geometry.registry.assembly_plan_from_spec", boom)
    errors = orch_mod._validate_live_primitives(_rank1_spec())
    assert errors == ["registry validation raised RuntimeError: mapper exploded"]


# ---------------------------------------------------------------------------
# the synthetic fixture
# ---------------------------------------------------------------------------

def test_fixture_is_synthetic_and_says_what_it_proves():
    fx = load_fixture(COUNCIL_FIXTURE)
    assert fx["synthetic"] is True
    assert ("prove replay and pipeline compatibility only" in fx["note"]
            and "not that an AI selected the primitive from prose" in fx["note"])


def test_fixture_matches_the_live_prompt_builders():
    """The transcript is what the Council WOULD be sent on this checkout:
    regenerate and compare byte for byte (loud expiry, never silent)."""
    import make_ffa3_fixture as gen

    assert gen.dumps(gen.build_fixture()) == COUNCIL_FIXTURE.read_text("utf-8")


def test_fixture_replays_and_every_spec_is_registry_valid(db, config):
    fx = load_fixture(COUNCIL_FIXTURE)
    sid = replay_session(db, config.pricing, fx)
    with db.get_session() as s:
        specs = [json.loads(r.spec_json) for r in
                 s.query(DesignSpecRow).filter_by(session_id=sid).all()]
        assert s.get(CouncilSessionRow, sid).total_cost_usd > 0
    assert len(specs) == 6
    for spec in specs:
        assert spec["massing"]["elements"][0]["primitive"] == "freeform_loop"
        assert _validate_live_primitives(spec) == []
    assert fx["arbiter_decision"]["chosen_spec_ids"][0] == _rank1_spec()["meta"]["spec_id"]


# ---------------------------------------------------------------------------
# intake -> brief, and the demo loader (real app, throwaway DB)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from app.db.database import reset_default_db
    from app.main import app

    old = {k: os.environ.get(k) for k in ("LUXURYFORM_DB", "LUXURYFORM_DATA_DIR")}
    os.environ["LUXURYFORM_DB"] = str(tmp_path / "ffa3.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(tmp_path / "data")
    reset_default_db()
    with TestClient(app) as c:
        yield c
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    reset_default_db()


def test_typed_intake_composes_the_fixture_brief(client):
    from app.api.routes_council import RunSessionRequest, _compose_brief
    from app.db.database import get_default_db

    intake_fx = json.loads(INTAKE_FIXTURE.read_text("utf-8"))
    created = client.post("/api/intake", json={
        "brief_text": intake_fx["brief_text"], "fields": intake_fx["fields"]})
    assert created.status_code == 201, created.text
    intake_id = created.json()["id"]
    assert all(v["source"] == "operator" for section in
               created.json()["intake"].values() if isinstance(section, dict)
               for v in section.values() if isinstance(v, dict)
               and v.get("source") != "unknown")
    confirmed = client.post(f"/api/intake/{intake_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text

    composed, ctx = _compose_brief(
        RunSessionRequest(brief_text=intake_fx["brief_text"], intake_id=intake_id),
        get_default_db())
    fx = load_fixture(COUNCIL_FIXTURE)
    assert composed.replace(intake_id, intake_fx["intake_id_in_fixture"]) \
        == fx["session"]["brief_text"]
    assert ctx["intake_id"] == intake_id


def test_demo_loader_takes_discovered_basenames_only(client):
    from app.api.routes_council import discovered_demo_fixtures

    names = discovered_demo_fixtures()
    assert "council_session_ffa3_v1" in names and "council_session_v1" in names
    for bad in ("../council_session_v1", "/etc/passwd", "council_session_v1.json",
                "tests/fixtures/council_session_v1", "council_session_nope",
                "..\\council_session_v1", ""):
        r = client.post("/api/council/demo-session", json={"fixture": bad})
        assert r.status_code == 422, (bad, r.text)
        assert r.json()["detail"]["available"] == names

    r = client.post("/api/council/demo-session", json={"fixture": "council_session_ffa3_v1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["synthetic"] is True and body["created"] is True
    assert "never spent" in body["note"]
    again = client.post("/api/council/demo-session", json={"fixture": "council_session_ffa3_v1"})
    assert again.json()["created"] is False
    transcript = client.get(f"/api/council/sessions/{body['session_id']}")
    assert transcript.status_code == 200
    specs = transcript.json()["specs"]
    assert len(specs) == 6

    default = client.post("/api/council/demo-session")
    assert default.status_code == 200 and default.json()["fixture"] == "council_session_v1"
