"""Fixture-mode Council replay (Phase 3, build step 1).

Persists a captured Council session (tests/fixtures/council_session_v1.json)
into the schema-v3 tables with ZERO provider calls — the $0 development and
gate path (operator: "a $0 offline gate I can re-run forever").

What replay does, in order, failing loudly on any defect:

1. validates the fixture's shape (FixtureError names the defect),
2. validates every Design Spec against schemas/design_spec_v1.json — a spec
   that fails schema validation is NEVER persisted as valid (schema_valid=0
   rows are only for recording the live orchestrator's failed candidates;
   a fixture that fails validation is a corrupt fixture: hard error),
3. recomputes each call's cost from the recorded token counts x
   pricing.yaml (never trusts a recorded cost — the pricing path is
   exercised offline; PricingLookupError propagates if a fixture model is
   absent from pricing.yaml),
4. enforces the Arbiter invariants: exactly 3 chosen specs, distinct, all
   present among the session's persisted specs, confidence in [0, 1],
5. writes council_sessions, council_calls, design_specs,
   engineering_reviews, defect_lists, arbiter_decisions and updates the
   session's total_cost_usd + arbiter_confidence.

spec_hash is COMPUTED (canonical JSON sha256 of the spec EXCLUDING
meta.spec_hash itself — a hash cannot contain itself; same sorted-keys
convention as geometry/kernel.py), and must match the fixture's recorded
meta.spec_hash — a mismatch means the fixture was hand-edited carelessly.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from app.core.config import PricingConfig, REPO_ROOT
from app.db.database import Database
from app.db.models import (
    ArbiterDecisionRow,
    CouncilCallRow,
    CouncilSessionRow,
    DefectListRow,
    DesignSpecRow,
    EngineeringReviewRow,
)

SCHEMA_PATH = REPO_ROOT / "schemas" / "design_spec_v1.json"

ROLES = ("researcher", "designer", "geometrist", "engineer", "critic", "arbiter")
SIDES = ("primary", "parallel", "tiebreaker")

_FIXTURE_REQUIRED_TOP = {
    "fixture_version",
    "synthetic",
    "session",
    "calls",
    "design_specs",
    "engineering_reviews",
    "defect_lists",
    "arbiter_decision",
}
_CALL_REQUIRED = {
    "id", "role", "side", "provider", "model", "ts", "prompt", "response",
    "tokens_in", "tokens_out", "latency_ms", "status",
}


class FixtureError(RuntimeError):
    """Raised when a Council session fixture is malformed or inconsistent."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_spec_hash(spec: dict) -> str:
    """sha256 of the canonical JSON, EXCLUDING meta.spec_hash.

    A hash cannot contain itself, so the hashed content is the full spec
    with meta.spec_hash removed (Amendment 1: the hash is the content
    address of the spec; meta.spec_hash merely records it). Sorted keys
    and compact separators — the same convention as geometry/kernel.py.
    """
    content = {k: v for k, v in spec.items() if k != "meta"}
    meta = {k: v for k, v in spec.get("meta", {}).items() if k != "spec_hash"}
    content["meta"] = meta
    blob = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_fixture(path: str | Path) -> dict:
    """Load and shape-validate a Council session fixture."""
    path = Path(path)
    if not path.exists():
        raise FixtureError(f"fixture not found: {path}")
    try:
        fx = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureError(f"fixture is not valid JSON: {path}: {exc}") from exc
    if not isinstance(fx, dict):
        raise FixtureError("fixture top level must be an object")
    missing = _FIXTURE_REQUIRED_TOP - set(fx)
    if missing:
        raise FixtureError(f"fixture missing top-level keys: {sorted(missing)}")
    if not isinstance(fx["synthetic"], bool):
        raise FixtureError("fixture 'synthetic' flag must be a boolean")
    sess = fx["session"]
    for key in ("id", "brief_text", "started_at", "ended_at"):
        if key not in sess:
            raise FixtureError(f"fixture session missing {key!r}")
    for i, call in enumerate(fx["calls"]):
        missing_keys = _CALL_REQUIRED - set(call)
        if missing_keys:
            raise FixtureError(
                f"fixture call #{i} missing keys: {sorted(missing_keys)}"
            )
        if call["role"] not in ROLES:
            raise FixtureError(f"fixture call #{i}: unknown role {call['role']!r}")
        if call["side"] not in SIDES:
            raise FixtureError(f"fixture call #{i}: unknown side {call['side']!r}")
    decision = fx["arbiter_decision"]
    for key in ("chosen_spec_ids", "confidence", "rationale", "disagreement_register"):
        if key not in decision:
            raise FixtureError(f"fixture arbiter_decision missing {key!r}")
    return fx


