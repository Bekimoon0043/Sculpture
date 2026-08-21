"""FastAPI application entry point — LuxuryForm Studio v1, Phase 2.

Uvicorn target: ``app.main:app``. On startup the database is created/migrated
from schema.sql (idempotent; a Phase 1 database file is renamed to a backup,
never deleted — SPEC_PHASE2 §2).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api import (
    routes_costing,
    routes_council,
    routes_assembly,
    routes_geometry,
    routes_health,
    routes_logs,
)
from app.db.database import get_default_db

app = FastAPI(
    title="LuxuryForm Studio v1",
    version="0.3.0",
    description=(
        "Local-first sculpture/fountain design platform for LuxuryCon — "
        "Phase 3 (in progress): the AI Council — orchestrator, transcript "
        "API; Phase 2 geometry kernel and viewport remain available."
    ),
)


@app.on_event("startup")
def _startup() -> None:
    get_default_db().init_db()


app.include_router(routes_health.router, prefix="/api")
app.include_router(routes_logs.router, prefix="/api")
app.include_router(routes_geometry.router, prefix="/api")
app.include_router(routes_assembly.router, prefix="/api")
app.include_router(routes_council.router, prefix="/api")
app.include_router(routes_costing.router, prefix="/api")
