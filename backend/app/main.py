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
    routes_dna,
    routes_geometry,
    routes_health,
    routes_intake,
    routes_logs,
    routes_ops,
    routes_render,
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
    db = get_default_db()
    db.init_db()
    # PR-2 (ADR-061): classify leftover spend holds honestly BEFORE the app
    # serves anything — a hold that survived a crash means the provider may
    # have billed a call we never settled; it becomes 'uncertain' and keeps
    # consuming cap headroom. Then assert the two books (reservations vs
    # ai_calls) agree in BOTH directions; a mismatch engages a GLOBAL
    # safety lock (fail closed) rather than serving with wrong arithmetic.
    from app.core.budget import recover_stale_spend_holds, reconcile_spend_books

    recover_stale_spend_holds(db)
    reconcile_spend_books(db)


app.include_router(routes_health.router, prefix="/api")
app.include_router(routes_logs.router, prefix="/api")
app.include_router(routes_geometry.router, prefix="/api")
app.include_router(routes_assembly.router, prefix="/api")
app.include_router(routes_council.router, prefix="/api")
app.include_router(routes_costing.router, prefix="/api")
app.include_router(routes_intake.router, prefix="/api")
app.include_router(routes_dna.router, prefix="/api")
app.include_router(routes_render.router, prefix="/api")
app.include_router(routes_ops.router, prefix="/api")
