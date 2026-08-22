#!/usr/bin/env python3
"""Phase 11 auto gate — DesignDNA precedent memory. $0, no network.

    docker compose exec backend python scripts/gate_phase11_auto.py

Proves, on a REAL design built through the real pipeline:

  1. build -> validate -> export -> ACCEPT creates one retrievable precedent
  2. acceptance without a package, author or note is refused with the reason
  3. retrieval explains WHY each hit matched, field by field
  4. the Council injection block is quarantined and provenance-marked
  5. archive hides from retrieval but keeps the record; delete tombstones
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
    print(f"[{no}/5] {title}")
    _hline()


def _check(failures: list[str], label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="luxform_gate11_")
    os.environ["LUXURYFORM_DB"] = os.path.join(tmp, "gate11.db")
    os.environ["LUXURYFORM_DATA_DIR"] = os.path.join(tmp, "data")

    from fastapi.testclient import TestClient

    from app.db.database import reset_default_db
    reset_default_db()
    from app.main import app

    failures: list[str] = []
    payload = {
        "seed": 7,
        "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
        "water": {"has_water": True, "flow_l_per_min": 120,
                  "operating_depth_mm": 200, "nozzle_bore_mm": 20},
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

    with TestClient(app) as client:
        # -------------------------------------------------------------
        _section(1, "PIPELINE ORDER — accept requires the deliverable")
        design_id = client.post("/api/geometry/assembly/build", json=payload).json()["design_id"]

        premature = client.post("/api/dna/accept", json={
            "design_id": design_id, "accepted_by": "operator",
            "acceptance_note": "too early",
        })
        _check(failures, "accepting before the export package is refused",
               premature.status_code == 409
               and "export package" in premature.json()["detail"],
               premature.json().get("detail", "")[:80])

        export = client.post(f"/api/geometry/assembly/{design_id}/exports").json()
        digest = export["content_digest"]
        _check(failures, "the export package sealed with a content digest",
               len(digest) == 64, digest[:16] + "...")

        anonymous = client.post("/api/dna/accept", json={
            "design_id": design_id, "accepted_by": " ",
            "acceptance_note": "x",
        })
        _check(failures, "accepting without an author is refused",
               anonymous.status_code == 409)

        accepted = client.post("/api/dna/accept", json={
            "design_id": design_id, "accepted_by": "operator",
            "acceptance_note": "clean basalt plaza fountain, strong proportions",
        })
        _check(failures, "accept creates one precedent",
               accepted.status_code == 201, accepted.json().get("id", "?")[:8])
        precedent = accepted.json()
        _check(failures, "the precedent carries the package digest (R1)",
               precedent["content_digest"] == digest)
        _check(failures, "the precedent carries authorship (R3)",
               precedent["accepted_by"] == "operator")

        duplicate = client.post("/api/dna/accept", json={
            "design_id": design_id, "accepted_by": "operator",
            "acceptance_note": "again",
        })
        _check(failures, "the same deliverable cannot be accepted twice",
               duplicate.status_code == 409
               and "already precedent" in duplicate.json()["detail"])

        # -------------------------------------------------------------
        _section(2, "TAGS — measured from the manifest, never inferred")
        tags = precedent["tags"]
        _check(failures, "materials measured", tags["materials"] == ["basalt_slab"],
               str(tags["materials"]))
        _check(failures, "height measured from world bbox",
               0.5 < tags["height_m"] < 1.5, f"{tags['height_m']} m")
        _check(failures, "water declared", tags["has_water"] is True)
        _check(failures, "validation rollup recorded",
               tags["overall_status"] in {"pass", "warn", "needs_input"},
               tags["overall_status"])

        # -------------------------------------------------------------
        _section(3, "RETRIEVAL — every hit explains itself (R4)")
        hits = client.get("/api/dna/search", params={
            "material": "basalt_slab", "has_water": True,
            "height_m": tags["height_m"],
        }).json()
        _check(failures, "the precedent is retrieved", hits["count"] == 1)
        reasons = hits["precedents"][0]["match_reasons"]
        _check(failures, "material match is named", "material basalt_slab" in reasons)
        _check(failures, "water match is named", "water design" in reasons)
        _check(failures, "height match names the band",
               any("within" in r for r in reasons), "; ".join(reasons)[:70])

        miss = client.get("/api/dna/search", params={
            "material": "basalt_slab", "has_water": False,
        }).json()
        _check(failures, "a non-matching criterion excludes (AND, not fuzzy)",
               miss["count"] == 0)

        # -------------------------------------------------------------
        _section(4, "INJECTION — quarantined, capped, provenance-marked")
        from app.db.database import get_default_db
        from app.dna import precedent_block, search_precedents

        db = get_default_db()
        with db.get_session() as session:
            matches = search_precedents(session, material="basalt_slab")
        block = precedent_block(matches)
        _check(failures, "the block is delimited",
               "BEGIN PRECEDENTS" in block and "END PRECEDENTS" in block)
        _check(failures, "numbers are marked as prior work, not requirements",
               "NOT requirements" in block)
        _check(failures, "dimension copying is explicitly forbidden",
               "Never copy a dimension" in block)
        _check(failures, "the acceptance note travels with the precedent",
               "strong proportions" in block)

        # -------------------------------------------------------------
        _section(5, "ARCHIVE vs DELETE — different operations (R6)")
        pid = precedent["id"]
        archived = client.post(f"/api/dna/{pid}/archive").json()
        _check(failures, "archive succeeds", archived["status"] == "archived")
        gone = client.get("/api/dna/search", params={"material": "basalt_slab"}).json()
        _check(failures, "archived precedent leaves retrieval", gone["count"] == 0)
        still = client.get(f"/api/dna/{pid}", params={"full": True}).json()
        _check(failures, "the archived record is intact for old sessions",
               still["acceptance_note"] is not None
               and still["record"]["manifest"]["schema"] == "assembly_manifest_v1")

        deleted = client.delete(f"/api/dna/{pid}").json()
        _check(failures, "delete tombstones", deleted["status"] == "deleted")
        tomb = client.get(f"/api/dna/{pid}").json()
        _check(failures, "the tombstone still resolves and says why",
               tomb["status"] == "deleted" and "deleted" in tomb["detail"])
        _check(failures, "the payload is gone from the tombstone",
               "acceptance_note" not in tomb)

    print()
    _hline()
    print("VERDICT")
    _hline()
    if failures:
        print(f"{FAIL} — Phase 11 auto gate: {len(failures)} check(s) failed:")
        for item in failures:
            print(f"    - {item}")
        return 1
    print(f"{PASS} — Phase 11 auto gate: all sections passed at $0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
