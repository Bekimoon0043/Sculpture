"""Atomic spend-cap enforcement (PR-2, ADR-061; supersedes the ADR-003 shape).

Hard ceilings on AI spend, enforced by RESERVATION, not by check-then-call:

* per-LOGICAL-RUN cap  (budget.yaml: run_cap_usd — one Council run, one
  fabrication run including repairs, one critique run including rounds)
* per-UTC-day cap      (budget.yaml: day_cap_usd — global across all runs)

Before every physical provider attempt, a cap-safe UPPER BOUND is reserved
inside ONE ``BEGIN IMMEDIATE`` transaction on a dedicated SQLite connection.
SQLite's single-writer lock serializes competing reservers across threads
AND processes, so two callers can never both pass when only one fits.
Settlement (the ai_calls insert, the reservation update and the sessions
ledger update) is a second single transaction — there is no partial state
for a crash to leave behind, and startup recovery classifies what remains.

Money in the ledger is INTEGER micro-USD (1 µUSD = $0.000001). Historical
REAL costs are converted through ``decimal.Decimal`` from their stored
decimal representation with explicit HALF-UP rounding (never binary-float
multiplication). Bounds round UP (ceiling) — a bound must never round down.

Fail-closed rules (operator amendments, 2026-08-28):
* No first-party documentation proves any provider error class is
  non-billing, so EVERY failed physical attempt is classified ``uncertain``
  and keeps consuming cap headroom at its full reserved bound. Silence in
  documentation is not proof of non-billing. (A ``released`` status
  deliberately does not exist — nothing can prove a release today.)
* A pricing failure after a billed call, or an actual cost above the
  reserved bound, engages a PERSISTED safety lock on that provider/model
  (or globally) and halts the spend scope: further matching paid dispatch
  refuses until the operator resolves the lock, audited, by reason.
* Cap refusals write their budget_events + jobs evidence INSIDE the
  refusing transaction — a refusal and its record are one atomic unit.

On breach the behavior of ADR-003 is preserved verbatim: halt, persist a
``budget_events`` row and a ``jobs`` row (status='halted_budget'), report,
never silently continue.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Iterator

from app.db.database import Database

log = logging.getLogger("luxuryform.budget")

#: Namespace for deterministic (uuid5) spend-scope identities. Full input
#: identifiers only — truncated prefixes are forbidden (a collision would
#: merge two $5 ledgers).
SPEND_SCOPE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL,
                                   "https://luxuryform.local/spend-scope")

#: How long a reserver waits on SQLite's write lock before failing loudly.
#: Judgement value (ADR-061): a reservation transaction is two aggregate
#: SELECTs and one INSERT — milliseconds — so 5 s absorbs a slow-disk WAL
#: checkpoint without ever masking a real deadlock.
LEDGER_BUSY_TIMEOUT_MS = 5000

_MICRO = Decimal("0.000001")


def usd_to_micro(value: float | str | Decimal, *,
                 rounding: str = ROUND_HALF_UP) -> int:
    """Convert a USD amount to integer micro-USD via Decimal.

    ``Decimal(str(value))`` reads the DECIMAL representation the repo
    stores/rounds to (all costs are round(x, 6)), never the binary-float
    expansion. HALF-UP is the default (settlements); bounds pass
    ``rounding=ROUND_CEILING`` so an upper bound can never round down.
    """
    if isinstance(value, Decimal):
        dec = value
    else:
        dec = Decimal(str(value))
    if dec < 0:
        raise ValueError("money amounts cannot be negative")
    return int(dec.quantize(_MICRO, rounding=rounding) / _MICRO)


def micro_to_usd(micro: int) -> float:
    """Exact float for display: 6-decimal USD (µUSD IS the 6th decimal)."""
    return float(Decimal(micro) * _MICRO)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round6(value: float) -> float:
    return round(float(value), 6)


def fabrication_scope_id(session_id: str, spec_id: str) -> str:
    """Deterministic fabrication spend-scope: uuid5 over the FULL canonical
    identity (operator ruling 2026-08-28: spend accumulates across every
    re-POST of the same (council session, spec) until PR-7B)."""
    return str(uuid.uuid5(SPEND_SCOPE_NAMESPACE,
                          f"fabrication:{session_id}:{spec_id}"))


def intake_scope_id(intake_id: str) -> str:
    """Deterministic intake spend-scope over the FULL intake id — repeated
    parses of one intake accumulate; the cap never resets by accident."""
    return str(uuid.uuid5(SPEND_SCOPE_NAMESPACE, f"intake:{intake_id}"))


def latest_open_scope(db: Database, kind: str, design_ref: str) -> str | None:
    """The newest OPEN spend scope for (kind, design_ref), or None.

    Critique resume semantics (Amendment 3): a restarted run reuses the
    latest open scope for its plan; once closed, a deliberate new
    invocation mints a fresh full-UUID scope — runs never share one
    lifetime cap. Halted scopes are NOT returned: they refuse dispatch."""
    with _ledger(db) as conn:
        row = conn.execute(
            "SELECT id FROM spend_scopes WHERE kind=? AND design_ref=? AND "
            "status='open' ORDER BY created_at DESC LIMIT 1",
            (kind, design_ref),
        ).fetchone()
    return row[0] if row else None


class BudgetHalt(Exception):
    """Raised when a spend cap would be breached. Carries the full context."""

    def __init__(self, session_id: str, reason: str, spent: float, cap: float,
                 cap_kind: str = "run") -> None:
        super().__init__(reason)
        self.session_id = session_id
        self.reason = reason
        self.spent_usd = _round6(spent)
        self.cap_usd = _round6(cap)
        self.cap_kind = cap_kind


class SafetyLockHalt(BudgetHalt):
    """An active spend safety lock (bound_exceeded / pricing_failure)
    refused the dispatch. Resolution: scripts/spend_admin.py (audited)."""


class ScopeHaltedHalt(BudgetHalt):
    """The spend scope is HALTED (sticky) and never reopens automatically."""


class LedgerIntegrityError(RuntimeError):
    """The reservation ledger and ai_calls disagree — refuse to continue."""


def _ledger_conn(db: Database) -> sqlite3.Connection:
    """Dedicated serialized-write connection for ledger transactions.

    The shared SQLAlchemy engine is AUTOCOMMIT (per-statement); reservations
    need multi-statement atomicity under SQLite's write lock, so they use
    their own raw connection with manual BEGIN IMMEDIATE.
    """
    conn = sqlite3.connect(str(db.path), isolation_level=None)
    conn.execute(f"PRAGMA busy_timeout={LEDGER_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _ledger(db: Database) -> "Iterator[sqlite3.Connection]":
    """Ledger connection that is ALWAYS closed (sqlite3's own context
    manager commits but never closes — that would leak a connection per
    read). Closing with an open transaction rolls it back."""
    conn = _ledger_conn(db)
    try:
        yield conn
    finally:
        conn.close()


def _day_spent_micro(conn: sqlite3.Connection, day: str) -> int:
    """Global UTC-day spend: settled truth from ai_calls (Decimal per row,
    half-up — covers all pre-PR-2 history) PLUS every open hold at its
    bound. Settled reservations are excluded here — their money is the
    ai_calls row; error rows carry cost 0 so an uncertain hold counts once."""
    total = 0
    for (cost,) in conn.execute(
        "SELECT cost_usd FROM ai_calls "
        "WHERE substr(ts, 1, 10) = ? AND status = 'ok'", (day,)
    ):
        total += usd_to_micro(cost)
    row = conn.execute(
        "SELECT COALESCE(SUM(reserved_usd_micro), 0) FROM spend_reservations "
        "WHERE day_utc = ? AND status IN ('held', 'uncertain')", (day,)
    ).fetchone()
    # Operator-RECONCILED holds have no 'ok' ai_calls row (the call died or
    # its pricing failed); their console-verified amount lives only here.
    rec = conn.execute(
        "SELECT COALESCE(SUM(settled_usd_micro), 0) FROM spend_reservations "
        "WHERE day_utc = ? AND status = 'reconciled'", (day,)
    ).fetchone()
    return total + int(row[0]) + int(rec[0])


def _run_spent_micro(conn: sqlite3.Connection, scope_id: str) -> int:
    """Logical-run spend: this scope's settled actuals plus its open holds
    at bound. Reservation-derived, so pre-PR-2 rows (no scope) never mix in."""
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE status "
        "  WHEN 'settled' THEN settled_usd_micro "
        "  WHEN 'reconciled' THEN settled_usd_micro "
        "  WHEN 'held' THEN reserved_usd_micro "
        "  WHEN 'uncertain' THEN reserved_usd_micro "
        "  ELSE 0 END), 0) "
        "FROM spend_reservations WHERE scope_id = ?", (scope_id,)
    ).fetchone()
    return int(row[0])


class BudgetEnforcer:
    """Reservation client for one logical paid run (spend scope)."""

    def __init__(
        self,
        session_id: str,
        run_cap_usd: float,
        day_cap_usd: float,
        db: Database,
        *,
        scope_id: str | None = None,
        scope_kind: str = "adhoc",
        design_ref: str | None = None,
    ) -> None:
        if run_cap_usd <= 0 or day_cap_usd <= 0:
            raise ValueError("caps must be positive USD amounts")
        self.session_id = session_id
        self.run_cap_usd = _round6(run_cap_usd)
        self.day_cap_usd = _round6(day_cap_usd)
        self.run_cap_micro = usd_to_micro(self.run_cap_usd)
        self.day_cap_micro = usd_to_micro(self.day_cap_usd)
        self.scope_id = scope_id or session_id
        self.scope_kind = scope_kind
        self.design_ref = design_ref
        self.db = db

    # -- read surfaces (display; enforcement happens inside reserve()) -------

    def spent_run_usd(self) -> float:
        with _ledger(self.db) as conn:
            return micro_to_usd(_run_spent_micro(conn, self.scope_id))

    def spent_today_usd(self) -> float:
        day = datetime.now(timezone.utc).date().isoformat()
        with _ledger(self.db) as conn:
            return micro_to_usd(_day_spent_micro(conn, day))

    # -- the reservation --------------------------------------------------------

    def reserve(
        self,
        bound_usd_micro: int,
        *,
        provider: str,
        model: str,
        kind: str,
        attempt_no: int,
    ) -> str:
        """Atomically take a hold of ``bound_usd_micro`` against BOTH caps.

        One BEGIN IMMEDIATE transaction: scope check/create, safety-lock
        check, both cap sums, and the hold insert — or, on refusal, the
        budget_events + jobs evidence rows — commit together. Raises
        BudgetHalt (or a subclass) after the evidence is durably committed.
        """
        if bound_usd_micro <= 0:
            raise ValueError("reservation bound must be positive")
        if attempt_no < 1:
            raise ValueError("attempt_no starts at 1")
        now = _utc_now_iso()
        day = now[:10]
        conn = _ledger_conn(self.db)
        try:
            conn.execute("BEGIN IMMEDIATE")
            # The sessions FK parent exists BEFORE the reservation row —
            # inside this same transaction (Amendment 5), so no caller
            # ordering can break it.
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, started_at, ended_at, "
                "status, total_cost_usd) VALUES (?, ?, NULL, 'active', 0)",
                (self.session_id, now),
            )
            self._ensure_scope_locked(conn, now)

            lock = conn.execute(
                "SELECT id, provider, model, reason FROM spend_safety_locks "
                "WHERE status = 'active' AND (provider IS NULL OR "
                "(provider = ? AND (model IS NULL OR model = ?))) "
                "ORDER BY created_at LIMIT 1", (provider, model)
            ).fetchone()
            if lock is not None:
                scope_label = lock[1] or "GLOBAL"
                self._refuse(
                    conn, now, exc_cls=SafetyLockHalt, cap_kind="safety_lock",
                    spent_micro=0, cap_micro=0,
                    reason=(
                        f"spend safety lock {lock[0]} is ACTIVE "
                        f"({scope_label}/{lock[2] or 'all models'}: {lock[3]}) "
                        "— paid dispatch refused until the operator resolves "
                        "it: python scripts/spend_admin.py resolve-lock "
                        f"{lock[0]} --reason \"...\""
                    ),
                    extra={"lock_id": lock[0], "lock_reason": lock[3]},
                )

            day_spent = _day_spent_micro(conn, day)
            if day_spent + bound_usd_micro > self.day_cap_micro:
                self._refuse(
                    conn, now, exc_cls=BudgetHalt, cap_kind="day",
                    spent_micro=day_spent, cap_micro=self.day_cap_micro,
                    reason=(
                        f"day spend cap would be breached: spent "
                        f"${micro_to_usd(day_spent):.6f} + reserved bound "
                        f"${micro_to_usd(bound_usd_micro):.6f} > day cap "
                        f"${self.day_cap_usd:.6f} — halting, state persisted "
                        "(halt_and_report)"
                    ),
                    extra={"attempted_bound_usd": micro_to_usd(bound_usd_micro)},
                )

            run_spent = _run_spent_micro(conn, self.scope_id)
            if run_spent + bound_usd_micro > self.run_cap_micro:
                self._refuse(
                    conn, now, exc_cls=BudgetHalt, cap_kind="run",
                    spent_micro=run_spent, cap_micro=self.run_cap_micro,
                    reason=(
                        f"run spend cap would be breached: scope "
                        f"{self.scope_id} spent ${micro_to_usd(run_spent):.6f} "
                        f"+ reserved bound ${micro_to_usd(bound_usd_micro):.6f}"
                        f" > run cap ${self.run_cap_usd:.6f} — halting, state "
                        "persisted (halt_and_report)"
                    ),
                    extra={"attempted_bound_usd": micro_to_usd(bound_usd_micro)},
                )

            reservation_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO spend_reservations (id, created_at, day_utc, "
                "scope_id, session_id, attempt_no, provider, model, kind, "
                "reserved_usd_micro, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'held')",
                (reservation_id, now, day, self.scope_id, self.session_id,
                 attempt_no, provider, model, kind, bound_usd_micro),
            )
            conn.execute("COMMIT")
            return reservation_id
        except BaseException:
            self._rollback_quietly(conn)
            raise
        finally:
            conn.close()

    # -- settlement (one transaction: ai_calls + reservation + sessions) -----

    def settle_success(
        self,
        reservation_id: str,
        *,
        ts: str,
        provider: str,
        model: str,
        purpose: str,
        prompt: str,
        response: str,
        tokens_in: int,
        tokens_out: int,
        cached_input_tokens: int,
        cache_write_input_tokens: int,
        latency_ms: float,
        cost_usd: float,
        pricing_version: str,
    ) -> str:
        """Insert the ai_calls row, settle the hold, reconcile the sessions
        ledger — atomically. If the actual cost exceeded the reserved bound
        (a bound-derivation defect), the same transaction records the
        bound_exceeded event, engages a provider/model safety lock and
        halts the scope (fail closed). Returns the ai_calls id."""
        cost = _round6(cost_usd)
        cost_micro = usd_to_micro(cost)
        now = _utc_now_iso()
        call_id = str(uuid.uuid4())
        conn = _ledger_conn(self.db)
        try:
            conn.execute("BEGIN IMMEDIATE")
            res = conn.execute(
                "SELECT status, reserved_usd_micro, scope_id "
                "FROM spend_reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
            if res is None or res[0] != "held":
                raise LedgerIntegrityError(
                    f"settle_success on reservation {reservation_id} in state "
                    f"{res[0] if res else 'MISSING'} — refusing to settle"
                )
            reserved_micro, scope_id = int(res[1]), res[2]
            self._insert_call_locked(
                conn, call_id=call_id, reservation_id=reservation_id,
                ts=ts, provider=provider, model=model, purpose=purpose,
                prompt=prompt, response=response, tokens_in=tokens_in,
                tokens_out=tokens_out,
                cached_input_tokens=cached_input_tokens,
                cache_write_input_tokens=cache_write_input_tokens,
                latency_ms=latency_ms, cost_usd=cost,
                pricing_version=pricing_version, status="ok", error=None,
            )
            cur = conn.execute(
                "UPDATE spend_reservations SET status='settled', "
                "settled_usd_micro=?, settled_at=?, ai_call_id=? "
                "WHERE id=? AND status='held'",
                (cost_micro, now, call_id, reservation_id),
            )
            if cur.rowcount != 1:
                raise LedgerIntegrityError(
                    f"reservation {reservation_id} left 'held' mid-settle"
                )
            self._assert_one_to_one_locked(conn, reservation_id, call_id)
            self._fold_into_session_locked(conn, cost)
            if cost_micro > reserved_micro:
                self._engage_lock_locked(
                    conn, now, provider=provider, model=model,
                    reason="bound_exceeded", scope_id=scope_id,
                    detail={
                        "reservation_id": reservation_id,
                        "ai_call_id": call_id,
                        "reserved_usd": micro_to_usd(reserved_micro),
                        "actual_usd": cost,
                    },
                )
            conn.execute("COMMIT")
            if cost_micro > reserved_micro:
                log.error(
                    "SPEND BOUND EXCEEDED: %s/%s actual $%.6f > reserved "
                    "$%.6f — safety lock engaged, scope %s halted",
                    provider, model, cost, micro_to_usd(reserved_micro),
                    scope_id,
                )
            return call_id
        except BaseException:
            self._rollback_quietly(conn)
            raise
        finally:
            conn.close()

    def record_failed_attempt(
        self,
        reservation_id: str,
        *,
        ts: str,
        provider: str,
        model: str,
        purpose: str,
        prompt: str,
        response: str,
        tokens_in: int,
        tokens_out: int,
        cached_input_tokens: int,
        cache_write_input_tokens: int,
        latency_ms: float,
        pricing_version: str,
        error: str,
        pricing_failure: bool = False,
    ) -> str:
        """One failed physical attempt: error ai_calls row + the hold goes
        ``uncertain`` (counted at full bound — fail closed; no first-party
        doc proves any error class non-billing). A pricing failure after a
        billed call additionally engages the provider/model safety lock and
        halts the scope, in the same transaction."""
        now = _utc_now_iso()
        call_id = str(uuid.uuid4())
        note = (
            "pricing failure after a billed call — counted at full reserved "
            "bound until operator reconciliation"
            if pricing_failure else
            "attempt failed; provider may have billed it (no first-party "
            "non-billing proof) — counted at full reserved bound"
        )
        conn = _ledger_conn(self.db)
        try:
            conn.execute("BEGIN IMMEDIATE")
            res = conn.execute(
                "SELECT status, reserved_usd_micro, scope_id "
                "FROM spend_reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
            if res is None or res[0] != "held":
                raise LedgerIntegrityError(
                    f"record_failed_attempt on reservation {reservation_id} "
                    f"in state {res[0] if res else 'MISSING'}"
                )
            scope_id = res[2]
            self._insert_call_locked(
                conn, call_id=call_id, reservation_id=reservation_id,
                ts=ts, provider=provider, model=model, purpose=purpose,
                prompt=prompt, response=response, tokens_in=tokens_in,
                tokens_out=tokens_out,
                cached_input_tokens=cached_input_tokens,
                cache_write_input_tokens=cache_write_input_tokens,
                latency_ms=latency_ms, cost_usd=0.0,
                pricing_version=pricing_version, status="error", error=error,
            )
            cur = conn.execute(
                "UPDATE spend_reservations SET status='uncertain', "
                "settled_at=?, ai_call_id=?, note=? "
                "WHERE id=? AND status='held'",
                (now, call_id, note, reservation_id),
            )
            if cur.rowcount != 1:
                raise LedgerIntegrityError(
                    f"reservation {reservation_id} left 'held' mid-record"
                )
            self._assert_one_to_one_locked(conn, reservation_id, call_id)
            if pricing_failure:
                self._engage_lock_locked(
                    conn, now, provider=provider, model=model,
                    reason="pricing_failure", scope_id=scope_id,
                    detail={"reservation_id": reservation_id,
                            "ai_call_id": call_id, "error": error},
                )
            conn.execute("COMMIT")
            return call_id
        except BaseException:
            self._rollback_quietly(conn)
            raise
        finally:
            conn.close()

    def close_scope(self) -> None:
        """Mark the scope closed at the natural end of its run. A HALTED
        scope stays halted (sticky) — only spend_admin resolution moves it."""
        with _ledger(self.db) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE spend_scopes SET status='closed', closed_at=? "
                "WHERE id=? AND status='open'",
                (_utc_now_iso(), self.scope_id),
            )
            conn.execute("COMMIT")

    # -- internals ------------------------------------------------------------

    def _ensure_scope_locked(self, conn: sqlite3.Connection, now: str) -> None:
        row = conn.execute(
            "SELECT status, note FROM spend_scopes WHERE id=?",
            (self.scope_id,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO spend_scopes (id, kind, created_at, status, "
                "design_ref) VALUES (?, ?, ?, 'open', ?)",
                (self.scope_id, self.scope_kind, now, self.design_ref),
            )
            return
        status = row[0]
        if status == "halted":
            self._refuse(
                conn, now, exc_cls=ScopeHaltedHalt, cap_kind="scope_halted",
                spent_micro=0, cap_micro=0,
                reason=(
                    f"spend scope {self.scope_id} is HALTED "
                    f"({row[1] or 'no note'}) and never reopens "
                    "automatically — resolve it deliberately: python "
                    f"scripts/spend_admin.py resolve-scope {self.scope_id} "
                    "--reason \"...\""
                ),
                extra={"scope_id": self.scope_id},
            )
        if status == "closed":
            note = f"reopened {now} by a new dispatch in the same logical run"
            conn.execute(
                "UPDATE spend_scopes SET status='open', closed_at=NULL, "
                "note=COALESCE(note || ' | ', '') || ? WHERE id=?",
                (note, self.scope_id),
            )

    def _refuse(
        self,
        conn: sqlite3.Connection,
        now: str,
        *,
        exc_cls: type[BudgetHalt],
        cap_kind: str,
        spent_micro: int,
        cap_micro: int,
        reason: str,
        extra: dict,
    ) -> None:
        """Persist the refusal evidence INSIDE the refusing transaction
        (budget_events + jobs, exactly the ADR-003 records), COMMIT, raise."""
        event_type = {
            "day": "cap_breach", "run": "cap_breach",
            "safety_lock": "safety_lock_refusal",
            "scope_halted": "scope_halted_refusal",
        }[cap_kind]
        spent = micro_to_usd(spent_micro)
        cap = micro_to_usd(cap_micro)
        detail = json.dumps(
            {"cap_kind": cap_kind, "spent_usd": spent, "cap_usd": cap,
             "scope_id": self.scope_id, **extra},
            sort_keys=True,
        )
        state = json.dumps(
            {"session_id": self.session_id, "scope_id": self.scope_id,
             "halted_at": now, "cap_kind": cap_kind, "spent_usd": spent,
             "cap_usd": cap, "run_cap_usd": self.run_cap_usd,
             "day_cap_usd": self.day_cap_usd, **extra},
            sort_keys=True,
        )
        conn.execute(
            "INSERT INTO budget_events (id, session_id, ts, event_type, "
            "detail) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), self.session_id, now, event_type, detail),
        )
        conn.execute(
            "INSERT INTO jobs (id, session_id, ts, job_type, status, "
            "state_json, halt_reason) VALUES (?, ?, ?, 'ai_dispatch', "
            "'halted_budget', ?, ?)",
            (str(uuid.uuid4()), self.session_id, now, state, reason),
        )
        conn.execute("COMMIT")
        raise exc_cls(self.session_id, reason, spent, cap, cap_kind=cap_kind)

    def _insert_call_locked(self, conn: sqlite3.Connection, **f) -> None:
        conn.execute(
            "INSERT INTO ai_calls (id, session_id, ts, provider, model, "
            "purpose, prompt, response, tokens_in, tokens_out, "
            "cached_input_tokens, cache_write_input_tokens, latency_ms, "
            "cost_usd, pricing_version, status, error, reservation_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f["call_id"], self.session_id, f["ts"], f["provider"],
             f["model"], f["purpose"], f["prompt"], f["response"],
             f["tokens_in"], f["tokens_out"], f["cached_input_tokens"],
             f["cache_write_input_tokens"], f["latency_ms"], f["cost_usd"],
             f["pricing_version"], f["status"], f["error"],
             f["reservation_id"]),
        )

    @staticmethod
    def _assert_one_to_one_locked(
        conn: sqlite3.Connection, reservation_id: str, call_id: str
    ) -> None:
        """Amendment 6: both directions of the 1:1 link, asserted in-txn
        (the unique partial indexes are the schema-level guarantee; this is
        the loud in-band check)."""
        n_calls = conn.execute(
            "SELECT COUNT(*) FROM ai_calls WHERE reservation_id=?",
            (reservation_id,),
        ).fetchone()[0]
        n_res = conn.execute(
            "SELECT COUNT(*) FROM spend_reservations WHERE ai_call_id=?",
            (call_id,),
        ).fetchone()[0]
        if n_calls != 1 or n_res != 1:
            raise LedgerIntegrityError(
                f"reservation/ai_call link is not 1:1 (reservation "
                f"{reservation_id}: {n_calls} calls; call {call_id}: "
                f"{n_res} reservations)"
            )

    def _fold_into_session_locked(
        self, conn: sqlite3.Connection, cost: float
    ) -> None:
        row = conn.execute(
            "SELECT total_cost_usd FROM sessions WHERE id=?",
            (self.session_id,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO sessions (id, started_at, ended_at, status, "
                "total_cost_usd) VALUES (?, ?, NULL, 'active', ?)",
                (self.session_id, _utc_now_iso(), cost),
            )
        else:
            conn.execute(
                "UPDATE sessions SET total_cost_usd=? WHERE id=?",
                (_round6(float(row[0]) + cost), self.session_id),
            )

    def _engage_lock_locked(
        self,
        conn: sqlite3.Connection,
        now: str,
        *,
        provider: str,
        model: str,
        reason: str,
        scope_id: str,
        detail: dict,
    ) -> None:
        """Persist an active provider/model safety lock + halt the scope +
        the budget_events record — callers hold the transaction."""
        lock_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO spend_safety_locks (id, created_at, provider, "
            "model, reason, detail, status) VALUES (?, ?, ?, ?, ?, ?, "
            "'active')",
            (lock_id, now, provider, model, reason,
             json.dumps(detail, sort_keys=True)),
        )
        conn.execute(
            "UPDATE spend_scopes SET status='halted', "
            "note=COALESCE(note || ' | ', '') || ? WHERE id=?",
            (f"halted {now}: {reason} (lock {lock_id})", scope_id),
        )
        conn.execute(
            "INSERT INTO budget_events (id, session_id, ts, event_type, "
            "detail) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), self.session_id, now, reason,
             json.dumps({**detail, "lock_id": lock_id, "scope_id": scope_id},
                        sort_keys=True)),
        )

    @staticmethod
    def _rollback_quietly(conn: sqlite3.Connection) -> None:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass


# ---------------------------------------------------------------------------
# Startup recovery + reconciliation + audited operator resolution
# ---------------------------------------------------------------------------


def recover_stale_spend_holds(db: Database) -> list[str]:
    """Classify every leftover 'held' reservation honestly at startup.

    Settlement is atomic with the ai_calls insert, so a surviving 'held'
    row means the process died between dispatch and settlement: the
    provider may have billed it and no usage exists. Exact-id correlation
    only (Amendment: never timestamp matching) — and by construction no
    ai_calls row can carry a still-held reservation's id, which the
    reconciliation below also asserts. Each hold becomes 'uncertain',
    stays counted at its full bound, and is never deleted."""
    recovered: list[str] = []
    now = _utc_now_iso()
    with _ledger(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id, provider, model, reserved_usd_micro "
            "FROM spend_reservations WHERE status='held'"
        ).fetchall()
        for rid, provider, model, bound in rows:
            linked = conn.execute(
                "SELECT id FROM ai_calls WHERE reservation_id=?", (rid,)
            ).fetchone()
            note = (
                "startup recovery: process died between dispatch and "
                "settlement; provider may have billed — counted at full "
                f"bound ${micro_to_usd(int(bound)):.6f}"
            )
            conn.execute(
                "UPDATE spend_reservations SET status='uncertain', "
                "settled_at=?, ai_call_id=COALESCE(ai_call_id, ?), note=? "
                "WHERE id=? AND status='held'",
                (now, linked[0] if linked else None, note, rid),
            )
            recovered.append(rid)
            log.warning(
                "spend recovery: hold %s (%s/%s) classified UNCERTAIN — %s",
                rid, provider, model, note,
            )
        conn.execute("COMMIT")
    return recovered


def reconcile_spend_books(db: Database) -> list[str]:
    """Assert the two books agree (Amendment 6, both directions). Any
    mismatch engages a GLOBAL safety lock — fail closed — and is returned."""
    problems: list[str] = []
    with _ledger(db) as conn:
        for rid, call_id, settled in conn.execute(
            "SELECT id, ai_call_id, settled_usd_micro FROM "
            "spend_reservations WHERE status='settled'"
        ).fetchall():
            row = conn.execute(
                "SELECT cost_usd, reservation_id FROM ai_calls WHERE id=?",
                (call_id,),
            ).fetchone() if call_id else None
            if row is None:
                problems.append(f"settled reservation {rid} has no ai_call")
            elif row[1] != rid:
                problems.append(
                    f"reservation {rid} -> call {call_id} backref is {row[1]}"
                )
            elif usd_to_micro(row[0]) != int(settled):
                problems.append(
                    f"reservation {rid} settled {settled}µ != ai_call cost "
                    f"{usd_to_micro(row[0])}µ"
                )
        # Non-overlap guarantee of the two spend books: a reconciled orphan
        # may link to an 'error' ai_calls row (cost 0), never to an 'ok'
        # one — that would count the same money twice.
        for rid, call_id in conn.execute(
            "SELECT id, ai_call_id FROM spend_reservations "
            "WHERE status='reconciled' AND ai_call_id IS NOT NULL"
        ).fetchall():
            row = conn.execute(
                "SELECT status FROM ai_calls WHERE id=?", (call_id,)
            ).fetchone()
            if row is not None and row[0] == "ok":
                problems.append(
                    f"reconciled hold {rid} links to 'ok' ai_call {call_id} "
                    "— double count"
                )
        for call_id, rid in conn.execute(
            "SELECT id, reservation_id FROM ai_calls "
            "WHERE reservation_id IS NOT NULL"
        ).fetchall():
            row = conn.execute(
                "SELECT ai_call_id, status FROM spend_reservations WHERE id=?",
                (rid,),
            ).fetchone()
            if row is None:
                problems.append(f"ai_call {call_id} cites missing hold {rid}")
            elif row[1] in ("settled", "uncertain") and row[0] != call_id:
                problems.append(
                    f"hold {rid} points at {row[0]}, not ai_call {call_id}"
                )
        if problems:
            now = _utc_now_iso()
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO spend_safety_locks (id, created_at, provider, "
                "model, reason, detail, status) VALUES (?, ?, NULL, NULL, "
                "'ledger_mismatch', ?, 'active')",
                (str(uuid.uuid4()), now,
                 json.dumps({"problems": problems}, sort_keys=True)),
            )
            conn.execute("COMMIT")
            for p in problems:
                log.error("spend ledger mismatch: %s", p)
    return problems


def _audited_resolution(db: Database, *, event_type: str, detail: dict) -> None:
    with _ledger(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO budget_events (id, session_id, ts, event_type, "
            "detail) VALUES (?, '__spend_admin__', ?, ?, ?)",
            (str(uuid.uuid4()), _utc_now_iso(), event_type,
             json.dumps(detail, sort_keys=True)),
        )
        conn.execute("COMMIT")


def resolve_safety_lock(db: Database, lock_id: str, reason: str) -> None:
    """Explicit audited operator resolution of one safety lock."""
    if not reason.strip():
        raise ValueError("a resolution reason is required")
    now = _utc_now_iso()
    with _ledger(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE spend_safety_locks SET status='resolved', resolved_at=?, "
            "resolution_note=? WHERE id=? AND status='active'",
            (now, reason.strip(), lock_id),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            raise ValueError(f"no ACTIVE safety lock with id {lock_id}")
        conn.execute("COMMIT")
    _audited_resolution(db, event_type="safety_lock_resolved",
                        detail={"lock_id": lock_id, "reason": reason.strip()})


def resolve_halted_scope(db: Database, scope_id: str, reason: str) -> None:
    """Explicit audited resolution: a halted scope becomes CLOSED (a later
    legitimate dispatch in the same logical run may reopen closed — never
    halted)."""
    if not reason.strip():
        raise ValueError("a resolution reason is required")
    now = _utc_now_iso()
    with _ledger(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE spend_scopes SET status='closed', closed_at=?, "
            "note=COALESCE(note || ' | ', '') || ? "
            "WHERE id=? AND status='halted'",
            (now, f"operator resolution {now}: {reason.strip()}", scope_id),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            raise ValueError(f"no HALTED spend scope with id {scope_id}")
        conn.execute("COMMIT")
    _audited_resolution(db, event_type="scope_halt_resolved",
                        detail={"scope_id": scope_id, "reason": reason.strip()})


def resolve_uncertain_hold(
    db: Database, reservation_id: str, actual_usd: float, reason: str
) -> None:
    """Explicit audited reconciliation of one UNCERTAIN hold to the amount
    the operator verified in the provider console (0.0 = confirmed not
    billed). The row becomes 'reconciled' — its own status, because it has
    no 'ok' ai_calls row to reconcile against: both cap sums count it at
    the verified amount, and the two-book assertion exempts it. Never
    deleted; the audit trail keeps both the bound and the verified amount."""
    if not reason.strip():
        raise ValueError("a resolution reason is required")
    if actual_usd < 0:
        raise ValueError("actual_usd cannot be negative")
    now = _utc_now_iso()
    actual_micro = usd_to_micro(_round6(actual_usd))
    with _ledger(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE spend_reservations SET status='reconciled', "
            "settled_usd_micro=?, settled_at=?, "
            "note=COALESCE(note || ' | ', '') || ? "
            "WHERE id=? AND status='uncertain'",
            (actual_micro, now,
             f"operator reconciliation {now}: verified "
             f"${_round6(actual_usd):.6f} — {reason.strip()}",
             reservation_id),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            raise ValueError(
                f"no UNCERTAIN reservation with id {reservation_id}"
            )
        conn.execute("COMMIT")
    _audited_resolution(
        db, event_type="hold_reconciled",
        detail={"reservation_id": reservation_id,
                "actual_usd": _round6(actual_usd), "reason": reason.strip()},
    )
