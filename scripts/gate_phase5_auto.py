#!/usr/bin/env python3
"""Phase 5 auto gate — vision critique loop, offline, $0.

Gate (operator, verbatim): a design measurably improves across at least three
critique iterations, with before/after renders and the parameter deltas that
caused each change.

This auto gate proves the machinery that makes the operator gate possible:
  1. Render job can be queued and collected (using a scripted render runner).
  2. Two-provider vision critique fixtures parse into strict JSON deltas.
  3. Consensus + annealing accept agreed deltas and reject disagreement.
  4. Objective score is computed from geometry facts, not model self-grading.
  5. Deltas can be applied to a flat parameter dictionary.

The gate does NOT spend API money or require Blender; the live loop does both.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Make `app` importable without a pip install when run from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.council.critique import (
    CritiqueDispatcher,
    CritiqueLoop,
    CritiqueOutcome,
    _annealing_limit,
    objective_score,
)
from app.render import RenderCamera, RenderView
from app.render.queue import RenderResult, submit_render_job

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "critique_round_v1.json"


@dataclass
class _ScriptedRenderRunner:
    """Fake render worker that claims four views succeeded."""

    job_dir: Path = field(default_factory=lambda: Path("/tmp/fake-render"))

    def submit(self, job):
        self.job_dir.mkdir(parents=True, exist_ok=True)
        (self.job_dir / "job.json").write_text("{}", encoding="utf-8")

    def collect(self, job_id: str, timeout_s: float) -> RenderResult:
        return RenderResult(
            ok=True,
            views={
                "front": self.job_dir / "front.png",
                "side": self.job_dir / "side.png",
                "top": self.job_dir / "top.png",
                "three_quarter": self.job_dir / "three_quarter.png",
            },
            total_s=4.0,
        )


class _ScriptedDispatcher:
    """Returns the fixture critique texts per provider."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.calls: list[dict] = []

    def dispatch(self, *, provider: str, **kwargs) -> CritiqueOutcome:
        self.calls.append({"provider": provider, **kwargs})
        text = self.data.get(f"{provider}_text", '{"observations": [], "deltas": []}')
        return CritiqueOutcome(
            provider=provider,
            model="test",
            text=text,
            tokens_in=1000,
            tokens_out=200,
            latency_ms=100.0,
            cost_usd=0.0,
            pricing_version="fixture",
        )


def _fail(step: int, msg: str) -> int:
    print(f"FAIL [{step}] {msg}")
    return 1


def main() -> int:
    if not FIXTURE.exists():
        return _fail(0, f"fixture missing: {FIXTURE}")
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    print("=" * 60)
    print("Phase 5 auto gate — vision critique loop (offline, $0)")
    print("=" * 60)

    # 1. Render queue submission/collection works with scripted runner.
    from app.db.database import Database

    db = Database(REPO_ROOT / "data" / "gate_phase5.db")
    db.init_db()
    runner = _ScriptedRenderRunner()
    job = submit_render_job(
        design_id="gate-design-01",
        input_mesh="/fake/assembly.glb",
        views=[
            RenderView(name="front", camera=RenderCamera.ortho_front),
            RenderView(name="side", camera=RenderCamera.ortho_side),
            RenderView(name="top", camera=RenderCamera.ortho_top),
            RenderView(name="three_quarter", camera=RenderCamera.perspective_3q),
        ],
        runner=runner,
    )
    result = runner.collect(job.id, timeout_s=1.0)
    if not result.ok or len(result.views) != 4:
        return _fail(1, f"render handoff failed: {result.error}")
    print("[1] PASS render handoff produced 4 views")

    # 2/3/4. Two-provider critique, consensus, annealing.
    dispatcher = _ScriptedDispatcher(data)
    loop = CritiqueLoop(db=db, dispatcher=dispatcher, max_iterations=1)
    rounds, outcomes = loop.run_one_round(
        session_id=data["session_id"],
        design_id=data["design_id"],
        image_paths=list(result.views.values()),
        spec_summary="tiered_cascade fountain, tier_height_m 0.25, basin_diameter_m 2.0",
        round_no=data["round_no"],
        validated_ranges=data["validated_ranges"],
        providers=["anthropic", "openai"],
    )
    if len(outcomes) != 2:
        return _fail(2, f"expected 2 provider calls, got {len(outcomes)}")
    if len(rounds) != 1:
        return _fail(3, "expected 1 round")
    round_result = rounds[0]
    if len(round_result.critiques) != 2:
        return _fail(4, f"expected 2 critiques, got {len(round_result.critiques)}")
    if not round_result.consensus.agreed_deltas:
        return _fail(5, "no agreed deltas — consensus failed")
    if round_result.consensus.agreed_deltas[0].parameter_path != data["expected_agreed_path"]:
        return _fail(
            6,
            f"expected agreed path {data['expected_agreed_path']!r}, got "
            f"{round_result.consensus.agreed_deltas[0].parameter_path!r}",
        )
    print("[2] PASS two-provider critique + consensus")

    # 5. Objective score is computed from facts — PR-5 (ADR-068): the
    # handling component scores the PICK weight with a stated basis, and a
    # bare total with no basis is refused (None), never scored.
    score_before = objective_score({"pick_mass_kg": 900, "max_lift_kg": 1000,
                                    "mass_basis": "measured_heaviest_module"})
    score_after = objective_score({"pick_mass_kg": 100, "max_lift_kg": 1000,
                                   "mass_basis": "measured_heaviest_module"})
    if score_before is None or score_after is None:
        return _fail(7, "objective score unavailable on a stated basis")
    if score_after <= score_before:
        return _fail(7, "objective score did not improve for lighter design")
    if objective_score({"total_mass_kg": 100, "max_lift_kg": 1000}) is not None:
        return _fail(7, "a bare total_mass_kg with no pick basis was scored")
    print(f"[3] PASS objective score before={score_before} after={score_after}"
          f"; bare total refused (None)")

    # 6. Delta application.
    params = {"tier_height_m": 0.25}
    new_params, applied, rejected = loop.apply_deltas(params, round_result.consensus.agreed_deltas)
    if not applied:
        return _fail(8, "no deltas applied")
    if new_params["tier_height_m"] <= params["tier_height_m"]:
        return _fail(9, "increase delta did not increase parameter")
    print(f"[4] PASS applied delta: {applied[0].parameter_path} {params['tier_height_m']} -> {new_params['tier_height_m']}")

    # 7. Annealing enforcement: round 2 limit is half of round 1.
    limit1 = _annealing_limit(1, data["validated_ranges"]["tier_height_m"])
    limit2 = _annealing_limit(2, data["validated_ranges"]["tier_height_m"])
    if limit2 >= limit1:
        return _fail(10, "annealing did not shrink limit at round 2")
    print(f"[5] PASS annealing: r1 limit={limit1:.6f} r2 limit={limit2:.6f}")

    print("=" * 60)
    print("Phase 5 auto gate PASS")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
