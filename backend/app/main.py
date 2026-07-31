"""FastAPI application entry point — LuxuryForm Studio v1, Phase 1.

Uvicorn target: ``app.main:app``. On startup the database is created/migrated
from schema.sql (idempotent).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api import routes_health, routes_logs
from app.db.database import get_default_db

app = FastAPI(
    title="LuxuryForm Studio v1",
    version="0.1.0",
    description=(
        "Local-first sculpture/fountain design platform for LuxuryCon — "
        "Phase 1: provider layer, spend caps, audit logging."
    ),
)


@app.on_event("startup")
def _startup() -> None:
    get_default_db().init_db()


app.include_router(routes_health.router, prefix="/api")
app.include_router(routes_logs.router, prefix="/api")
