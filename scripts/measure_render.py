#!/usr/bin/env python3
"""Measure what a render round actually costs on this machine.

    docker compose --profile render up -d render-worker
    docker compose exec backend python scripts/measure_render.py --list
    docker compose exec backend python scripts/measure_render.py --design-id <id>

WHY THIS EXISTS
---------------
`max_vision_iterations` in config/budget.yaml bounds how many critique rounds
the Phase 5 loop may run, and every round renders four views before it spends
anything on a vision call. On this hardware -- four cores, no GPU, Cycles on
the CPU -- that render is the slow part, by a wide margin. Choosing an
iteration count without knowing the per-round wall-clock is guessing.

So this measures it, on the operator's own machine, with the operator's own
design, and prints what a full loop would cost in time.

It also produces the before/after renders the Phase 5 visual gate asks the
operator to look at.

HONESTY NOTE
------------
Earlier drafts of PHASE_5_REPORT.md and gate_phase5_visual.md both told the
operator to run `scripts/measure_render.py`. It did not exist. This is that
file, written to do what those documents claimed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.db.database import get_default_db
from app.db.models import DesignRow
from app.render import DEFAULT_VIEWS, RenderView
from app.render.queue import ScratchRenderRunner, submit_render_job


def list_designs(limit: int) -> int:
    """Show designs that have a GLB, newest first."""
    db = get_default_db()
    with db.get_session() as s:
        rows = (
            s.query(DesignRow)
            .filter(DesignRow.glb_path.isnot(None))
            .order_by(DesignRow.created_at.desc())
            .limit(limit)
            .all()
        )
        rows = [(r.id, r.created_at, r.status, r.glb_path) for r in rows]

    if not rows:
        print("No design in the database has a GLB artifact yet.")
        print("Build a design first — a render needs geometry to render.")
        return 1

    print(f"{'design id':<36}  {'created':<26}  {'status':<10}  GLB")
    print("-" * 100)
    for design_id, created, status, glb in rows:
        exists = "" if glb and Path(glb).exists() else "  [MISSING ON DISK]"
        print(f"{design_id:<36}  {str(created):<26}  {str(status):<10}  "
              f"{Path(glb).name if glb else '-'}{exists}")
    return 0


def pick_latest() -> str | None:
    db = get_default_db()
    with db.get_session() as s:
        row = (
            s.query(DesignRow)
            .filter(DesignRow.glb_path.isnot(None))
            .order_by(DesignRow.created_at.desc())
            .first()
        )
        return row.id if row else None


def resolve_mesh(design_id: str) -> Path:
    db = get_default_db()
    with db.get_session() as s:
        design = s.get(DesignRow, design_id)
        glb = design.glb_path if design else None
    if design is None:
        raise SystemExit(f"no design with id {design_id!r} "
                         "(run with --list to see what exists)")
    if not glb:
        raise SystemExit(f"design {design_id!r} has no GLB artifact; the "
                         "geometry build has not produced one")
    path = Path(glb)
    if not path.exists():
        raise SystemExit(f"design {design_id!r} records a GLB at {path} but "
                         "the file is not on disk")
    return path


def measure(design_id: str, mesh: Path, resolution: int, samples: int,
            rounds: int, out_dir: Path | None) -> int:
    runner = ScratchRenderRunner()
    views = [RenderView(name=v.name, camera=v.camera, resolution=resolution,
                        samples=samples, time_budget_s=600.0)
             for v in DEFAULT_VIEWS]

    print("=" * 70)
    print("Render measurement")
    print("=" * 70)
    print(f"design      {design_id}")
    print(f"mesh        {mesh}  ({mesh.stat().st_size} bytes)")
    print(f"settings    {resolution}x{resolution}, {samples} samples, "
          f"{len(views)} views, {rounds} round(s)")
    print()

    round_times: list[float] = []
    per_view: dict[str, list[float]] = {}

    for r in range(1, rounds + 1):
        job = submit_render_job(design_id=design_id, input_mesh=str(mesh),
                                views=views, runner=runner)
        t0 = time.perf_counter()
        result = runner.collect(job.id, timeout_s=600.0)
        wall = time.perf_counter() - t0

        if not result.ok:
            print(f"round {r}: FAILED — {result.error}")
            print()
            print("Is the render worker running?")
            print("  docker compose --profile render up -d render-worker")
            return 1

        round_times.append(wall)

        job_dir = runner._job_dir(job.id)
        views_json = job_dir / "views.json"
        timings = {}
        if views_json.exists():
            data = json.loads(views_json.read_text(encoding="utf-8"))
            for v in data.get("views", []):
                timings[v["name"]] = v.get("elapsed_s", 0.0)
                per_view.setdefault(v["name"], []).append(v.get("elapsed_s", 0.0))

        detail = "  ".join(f"{n}={timings[n]:.1f}s" for n in sorted(timings))
        print(f"round {r}: {wall:6.1f}s wall   {detail}")

        # Keep the images: the Phase 5 visual gate asks the operator to
        # compare rounds, which is impossible if each round is discarded.
        if out_dir is not None:
            dest = out_dir / f"round_{r}"
            dest.mkdir(parents=True, exist_ok=True)
            for name, png in result.views.items():
                shutil.copyfile(png, dest / f"{name}.png")

    print()
    print("-" * 70)
    if per_view:
        print("per view (mean across rounds):")
        for name in sorted(per_view):
            vals = per_view[name]
            print(f"  {name:<15} {statistics.mean(vals):6.1f}s"
                  + (f"   (min {min(vals):.1f}, max {max(vals):.1f})"
                     if len(vals) > 1 else ""))
        print()

    mean_round = statistics.mean(round_times)
    print(f"mean round: {mean_round:.1f}s for {len(views)} views")

    # The number this script exists to produce.
    print()
    print("What this means for the Phase 5 critique loop:")
    for iterations in (3, 6, 10):
        total = mean_round * iterations
        print(f"  max_vision_iterations = {iterations:<3} -> "
              f"{total / 60.0:5.1f} min of rendering per design "
              f"(plus vision-call latency and cost)")
    print()
    print("Rendering is the slow half of a critique round on this hardware;")
    print("the vision calls themselves are seconds. Size the iteration count")
    print("against the time above, not against the API bill.")

    if out_dir is not None:
        print()
        print(f"renders written to: {out_dir}")
    print("=" * 70)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Measure render wall-clock for the Phase 5 critique loop.")
    ap.add_argument("--design-id", help="design to render "
                                        "(default: most recent with a GLB)")
    ap.add_argument("--list", action="store_true",
                    help="list designs that have a GLB, then exit")
    ap.add_argument("--limit", type=int, default=20,
                    help="how many designs --list shows (default 20)")
    ap.add_argument("--resolution", type=int, default=512,
                    help="square render resolution (default 512)")
    ap.add_argument("--samples", type=int, default=32,
                    help="Cycles samples per view (default 32)")
    ap.add_argument("--rounds", type=int, default=1,
                    help="how many times to render, to see variance "
                         "(default 1)")
    ap.add_argument("--out", default=None,
                    help="directory to copy the PNGs into "
                         "(default data/critiques/<design_id>)")
    args = ap.parse_args()

    if args.list:
        return list_designs(args.limit)

    design_id = args.design_id or pick_latest()
    if not design_id:
        print("No design in the database has a GLB artifact yet.")
        print("Build a design first, or run with --list.")
        return 1
    if not args.design_id:
        print(f"(no --design-id given; using the most recent: {design_id})\n")

    mesh = resolve_mesh(design_id)
    out_dir = Path(args.out) if args.out else (
        Path("/app/data" if Path("/app/data").exists() else REPO_ROOT / "data")
        / "critiques" / design_id
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    return measure(design_id, mesh, args.resolution, args.samples,
                   args.rounds, out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
