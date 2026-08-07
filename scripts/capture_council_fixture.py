"""Capture a LIVE Council session from the database as a replayable fixture
(Phase 3, build step 4).

Usage (operator, in the backend container):

    docker compose exec backend python scripts/capture_council_fixture.py <session_id>

Writes tests/fixtures/council_session_live_<shortid>.json in the EXACT shape
replay.load_fixture() validates, with synthetic=false — so a real session
becomes a $0 regression fixture forever after. The file records real prompts
and responses; review it before committing (client briefs may be private).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import REPO_ROOT  # noqa: E402
from app.db.database import get_default_db  # noqa: E402
from app.db.models import (  # noqa: E402
    ArbiterDecisionRow,
    CouncilCallRow,
    CouncilSessionRow,
    DefectListRow,
    DesignSpecRow,
    EngineeringReviewRow,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    session_id = sys.argv[1]
    db = get_default_db()
    with db.get_session() as s:
        sess = s.get(CouncilSessionRow, session_id)
        if sess is None:
            print(f"no council session {session_id!r} in the database")
            return 1
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

    if not decisions:
        print(f"session {session_id} has no arbiter decision (status "
              f"{sess.status!r}) — only completed sessions make fixtures")
        return 1

    fixture = {
        "fixture_version": 1,
        "synthetic": False,
        "note": (
            f"Captured LIVE session {session_id} "
            f"({sess.created_at}, pricing {sess.pricing_version}). "
            "Real prompts/responses — review for client privacy before "
            "committing."
        ),
        "session": {
            "id": sess.id,
            "brief_text": sess.brief_text,
            "started_at": sess.started_at,
            "ended_at": sess.ended_at,
            "degraded": sess.degraded,
        },
        "calls": [
            {
                "id": c.id,
                "role": c.role,
                "side": c.side,
                "provider": c.provider,
                "model": c.model,
                "ts": c.ts,
                "prompt": c.prompt,
                "response": c.response,
                "tokens_in": c.tokens_in,
                "tokens_out": c.tokens_out,
                "cached_input_tokens": c.cached_input_tokens,
                "cache_write_input_tokens": c.cache_write_input_tokens,
                "latency_ms": c.latency_ms,
                "status": c.status,
            }
            for c in calls
        ],
        "design_specs": [
            {"spec": json.loads(r.spec_json)} for r in specs
        ],
        "engineering_reviews": [
            {
                "id": r.id,
                "provider": r.provider,
                "side": r.side,
                "payload": json.loads(r.payload_json),
            }
            for r in reviews
        ],
        "defect_lists": [
            {
                "id": r.id,
                "provider": r.provider,
                "side": r.side,
                "payload": json.loads(r.payload_json),
            }
            for r in defects
        ],
        "arbiter_decision": {
            "chosen_spec_ids": json.loads(decisions[0].chosen_spec_ids_json),
            "confidence": decisions[0].confidence,
            "rationale": decisions[0].rationale,
            "disagreement_register": json.loads(
                decisions[0].disagreement_register_json
            ),
        },
    }

    out = (
        REPO_ROOT / "tests" / "fixtures"
        / f"council_session_live_{session_id[:8]}.json"
    )
    out.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"  calls={len(calls)} specs={len(specs)} "
          f"reviews={len(reviews)} defect_lists={len(defects)} "
          f"total_cost=${sess.total_cost_usd:.6f}")
    print("review the file for client-private content before committing it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