def replay_session(db: Database, pricing: PricingConfig, fixture: dict) -> str:
    """Persist one fixture session. Returns the council session id."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sess = fixture["session"]
    session_id = sess["id"]

    with db.get_session() as s:
        if s.get(CouncilSessionRow, session_id) is not None:
            raise FixtureError(
                f"council session {session_id} already replayed into this database"
            )

    # --- design specs: schema-validate, compute hash, cross-check ----------
    spec_rows: list[DesignSpecRow] = []
    seen_ids: set[str] = set()
    for entry in fixture["design_specs"]:
        spec = entry["spec"]
        try:
            jsonschema.validate(instance=spec, schema=schema)
        except jsonschema.ValidationError as exc:
            raise FixtureError(
                f"fixture spec {spec.get('meta', {}).get('spec_id', '?')} fails "
                f"design_spec_v1.json validation: {exc.message}"
            ) from exc
        meta = spec["meta"]
        spec_id = meta["spec_id"]
        if spec_id in seen_ids:
            raise FixtureError(f"duplicate spec_id in fixture: {spec_id}")
        seen_ids.add(spec_id)
        computed = canonical_spec_hash(spec)
        recorded = meta.get("spec_hash", "").removeprefix("sha256:")
        if recorded and recorded != computed:
            raise FixtureError(
                f"spec {spec_id}: recorded meta.spec_hash does not match the "
                f"computed canonical hash — fixture was edited without "
                f"re-hashing (recorded {recorded[:16]}..., computed {computed[:16]}...)"
            )
        spec_rows.append(
            DesignSpecRow(
                id=spec_id,
                created_at=sess["started_at"],
                session_id=session_id,
                provider=meta["provider"],
                alternative_no=meta["alternative_no"],
                spec_json=json.dumps(spec, sort_keys=True),
                spec_hash=computed,
                seed=meta["seed"],
                schema_valid=1,
            )
        )

    # --- arbiter invariants -------------------------------------------------
    decision = fixture["arbiter_decision"]
    chosen = decision["chosen_spec_ids"]
    if len(chosen) != 3 or len(set(chosen)) != 3:
        raise FixtureError(
            f"arbiter must bind exactly 3 DISTINCT specs, got {chosen}"
        )
    unknown = set(chosen) - seen_ids
    if unknown:
        raise FixtureError(
            f"arbiter chose spec ids not present in this session: {sorted(unknown)}"
        )
    confidence = decision["confidence"]
    if not (0.0 <= float(confidence) <= 1.0):
        raise FixtureError(f"arbiter confidence out of [0, 1]: {confidence}")

    # --- calls: recompute cost from tokens x pricing.yaml -------------------
    call_rows: list[CouncilCallRow] = []
    total_cost = 0.0
    for call in fixture["calls"]:
        cached_in = int(call.get("cached_input_tokens", 0))
        cache_write_in = int(call.get("cache_write_input_tokens", 0))
        cost = pricing.cost_usd(
            call["provider"], call["model"],
            call["tokens_in"], call["tokens_out"],
            cached_input_tokens=cached_in,
            cache_write_input_tokens=cache_write_in,
        )
        total_cost += cost
        call_rows.append(
            CouncilCallRow(
                id=call["id"],
                session_id=session_id,
                ts=call["ts"],
                role=call["role"],
                side=call["side"],
                provider=call["provider"],
                model=call["model"],
                prompt=call["prompt"],
                response=call["response"],
                tokens_in=call["tokens_in"],
                tokens_out=call["tokens_out"],
                cached_input_tokens=cached_in,
                cache_write_input_tokens=cache_write_in,
                latency_ms=call["latency_ms"],
                cost_usd=cost,
                pricing_version=pricing.pricing_version,
                status=call["status"],
                error=call.get("error"),
            )
        )

    # --- persist everything --------------------------------------------------
    # Flush order is explicit: the session row FIRST, in its own flush, then
    # the children. SQLAlchemy's unit of work only orders cross-mapper
    # inserts from relationship() dependency processors — we declare none —
    # so without an explicit flush a child INSERT can be emitted before its
    # parent (observed: arbiter_decisions before council_sessions, FK
    # violation under PRAGMA foreign_keys=ON).
    with db.get_session() as s:
        s.add(
            CouncilSessionRow(
                id=session_id,
                created_at=sess["started_at"],
                brief_text=sess["brief_text"],
                status="completed",
                started_at=sess["started_at"],
                ended_at=sess["ended_at"],
                total_cost_usd=round(total_cost, 6),
                pricing_version=pricing.pricing_version,
                arbiter_confidence=float(confidence),
                degraded=int(sess.get("degraded", 0)),
            )
        )
        s.flush()  # parent row exists before any child insert is emitted
        for row in call_rows + spec_rows:
            s.add(row)
        for rev in fixture["engineering_reviews"]:
            s.add(
                EngineeringReviewRow(
                    id=rev["id"],
                    created_at=sess["started_at"],
                    session_id=session_id,
                    provider=rev["provider"],
                    side=rev["side"],
                    payload_json=json.dumps(rev["payload"], sort_keys=True),
                )
            )
        for dl in fixture["defect_lists"]:
            s.add(
                DefectListRow(
                    id=dl["id"],
                    created_at=sess["started_at"],
                    session_id=session_id,
                    provider=dl["provider"],
                    side=dl["side"],
                    payload_json=json.dumps(dl["payload"], sort_keys=True),
                )
            )
        s.add(
            ArbiterDecisionRow(
                id=decision["id"],
                created_at=sess["ended_at"],
                session_id=session_id,
                chosen_spec_ids_json=json.dumps(chosen),
                confidence=float(confidence),
                rationale=decision["rationale"],
                disagreement_register_json=json.dumps(
                    decision["disagreement_register"], sort_keys=True
                ),
                binding=1,
            )
        )
    return session_id
