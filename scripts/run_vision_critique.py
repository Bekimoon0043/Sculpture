#!/usr/bin/env python3
"""Run the Phase 5 vision critique loop against REAL providers. SPENDS MONEY.

    docker compose --profile render up -d render-worker
    docker compose exec backend python scripts/run_vision_critique.py --rounds 3

This is the live counterpart to `gate_phase5_auto.py`. That gate proves the
orchestration with scripted providers and costs $0; it cannot prove that two
real vision models, looking at real renders, produce parseable deltas and
agree often enough for the loop to move. Only this can.

WHAT ONE ROUND DOES
-------------------
  assemble(elements) -> GLB -> render 4 views -> contact sheet
    -> anthropic + openai vision critique (strict JSON deltas)
    -> consensus (same parameter, same direction, magnitude within tolerance)
    -> clamp to the annealed step limit for that parameter's validated range
    -> apply to the element parameters
  and then round N+1 rebuilds the geometry, so the next render shows the
  change. Without the rebuild this would be three critiques of one picture,
  which proves nothing about convergence.

COST CONTROL
------------
Every call goes through AIProvider.vision() -> app.ai.call_log, so the
budget ceilings in config/budget.yaml are enforced BEFORE any network
traffic and a breach raises BudgetHalt rather than overspending. This script
adds a second, tighter ceiling of its own (--max-spend) and refuses to start
a round that could exceed it. Measured cost is printed per round and in
total, from real tokens against pricing.yaml -- never estimated.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.ai.providers import build_providers
from app.core.budget import BudgetEnforcer, BudgetHalt
from app.core.config import get_settings, load_config_bundle
from app.council.critique import CritiqueLoop, compute_consensus, objective_score
from app.council.critique_live import LiveCritiqueDispatcher
from app.db.database import Database
from app.geometry.assembly import assemble
from app.geometry.exporters import export_glb
from app.geometry.primitives import PRIMITIVES
from app.render import DEFAULT_VIEWS, RenderView
from app.render.contact_sheet import build_contact_sheet
from app.render.queue import ScratchRenderRunner, submit_render_job

#: The design the loop starts from. Deliberately a plain, slightly awkward
#: stack -- a wide shallow basin on a squat plinth -- so there is something
#: for a critique to actually say. All dimensions mm (build123d's unit).
DEFAULT_PLAN: list[dict] = [
    {
        "element_id": "a_plinth",
        "primitive": "plinth",
        # The plinth is a body of revolution: top_diameter_mm, not width/depth.
        "parameters": {"top_diameter_mm": 1400, "height_mm": 350,
                       "taper_deg": 0.0},
    },
    {
        "element_id": "b_basin",
        "primitive": "basin_round",
        "parameters": {"diameter_mm": 2600, "height_mm": 300,
                       "wall_mm": 60, "floor_mm": 80},
        "joint": {"type": "stack_on", "parent": "a_plinth"},
    },
]

#: Parameters the loop is allowed to move, as "element_id.parameter".
#: Everything else the model proposes is recorded as an observation and NOT
#: executed -- the loop may restyle proportion, it may not invent structure.
TUNABLE = ("b_basin.diameter_mm", "b_basin.height_mm",
           "a_plinth.top_diameter_mm", "a_plinth.height_mm",
           "a_plinth.taper_deg")


def validated_ranges(plan: list[dict]) -> dict[str, tuple[float, float]]:
    """Real min/max per tunable parameter, from the primitive's own PARAMETERS.

    Rule 11: ranges come from the primitive's declared engineering envelope,
    never from what looked reasonable here.
    """
    ranges: dict[str, tuple[float, float]] = {}
    for el in plan:
        spec = PRIMITIVES[el["primitive"]].PARAMETERS
        for pname, meta in spec.items():
            key = f"{el['element_id']}.{pname}"
            if key in TUNABLE and "min" in meta and "max" in meta:
                ranges[key] = (float(meta["min"]), float(meta["max"]))
    return ranges


def spec_summary(plan: list[dict]) -> str:
    parts = []
    for el in plan:
        params = ", ".join(f"{k}={v:g}" for k, v in
                           sorted(el["parameters"].items()))
        parts.append(f"{el['element_id']} ({el['primitive']}): {params}")
    return "; ".join(parts) + " [all dimensions mm]"


def flat_params(plan: list[dict]) -> dict[str, float]:
    return {f"{el['element_id']}.{k}": float(v)
            for el in plan for k, v in el["parameters"].items()
            if isinstance(v, (int, float))}


def apply_flat(plan: list[dict], flat: dict[str, float]) -> None:
    for el in plan:
        for k in list(el["parameters"]):
            key = f"{el['element_id']}.{k}"
            if key in flat:
                el["parameters"][k] = flat[key]


def build_and_render(plan: list[dict], round_dir: Path, resolution: int,
                     samples: int) -> tuple[dict, dict[str, Path], Path]:
    """assemble -> GLB -> 4 views -> contact sheet. Returns (manifest, views, sheet)."""
    round_dir.mkdir(parents=True, exist_ok=True)
    solid, manifest = assemble([dict(e, parameters=dict(e["parameters"]))
                                for e in plan], seed=0, strict=False)
    glb = round_dir / "assembly.glb"
    export_glb(solid, glb)

    runner = ScratchRenderRunner()
    views = [RenderView(name=v.name, camera=v.camera, resolution=resolution,
                        samples=samples, time_budget_s=600.0)
             for v in DEFAULT_VIEWS]
    job = submit_render_job(design_id=round_dir.name, input_mesh=str(glb),
                            views=views, runner=runner)
    result = runner.collect(job.id, timeout_s=600.0)
    if not result.ok:
        raise SystemExit(
            f"render failed: {result.error}\n"
            "Start the render worker:\n"
            "  docker compose --profile render up -d render-worker"
        )
    local: dict[str, Path] = {}
    for name, png in result.views.items():
        dest = round_dir / f"{name}.png"
        shutil.copyfile(png, dest)
        local[name] = dest
    sheet = build_contact_sheet(local, round_dir / "contact_sheet.png")
    return manifest, local, sheet


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Live Phase 5 vision critique loop (SPENDS MONEY).")
    ap.add_argument("--rounds", type=int, default=3,
                    help="critique rounds (default 3; budget.yaml caps at "
                         "max_vision_iterations)")
    ap.add_argument("--resolution", type=int, default=512)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--max-spend", type=float, default=1.00,
                    help="hard USD ceiling for THIS run, on top of the "
                         "budget.yaml session cap (default 1.00)")
    ap.add_argument("--providers", default="anthropic,openai")
    ap.add_argument("--out", default=None)
    ap.add_argument("--yes", action="store_true",
                    help="skip the confirmation prompt")
    args = ap.parse_args()

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    run_id = uuid.uuid4().hex[:12]
    data_root = Path("/app/data") if Path("/app/data").exists() else REPO_ROOT / "data"
    out_dir = Path(args.out) if args.out else data_root / "critiques" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("Phase 5 LIVE vision critique loop — THIS SPENDS REAL MONEY")
    print("=" * 72)
    print(f"run id      {run_id}")
    print(f"providers   {', '.join(providers)}")
    print(f"rounds      {args.rounds}   ({len(providers)} vision calls each)")
    print(f"ceiling     ${args.max_spend:.2f} for this run")
    print(f"output      {out_dir}")
    print()

    if not args.yes:
        reply = input("Proceed? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted; nothing was spent")
            return 1

    db = Database(data_root / "luxuryform.db")
    db.init_db()
    settings = get_settings()
    bundle = load_config_bundle()

    if args.rounds > bundle.budget.max_vision_iterations:
        print(f"FAIL: --rounds {args.rounds} exceeds max_vision_iterations "
              f"({bundle.budget.max_vision_iterations}) in config/budget.yaml. "
              "That cap is the ADR-007 bound on this loop; raise it there "
              "deliberately rather than passing it here.")
        return 1

    session_id = f"critique-live-{run_id}"
    # The same enforcer the Council uses: it checks the session and day caps
    # BEFORE any network call and raises BudgetHalt rather than overspending.
    budget = BudgetEnforcer(
        session_id,
        min(bundle.budget.session_cap_usd, args.max_spend),
        bundle.budget.day_cap_usd,
        db,
    )
    provider_map = build_providers(settings, bundle, db, budget)
    missing = [p for p in providers if p not in provider_map]
    if missing:
        print(f"FAIL: provider(s) not configured: {', '.join(missing)}")
        return 1

    plan = [dict(e, parameters=dict(e["parameters"])) for e in DEFAULT_PLAN]
    ranges = validated_ranges(plan)
    print(f"tunable parameters ({len(ranges)}):")
    for k, (lo, hi) in sorted(ranges.items()):
        print(f"  {k:<26} [{lo:g}, {hi:g}] mm")
    print()

    rounds_record: list[dict] = []
    spent = 0.0

    for round_no in range(1, args.rounds + 1):
        round_dir = out_dir / f"round_{round_no}"
        print("-" * 72)
        print(f"ROUND {round_no}")
        print(f"  params: {spec_summary(plan)}")

        t0 = time.time()
        try:
            manifest, views, sheet = build_and_render(
                plan, round_dir, args.resolution, args.samples)
        except Exception as exc:
            print(f"  build/render FAILED: {type(exc).__name__}: {exc}")
            return 1
        print(f"  rendered 4 views + contact sheet in {time.time() - t0:.0f}s")

        score_before = objective_score(_facts(manifest))

        dispatcher = LiveCritiqueDispatcher(provider_map, sheet_dir=round_dir)
        loop = CritiqueLoop(db=db, dispatcher=dispatcher,
                            max_iterations=args.rounds)
        try:
            results, outcomes = loop.run_one_round(
                session_id=session_id,
                design_id=run_id,
                image_paths=list(views.values()),
                spec_summary=spec_summary(plan),
                round_no=round_no,
                validated_ranges=ranges,
                providers=providers,
                current_params=flat_params(plan),
            )
        except BudgetHalt as halt:
            print(f"  BUDGET HALT before dispatch: {halt}")
            print("  Nothing further was spent. This is the cap working.")
            break

        round_cost = sum(o.cost_usd for o in outcomes)
        spent += round_cost

        for o in outcomes:
            status = "ok" if o.status == "ok" else f"ERROR {o.error}"
            print(f"    {o.provider:<10} {o.model:<22} "
                  f"in={o.tokens_in:<6} out={o.tokens_out:<5} "
                  f"${o.cost_usd:.6f}  {o.latency_ms:.0f}ms  {status}")

        rr = results[0]
        for c in rr.critiques:
            for obs in c.observations[:3]:
                print(f"      [{c.provider}] obs: {obs[:96]}")
            for d in c.deltas:
                print(f"      [{c.provider}] delta: {d.parameter_path} "
                      f"{d.direction} {d.magnitude:g} {d.unit}")

        agreed = rr.consensus.agreed_deltas
        print(f"  consensus: {len(agreed)} agreed delta(s)"
              + ("" if agreed else "  (no two-provider agreement this round)"))

        before = flat_params(plan)
        applied: list = []
        if agreed:
            after, applied, rejected = loop.apply_deltas(dict(before), agreed)
            for d in applied:
                print(f"    APPLY {d.parameter_path}: "
                      f"{before.get(d.parameter_path, float('nan')):g} -> "
                      f"{after[d.parameter_path]:g}")
            for d in rejected:
                print(f"    REJECT {d.parameter_path} (outside validated range)")
            apply_flat(plan, after)

        rounds_record.append({
            "round": round_no,
            "params_before": before,
            "params_after": flat_params(plan),
            "objective_score_before": score_before,
            "agreed_deltas": [
                {"parameter_path": d.parameter_path, "direction": d.direction,
                 "magnitude": d.magnitude, "unit": d.unit, "reason": d.reason}
                for d in agreed],
            "applied": [d.parameter_path for d in applied],
            "observations": rr.consensus.observations,
            "critiques": [
                {"provider": c.provider, "observations": c.observations,
                 "deltas": [{"parameter_path": d.parameter_path,
                             "direction": d.direction,
                             "magnitude": d.magnitude, "unit": d.unit}
                            for d in c.deltas],
                 "raw": c.raw}
                for c in rr.critiques],
            "calls": [
                {"provider": o.provider, "model": o.model, "status": o.status,
                 "tokens_in": o.tokens_in, "tokens_out": o.tokens_out,
                 "cost_usd": o.cost_usd, "latency_ms": o.latency_ms,
                 "error": o.error}
                for o in outcomes],
            "round_cost_usd": round_cost,
        })

        print(f"  round cost ${round_cost:.6f}   running total ${spent:.6f}")
        if spent >= args.max_spend:
            print(f"  reached this run's ${args.max_spend:.2f} ceiling; stopping")
            break

    # Final geometry, so the operator can see round N vs round 1.
    final_dir = out_dir / "final"
    try:
        manifest, views, sheet = build_and_render(
            plan, final_dir, args.resolution, args.samples)
        final_score = objective_score(_facts(manifest))
    except Exception as exc:
        print(f"final rebuild failed: {exc}")
        final_score = None

    summary = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "rounds_requested": args.rounds,
        "rounds_completed": len(rounds_record),
        "total_cost_usd": spent,
        "initial_params": flat_params(
            [dict(e, parameters=dict(e["parameters"])) for e in DEFAULT_PLAN]),
        "final_params": flat_params(plan),
        "final_objective_score": final_score,
        "validated_ranges": {k: list(v) for k, v in ranges.items()},
        "rounds": rounds_record,
    }
    (out_dir / "critique_rounds.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print()
    print("=" * 72)
    print(f"rounds completed  {len(rounds_record)}/{args.rounds}")
    print(f"total measured cost  ${spent:.6f}")
    agreed_total = sum(len(r["agreed_deltas"]) for r in rounds_record)
    applied_total = sum(len(r["applied"]) for r in rounds_record)
    print(f"agreed deltas {agreed_total}, applied {applied_total}")
    print(f"evidence: {out_dir / 'critique_rounds.json'}")
    print(f"renders:  {out_dir}/round_*/  and  {final_dir}")
    print("=" * 72)
    return 0


def _facts(manifest: dict) -> dict:
    """The geometry facts objective_score reads. Never model self-scoring."""
    return {
        "total_mass_kg": manifest.get("total_mass_kg", 0.0),
        "max_lift_kg": manifest.get("max_lift_kg", 1000.0),
    }


if __name__ == "__main__":
    raise SystemExit(main())
