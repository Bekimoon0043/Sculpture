"""Council transcript API (Phase 3, build step 3).

GET  /api/council/sessions            -> session list (newest first)
GET  /api/council/sessions/{id}       -> full transcript: calls, specs,
                                         engineering reviews, defect lists,
                                         arbiter decision, cost rollup
POST /api/council/demo-session        -> replays the COMMITTED synthetic
                                         fixture into the database so the
                                         transcript UI is explorable offline
                                         ($0). The fixture is labeled
                                         synthetic everywhere it surfaces.

Cost rollup is computed from council_calls rows (themselves recomputed from
tokens x pricing.yaml on replay — fixture costs are never trusted). The
rollup also reports cache_savings_usd: what the same calls WOULD have cost
had every input token billed at the full input rate, minus what they
actually cost (ADR-022 cache classes). Honest arithmetic from logged fields.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from pydantic import BaseModel

from app.core.config import REPO_ROOT, get_settings, load_config_bundle
from app.core.budget import BudgetEnforcer, BudgetHalt
from app.council.dispatch import LiveDispatcher
from app.council.orchestrator import CouncilOrchestrator, OrchestratorError
from app.council.replay import FixtureError, load_fixture, replay_session
from app.db.database import get_default_db
from app.db.models import (
    ArbiterDecisionRow,
    CouncilCallRow,
    CouncilSessionRow,
    DefectListRow,
    DesignSpecRow,
    EngineeringReviewRow,
    GeneratedProgramRow,
)

router = APIRouter(tags=["council"])

DEMO_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "council_session_v1.json"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"


def _synthetic_ids() -> set[str]:
    """Session ids that came from a committed synthetic fixture.

    The database does not stamp fixture sessions; the honest marker is that
    the session id appears verbatim in a committed fixture file (which is
    labeled synthetic: true inside). Live session ids are random uuids and
    can never collide with a fixture recorded in git.
    """
    ids: set[str] = set()
    if FIXTURE_DIR.exists():
        for path in FIXTURE_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("synthetic") and "session" in data:
                    ids.add(data["session"]["id"])
            except Exception:
                continue
    return ids


@router.get("/council/sessions")
def list_council_sessions() -> dict:
    db = get_default_db()
    with db.get_session() as s:
        rows = s.execute(
            select(CouncilSessionRow).order_by(CouncilSessionRow.created_at.desc())
        ).scalars().all()
    synthetic_ids = _synthetic_ids()
    return {
        "count": len(rows),
        "sessions": [
            {
                "id": r.id,
                "created_at": r.created_at,
                "brief_text": r.brief_text,
                "status": r.status,
                "total_cost_usd": r.total_cost_usd,
                "pricing_version": r.pricing_version,
                "arbiter_confidence": r.arbiter_confidence,
                "degraded": r.degraded,
                "corrected": r.corrected,
                "synthetic": r.id in synthetic_ids,
            }
            for r in rows
        ],
    }


def _resolve_session(db, session_id: str) -> CouncilSessionRow | None:
    """Unique-prefix resolution: the operator reads shortened ids
    (e.g. "session 32e1c68f") — resolve them honestly (400 on ambiguous,
    None on unknown)."""
    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, session_id)
        if sess is None:
            matches = s.execute(
                select(CouncilSessionRow).where(
                    CouncilSessionRow.id.startswith(session_id)
                )
            ).scalars().all()
            if len(matches) == 1:
                sess = matches[0]
            elif len(matches) > 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"session id prefix {session_id!r} is ambiguous "
                    f"({len(matches)} matches); use more characters",
                )
        return sess


@router.get("/council/sessions/{session_id}")
def council_session_detail(session_id: str) -> dict:
    db = get_default_db()
    bundle = load_config_bundle()
    caps = bundle.budget
    with db.get_session() as s:
        sess = _resolve_session(db, session_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="council session not found")
        session_id = sess.id
        calls = s.execute(
            select(CouncilCallRow)
            .where(CouncilCallRow.session_id == session_id)
            .order_by(CouncilCallRow.ts.asc())
        ).scalars().all()
        specs = s.execute(
            select(DesignSpecRow).where(DesignSpecRow.session_id == session_id)
        ).scalars().all()
        reviews = s.execute(
            select(EngineeringReviewRow)
            .where(EngineeringReviewRow.session_id == session_id)
        ).scalars().all()
        defects = s.execute(
            select(DefectListRow).where(DefectListRow.session_id == session_id)
        ).scalars().all()
        decisions = s.execute(
            select(ArbiterDecisionRow)
            .where(ArbiterDecisionRow.session_id == session_id)
        ).scalars().all()
        programs = s.execute(
            select(GeneratedProgramRow)
            .where(GeneratedProgramRow.session_id == session_id)
            .order_by(GeneratedProgramRow.attempt_no.asc())
        ).scalars().all()

    # Cost rollup — actual vs hypothetical all-full-input-rate (ADR-022).
    by_role: dict[str, float] = {}
    by_provider: dict[str, float] = {}
    cache_savings = 0.0
    for c in calls:
        by_role[c.role] = round(by_role.get(c.role, 0.0) + c.cost_usd, 6)
        by_provider[c.provider] = round(
            by_provider.get(c.provider, 0.0) + c.cost_usd, 6
        )
        if c.status != "ok":
            continue  # failed calls cost $0 and their model may be blank
        entry = bundle.pricing.price_for(c.provider, c.model)
        full_rate_cost = (
            (c.tokens_in + c.cached_input_tokens + c.cache_write_input_tokens)
            * entry.usd_per_1m_input_tokens
            + c.tokens_out * entry.usd_per_1m_output_tokens
        ) / 1_000_000
        cache_savings += full_rate_cost - c.cost_usd

    return {
        "session": {
            "id": sess.id,
            "created_at": sess.created_at,
            "brief_text": sess.brief_text,
            "status": sess.status,
            "started_at": sess.started_at,
            "ended_at": sess.ended_at,
            "total_cost_usd": sess.total_cost_usd,
            "pricing_version": sess.pricing_version,
            "arbiter_confidence": sess.arbiter_confidence,
            "degraded": sess.degraded,
            "corrected": sess.corrected,
            "synthetic": sess.id in _synthetic_ids(),
        },
        "calls": [
            {
                "id": c.id,
                "ts": c.ts,
                "role": c.role,
                "side": c.side,
                "provider": c.provider,
                "model": c.model,
                "prompt": c.prompt,
                "response": c.response,
                "tokens_in": c.tokens_in,
                "tokens_out": c.tokens_out,
                "cached_input_tokens": c.cached_input_tokens,
                "cache_write_input_tokens": c.cache_write_input_tokens,
                "latency_ms": c.latency_ms,
                "cost_usd": c.cost_usd,
                "pricing_version": c.pricing_version,
                "status": c.status,
                "error": c.error,
            }
            for c in calls
        ],
        "specs": [
            {
                "id": r.id,
                "provider": r.provider,
                "alternative_no": r.alternative_no,
                "spec_json": r.spec_json,
                "spec_hash": r.spec_hash,
                "seed": r.seed,
                "schema_valid": r.schema_valid,
            }
            for r in specs
        ],
        "programs": [
            {
                "id": p.id,
                "spec_id": p.spec_id,
                "attempt_no": p.attempt_no,
                "provider": p.provider,
                "model": p.model,
                "status": p.status,
                "rejection_reason": p.rejection_reason,
                "error_digest": p.error_digest,
                "program_hash": p.program_hash,
                "artifacts_json": p.artifacts_json,
                "validation_json": p.validation_json,
            }
            for p in programs
        ],
        "engineering_reviews": [
            {"id": r.id, "provider": r.provider, "side": r.side,
             "payload_json": r.payload_json}
            for r in reviews
        ],
        "defect_lists": [
            {"id": r.id, "provider": r.provider, "side": r.side,
             "payload_json": r.payload_json}
            for r in defects
        ],
        "arbiter_decision": (
            None
            if not decisions
            else {
                "id": decisions[0].id,
                "chosen_spec_ids_json": decisions[0].chosen_spec_ids_json,
                "confidence": decisions[0].confidence,
                "rationale": decisions[0].rationale,
                "disagreement_register_json": decisions[0].disagreement_register_json,
                "binding": decisions[0].binding,
            }
        ),
        "cost_rollup": {
            "total_cost_usd": sess.total_cost_usd,
            "by_role": by_role,
            "by_provider": by_provider,
            "cache_savings_usd": round(cache_savings, 6),
            "session_cap_usd": caps.session_cap_usd,
            "day_cap_usd": caps.day_cap_usd,
            "call_count": len(calls),
            "pricing_version": sess.pricing_version,
        },
    }


@router.post("/council/demo-session")
def load_demo_session() -> dict:
    """Replay the committed synthetic fixture ($0, offline, idempotent)."""
    if not Path(DEMO_FIXTURE_PATH).exists():
        raise HTTPException(status_code=500, detail="demo fixture missing")
    db = get_default_db()
    bundle = load_config_bundle()
    try:
        fixture = load_fixture(DEMO_FIXTURE_PATH)
    except FixtureError as exc:
        raise HTTPException(status_code=500, detail=f"fixture invalid: {exc}")
    session_id = fixture["session"]["id"]
    with db.get_session() as s:
        existing = s.get(CouncilSessionRow, session_id)
    if existing is None:
        replay_session(db, bundle.pricing, fixture)
        created = True
    else:
        created = False
    return {
        "session_id": session_id,
        "created": created,
        "synthetic": True,
        "note": (
            "Synthetic fixture (tests/fixtures/council_session_v1.json) — no "
            "real API calls were made; costs recomputed from tokens x "
            "pricing.yaml on load. Safe to reload; it never overwrites."
        ),
    }


class RunSessionRequest(BaseModel):
    brief_text: str


@router.post("/council/sessions", status_code=201)
def run_council_session(req: RunSessionRequest) -> dict:
    """Run one LIVE Council session (Phase 3, build step 4) — real API calls,
    real money, hard-capped by budget.yaml ($5 session / $25 day,
    pre-dispatch check per call).

    Synchronous by design: a full session is ~15 provider calls and takes
    minutes; the HTTP request stays open until the session completes. The
    full transcript is visible afterwards via GET /api/council/sessions/{id}
    (and live in ai_calls/council_calls as it runs).
    """
    brief = req.brief_text.strip()
    if not brief:
        raise HTTPException(status_code=422, detail="brief_text is empty")
    db = get_default_db()
    bundle = load_config_bundle()
    settings = get_settings()

    import uuid

    from app.ai.providers import build_providers

    # Pre-generate the session id so the BudgetEnforcer watches the SAME
    # session the calls are written to (session-cap accounting reads
    # ai_calls by session_id).
    session_id = str(uuid.uuid4())
    budget = BudgetEnforcer(
        session_id,
        bundle.budget.session_cap_usd,
        bundle.budget.day_cap_usd,
        db,
    )
    providers = build_providers(settings, bundle, db, budget)
    orchestrator = CouncilOrchestrator(
        db, bundle.pricing, LiveDispatcher(providers), bundle.council
    )
    try:
        orchestrator.run_session(brief, session_id=session_id)
    except BudgetHalt as exc:
        raise HTTPException(
            status_code=402,
            detail=(
                f"budget halt: {exc.reason} (spent ${exc.spent_usd:.4f} of "
                f"${exc.cap_usd:.2f} cap); partial session {exc.session_id} "
                "is persisted and visible in the transcript API"
            ),
        ) from exc
    except OrchestratorError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        # e.g. ProviderError("provider not configured") — the session row is
        # already finalized "failed" by the orchestrator; report honestly.
        raise HTTPException(
            status_code=500,
            detail=f"council session {session_id} failed: {exc}",
        ) from exc
    return {"session_id": session_id, "status": "completed"}


# ---------------------------------------------------------------------------
# Phase 4 — fabrication (GEOMETRIST code generation + sandbox)
# ---------------------------------------------------------------------------


class FabricateRequest(BaseModel):
    spec_id: str | None = None  # default: the Arbiter's first-ranked choice
    max_attempts: int = 3       # the bounded repair limit


@router.post("/council/sessions/{session_id}/fabricate", status_code=201)
def fabricate(session_id: str, req: FabricateRequest) -> dict:
    """Fabricate one Design Spec: the GEOMETRIST writes parametric build123d
    code, executed ONLY in the ADR-005 sandbox, with bounded repair.

    Real API calls, real money (each attempt is one audited geometrist_code
    call, visible separately in the rollup). Synchronous like the session
    endpoint. Requires the geo-worker container running (docker compose up).
    """
    db = get_default_db()
    sess = _resolve_session(db, session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="council session not found")
    session_id = sess.id

    spec_id = req.spec_id
    if spec_id is None:
        with db.get_session() as s:
            decision = s.execute(
                select(ArbiterDecisionRow)
                .where(ArbiterDecisionRow.session_id == session_id)
            ).scalars().first()
        if decision is None:
            raise HTTPException(
                status_code=422,
                detail="session has no Arbiter decision — nothing to fabricate",
            )
        chosen = json.loads(decision.chosen_spec_ids_json)
        spec_id = chosen[0]  # ranked best-first

    bundle = load_config_bundle()
    settings = get_settings()

    from app.ai.providers import build_providers
    from app.council.fabricate import ScratchSandboxRunner, fabricate_spec

    budget = BudgetEnforcer(
        session_id,
        bundle.budget.session_cap_usd,
        bundle.budget.day_cap_usd,
        db,
    )
    providers = build_providers(settings, bundle, db, budget)
    orchestrator = CouncilOrchestrator(
        db, bundle.pricing, LiveDispatcher(providers), bundle.council
    )
    try:
        outcome = fabricate_spec(
            orchestrator, session_id, spec_id,
            ScratchSandboxRunner(),
            max_attempts=req.max_attempts,
        )
    except BudgetHalt as exc:
        raise HTTPException(
            status_code=402,
            detail=(
                f"budget halt: {exc.reason} (spent ${exc.spent_usd:.4f} of "
                f"${exc.cap_usd:.2f} cap)"
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "success": outcome.success,
        "session_id": session_id,
        "spec_id": spec_id,
        "attempts": outcome.attempts,
        "program_ids": outcome.program_ids,
        "final_status": outcome.final_status,
        "artifacts": outcome.artifacts,
        "validation": outcome.validation,
        "error": outcome.error,
    }


@router.get("/council/fabrication-rates")
def fabrication_rates(session_id: str | None = None) -> dict:
    """GEOMETRIST success rates: first attempt AND each repair round,
    separately (operator order 2026-08-09), plus the AST rejection
    catalogue that informs the Phase 6 vocabulary widening."""
    from app.council.fabricate import success_rates

    return success_rates(get_default_db(), session_id)
