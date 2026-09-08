"""Vision critique loop tests (Phase 5, Slice 2) — offline, $0.

Proves consensus, annealing, rejection of non-conforming deltas, and the
objective score without touching any provider or the render worker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.council.critique import (
    CritiqueDispatcher,
    CritiqueLoop,
    CritiqueOutcome,
    ParameterDelta,
    compute_consensus,
    objective_score,
    _parse_critique,
    _annealing_limit,
)
# RenderResult lives in app.render.queue, not app.render: re-exporting it from
# the package __init__ would make queue.py and __init__.py import each other.
from app.render.queue import RenderResult


class _ScriptedDispatcher:
    """Injected provider: returns pre-canned text per provider."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def dispatch(self, *, provider: str, **kwargs) -> CritiqueOutcome:
        self.calls.append({"provider": provider, **kwargs})
        text = self.responses.get(provider, '{"observations": [], "deltas": []}')
        return CritiqueOutcome(
            provider=provider,
            model="test",
            text=text,
            tokens_in=1000,
            tokens_out=200,
            latency_ms=100.0,
            cost_usd=0.001,
            pricing_version="test",
        )


def _delta(path: str, direction: str, magnitude: float, unit: str = "m") -> ParameterDelta:
    return ParameterDelta(
        parameter_path=path,
        direction=direction,
        magnitude=magnitude,
        unit=unit,
        reason="test",
    )


def test_parse_critique_extracts_deltas_and_observations():
    text = (
        '{"observations": ["top heavy"], '
        '"deltas": [{"parameter_path": "tier_height_m", "direction": "decrease", '
        '"magnitude": 0.02, "unit": "m", "reason": "reduce height"}]}'
    )
    critique = _parse_critique("anthropic", text)
    assert len(critique.observations) == 1
    assert critique.observations[0] == "top heavy"
    assert len(critique.deltas) == 1
    assert critique.deltas[0].parameter_path == "tier_height_m"
    assert critique.deltas[0].direction == "decrease"
    assert critique.deltas[0].magnitude == pytest.approx(0.02)


def test_consensus_requires_same_path_and_direction():
    a = _parse_critique(
        "anthropic",
        '{"observations": [], "deltas": [{"parameter_path": "x", "direction": "increase", "magnitude": 0.1, "unit": "m"}]}',
    )
    b = _parse_critique(
        "openai",
        '{"observations": [], "deltas": [{"parameter_path": "x", "direction": "increase", "magnitude": 0.11, "unit": "m"}]}',
    )
    ranges = {"x": (0.0, 1.0)}
    result = compute_consensus(a, b, 1, ranges, tolerance=0.2)
    assert len(result.agreed_deltas) == 1
    assert result.agreed_deltas[0].parameter_path == "x"


def test_consensus_rejects_opposing_directions():
    a = _parse_critique(
        "anthropic",
        '{"observations": [], "deltas": [{"parameter_path": "x", "direction": "increase", "magnitude": 0.1, "unit": "m"}]}',
    )
    b = _parse_critique(
        "openai",
        '{"observations": [], "deltas": [{"parameter_path": "x", "direction": "decrease", "magnitude": 0.1, "unit": "m"}]}',
    )
    ranges = {"x": (0.0, 1.0)}
    result = compute_consensus(a, b, 1, ranges)
    assert len(result.agreed_deltas) == 0
    assert result.tiebreak_needed


def test_annealing_limit_halves_each_round():
    # _annealing_limit takes ONE range tuple, not the whole ranges dict --
    # callers index the dict themselves (compute_consensus does
    # validated_ranges.get(path, ...)).
    x_range = (0.0, 1.0)
    r1 = _annealing_limit(1, x_range)
    r2 = _annealing_limit(2, x_range)
    assert r2 == pytest.approx(r1 / 2)
    r3 = _annealing_limit(3, x_range)
    assert r3 == pytest.approx(r1 / 4)
    # Round 1 is 10% of the span, per the docstring.
    assert r1 == pytest.approx(0.10)


def test_agreed_delta_clamped_to_annealing_limit():
    a = _parse_critique(
        "anthropic",
        '{"observations": [], "deltas": [{"parameter_path": "x", "direction": "increase", "magnitude": 0.5, "unit": "m"}]}',
    )
    b = _parse_critique(
        "openai",
        '{"observations": [], "deltas": [{"parameter_path": "x", "direction": "increase", "magnitude": 0.51, "unit": "m"}]}',
    )
    ranges = {"x": (0.0, 1.0)}
    result = compute_consensus(a, b, 1, ranges)
    assert len(result.agreed_deltas) == 1
    # limit for range 1.0 round 1 = 0.10
    assert abs(result.agreed_deltas[0].magnitude) <= 0.10 + 1e-9


def test_objective_score_improves_when_pick_mass_drops():
    """PR-5 (ADR-068): the handling component scores the PICK weight — the
    heaviest module after segmentation — against the declared lift limit,
    and only with a stated basis."""
    heavy = objective_score({"pick_mass_kg": 900.0, "max_lift_kg": 1000.0,
                             "mass_basis": "measured_heaviest_module"})
    light = objective_score({"pick_mass_kg": 100.0, "max_lift_kg": 1000.0,
                             "mass_basis": "measured_heaviest_module"})
    assert light is not None and heavy is not None
    assert light > heavy


def test_objective_score_is_unavailable_without_a_lift_limit():
    """The 1,000 kg default is gone: no limit means no handling score, and
    the composite is None — never a number that compares."""
    from app.council.critique import objective_score_detail
    detail = objective_score_detail({"pick_mass_kg": 100.0,
                                     "max_lift_kg": None,
                                     "mass_basis": "measured_heaviest_module"})
    assert detail.score is None
    assert detail.handling.kind == "unavailable"
    assert "max_lift_kg" in detail.handling.reason
    assert objective_score({"pick_mass_kg": 100.0,
                            "mass_basis": "measured_heaviest_module"}) is None


def test_objective_score_refuses_a_total_mass_with_no_basis():
    """A bare total_mass_kg (the pre-PR-5 call shape) says nothing about
    what a crane would pick, so it cannot be scored."""
    assert objective_score({"total_mass_kg": 100.0, "max_lift_kg": 1000.0}) is None


def test_unavailable_scores_are_never_compared():
    from app.council.critique import score_delta
    assert score_delta(None, 0.8) is None
    assert score_delta(0.8, None) is None
    assert score_delta(0.5, 0.8) == 0.3


def test_loop_runs_one_round_offline(db):
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "critique_round_v1.json"
    data = __import__("json").loads(fixture.read_text(encoding="utf-8"))
    dispatcher = _ScriptedDispatcher(
        {"anthropic": data["anthropic_text"], "openai": data["openai_text"]}
    )
    loop = CritiqueLoop(db=db, dispatcher=dispatcher, max_iterations=1)
    rounds, outcomes = loop.run_one_round(
        session_id=data["session_id"],
        design_id=data["design_id"],
        image_paths=[Path("/fake/front.png")],
        spec_summary="tiered_cascade fountain, tier_height_m 0.25, basin_diameter_m 2.0",
        round_no=data["round_no"],
        validated_ranges=data["validated_ranges"],
        providers=["anthropic", "openai"],
    )
    assert len(rounds) == 1
    assert len(outcomes) == 2
    assert len(rounds[0].critiques) == 2
    assert len(rounds[0].consensus.agreed_deltas) == 1
    assert rounds[0].consensus.agreed_deltas[0].parameter_path == data["expected_agreed_path"]
    assert not rounds[0].consensus.tiebreak_needed
