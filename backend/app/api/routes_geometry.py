"""Geometry API — Phase 2 cascade build/validation/download endpoints.

Mounted in app.main at /api. Every build is validated (hard constraints,
ADD-4), persisted (designs + validation_reports rows), and exported
(STEP canonical + GLB preview) before the response returns — no lazy paths.

Data files live under <data dir>/designs/<spec_hash>/ where the data dir is
LUXURYFORM_DATA_DIR (default <repo>/data) — the same directory the operator
already volume-mounts for the database.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import REPO_ROOT, load_config_bundle
from app.db.database import get_default_db
from app.db.models import DesignRow, ValidationReportRow
from app.geometry import (
    CASCADE_PARAMETERS,
    ConstraintViolation,
    GeometryBuild,
    export_glb,
    export_step,
    validate_mesh,
    validate_params,
)

log = logging.getLogger("luxuryform.api.geometry")

router = APIRouter(prefix="/geometry/cascade", tags=["geometry"])


def data_dir() -> Path:
    """Root for exported design files (env-overridable for tests)."""
    return Path(os.environ.get("LUXURYFORM_DATA_DIR", str(REPO_ROOT / "data")))


class BuildRequest(BaseModel):
    parameters: dict[str, Any] = {}
    seed: int = 0


def _materials_public() -> dict[str, dict[str, Any]]:
    bundle = load_config_bundle()
    return {
        mid: {
            "name": m.name,
            "category": m.category,
            "density_kg_per_m3": m.density_kg_per_m3,
            "min_wall_mm": m.min_wall_mm,
        }
        for mid, m in bundle.materials.materials.items()
    }


@router.get("/defaults")
def get_defaults() -> dict[str, Any]:
    """The full parameter registry + materials, for the frontend panel."""
    return {
        "parameters": CASCADE_PARAMETERS,
        "materials": _materials_public(),
    }


@router.post("/build")
def post_build(request: BuildRequest) -> dict[str, Any]:
    """Validate -> build -> export -> validate mesh -> persist -> respond."""
    t0 = time.perf_counter()
    try:
        params = validate_params(request.parameters)
    except ConstraintViolation as exc:
        # 422 with EVERY violation, each carrying real numbers (ADD-4).
        raise HTTPException(
            status_code=422,
            detail={"violations": exc.violations},
        ) from exc

    build = GeometryBuild(request.seed, params)
    solid = build.build()

    out_dir = data_dir() / "designs" / build.spec_hash
    step_path = out_dir / "cascade.step"
    glb_path = out_dir / "cascade.glb"
    step_sha256 = export_step(solid, step_path, build.step_timestamp)
    glb_sha256 = export_glb(solid, glb_path)

    bundle = load_config_bundle()
    material = bundle.materials.materials[params.material_id]
    report = validate_mesh(
        glb_path,
        material,
        material_id=params.material_id,
        reference_volume_mm3=float(solid.volume),
    )

    build_ms = (time.perf_counter() - t0) * 1000.0
    now = datetime.now(timezone.utc).isoformat()
    design_id = str(uuid.uuid4())
    db = get_default_db()
    with db.get_session() as session:
        session.add(
            DesignRow(
                id=design_id,
                created_at=now,
                spec_id=None,
                geometry_hash=step_sha256,
                parameter_json=json.dumps(params.canonical_dict(), sort_keys=True),
                status="built",
                seed=request.seed,
                spec_hash=build.spec_hash,
                build_ms=build_ms,
                glb_path=str(glb_path),
                step_path=str(step_path),
            )
        )
        session.add(
            ValidationReportRow(
                id=str(uuid.uuid4()),
                created_at=now,
                design_id=design_id,
                gate_name="mesh",
                passed=1 if report.passed else 0,
                numbers_json=report.model_dump_json(),
            )
        )
    log.info(
        "cascade build persisted: design=%s spec_hash=%s seed=%d passed=%s",
        design_id,
        build.spec_hash,
        request.seed,
        report.passed,
    )

    return {
        "spec_hash": build.spec_hash,
        "seed": request.seed,
        "step_sha256": step_sha256,
        "glb_sha256": glb_sha256,
        "glb_url": "/api/geometry/cascade/latest.glb",
        "step_url": "/api/geometry/cascade/latest.step",
        "build_ms": build_ms,
        "validation": {**report.model_dump(), "rows": report.check_rows()},
    }


def _latest_design() -> DesignRow:
    db = get_default_db()
    with db.get_session() as session:
        row = session.execute(
            select(DesignRow).order_by(DesignRow.created_at.desc()).limit(1)
        ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="no cascade build yet")
    return row


@router.get("/latest.glb")
def get_latest_glb() -> FileResponse:
    row = _latest_design()
    if not row.glb_path or not Path(row.glb_path).exists():
        raise HTTPException(status_code=404, detail="latest build has no GLB on disk")
    return FileResponse(row.glb_path, media_type="model/gltf-binary", filename="cascade.glb")


@router.get("/latest.step")
def get_latest_step() -> FileResponse:
    row = _latest_design()
    if not row.step_path or not Path(row.step_path).exists():
        raise HTTPException(status_code=404, detail="latest build has no STEP on disk")
    return FileResponse(
        row.step_path, media_type="application/step", filename="cascade.step"
    )


@router.get("/latest/validation")
def get_latest_validation() -> dict[str, Any]:
    db = get_default_db()
    with db.get_session() as session:
        row = session.execute(
            select(ValidationReportRow)
            .order_by(ValidationReportRow.created_at.desc())
            .limit(1)
        ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="no validation report yet")
    numbers = json.loads(row.numbers_json)
    return {
        "created_at": row.created_at,
        "design_id": row.design_id,
        "gate_name": row.gate_name,
        "passed": bool(row.passed),
        "validation": numbers,
    }
