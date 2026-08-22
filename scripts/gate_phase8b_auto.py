#!/usr/bin/env python3
"""Phase 8b re-gate — intake context drives the Phase 8 gates. $0, no network.

    docker compose exec backend python scripts/gate_phase8b_auto.py

Phase 8 closed accepting `needs_input` as the hydraulic gate's terminal
status, because nothing populated the water context. Phase 12 (brief intake)
is that supply. This re-gate proves the chain end to end WITH NO
HAND-INJECTED CONTEXT: an intake filled through the real API drives the
hydraulic gate to a real verdict and puts real physics into the structural
gate — and the provenance of every supplied number survives to the report.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PASS, FAIL = "PASS", "FAIL"


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/4] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="luxform_gate8b_")
    os.environ["LUXURYFORM_DB"] = os.path.join(tmp, "gate8b.db")
    os.environ["LUXURYFORM_DATA_DIR"] = os.path.join(tmp, "data")

    from fastapi.testclient import TestClient

    from app.db.database import reset_default_db
    reset_default_db()
    from app.main import app

    failures: list[str] = []

    with TestClient(app) as client:
        # -------------------------------------------------------------
        _section(1, "BASELINE — without intake, the gates honestly cannot check")
        payload = {
            "seed": 7,
            "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
            "elements": [
                {"element_id": "plinth_01", "primitive": "plinth",
                 "parameters": {"top_diameter_mm": 2200, "height_mm": 300,
                                "wall_mm": 120}},
                {"element_id": "basin_01", "primitive": "basin_round",
                 "parameters": {"diameter_mm": 2000, "height_mm": 450,
                                "wall_mm": 40, "floor_mm": 160,
                                "min_clearance_mm": 220},
                 "joint": {"type": "stack_on", "parent": "plinth_01"}},
            ],
        }
        bare = client.post("/api/geometry/assembly/build", json=payload).json()
        _check(failures, "hydraulics reports needs_input with no context",
               bare["validation_gates"]["hydraulics"]["status"] == "needs_input")

        # -------------------------------------------------------------
        _section(2, "INTAKE — the readiness ladder gates paid work")
        created = client.post("/api/intake", json={
            "brief_text": "A basalt plaza fountain for Meskel Square, about "
                          "2.4 m tall with a gentle central jet.",
        }).json()
        intake_id = created["id"]
        _check(failures, "an empty intake is not ready for Council",
               created["readiness"]["ready_for_council"] is False)
        refused = client.post(f"/api/intake/{intake_id}/confirm")
        _check(failures, "confirming an unready intake is refused, naming fields",
               refused.status_code == 409
               and "missing_by_tier" in refused.json()["detail"])

        updated = client.put(f"/api/intake/{intake_id}", json={"fields": {
            "project.project_type": "fountain",
            "dimensions.height_m": 2.4, "dimensions.footprint_m": 3.0,
            "site.indoor": False,
            "site.altitude_m": 2355.0,
            "site.design_wind_speed_m_s": 30.0,
            "site.allowable_bearing_kpa": 150.0,
            "water.has_water": True, "water.flow_l_per_min": 120.0,
            "water.operating_depth_mm": 200.0, "water.nozzle_bore_mm": 20.0,
        }}).json()
        _check(failures, "operator-entered fields make it ready — no paid call",
               updated["readiness"]["ready_for_council"] is True)
        confirm = client.post(f"/api/intake/{intake_id}/confirm")
        _check(failures, "the intake confirms", confirm.status_code == 200)
        _check(failures, "the summary block marks provenance",
               "(operator)" in confirm.json()["summary_block"]
               and "UNKNOWN" in confirm.json()["summary_block"])

        # -------------------------------------------------------------
        _section(3, "THE RE-GATE — intake context reaches the gates")
        payload["intake_id"] = intake_id
        body = client.post("/api/geometry/assembly/build", json=payload).json()
        gates = body["validation_gates"]

        hydro = gates["hydraulics"]["status"]
        _check(failures, "hydraulics reaches a real verdict from the intake",
               hydro in {"pass", "warn", "fail"}, f"status {hydro}")
        rows = {r["check"]: r for r in gates["hydraulics"]["rows"]}
        _check(failures, "the nozzle bore was derived and judged",
               rows["nozzle_bore_mm"]["status"] in {"pass", "warn", "fail"},
               f"declared {rows['nozzle_bore_mm']['value']} mm, "
               f"band {rows['nozzle_bore_mm']['limit']}")
        _check(failures, "freeboard was measured",
               "basin_01.freeboard_mm" in rows,
               f"{rows.get('basin_01.freeboard_mm', {}).get('value')} mm")

        struct = {r["check"]: r for r in gates["structure_static_v1"]["rows"]}
        _check(failures, "ground bearing EVALUATES from the intake's site fact",
               struct["ground_bearing_pressure_kpa"]["status"]
               in {"pass", "warn", "fail"},
               f"{struct['ground_bearing_pressure_kpa']['value']} kPa vs "
               f"{struct['ground_bearing_pressure_kpa']['limit']} allowable")
        _check(failures, "wind pressure computed from the intake's wind + altitude",
               struct["design_wind_pressure_pa"]["value"] > 0,
               f"{struct['design_wind_pressure_pa']['value']} Pa")
        overturning = struct["overturning_safety_factor"]
        _check(failures,
               "overturning is COMPUTED; only the engineer's policy factor remains",
               overturning["status"] == "needs_input"
               and "computed safety factor is" in overturning["message"],
               overturning["message"][:70])

        # -------------------------------------------------------------
        _section(4, "PROVENANCE — the report says where every number came from")
        over = struct["site_overrides"]
        _check(failures, "the overrides row exists", over["status"] == "pass")
        _check(failures, "wind speed carries its source",
               over["value"]["design_wind_speed_m_s"]["source"] == "operator")
        _check(failures, "the basis names the intake channel",
               "intake_v1" in over["basis"])
        stored = client.get("/api/geometry/assembly/latest/manifest").json()
        _check(failures, "the stored request carries the intake id",
               stored["request"]["intake_id"] == intake_id)

    print()
    _hline()
    print("VERDICT")
    _hline()
    if failures:
        print(f"{FAIL} — Phase 8b re-gate: {len(failures)} check(s) failed:")
        for item in failures:
            print(f"    - {item}")
        return 1
    print(f"{PASS} — Phase 8b re-gate: intake context drives the gates at $0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
