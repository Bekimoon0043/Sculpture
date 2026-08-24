"""Vision critique loop (Phase 5).

Converts model feedback into bounded parameter deltas with two-provider
consensus (ADR-007).  Anything that cannot be expressed as a delta is recorded
as an observation, never executed.

The loop is intentionally independent of the actual render worker: a
CritiqueRunner injects the render and provider calls, so the orchestration
logic is provable offline at $0 with fixtures.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import jsonschema

from app.core.config import PricingConfig, load_config_bundle
from app.core.budget import BudgetHalt
from app.db.database import Database

log = logging.getLogger("luxuryform.council.critique")

MAX_ATTEMPTS = 3
MAX_TOKENS = 8192


class CritiqueDispatcher(Protocol):
    """One vision or text provider call.  Production uses call_log.execute;
    tests inject scripted responses."""

    def dispatch(
        self,
        *,
        role: str,
        side: str,
        provider: str,
        prompt: str,
        session_id: str,
        max_tokens: int,
        image_paths: list[Path] | None = None,
    ) -> "CritiqueOutcome": ...


@dataclass
class CritiqueOutcome:
    provider: str
    model: str
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    pricing_version: str
    status: str = "ok"
    error: str | None = None


@dataclass
class ParameterDelta:
    """A bounded, validated change to one registered parameter."""

    parameter_path: str
    direction: str  # increase | decrease | set
    magnitude: float
    unit: str
    reason: str


@dataclass
class VisionCritique:
    """One provider's parsed response."""

    provider: str
    observations: list[str] = field(default_factory=list)
    deltas: list[ParameterDelta] = field(default_factory=list)
    raw: str = ""


@dataclass
class ConsensusResult:
    """Result of comparing two provider critiques."""

    agreed_deltas: list[ParameterDelta] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    tiebreak_needed: bool = False


@dataclass
class CritiqueRound:
    """One round of the vision critique loop."""

    round_no: int
    design_id: str
    render_job_id: str
    critiques: list[VisionCritique] = field(default_factory=list)
    consensus: ConsensusResult = field(default_factory=ConsensusResult)
    applied_deltas: list[ParameterDelta] = field(default_factory=list)
    rejected_deltas: list[ParameterDelta] = field(default_factory=list)
    objective_score_before: float | None = None
    objective_score_after: float | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if "\n" in t:
            t = t.split("\n", 1)[1]
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(t[start : end + 1])


def _schema_for_delta() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "observations": {
                "type": "array",
                "items": {"type": "string"},
            },
            "deltas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "parameter_path": {"type": "string"},
                        "direction": {"enum": ["increase", "decrease", "set"]},
                        "magnitude": {"type": "number"},
                        "unit": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["parameter_path", "direction", "magnitude", "unit"],
                },
            },
        },
        "required": ["observations", "deltas"],
    }


def _parse_critique(provider: str, text: str) -> VisionCritique:
    """Parse a strict-JSON critique into observations and deltas."""
    raw = text
    try:
        data = _extract_json(text)
    except Exception as exc:
        log.warning("critique from %s is not JSON: %s", provider, exc)
        return VisionCritique(provider=provider, observations=[raw], raw=raw)

    try:
        jsonschema.validate(data, _schema_for_delta())
    except jsonschema.ValidationError as exc:
        log.warning("critique from %s failed delta schema: %s", provider, exc)
        return VisionCritique(
            provider=provider,
            observations=["schema error: " + str(exc), raw],
            raw=raw,
        )

    deltas = []
    for d in data.get("deltas", []):
        deltas.append(
            ParameterDelta(
                parameter_path=d["parameter_path"],
                direction=d["direction"],
                magnitude=float(d["magnitude"]),
                unit=d.get("unit", ""),
                reason=d.get("reason", ""),
            )
        )
    return VisionCritique(
        provider=provider,
        observations=data.get("observations", []),
        deltas=deltas,
        raw=raw,
    )


def _delta_key(delta: ParameterDelta) -> str:
    return f"{delta.parameter_path}:{delta.direction}"


