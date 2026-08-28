#!/usr/bin/env python3
"""PR-1 AUTO GATE — per-axis fabrication limits (ADR-059). $0, offline.

The Design Spec has always declared fabrication.max_module_m as {x,y,z}
(design_spec_v1.json requires the object); until PR-1 the mapper collapsed
it to max(x,y,z), so the two tighter axes were gated against the loosest.
This gate proves the axes now survive end-to-end, that the Designer's
deliberate cubic scalar still works, and that historical collapsed-spec
designs are flagged for rebuild rather than silently re-judged
(the approved compatibility truth table, PR-1 Amendments 1, 2, 4, 5).

Run inside the backend container:
    docker compose exec backend python scripts/gate_pr1_auto.py

Sections:
  1. MAPPER — {2.4, 2.4, 2.2} preserved exactly; scalar and malformed
     axes refused with the offence named (never a collapse, never a
     TypeError).
  2. THE Z-AXIS PROOF — a basin that fits x/y but stands 2,300 mm tall
     is CUT under a 2.4 x 2.4 x 2.2 m envelope; every measured module
     fits every axis on its own limit.
  3. THE CLOSED DEFECT — the same solid under the old collapsed value
     (max = 2.4 cubic) ships WHOLE, 100 mm too tall for the declared
     truck. The difference between sections 2 and 3 is the defect.
  4. BOUNDARY — assemble() normalizes the Designer scalar to a cubic
     envelope, refuses malformed limits as ConstraintViolation, and the
     discrete-array refusal names the binding axis from a dict limit.
  5. PROVENANCE TRUTH TABLE — through the REAL API (TestClient, temp
     DB): per-axis and cubic designs read clean; a spec-backed scalar
     design reports needs_input with the recovered axes and its
     geometry-rebuilding endpoints refuse with the one next action; a
     mismatched spec is unverifiable, never assumed cubic.
  6. CANONICAL HASHES — all four unmoved (limit parsing cannot reach
     STEP bytes; asserted, not assumed).
  7. DETERMINISM — segmentation at a NON-cubic limit is byte-identical
     across two processes.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

CASCADE_STEP_SHA256 = (
    "e1a59fa6fd8ef05074373b9098feb62f10e186f9875c38679304e45f10ee6e13")
A1_ASSEMBLY_STEP_SHA256 = (
    "529014af672a282b6626cece8eebc777f5d839a34be02c9a031b5813cf22ddbd")
DEFAULT_BASIN_STEP_SHA256 = (
    "6038d26f28cd61b0c01ae9fde00ff2841b34ad0d6228cc7c4bbdbdd1eeacf0f0")
A1_SEED = 42
#: The C1 gate composition, byte-for-byte (same fixture as the 6c/6c2
#: gates); prefix pinned exactly as slice C1 published it.
C1_PLAN = [
    {"element_id": "p1", "primitive": "plinth",
     "parameters": {"top_diameter_mm": 1400, "height_mm": 400,
                    "material_id": "basalt_slab"}},
    {"element_id": "b1", "primitive": "basin_round",
     "parameters": {"diameter_mm": 1200, "height_mm": 350, "wall_mm": 40,
                    "floor_mm": 80, "material_id": "basalt_slab"},
     "joint": {"type": "stack_on", "parent": "p1"}},
    {"element_id": "a1", "primitive": "blade_fin_array",
     "parameters": {"hub_diameter_mm": 320, "hub_height_mm": 500,
                    "blade_count": 24, "blade_length_mm": 250,
                    "blade_height_mm": 400, "blade_thickness_mm": 20,
                    "material_id": "stainless_316l_sheet"},
     "joint": {"type": "concentric_insert", "parent": "b1"}},
]
C1_SEED = 7
C1_ASSEMBLY_STEP_SHA256 = "956436c1"

BASALT_DENSITY = 2700.0

failures: list[str] = []


def _check(label: str, ok: bool, detail: str = "") -> None:
    mark = "ok  " if ok else "FAIL"
    print(f"  {mark} {label}" + (f" :: {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def _section(n: int, title: str) -> None:
    print(f"\n[{n}] {title}")


def main() -> int:
    from app.geometry.assembly import assemble
    from app.geometry.primitives import PRIMITIVES
    from app.geometry.primitives.base import ConstraintViolation
    from app.geometry.segmentation import segment_solid
    from app.geometry.spec_mapper import fabrication_limits_from_spec

    # ------------------------------------------------------------------
    _section(1, "MAPPER — the spec's axes survive; bad shapes are refused")
    spec = {"fabrication": {"max_lift_kg": 2000,
                            "max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2}}}
    limits = fabrication_limits_from_spec(spec)
    _check("axes preserved exactly",
           limits["max_module_m"] == {"x": 2.4, "y": 2.4, "z": 2.2},
           repr(limits["max_module_m"]))
    for bad, label in [
        (2.4, "scalar (Design-Spec path must refuse — Amendment 3)"),
        ({"x": 2.4, "y": 2.4}, "missing axis"),
        ({"x": 2.4, "y": 2.4, "z": 2.2, "w": 9}, "extra axis"),
        ({"x": True, "y": 2.4, "z": 2.2}, "boolean axis"),
        ({"x": float("nan"), "y": 2.4, "z": 2.2}, "non-finite axis"),
        ({"x": 0, "y": 2.4, "z": 2.2}, "zero axis"),
        ({"x": -1, "y": 2.4, "z": 2.2}, "negative axis"),
    ]:
        try:
            fabrication_limits_from_spec(
                {"fabrication": {"max_module_m": bad}})
            _check(f"refuses {label}", False, "was accepted")
        except ConstraintViolation as exc:
            _check(f"refuses {label}",
                   "max_module_m" in "; ".join(exc.violations))
        except Exception as exc:  # a TypeError here is the old defect
            _check(f"refuses {label}", False,
                   f"wrong exception {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    _section(2, "THE Z-AXIS PROOF — 2.4 x 2.4 x 2.2 m cuts a 2.3 m column")
    module = PRIMITIVES["sculptural_column"]
    tall = module.build(module.validate(
        {"diameter_mm": 600, "height_mm": 2300,
         "material_id": "basalt_slab"}))
    per_axis = {"x": 2400.0, "y": 2400.0, "z": 2200.0}
    seg = segment_solid(tall, per_axis, density_kg_per_m3=BASALT_DENSITY)
    _check("grid splits ONLY the z axis",
           seg.grid == {"x": 1, "y": 1, "z": 2}, repr(seg.grid))
    _check("more than one module", seg.module_count >= 2,
           f"{seg.module_count} modules")
    worst_z = max(m["bbox_mm"][2] for m in seg.modules)
    _check("every module fits z <= 2200 mm", worst_z <= 2200.0 + 1e-6,
           f"tallest module z = {worst_z:.1f} mm")
    _check("volume conserved", seg.volume_delta_pct < 1e-6,
           f"{seg.volume_delta_pct:.10f} %")

    # ------------------------------------------------------------------
    _section(3, "THE CLOSED DEFECT — the collapsed value ships it whole")
    collapsed = segment_solid(
        tall, {"x": 2400.0, "y": 2400.0, "z": 2400.0},
        density_kg_per_m3=BASALT_DENSITY)
    _check("max(x,y,z)=2.4 cubic does NOT split it",
           collapsed.module_count == 1,
           f"{collapsed.module_count} module — 2,300 mm tall against the "
           f"declared 2,200 mm truck: this is what every spec-path design "
           f"was gated by before PR-1")

    # ------------------------------------------------------------------
    _section(4, "BOUNDARY — assemble(): cubic compat, loud refusals")
    plan = [{"element_id": "c1", "primitive": "sculptural_column",
             "parameters": {"diameter_mm": 600, "height_mm": 2300,
                            "material_id": "basalt_slab"}}]
    _, manifest = assemble(
        plan, seed=0,
        fabrication={"max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2},
                     "max_lift_kg": 20000}, strict=True)
    stored = manifest["fabrication_limits"]["max_module_m"]
    _check("manifest round-trips the dict",
           stored == {"x": 2.4, "y": 2.4, "z": 2.2}, repr(stored))
    mods = manifest["segmentation"]["elements"]["c1"]["modules"]
    _check("assemble cut the tall axis", len(mods) >= 2,
           f"{len(mods)} modules")

    _, cubic_manifest = assemble(
        plan, seed=0, fabrication={"max_module_m": 4.0,
                                   "max_lift_kg": 20000}, strict=True)
    cubic_stored = cubic_manifest["fabrication_limits"]["max_module_m"]
    _check("Designer scalar normalizes to a cubic dict",
           cubic_stored == {"x": 4.0, "y": 4.0, "z": 4.0},
           repr(cubic_stored))

    refused = 0
    for bad in [{"x": 2.4, "y": 2.4}, {"x": True, "y": 1, "z": 1},
                "2.4", 0, -1, float("nan")]:
        try:
            assemble(plan, seed=0, fabrication={"max_module_m": bad},
                     strict=True)
        except ConstraintViolation:
            refused += 1
        except Exception as exc:
            _check(f"malformed {bad!r} refused as ConstraintViolation",
                   False, f"{type(exc).__name__}: {exc}")
    _check("all 6 malformed limits refused as ConstraintViolation",
           refused == 6, f"{refused}/6")

    array_plan = [{"element_id": "a1", "primitive": "blade_fin_array",
                   "parameters": {"hub_diameter_mm": 900, "blade_count": 24,
                                  "blade_length_mm": 700,
                                  "material_id": "stainless_316l_sheet"}}]
    _, array_manifest = assemble(
        array_plan, seed=0,
        fabrication={"max_module_m": {"x": 0.8, "y": 3.0, "z": 3.0},
                     "max_lift_kg": 5000}, strict=False)
    refusal = array_manifest["segmentation"]["elements"]["a1"]["refusal"]
    _check("discrete-array refusal names the binding axis from a dict",
           "x axis" in refusal and "discrete_array" in refusal,
           refusal[:120])

    # ------------------------------------------------------------------
    _section(5, "PROVENANCE TRUTH TABLE — through the real API")
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LUXURYFORM_DB"] = str(Path(tmp) / "gate_pr1.db")
        os.environ["LUXURYFORM_DATA_DIR"] = str(Path(tmp) / "data")
        from app.db.database import reset_default_db
        reset_default_db()
        from app.main import app

        payload = {
            "seed": 7,
            "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
            "elements": [
                {"element_id": "b1", "primitive": "basin_round",
                 "parameters": {"diameter_mm": 2000, "height_mm": 450,
                                "wall_mm": 40, "floor_mm": 160,
                                "min_clearance_mm": 220}},
            ],
        }
        with TestClient(app) as client:
            cubic_id = client.post(
                "/api/geometry/assembly/build", json=payload
            ).json()["design_id"]
            body = client.get(
                f"/api/geometry/assembly/{cubic_id}/manifest").json()
            _check("row 1: spec_id NULL + scalar -> cubic, valid",
                   body["module_limit_provenance"] ==
                   {"kind": "cubic_request", "status": "ok"},
                   repr(body["module_limit_provenance"]))

            per_axis_payload = dict(payload)
            per_axis_payload["fabrication"] = {
                "max_lift_kg": 3000,
                "max_module_m": {"x": 4.0, "y": 4.0, "z": 2.2}}
            axis_id = client.post(
                "/api/geometry/assembly/build", json=per_axis_payload
            ).json()["design_id"]
            body = client.get(
                f"/api/geometry/assembly/{axis_id}/manifest").json()
            _check("row 2: spec_id NULL + {x,y,z} -> per-axis, valid",
                   body["module_limit_provenance"]["status"] == "ok"
                   and body["module_limit_provenance"]["kind"]
                   == "per_axis_request",
                   repr(body["module_limit_provenance"]))

            hist_id = client.post(
                "/api/geometry/assembly/build", json=payload
            ).json()["design_id"]
            conn = sqlite3.connect(os.environ["LUXURYFORM_DB"])
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "INSERT INTO council_sessions (id, created_at, brief_text, "
                "status, started_at, total_cost_usd, pricing_version) "
                "VALUES ('cs', 't', 'b', 'completed', 't', 0, 'v')")
            spec_json = json.dumps({"fabrication": {"max_module_m":
                                    {"x": 2.0, "y": 4.0, "z": 2.2}}})
            conn.execute(
                "INSERT INTO design_specs (id, created_at, session_id, "
                "provider, alternative_no, spec_json, spec_hash, seed, "
                "schema_valid) VALUES ('sp', 't', 'cs', 'p', 1, ?, 'h', 7, 1)",
                (spec_json,))
            conn.execute(
                "UPDATE designs SET spec_id = 'sp' WHERE id = ?", (hist_id,))
            conn.commit()
            conn.close()

            body = client.get(
                f"/api/geometry/assembly/{hist_id}/manifest").json()
            provenance = body["module_limit_provenance"]
            _check("row 4: spec-backed scalar -> collapsed_spec needs_input",
                   provenance["kind"] == "collapsed_spec"
                   and provenance["status"] == "needs_input",
                   repr({k: provenance[k] for k in ("kind", "status")}))
            _check("recovered spec axes ride along",
                   provenance.get("spec_max_module_m") ==
                   {"x": 2.0, "y": 4.0, "z": 2.2})
            _check("the one next action names the rebuild",
                   "rebuild" in provenance.get("action", "")
                   and "POST /api/geometry/assembly/build"
                   in provenance.get("action", ""))
            resp = client.post(
                f"/api/geometry/assembly/{hist_id}/exports")
            _check("geometry-rebuilding endpoint refuses with 409",
                   resp.status_code == 409
                   and "rebuild" in resp.json()["detail"],
                   f"HTTP {resp.status_code}")

            conn = sqlite3.connect(os.environ["LUXURYFORM_DB"])
            conn.execute(
                "UPDATE design_specs SET spec_json = ? WHERE id = 'sp'",
                (json.dumps({"fabrication": {"max_module_m":
                             {"x": 1.0, "y": 1.2, "z": 0.8}}}),))
            conn.commit()
            conn.close()
            body = client.get(
                f"/api/geometry/assembly/{hist_id}/manifest").json()
            _check("row 5: mismatched spec -> unverifiable, never cubic",
                   body["module_limit_provenance"]["kind"] == "unverifiable"
                   and body["module_limit_provenance"]["status"]
                   == "needs_input",
                   repr(body["module_limit_provenance"]["kind"]))
        reset_default_db()
        os.environ.pop("LUXURYFORM_DB", None)
        os.environ.pop("LUXURYFORM_DATA_DIR", None)

    # ------------------------------------------------------------------
    _section(6, "CANONICAL HASHES — all four unmoved")
    from _assembly_build_once import GATE_PLAN as A1_PLAN  # noqa: E402
    from app.geometry.exporters import export_step
    from app.geometry.kernel import step_timestamp_for
    from app.geometry.registry import cascade_fountain

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        solid, _ = cascade_fountain({}, seed=42)
        sha = export_step(solid, out / "cascade.step", step_timestamp_for(42))
        _check("cascade e1a59fa6...", sha == CASCADE_STEP_SHA256, sha[:16])

        fused, _ = assemble(A1_PLAN, seed=A1_SEED)
        sha = export_step(fused, out / "a1.step", step_timestamp_for(A1_SEED))
        _check("A1 composition 529014af...",
               sha == A1_ASSEMBLY_STEP_SHA256, sha[:16])

        from app.geometry.primitives import basin_round
        pb = basin_round.validate({}, None)
        basin = basin_round.build(pb)
        sha = export_step(basin, out / "basin.step", step_timestamp_for(42))
        _check("default basin 6038d26f...",
               sha == DEFAULT_BASIN_STEP_SHA256, sha[:16])

        fused_c1, _ = assemble(C1_PLAN, seed=C1_SEED)
        sha = export_step(fused_c1, out / "c1.step",
                          step_timestamp_for(C1_SEED))
        _check("C1 composition 956436c1...",
               sha.startswith(C1_ASSEMBLY_STEP_SHA256), sha[:16])

    # ------------------------------------------------------------------
    _section(7, "DETERMINISM — non-cubic cut byte-identical across processes")
    mine = segment_solid(tall, per_axis,
                         density_kg_per_m3=BASALT_DENSITY).canonical_json()
    child = subprocess.run(
        [sys.executable, "-c", (
            "import sys, json; sys.path.insert(0, r'%s')\n"
            "from app.geometry.primitives import PRIMITIVES\n"
            "from app.geometry.segmentation import segment_solid\n"
            "m = PRIMITIVES['sculptural_column']\n"
            "s = m.build(m.validate({'diameter_mm': 600, 'height_mm': 2300,"
            " 'material_id': 'basalt_slab'}))\n"
            "print(segment_solid(s, {'x': 2400.0, 'y': 2400.0, 'z': 2200.0},"
            " density_kg_per_m3=%r).canonical_json())\n"
        ) % (REPO_ROOT / "backend", BASALT_DENSITY)],
        capture_output=True, text=True,
    )
    theirs = child.stdout.strip().splitlines()[-1] if child.stdout else ""
    _check("byte-identical across two processes", mine == theirs,
           f"{len(mine)} chars" if mine == theirs
           else child.stderr[-200:])

    print()
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — PR-1 auto gate: all sections passed at $0, no network, "
          "no AI call.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
