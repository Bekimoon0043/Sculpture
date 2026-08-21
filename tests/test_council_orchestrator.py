"""Council orchestrator tests (Phase 3, build step 2) — OFFLINE, $0.

A ScriptedDispatcher stands in for the providers: every dispatch returns a
canned response with scripted token counts; costs are computed through the
REAL pricing.yaml (config fixture), never hand-typed. The tests prove the
orchestration contract end to end:

- happy path: 15 calls (critic runs kimi-only under the dynamic rule
  with the static designer pair), 6 valid specs, binding arbiter decision;
- designer re-ask on invalid JSON, candidate exclusion after 3 failures;
- critic dynamic rule resolution (never a producer provider);
- arbiter bounded re-ask, invariants, and loud failure past the bound;
- BudgetHalt -> session halted_budget, partial calls persisted, re-raised;
- fewer than 3 valid specs -> session failed, no fabricated decision.
"""

from __future__ import annotations

import copy
import json
import uuid

import pytest

from app.core.budget import BudgetHalt
from app.council import orchestrator as orch
from app.council.orchestrator import CouncilOrchestrator, DispatchOutcome, OrchestratorError
from app.db.models import (
    ArbiterDecisionRow,
    CouncilCallRow,
    CouncilSessionRow,
    DefectListRow,
    DesignSpecRow,
    EngineeringReviewRow,
)

MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4o", "kimi": "kimi-k3"}


def _spec_for(provider: str, alt: int, seed: int, base_spec: dict) -> dict:
    s = copy.deepcopy(base_spec)
    s["meta"]["spec_id"] = str(uuid.uuid4())
    s["meta"]["provider"] = provider
    s["meta"]["alternative_no"] = alt
    s["meta"]["seed"] = seed
    s["form_language"]["concept"] = f"concept {provider} alt {alt} (scripted test)"
    return s


class ScriptedDispatcher:
    """Canned responses per (role, side, provider); cost from real pricing."""

    def __init__(self, pricing, base_spec: dict):
        self._pricing = pricing
        self._base_spec = base_spec
        self.calls: list[dict] = []
        self.designer_script: dict = {}   # (provider, alt) -> list of replies
        self.arbiter_script: list = []    # successive primary replies
        self.halt_on_call: int | None = None

    def dispatch(self, *, role, side, provider, prompt, session_id, max_tokens):
        self.calls.append({"role": role, "side": side, "provider": provider})
        if self.halt_on_call is not None and len(self.calls) == self.halt_on_call:
            raise BudgetHalt(session_id, "scripted halt: session cap would be breached", 4.99, 5.00)

        if role == "designer":
            alt = 1 if "ALTERNATIVE 1" in prompt else 2 if "ALTERNATIVE 2" in prompt else 3
            queue = self.designer_script.get((provider, alt))
            if queue is not None:
                text = queue.pop(0) if len(queue) > 1 else queue[0]
            else:
                text = json.dumps(_spec_for(provider, alt, 100 + alt, self._base_spec))
        elif role == "arbiter" and side == "primary" and self.arbiter_script:
            text = (self.arbiter_script.pop(0) if len(self.arbiter_script) > 1
                    else self.arbiter_script[0])
        else:
            text = self._default_text(role, side)
        tokens_in = 1000 + len(prompt) // 4
        tokens_out = 800
        return DispatchOutcome(
            provider=provider, model=MODELS[provider], text=text,
            tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=100.0,
            cost_usd=self._pricing.cost_usd(provider, MODELS[provider], tokens_in, tokens_out),
            pricing_version=self._pricing.pricing_version,
        )

    def _default_text(self, role, side):
        if role == "engineer":
            return json.dumps({"summary": f"engineering review ({side})",
                               "per_spec": []})
        if role == "critic":
            return json.dumps({"defects": [
                {"id": "D1", "severity": "major", "spec_id": "n/a",
                 "defect": "scripted defect with a real number: head margin 5%"}
            ]})
        if role == "arbiter":
            return json.dumps({"note": f"parallel concurrence ({side})"})
        return f"{role} {side} scripted response"


def _arbiter_decision_json(spec_ids):
    return json.dumps({
        "chosen_spec_ids": spec_ids[:3],
        "confidence": 0.72,
        "rationale": "scripted binding decision",
        "disagreement_register": [
            {"topic": "scripted", "positions": {"a": "x", "b": "y"},
             "resolution": "recorded"}
        ],
        "stated_differences": {},
    })