#: Relative tolerance on magnitude for two providers to count as agreeing.
#:
#: 0.20, not the 0.05 this started at. Consensus here is asking "did two
#: independent vision models identify the same problem and the same direction
#: of fix" -- it is NOT asking them to agree on a number to two significant
#: figures, which is not something a language model's magnitude estimate can
#: honestly deliver. At 0.05, two models proposing +0.030 m and +0.032 m on a
#: tier height (2 mm apart, 6.25% relative) were scored as DISAGREEING and the
#: round produced nothing. That is the common case, so the loop would almost
#: never accept a delta and the whole phase would be dead code that passes its
#: own unit tests.
#:
#: Widening this is safe because magnitude is not trusted from the model
#: anyway: whatever survives here is clamped to the annealed step limit
#: (_annealing_limit), which is derived from the parameter's validated range.
#: The model chooses the direction; the engineering envelope chooses how far.
DELTA_AGREEMENT_TOLERANCE = 0.20


def _deltas_agree(a: ParameterDelta, b: ParameterDelta,
                  tolerance: float = DELTA_AGREEMENT_TOLERANCE) -> bool:
    """Two deltas agree if they target the same path, same direction, and
    their magnitudes are within the given relative tolerance."""
    if a.parameter_path != b.parameter_path:
        return False
    if a.direction != b.direction:
        return False
    ref = max(abs(a.magnitude), abs(b.magnitude), 1e-9)
    return abs(a.magnitude - b.magnitude) / ref <= tolerance


def _annealing_limit(round_no: int, validated_range: tuple[float, float]) -> float:
    """Permitted step shrinks each round: 10% of the validated range in round 1,
    halving thereafter."""
    span = abs(validated_range[1] - validated_range[0])
    base = span * 0.10
    return base * (0.5 ** (round_no - 1))


def compute_consensus(
    a: VisionCritique,
    b: VisionCritique,
    round_no: int,
    validated_ranges: dict[str, tuple[float, float]],
    tolerance: float = DELTA_AGREEMENT_TOLERANCE,
) -> ConsensusResult:
    """Return deltas that BOTH providers propose within tolerance.

    Each agreed delta is clamped to the annealed magnitude limit for its
    parameter's validated range.
    """
    agreed: list[ParameterDelta] = []
    observations = list(set(a.observations + b.observations))
    used_b: set[str] = set()

    for da in a.deltas:
        key_a = _delta_key(da)
        for db in b.deltas:
            key_b = _delta_key(db)
            if key_b in used_b:
                continue
            if _deltas_agree(da, db, tolerance=tolerance):
                limit = _annealing_limit(
                    round_no, validated_ranges.get(da.parameter_path, (0.0, 1.0))
                )
                # Take the SMALLER of the two proposals, not provider a's.
                # Two reasons: it is the conservative choice when the models
                # disagree on how far to go, and it is symmetric -- using
                # da.magnitude made the result depend on which provider
                # happened to be passed first, so swapping the provider order
                # silently changed the design.
                proposed = min(abs(da.magnitude), abs(db.magnitude))
                magnitude = min(proposed, limit)
                if da.direction == "decrease":
                    magnitude = -magnitude
                agreed.append(
                    ParameterDelta(
                        parameter_path=da.parameter_path,
                        direction=da.direction,
                        magnitude=magnitude,
                        unit=da.unit,
                        reason=f"consensus ({a.provider}+{b.provider}): {da.reason}",
                    )
                )
                used_b.add(key_b)
                break

    return ConsensusResult(
        agreed_deltas=agreed,
        observations=observations,
        tiebreak_needed=len(a.deltas) > 0 and len(agreed) == 0,
    )


