#!/usr/bin/env python3
r"""Phase 15 auto gate - draft isolation and frontend build, $0/offline.

Geometry/API section (backend container):
    docker compose exec backend python scripts/gate_phase15_auto.py

Frontend section (host):
    python scripts\gate_phase15_auto.py --frontend-only
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

PLAN = [
    {
        "element_id": "plinth_01",
        "primitive": "plinth",
        "parameters": {"top_diameter_mm": 2200, "height_mm": 300, "wall_mm": 120},
    },
    {
        "element_id": "basin_01",
        "primitive": "basin_round",
        "parameters": {
            "diameter_mm": 2000,
            "height_mm": 450,
            "wall_mm": 40,
            "floor_mm": 160,
            "min_clearance_mm": 220,
        },
        "joint": {"type": "stack_on", "parent": "plinth_01"},
    },
    {
        "element_id": "column_01",
        "primitive": "sculptural_column",
        "parameters": {"diameter_mm": 360, "height_mm": 900, "bore_mm": 80},
        "joint": {"type": "concentric_insert", "parent": "basin_01"},
    },
]
PAYLOAD = {
    "elements": PLAN,
    "seed": 42,
    "fabrication": {"max_lift_kg": 3000, "max_module_m": 4.0},
}
ELEMENT_IDS = sorted(element["element_id"] for element in PLAN)


def section(title: str) -> None:
    print("\n" + "-" * 72)
    print(title)
    print("-" * 72)


def glb_node_names(blob: bytes) -> list[str]:
    magic, version, length = struct.unpack_from("<4sII", blob, 0)
    assert magic == b"glTF" and version == 2 and length == len(blob)
    chunk_len, chunk_type = struct.unpack_from("<I4s", blob, 12)
    assert chunk_type == b"JSON"
    gltf = json.loads(blob[20 : 20 + chunk_len].decode("utf-8"))
    return sorted(
        node["name"]
        for node in gltf.get("nodes", [])
        if "mesh" in node and node.get("name")
    )


def backend_available() -> bool:
    try:
        import build123d  # noqa: F401
        import fastapi  # noqa: F401
        import trimesh  # noqa: F401
        return True
    except ImportError:
        return False


def run_backend() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="luxuryform_gate15_"))
    os.environ["LUXURYFORM_DB"] = str(workdir / "gate15.db")
    os.environ["LUXURYFORM_DATA_DIR"] = str(workdir / "data")

    from fastapi.testclient import TestClient
    from sqlalchemy import func, select

    from app.db.database import get_default_db, reset_default_db
    from app.db.models import DesignRow, ValidationReportRow
    from app.main import app

    reset_default_db()

    def counts() -> tuple[int, int]:
        db = get_default_db()
        with db.get_session() as session:
            return (
                session.scalar(select(func.count()).select_from(DesignRow)) or 0,
                session.scalar(select(func.count()).select_from(ValidationReportRow)) or 0,
            )

    with TestClient(app) as client:
        section("[1/3] DRAFT GLB - real named CAD geometry")
        before = counts()
        first = client.post("/api/geometry/assembly/preview.glb", json=PAYLOAD)
        assert first.status_code == 200, first.text
        assert first.headers["content-type"].startswith("model/gltf-binary")
        nodes = glb_node_names(first.content)
        assert nodes == ELEMENT_IDS, (nodes, ELEMENT_IDS)
        preview_hash = first.headers["x-luxuryform-preview-hash"]
        assert len(preview_hash) == 64
        print(f"preview: {len(first.content)} bytes, nodes={nodes}")
        print(f"kernel time: {float(first.headers['x-luxuryform-build-ms']):.0f} ms")

        section("[2/3] ISOLATION - no design or validation persistence")
        after = counts()
        assert after == before, (before, after)
        second = client.post("/api/geometry/assembly/preview.glb", json=PAYLOAD)
        assert second.status_code == 200
        assert second.headers["x-luxuryform-preview-hash"] == preview_hash
        assert counts() == before
        print(f"rows before={before}, after two previews={counts()}")
        print("stable request hash; no database writes")

        section("[3/3] FULL BUILD - canonical contract still persists")
        build_a = client.post("/api/geometry/assembly/build", json=PAYLOAD)
        build_b = client.post("/api/geometry/assembly/build", json=PAYLOAD)
        assert build_a.status_code == 200, build_a.text
        assert build_b.status_code == 200, build_b.text
        body_a, body_b = build_a.json(), build_b.json()
        assert body_a["step_sha256"] == body_b["step_sha256"]
        design_count, validation_count = counts()
        assert design_count == before[0] + 2
        assert validation_count > before[1]
        print(f"STEP sha256: {body_a['step_sha256'][:20]}...")
        print(f"persisted designs={design_count}, validation rows={validation_count}")

    reset_default_db()


def run_frontend() -> None:
    section("FRONTEND - strict typecheck and production build")
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm not found; run this section on the host")
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=REPO_ROOT / "frontend",
        capture_output=True,
        text=True,
        timeout=600,
    )
    for line in (result.stdout + result.stderr).splitlines()[-8:]:
        print(f"  {line}")
    assert result.returncode == 0, f"frontend build exited {result.returncode}"


def main() -> int:
    frontend_only = "--frontend-only" in sys.argv
    covered: list[str] = []
    try:
        if not frontend_only:
            if backend_available():
                run_backend()
                covered.append("backend")
            else:
                print("Backend section not run here; use the backend container.")
        if frontend_only or shutil.which("npm"):
            run_frontend()
            covered.append("frontend")
    except Exception as exc:
        print(f"\nFAIL - {type(exc).__name__}: {exc}")
        return 1
    if not covered:
        print("FAIL - no section could run")
        return 1
    print(f"\nPASS - Phase 15 sections: {', '.join(covered)} ($0, offline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
