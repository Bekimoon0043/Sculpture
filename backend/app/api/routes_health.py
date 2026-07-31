"""GET /api/health — stack status without leaking any key material.
GET /api/schema/design-spec — serves schemas/design_spec_v1.json, the
machine-readable contract between the AI Council and the Geometry Engine,
exactly as versioned in the repo.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import REPO_ROOT, get_settings, load_config_bundle, provider_keys_status
from app.db.database import get_default_db

router = APIRouter(tags=["health"])

SCHEMA_PATH = REPO_ROOT / "schemas" / "design_spec_v1.json"


@router.get("/health")
def health() -> dict:
    db = get_default_db()
    db_ok = True
    db_error = None
    try:
        with db.get_session() as s:
            s.execute(text("SELECT 1"))
    except Exception as exc:  # report honestly; health must not 500
        db_ok = False
        db_error = str(exc)

    bundle = load_config_bundle()
    budget = bundle.budget
    return {
        "status": "ok" if db_ok else "degraded",
        "phase": 1,
        "db": {"ok": db_ok, "error": db_error, "path": str(db.path)},
        "providers": provider_keys_status(get_settings()),
        "pricing_version": bundle.pricing.pricing_version,
        "budget": {
            "session_cap_usd": budget.session_cap_usd,
            "day_cap_usd": budget.day_cap_usd,
            "max_vision_iterations": budget.max_vision_iterations,
            "on_breach": budget.on_breach,
        },
    }


@router.get("/schema/design-spec")
def design_spec_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