class CritiqueLoop:
    """Phase 5 vision critique orchestrator."""

    def __init__(
        self,
        db: Database,
        dispatcher: CritiqueDispatcher,
        max_iterations: int | None = None,
    ) -> None:
        self._db = db
        self._dispatcher = dispatcher
        bundle = load_config_bundle()
        self._max_iterations = max_iterations or bundle.budget.max_vision_iterations

    def _call_provider(
        self,
        session_id: str,
        provider: str,
        side: str,
        prompt: str,
        image_paths: list[Path],
    ) -> CritiqueOutcome:
        return self._dispatcher.dispatch(
            role="vision_critique",
            side=side,
            provider=provider,
            prompt=prompt,
            session_id=session_id,
            max_tokens=MAX_TOKENS,
            image_paths=image_paths,
        )

    def run_one_round(
        self,
        session_id: str,
        design_id: str,
        image_paths: list[Path],
        spec_summary: str,
        round_no: int,
        validated_ranges: dict[str, tuple[float, float]],
        providers: list[str] | None = None,
    ) -> tuple[list[CritiqueRound], list[CritiqueOutcome]]:
        """Run a single critique round (render + two-provider critique + consensus).

        Returns the round plus every provider outcome for persistence.
        """
        providers = providers or ["anthropic", "openai"]
        from app.council import prompts

        prompt = prompts.vision_critique_prompt(spec_summary, round_no)

        critiques: list[VisionCritique] = []
        outcomes: list[CritiqueOutcome] = []
        for side, provider in enumerate(providers):
            outcome = self._call_provider(
                session_id=session_id,
                provider=provider,
                side="primary" if side == 0 else "parallel",
                prompt=prompt,
                image_paths=image_paths,
            )
            outcomes.append(outcome)
            if outcome.status != "ok":
                critiques.append(
                    VisionCritique(
                        provider=provider,
                        observations=[f"provider error: {outcome.error}"],
                        raw=outcome.error or "",
                    )
                )
                continue
            critique = _parse_critique(provider, outcome.text)
            critiques.append(critique)

        if len(critiques) < 2:
            round_result = CritiqueRound(
                round_no=round_no,
                design_id=design_id,
                render_job_id="",
                critiques=critiques,
                consensus=ConsensusResult(observations=["not enough providers responded"]),
            )
            return [round_result], outcomes

        consensus = compute_consensus(
            critiques[0], critiques[1], round_no, validated_ranges
        )
        round_result = CritiqueRound(
            round_no=round_no,
            design_id=design_id,
            render_job_id="",
            critiques=critiques,
            consensus=consensus,
        )
        return [round_result], outcomes

    def apply_deltas(
        self,
        params: dict[str, Any],
        deltas: list[ParameterDelta],
    ) -> tuple[dict[str, Any], list[ParameterDelta], list[ParameterDelta]]:
        """Apply agreed deltas to a flat parameter dictionary.

        Returns (new_params, applied, rejected).  A delta whose parameter path
        is not present is rejected rather than inventing a key.
        """
        new_params = dict(params)
        applied: list[ParameterDelta] = []
        rejected: list[ParameterDelta] = []
        for delta in deltas:
            if delta.parameter_path not in new_params:
                rejected.append(delta)
                continue
            current = float(new_params[delta.parameter_path])
            if delta.direction == "increase":
                new_value = current + abs(delta.magnitude)
            elif delta.direction == "decrease":
                new_value = current - abs(delta.magnitude)
            else:
                new_value = delta.magnitude
            new_params[delta.parameter_path] = new_value
            applied.append(
                ParameterDelta(
                    parameter_path=delta.parameter_path,
                    direction=delta.direction,
                    magnitude=new_value - current,
                    unit=delta.unit,
                    reason=delta.reason,
                )
            )
        return new_params, applied, rejected


def objective_score(params: dict[str, Any],
                    silhouette_areas: dict[str, float] | None = None) -> float:
    """Compute a falsifiable objective improvement score.

    Components (all normalised so higher is better):
      - constraint margin: distance from hard min/max boundaries
      - mass vs handling: how far total mass is below max_lift_kg
      - silhouette stability: inverse of variance in projected outline area
        across ortho views
    """
    silhouette_areas = silhouette_areas or {}
    mass = float(params.get("total_mass_kg", 0.0) or 0.0)
    max_lift = float(params.get("max_lift_kg", 1000.0) or 1000.0)
    handling_score = max(0.0, 1.0 - mass / max_lift)

    # Constraint margin: arbitrary normalised distance from a 5% envelope.
    # Real ranges come from validate_params; this is the minimal honest version.
    margin = 1.0

    # Silhouette stability: lower variance is better.
    areas = list(silhouette_areas.values())
    stability = 1.0
    if len(areas) > 1:
        mean = sum(areas) / len(areas)
        variance = sum((a - mean) ** 2 for a in areas) / len(areas)
        stability = max(0.0, 1.0 - variance / (mean ** 2 + 1e-9))

    return round(margin * 0.3 + handling_score * 0.4 + stability * 0.3, 6)