@pytest.fixture()
def base_spec(repo_root):
    from tests.test_design_spec_schema import valid_example_spec
    return valid_example_spec()


def _make_orch(db, config, dispatcher):
    return CouncilOrchestrator(db, config.pricing, dispatcher, config.council)


def test_designer_prompt_carries_live_primitive_index(base_spec):
    from app.council import prompts

    prompt = prompts.designer_prompt(
        "brief",
        "research",
        1,
        json.dumps({"type": "object"}),
    )
    assert "LIVE PRIMITIVE INDEX" in prompt
    for primitive_id in (
        "tiered_cascade",
        "basin_round",
        "plinth",
        "sculptural_column",
    ):
        assert primitive_id in prompt
    assert "do not invent a primitive id" in prompt


def test_happy_path_completed_session(db, config, base_spec):
    d = ScriptedDispatcher(config.pricing, base_spec)
    # arbiter decision needs real spec ids -> inject after designers ran:
    # simplest: let the scripted arbiter choose from whatever the DB has.
    session_holder = {}

    class ArbiterAware(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "arbiter" and kw["side"] == "primary" and not self.arbiter_script:
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                return DispatchOutcome(
                    provider=kw["provider"], model=MODELS[kw["provider"]],
                    text=_arbiter_decision_json(ids), tokens_in=2000, tokens_out=900,
                    latency_ms=100.0,
                    cost_usd=config.pricing.cost_usd(kw["provider"], MODELS[kw["provider"]], 2000, 900),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)

    orch_ = _make_orch(db, config, ArbiterAware(config.pricing, base_spec))
    sid = orch_.run_session("A monumental lotus fountain for Hawassa (scripted test)")

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "completed"
        # ADR-025: the critic running kimi-only under the never-a-producer
        # rule is the rule working, NOT degradation — the badge stays clean
        # on a healthy session.
        assert sess.degraded == 0
        assert sess.corrected == 0
        assert sess.arbiter_confidence == pytest.approx(0.72)

        calls = s.query(CouncilCallRow).filter_by(session_id=sid).all()
        by_role = {}
        for c in calls:
            by_role.setdefault(c.role, []).append(c)
        assert len(by_role["researcher"]) == 2
        assert len(by_role["designer"]) == 6
        assert len(by_role["geometrist"]) == 2
        assert len(by_role["engineer"]) == 2
        assert len(by_role["critic"]) == 1
        assert by_role["critic"][0].provider == "kimi"
        assert len(by_role["arbiter"]) == 2
        assert len(calls) == 15
        assert sess.total_cost_usd == round(sum(c.cost_usd for c in calls), 6)
        assert sess.total_cost_usd > 0

        specs = s.query(DesignSpecRow).filter_by(session_id=sid).all()
        assert len(specs) == 6
        assert all(sp.schema_valid == 1 for sp in specs)
        assert {sp.provider for sp in specs} == {"anthropic", "openai"}

        assert s.query(EngineeringReviewRow).filter_by(session_id=sid).count() == 2
        assert s.query(DefectListRow).filter_by(session_id=sid).count() == 1

        dec = s.query(ArbiterDecisionRow).filter_by(session_id=sid).one()
        assert dec.binding == 1
        chosen = json.loads(dec.chosen_spec_ids_json)
        assert len(chosen) == 3 and len(set(chosen)) == 3
        assert set(chosen) <= {sp.id for sp in specs}


def test_designer_unknown_primitive_reasked_before_persist(
    db, config, base_spec
):
    """Phase 6 A2: unknown primitive ids fail at the Designer boundary, not
    later in fabrication."""
    invalid = _spec_for("anthropic", 1, 101, base_spec)
    invalid["massing"]["elements"][0]["primitive"] = "lotus_array"
    fixed = _spec_for("anthropic", 1, 101, base_spec)

    class ArbiterAware(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "arbiter" and kw["side"] == "primary" and not self.arbiter_script:
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                return DispatchOutcome(
                    provider=kw["provider"], model=MODELS[kw["provider"]],
                    text=_arbiter_decision_json(ids), tokens_in=2000, tokens_out=900,
                    latency_ms=100.0,
                    cost_usd=config.pricing.cost_usd(
                        kw["provider"], MODELS[kw["provider"]], 2000, 900
                    ),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)

    d = ArbiterAware(config.pricing, base_spec)
    d.designer_script[("anthropic", 1)] = [
        json.dumps(invalid),
        json.dumps(fixed),
    ]
    orch_ = _make_orch(db, config, d)
    sid = orch_.run_session("A primitive validation brief")

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "completed"
        assert sess.corrected == 1
        calls = (
            s.query(CouncilCallRow)
            .filter_by(session_id=sid, role="designer", provider="anthropic")
            .all()
        )
        assert len(calls) == 4  # alt 1 had one re-ask; alts 2/3 normal
        reask_prompts = [
            c.prompt for c in calls if "live registry violation" in c.prompt
        ]
        assert len(reask_prompts) == 1
        assert "lotus_array" in reask_prompts[0]
        specs = s.query(DesignSpecRow).filter_by(session_id=sid).all()
        persisted = [json.loads(sp.spec_json) for sp in specs]
        assert all(
            el["primitive"] != "lotus_array"
            for sp in persisted
            for el in sp["massing"]["elements"]
        )


def test_designer_reask_then_success(db, config, base_spec):
    d = ScriptedDispatcher(config.pricing, base_spec)
    d.designer_script[("anthropic", 1)] = [
        "this is not json at all",
        json.dumps(_spec_for("anthropic", 1, 101, base_spec)),
    ]
    # arbiter must pick real ids
    d.arbiter_script = []  # filled dynamically below via wrapper
    class A(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "arbiter" and kw["side"] == "primary":
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                t = _arbiter_decision_json(ids)
                return DispatchOutcome(provider="openai", model="gpt-4o", text=t,
                    tokens_in=100, tokens_out=100, latency_ms=1.0,
                    cost_usd=config.pricing.cost_usd("openai", "gpt-4o", 100, 100),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)
    orch_ = _make_orch(db, config, A(config.pricing, base_spec))
    orch_._dispatcher.designer_script = d.designer_script
    sid = orch_.run_session("brief")
    with db.get_session() as s:
        calls = s.query(CouncilCallRow).filter_by(session_id=sid, role="designer").all()
        assert len(calls) == 7  # 6 + 1 re-ask
        assert s.get(CouncilSessionRow, sid).status == "completed"


def test_designer_persistent_failure_excludes_candidate(db, config, base_spec):
    class A(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "designer" and kw["provider"] == "kimi":
                raise AssertionError("kimi is not a designer")
            if kw["role"] == "designer" and kw["provider"] == "openai" and "ALTERNATIVE 2" in kw["prompt"]:
                return DispatchOutcome(provider="openai", model="gpt-4o",
                    text="still not json", tokens_in=10, tokens_out=10, latency_ms=1.0,
                    cost_usd=0.0, pricing_version=config.pricing.pricing_version)
            if kw["role"] == "arbiter" and kw["side"] == "primary":
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                t = _arbiter_decision_json(ids)
                return DispatchOutcome(provider="openai", model="gpt-4o", text=t,
                    tokens_in=100, tokens_out=100, latency_ms=1.0,
                    cost_usd=config.pricing.cost_usd("openai", "gpt-4o", 100, 100),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)
    orch_ = _make_orch(db, config, A(config.pricing, base_spec))
    sid = orch_.run_session("brief")
    with db.get_session() as s:
        specs = s.query(DesignSpecRow).filter_by(session_id=sid).all()
        assert len(specs) == 5  # one candidate lost after MAX_ATTEMPTS
        designer_calls = s.query(CouncilCallRow).filter_by(
            session_id=sid, role="designer").all()
        assert len(designer_calls) == 6 + orch.MAX_ATTEMPTS - 1  # +2 extra re-asks
        assert s.get(CouncilSessionRow, sid).status == "completed"


def test_successful_reask_sets_corrected_not_degraded(db, config, base_spec):
    """ADR-025: a designer re-ask that succeeds marks corrected=1, degraded=0.

    Session 32e1c68f (first live run) flagged degraded with ZERO error rows —
    the old semantics flagged the critic's by-design producer exclusion, so
    every healthy session wore the badge. Re-asks are self-correction.
    """
    class ArbiterAware(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "arbiter" and kw["side"] == "primary" and not self.arbiter_script:
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                return DispatchOutcome(
                    provider=kw["provider"], model=MODELS[kw["provider"]],
                    text=_arbiter_decision_json(ids), tokens_in=2000, tokens_out=900,
                    latency_ms=100.0,
                    cost_usd=config.pricing.cost_usd(kw["provider"], MODELS[kw["provider"]], 2000, 900),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)

    d = ArbiterAware(config.pricing, base_spec)
    # anthropic alt 1: first reply is garbage, re-ask succeeds.
    d.designer_script[("anthropic", 1)] = [
        "this is not JSON at all",
        json.dumps(_spec_for("anthropic", 1, 101, base_spec)),
    ]
    orch_ = _make_orch(db, config, d)
    sid = orch_.run_session("A re-ask test brief")

    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "completed"
        assert sess.corrected == 1
        assert sess.degraded == 0
        calls = s.query(CouncilCallRow).filter_by(session_id=sid, role="designer").all()
        assert len(calls) == 7  # 6 normal + 1 re-ask
        assert all(c.status == "ok" for c in calls)


def test_critic_dynamic_rule_excludes_producers(db, config, base_spec):
    """If only anthropic specs survive, the critic pair is openai+kimi
    (anthropic is a producer) and the session is NOT degraded."""
    class A(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "designer" and kw["provider"] == "openai":
                return DispatchOutcome(provider="openai", model="gpt-4o",
                    text="garbage", tokens_in=10, tokens_out=10, latency_ms=1.0,
                    cost_usd=0.0, pricing_version=config.pricing.pricing_version)
            if kw["role"] == "arbiter" and kw["side"] == "primary":
                with db.get_session() as s:
                    ids = [r.id for r in s.query(DesignSpecRow).all()]
                return DispatchOutcome(provider="openai", model="gpt-4o",
                    text=_arbiter_decision_json(ids), tokens_in=100, tokens_out=100,
                    latency_ms=1.0,
                    cost_usd=config.pricing.cost_usd("openai", "gpt-4o", 100, 100),
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)
    orch_ = _make_orch(db, config, A(config.pricing, base_spec))
    sid = orch_.run_session("brief")
    with db.get_session() as s:
        critic = s.query(CouncilCallRow).filter_by(session_id=sid, role="critic").all()
        assert {c.provider for c in critic} == {"openai", "kimi"}
        assert "anthropic" not in {c.provider for c in critic}
        assert s.get(CouncilSessionRow, sid).degraded == 0


def test_arbiter_invalid_decision_reasked_then_fail(db, config, base_spec):
    class A(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "arbiter" and kw["side"] == "primary":
                return DispatchOutcome(provider="openai", model="gpt-4o",
                    text=json.dumps({"chosen_spec_ids": ["x"], "confidence": 5}),
                    tokens_in=10, tokens_out=10, latency_ms=1.0, cost_usd=0.0,
                    pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)
    orch_ = _make_orch(db, config, A(config.pricing, base_spec))
    with pytest.raises(OrchestratorError, match="no valid binding decision"):
        orch_.run_session("brief")
    with db.get_session() as s:
        sid = s.query(CouncilSessionRow).first().id
        sess = s.get(CouncilSessionRow, sid)
        assert sess.status == "failed"
        arb = s.query(CouncilCallRow).filter_by(session_id=sid, role="arbiter").all()
        assert len([c for c in arb if c.side == "primary"]) == orch.MAX_ATTEMPTS


def test_budget_halt_marks_session_and_keeps_calls(db, config, base_spec):
    d = ScriptedDispatcher(config.pricing, base_spec)
    d.halt_on_call = 5
    orch_ = _make_orch(db, config, d)
    with pytest.raises(BudgetHalt):
        orch_.run_session("brief")
    with db.get_session() as s:
        sess = s.query(CouncilSessionRow).first()
        assert sess.status == "halted_budget"
        assert sess.ended_at is not None
        calls = s.query(CouncilCallRow).filter_by(session_id=sess.id).all()
        assert len(calls) == 4  # the 5th was halted BEFORE dispatch


def test_too_few_valid_specs_fails_loudly(db, config, base_spec):
    class A(ScriptedDispatcher):
        def dispatch(self, **kw):
            if kw["role"] == "designer" and not (
                kw["provider"] == "anthropic" and "ALTERNATIVE 1" in kw["prompt"]
            ):
                return DispatchOutcome(provider=kw["provider"], model=MODELS[kw["provider"]],
                    text="nope", tokens_in=10, tokens_out=10, latency_ms=1.0,
                    cost_usd=0.0, pricing_version=config.pricing.pricing_version)
            return super().dispatch(**kw)
    orch_ = _make_orch(db, config, A(config.pricing, base_spec))
    with pytest.raises(OrchestratorError, match="at least 3"):
        orch_.run_session("brief")
    with db.get_session() as s:
        assert s.query(CouncilSessionRow).first().status == "failed"
        assert s.query(ArbiterDecisionRow).count() == 0
