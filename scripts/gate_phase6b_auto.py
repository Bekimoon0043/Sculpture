#!/usr/bin/env python3
"""PHASE 6 SLICE B AUTO GATE — rim treatments + nozzle fixture, $0.

Runs inside Docker (``docker compose exec backend python
scripts/gate_phase6b_auto.py``) or on any machine with build123d+trimesh.
No stdin, no prompts, no API calls, no AI-written code; prints a numbered
transcript; exits 0 only on PASS.

  1. CANONICAL GUARDS — cascade e1a59fa6… and the A1 gate-composition
     assembly sha 529014af… still byte-identical.
  2. UNTREATED-BASIN BYTE-GUARD — the default basin still exports the
     sha pinned BEFORE slice B touched the profile code.
  3. TREATMENT BATTERY — weir/coping/pool build watertight per material;
     refusals with real numbers: crest land under the feature floor, the
     316L formula floor, bullnose over wall/2, coping overhang bound.
  4. WEIR FROM THE SPEC — matching node elevation passes; a mismatch is
     refused naming BOTH elevations; a weir rim with no node is refused
     (never a silent default).
  5. NOZZLES FROM THE SPEC — 3 nodes ⌀20.6 remove exactly 3·π·r²·floor of
     stone (printed); a vanishing web, mixed bores and a floorless host
     are refused.
  6. DETERMINISM — a weir+nozzle assembly, byte-identical STEP across two
     separate processes, both hashes and both PIDs printed.
  7. VERDICT.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS = "PASS"
FAIL = "FAIL"

PHASE2_CANONICAL_STEP_SHA256 = (
    "e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13"
)
A1_ASSEMBLY_STEP_SHA256 = (
    "529014af672a282b6626cece8eebc777f5d839a34be02c9a031b5813cf22ddbd"
)
#: Pinned 2026-08-26 BEFORE the first slice-B profile edit.
DEFAULT_BASIN_STEP_SHA256 = (
    "6038d26f28cd61b0c01ae9fde00ff2841b34ad0d6228cc7c4bbdbdd1eeacf0f0"
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from _assembly_build_once import GATE_PLAN as A1_PLAN  # noqa: E402  — the
# canonical A1 composition, imported so this gate can never drift from it
# (first run of this gate had a hand-copied plan missing taper_deg and used
# the wrong seed — pinned-hash mismatch, caught by section 1).
A1_SEED = 42

#: The slice-B showcase: a weir-crested, nozzle-bored basin on a plinth.
B_PLAN = [
    {"element_id": "b1", "primitive": "basin_round",
     "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                    "floor_mm": 60, "rim_treatment": "weir_edge",
                    "material_id": "basalt_slab"},
     "fixtures": [{"type": "nozzle_ring", "count": 3, "bore_mm": 20.6}],
     "joint": {"type": "stack_on", "parent": "p1"}},
    {"element_id": "p1", "primitive": "plinth",
     "parameters": {"top_diameter_mm": 2200, "height_mm": 800,
                    "wall_mm": 150, "material_id": "basalt_slab"}},
]
B_SEED = 7


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/7] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} — {label}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def _expect(failures, label, fn, *needles):
    from app.geometry.primitives.base import ConstraintViolation

    try:
        fn()
    except ConstraintViolation as exc:
        text = str(exc)
        missing = [n for n in needles if n not in text]
        _check(failures, label, not missing,
               exc.violations[0][:150] if not missing
               else f"message lacks {missing}: {text[:150]}")
        return
    _check(failures, label, False, "NO violation raised")


def main() -> int:
    import logging

    for name in ("luxuryform.config", "luxuryform.geometry", "luxuryform.db"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    failures: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate6b_"))

    from app.geometry.assembly import assemble
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.primitives import basin_round
    from app.geometry.registry import cascade_fountain
    from app.geometry.spec_mapper import assembly_plan_from_spec

    # ------------------------------------------------------------------
    _section(1, "CANONICAL GUARDS — nothing that passed before moved")
    solid, _ = cascade_fountain({}, seed=42)
    sha = export_step(solid, workdir / "cascade.step", step_timestamp_for(42))
    print(f"cascade: {sha}")
    _check(failures, "Phase 2 canonical cascade byte-identical",
           sha == PHASE2_CANONICAL_STEP_SHA256)
    fused, _ = assemble(A1_PLAN, seed=A1_SEED)
    sha_a1 = export_step(fused, workdir / "a1.step",
                         step_timestamp_for(A1_SEED))
    print(f"A1 composition: {sha_a1}")
    _check(failures, "A1 gate-composition assembly byte-identical",
           sha_a1 == A1_ASSEMBLY_STEP_SHA256)

    # ------------------------------------------------------------------
    _section(2, "UNTREATED-BASIN BYTE-GUARD (pinned pre-slice-B)")
    p = basin_round.validate({}, None)
    sha_b = export_step(basin_round.build(p), workdir / "basin.step",
                        step_timestamp_for(42))
    print(f"expected: {DEFAULT_BASIN_STEP_SHA256}")
    print(f"got:      {sha_b}")
    _check(failures, "default basin bytes unchanged by the treatment code",
           sha_b == DEFAULT_BASIN_STEP_SHA256)

    # ------------------------------------------------------------------
    _section(3, "TREATMENT BATTERY — built and refused with real numbers")
    for treatment, params in [
        ("weir_edge", {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                       "floor_mm": 60}),
        ("coping", {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                    "coping_overhang_mm": 60, "coping_thickness_mm": 50}),
        ("pool_edge", {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 40,
                       "pool_edge_radius_mm": 15}),
    ]:
        pp = basin_round.validate(
            {**params, "rim_treatment": treatment,
             "material_id": "basalt_slab"}, None)
        s = basin_round.build(pp)
        _check(failures, f"{treatment} builds ONE watertight solid (basalt)",
               len(s.solids()) == 1,
               f"outer ⌀{basin_round.max_outer_diameter_mm(pp):g}, "
               f"height {basin_round.height_mm(pp):g} mm")
    _expect(failures,
            "crest land under the basalt feature floor refused",
            lambda: basin_round.validate(
                {"diameter_mm": 2000, "wall_mm": 20,
                 "rim_treatment": "weir_edge", "drip_edge_mm": 4,
                 "crest_radius_mm": 10, "material_id": "basalt_slab"}, None),
            "crest land", "15")
    _expect(failures,
            "316L formula floor (crest radius < wall) refused",
            lambda: basin_round.validate(
                {"diameter_mm": 800, "height_mm": 300, "wall_mm": 6,
                 "rim_treatment": "weir_edge", "crest_radius_mm": 4,
                 "material_id": "stainless_316l_sheet"}, None),
            "crest_radius_mm")
    _expect(failures,
            "bullnose over wall/2 refused",
            lambda: basin_round.validate(
                {"diameter_mm": 2000, "wall_mm": 40,
                 "rim_treatment": "pool_edge", "pool_edge_radius_mm": 25,
                 "material_id": "basalt_slab"}, None),
            "wall_mm/2")
    _expect(failures,
            "coping overhang over the 100 mm cantilever bound refused",
            lambda: basin_round.validate(
                {"diameter_mm": 2000, "wall_mm": 40,
                 "rim_treatment": "coping", "coping_overhang_mm": 150,
                 "material_id": "basalt_slab"}, None),
            "coping_overhang_mm")

    # ------------------------------------------------------------------
    _section(4, "WEIR FROM THE SPEC — matched, mismatched, missing")

    def _spec(nodes, rim=None):
        params = {"diameter": {"value": 2000, "unit": "mm"},
                  "height": {"value": 450, "unit": "mm"},
                  "wall": {"value": 40, "unit": "mm"},
                  "floor": {"value": 60, "unit": "mm"}}
        if rim:
            params["rim_treatment"] = rim
        return {"massing": {"elements": [{
            "element_id": "b1", "primitive": "basin_round",
            "material_id": "basalt_slab", "parameters": params,
            "position": {"x_m": 0, "y_m": 0, "z_m": 0.8, "rot_z_deg": 0},
        }]}, "hydraulic_network": {"nodes": nodes, "edges": []}}

    plan = assembly_plan_from_spec(_spec([
        {"node_id": "w1", "type": "weir", "elevation_m": 1.25,
         "element_id": "b1"}]))
    _check(failures, "weir node at the crest elevation wires the treatment",
           plan[0]["parameters"]["rim_treatment"] == "weir_edge",
           "crest 1250 mm == node 1250 mm")
    _expect(failures,
            "elevation mismatch refused naming BOTH numbers",
            lambda: assembly_plan_from_spec(_spec([
                {"node_id": "w1", "type": "weir", "elevation_m": 1.10,
                 "element_id": "b1"}])),
            "1100", "1250")
    _expect(failures,
            "weir rim with NO weir node refused (invention)",
            lambda: assembly_plan_from_spec(_spec([], rim="weir_edge")),
            "weir node")

    # ------------------------------------------------------------------
    _section(5, "NOZZLES FROM THE SPEC — exact stone removed, honest refusals")
    plain, _ = assemble([dict(B_PLAN[0], fixtures=[],
                              parameters={**B_PLAN[0]["parameters"]}),
                         B_PLAN[1]], seed=B_SEED)
    bored, manifest = assemble(B_PLAN, seed=B_SEED)
    removed = float(plain.volume) - float(bored.volume)
    expected = 3 * math.pi * (20.6 / 2) ** 2 * 60
    print(f"volume removed: {removed:.0f} mm³, expected 3·π·(20.6/2)²·60 = "
          f"{expected:.0f} mm³")
    _check(failures, "3 bores remove exactly the drilled stone (±1%)",
           abs(removed - expected) <= 0.01 * expected)
    _check(failures, "manifest records the fixture with real numbers",
           manifest["elements"][0]["fixtures"][0]["count"] == 3
           and manifest["elements"][0]["fixtures"][0]["bore_mm"] == 20.6)
    _check(failures, "bored assembly still body_count 1",
           manifest["body_count_brep"] == 1)
    _expect(failures,
            "vanishing web between bores refused",
            lambda: assemble([{
                "element_id": "b1", "primitive": "basin_round",
                "parameters": {"diameter_mm": 2000, "height_mm": 450,
                               "wall_mm": 40, "floor_mm": 60,
                               "material_id": "basalt_slab"},
                "fixtures": [{"type": "nozzle_ring", "count": 24,
                              "bore_mm": 50, "ring_diameter_mm": 200}],
            }], seed=7),
            "web", "15")
    nodes = [
        {"node_id": "n1", "type": "nozzle", "elevation_m": 0.86,
         "element_id": "b1", "nozzle_bore_mm": 20.6},
        {"node_id": "n2", "type": "nozzle", "elevation_m": 0.86,
         "element_id": "b1", "nozzle_bore_mm": 32.0},
    ]
    _expect(failures, "mixed bores refused naming both",
            lambda: assembly_plan_from_spec(_spec(nodes)), "20.6", "32")
    _expect(failures, "fixture on a floorless host refused",
            lambda: assemble([{
                "element_id": "p1", "primitive": "plinth",
                "parameters": {"top_diameter_mm": 900,
                               "material_id": "basalt_slab"},
                "fixtures": [{"type": "nozzle_ring", "count": 2,
                              "bore_mm": 20}],
            }], seed=7),
            "basin_round")

    # ------------------------------------------------------------------
    _section(6, "DETERMINISM — two processes, one identity")
    sha_1 = export_step(bored, workdir / "b_run1.step",
                        step_timestamp_for(B_SEED))
    child = subprocess.run(
        [sys.executable, "-c", (
            "import sys, json, os; sys.path.insert(0, r'%s')\n"
            "from app.geometry.assembly import assemble\n"
            "from app.geometry.exporters import export_step\n"
            "from app.geometry.kernel import step_timestamp_for\n"
            "solid, m = assemble(json.loads(sys.argv[1]), seed=%d)\n"
            "print(os.getpid())\n"
            "print(export_step(solid, r'%s', step_timestamp_for(%d)))\n"
        ) % (REPO_ROOT / "backend", B_SEED,
             workdir / "b_run2.step", B_SEED),
         json.dumps(B_PLAN)],
        capture_output=True, text=True,
    )
    lines = child.stdout.strip().splitlines()
    child_pid = lines[-2] if len(lines) >= 2 else "?"
    sha_2 = lines[-1] if lines else ""
    print(f"process {os.getpid()}: {sha_1}")
    print(f"process {child_pid}: {sha_2 or child.stderr[-200:]}")
    _check(failures, "weir+nozzle assembly byte-identical across processes",
           sha_1 == sha_2)

    # ------------------------------------------------------------------
    _section(7, "VERDICT")
    if failures:
        print(f"{FAIL} — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{PASS} — Phase 6 slice B auto gate: all sections passed at $0, "
          "no network, no AI-written code executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
