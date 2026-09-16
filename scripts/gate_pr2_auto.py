"""gate_pr2_auto.py — PR-2 (ADR-061): atomic hard spend caps. $0, offline.

Run in the backend container:

    docker compose exec backend python scripts/gate_pr2_auto.py

Sections:
  [1] config + bound derivation — run_cap_usd renamed; every model carries a
      first-party context window with a dated source; the reservation bounds
      are exact integer micro-USD and dominate the retired chars/4 estimate
  [2] barrier race (threads) — two reservers, one slot, exactly one passes
  [3] cross-process contention — two processes hammer one DB file; the
      ledger never jointly exceeds the cap
  [4] the attempt matrix through the REAL dispatch path (injected SDK
      transports — scripted shapes, no network): settle 1:1 both ways,
      per-attempt retry reservations, exhaustion all-uncertain, pricing
      failure and bound-exceeded engage safety locks + halt the scope,
      cap refusals commit their evidence atomically
  [5] recovery + reconciliation — dead holds classified uncertain by exact
      id, never deleted; a tampered book engages a GLOBAL lock; audited
      resolutions demand a reason
  [6] spend-scope identity — full uuid5, fabrication accumulation across
      close/reopen, critique open-reuse/closed-new, intake stability
  [7] the operator surface — /api/logs/budget reports run_cap_usd, open
      holds and active locks; no code path still says session_cap_usd

No network, no AI call, no AI-written code. Everything runs on throwaway
temp databases.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

failures: list[str] = []


def _check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f" :: {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def _section(n: int, title: str) -> None:
    print(f"\n[{n}] {title}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tmp_db():
    from app.db.database import Database

    d = Path(tempfile.mkdtemp(prefix="gate_pr2_"))
    db = Database(d / "gate.db")
    db.init_db()
    return db


class _Transport:
    """Scripted openai-shaped SDK client (the conftest transport pattern):
    a canned response or a scripted exception per call. $0, no network."""

    def __init__(self, text: str, tokens_in: int, tokens_out: int,
                 cached_tokens: int = 0, fail_first: int = 0) -> None:
        self.calls: list[dict] = []
        self._fail_first = fail_first
        self._response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(
                prompt_tokens=tokens_in, completion_tokens=tokens_out,
                total_tokens=tokens_in + tokens_out,
                cached_tokens=cached_tokens,
                prompt_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
                completion_tokens_details=SimpleNamespace(),
            ),
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self._fail_first:
            raise TimeoutError("gate: simulated network timeout")
        return self._response


_CHILD_SOURCE = r"""
import sys
sys.path.insert(0, sys.argv[1])
from app.core.budget import BudgetEnforcer, BudgetHalt, usd_to_micro
from app.db.database import Database

db = Database(sys.argv[2])
enforcer = BudgetEnforcer(f"proc-{sys.argv[3]}", 100.0, 0.005, db,
                          scope_id=f"scope-{sys.argv[3]}")
successes = 0
for i in range(8):
    try:
        enforcer.reserve(usd_to_micro(0.001), provider="openai",
                         model="gpt-4o", kind="text", attempt_no=i + 1)
        successes += 1
    except BudgetHalt:
        pass
print(successes)
"""


def main() -> int:
    import os

    os.environ.setdefault("LUXURYFORM_PROVIDER_BACKOFF_BASE_S", "0")

    from app.ai.call_log import reserve_bound_usd_micro
    from app.ai.provider import ProviderError
    from app.ai.providers.openai_provider import OpenAIProvider
    from app.core.budget import (
        BudgetEnforcer, BudgetHalt, SafetyLockHalt, ScopeHaltedHalt,
        fabrication_scope_id, intake_scope_id, latest_open_scope,
        micro_to_usd, recover_stale_spend_holds, reconcile_spend_books,
        resolve_safety_lock, resolve_uncertain_hold, usd_to_micro,
    )
    from app.core.config import load_config_bundle

    bundle = load_config_bundle()
    pricing = bundle.pricing

    # ------------------------------------------------------------------
    _section(1, "config + the cap-safe bound derivation")
    caps = bundle.budget
    _check("budget.yaml carries run_cap_usd (renamed by operator ruling)",
           hasattr(caps, "run_cap_usd") and caps.run_cap_usd > 0,
           f"run ${caps.run_cap_usd:.2f} / day ${caps.day_cap_usd:.2f}")
    _check("pricing_version bumped for the context windows",
           pricing.pricing_version == "2026-08-v4", pricing.pricing_version)
    # D-28 (ADR-070): these three values are now the context-window CEILING
    # the envelope bound can never exceed (gate_d28_auto.py proves the
    # envelope bound itself); the ceiling stays exact and first-party.
    expected = {
        ("anthropic", "claude-sonnet-4-5", 8192): 872_880,
        ("openai", "gpt-4o", 8192): 401_920,
        ("kimi", "kimi-k3", 8192): 3_268_608,
    }
    for (prov, model, mt), want in expected.items():
        entry = pricing.price_for(prov, model)
        _check(f"{prov}/{model} context window is first-party + dated",
               entry.context_window_tokens is not None
               and entry.context_window_source is not None
               and "2026-08-28" in (entry.context_window_source or ""),
               f"{entry.context_window_tokens} tokens :: {entry.context_window_source}")
        got = reserve_bound_usd_micro(pricing, prov, model, mt)
        _check(f"{prov}/{model} CEILING at max_tokens={mt} is exact",
               got == want, f"${micro_to_usd(got):.6f} == ${micro_to_usd(want):.6f}")
    dense = "警告" * 4000
    old_est = ((len(dense) // 4 + 1) * 2.50 + 256 * 10.0) / 1_000_000
    new_bound = micro_to_usd(reserve_bound_usd_micro(pricing, "openai", "gpt-4o", 256))
    _check("the ceiling dominates the retired chars/4 estimate on dense text",
           new_bound > old_est, f"ceiling ${new_bound:.6f} > old ${old_est:.6f}")

    # ------------------------------------------------------------------
    _section(2, "barrier race — two reservers, one slot")
    db = _tmp_db()
    bound = usd_to_micro(2.0)
    barrier = threading.Barrier(2)
    ids: list[str] = []
    halts: list[BudgetHalt] = []

    def contend() -> None:
        e = BudgetEnforcer("race", 3.0, 25.0, db, scope_id="race-scope")
        barrier.wait(timeout=10)
        try:
            ids.append(e.reserve(bound, provider="openai", model="gpt-4o",
                                 kind="text", attempt_no=1))
        except BudgetHalt as h:
            halts.append(h)

    threads = [threading.Thread(target=contend) for _ in range(2)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    _check("exactly one of two simultaneous reservers passed",
           len(ids) == 1 and len(halts) == 1,
           f"holds={len(ids)} halts={len(halts)} "
           f"(cap $3.00, bound $2.00 each — only one fits)")
    with sqlite3.connect(str(db.path)) as conn:
        n_events = conn.execute(
            "SELECT COUNT(*) FROM budget_events WHERE event_type='cap_breach'"
        ).fetchone()[0]
        n_jobs = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='halted_budget'"
        ).fetchone()[0]
    _check("the refusal committed its evidence atomically",
           n_events == 1 and n_jobs == 1,
           f"budget_events={n_events} jobs(halted_budget)={n_jobs}")

    # ------------------------------------------------------------------
    _section(3, "cross-process contention on one database file")
    db3 = _tmp_db()
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _CHILD_SOURCE, str(REPO_ROOT / "backend"),
             str(db3.path), name],
            stdout=subprocess.PIPE, text=True,
        )
        for name in ("a", "b")
    ]
    child_successes = []
    for p in procs:
        out, _ = p.communicate(timeout=120)
        child_successes.append(int(out.strip().splitlines()[-1]))
    with sqlite3.connect(str(db3.path)) as conn:
        total_held = conn.execute(
            "SELECT COALESCE(SUM(reserved_usd_micro),0) FROM "
            "spend_reservations WHERE status='held'").fetchone()[0]
    _check("two processes x 8 x $0.001 against a $0.005 day cap: exactly 5 "
           "holds landed",
           sum(child_successes) == 5 and total_held == 5000,
           f"successes per child={child_successes}, "
           f"ledger total ${micro_to_usd(total_held):.6f} <= $0.005000")

    # ------------------------------------------------------------------
    _section(4, "the attempt matrix through the real dispatch path")

    def provider_for(dbx, transport, *, prices=None, scope="s-scope",
                     run_cap=5.0):
        b = BudgetEnforcer("sess-g", run_cap, 25.0, dbx, scope_id=scope)
        return OpenAIProvider(
            "gate-key", client=transport, text_model="gpt-4o",
            vision_model="gpt-4o", db=dbx, pricing=prices or pricing,
            budget=b,
        ), b

    db4 = _tmp_db()
    prov, b4 = provider_for(db4, _Transport("OK", 12, 3))
    resp = prov.complete("gate", purpose="gate_settle", session_id="sess-g")
    with sqlite3.connect(str(db4.path)) as conn:
        row = conn.execute(
            "SELECT r.status, r.settled_usd_micro, r.ai_call_id, "
            "c.reservation_id, c.id FROM spend_reservations r "
            "JOIN ai_calls c ON c.reservation_id = r.id").fetchone()
        session_total = conn.execute(
            "SELECT total_cost_usd FROM sessions WHERE id='sess-g'"
        ).fetchone()[0]
    _check("success settles atomically, 1:1 both directions, exact micro",
           row is not None and row[0] == "settled" and row[1] == 60
           and row[2] == row[4] and resp.cost_usd == 0.00006
           and session_total == 0.00006,
           f"settled 60µ == $0.000060; sessions ledger ${session_total:.6f}")

    db4b = _tmp_db()
    prov, b4b = provider_for(db4b, _Transport("OK", 12, 3, fail_first=1))
    prov.complete("gate", purpose="gate_retry", session_id="sess-g")
    with sqlite3.connect(str(db4b.path)) as conn:
        st = [r[0] for r in conn.execute(
            "SELECT status FROM spend_reservations ORDER BY attempt_no")]
        n_calls = conn.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0]
        uncertain_bound = conn.execute(
            "SELECT reserved_usd_micro FROM spend_reservations "
            "WHERE status='uncertain'").fetchone()[0]
    _check("a transient retry took a NEW reservation per physical attempt",
           st == ["uncertain", "settled"] and n_calls == 2,
           f"reservation statuses {st}; ai_calls rows {n_calls} (one per attempt)")
    # D-28 (ADR-070): the hold is the ENVELOPE bound of the request, not the
    # window ceiling; the uncertain attempt still counts at all of it.
    _check("the uncertain attempt stays counted at its full (envelope) bound",
           b4b.spent_run_usd() == micro_to_usd(int(uncertain_bound) + 60)
           and 0 < int(uncertain_bound) < reserve_bound_usd_micro(
               pricing, "openai", "gpt-4o", 256),
           f"run spend ${b4b.spent_run_usd():.6f} == uncertain bound "
           f"${micro_to_usd(int(uncertain_bound)):.6f} + $0.000060; ceiling "
           f"${micro_to_usd(reserve_bound_usd_micro(pricing, 'openai', 'gpt-4o', 256)):.6f}")

    db4c = _tmp_db()
    prov, b4c = provider_for(db4c, _Transport("never", 1, 1, fail_first=99))
    try:
        prov.complete("gate", purpose="gate_exhaust", session_id="sess-g")
        _check("exhausted attempts raise ProviderError", False)
    except ProviderError:
        with sqlite3.connect(str(db4c.path)) as conn:
            st = [r[0] for r in conn.execute(
                "SELECT status FROM spend_reservations")]
        _check("every exhausted attempt is uncertain (fail closed)",
               st == ["uncertain"] * 3, f"{st}")

    db4d = _tmp_db()
    p_broken = pricing.model_copy(deep=True)
    p_broken.providers["openai"]["gpt-4o"] = p_broken.providers["openai"][
        "gpt-4o"].model_copy(update={"context_window_tokens": 1})
    prov, b4d = provider_for(db4d, _Transport("BIG", 100, 50),
                             prices=p_broken, scope="bx")
    prov.complete("gate", purpose="gate_bx", session_id="sess-g", max_tokens=1)
    with sqlite3.connect(str(db4d.path)) as conn:
        lock = conn.execute(
            "SELECT reason, status FROM spend_safety_locks").fetchone()
        scope_status = conn.execute(
            "SELECT status FROM spend_scopes WHERE id='bx'").fetchone()[0]
        res = conn.execute(
            "SELECT settled_usd_micro, reserved_usd_micro FROM "
            "spend_reservations").fetchone()
    _check("actual > reserved: settled at truth, lock engaged, scope halted",
           lock == ("bound_exceeded", "active") and scope_status == "halted"
           and res[0] > res[1],
           f"settled {res[0]}µ > reserved {res[1]}µ; lock {lock}; scope {scope_status}")
    try:
        BudgetEnforcer("s2", 5.0, 25.0, db4d).reserve(
            1, provider="openai", model="gpt-4o", kind="text", attempt_no=1)
        _check("the safety lock refuses the next matching dispatch", False)
    except SafetyLockHalt as h:
        _check("the safety lock refuses the next matching dispatch", True,
               h.reason[:100])

    # ------------------------------------------------------------------
    _section(5, "recovery + reconciliation (exact id, never a timestamp)")
    db5 = _tmp_db()
    ts = _now()
    with sqlite3.connect(str(db5.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s', ?, 'active', 0)", (ts,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc', 'council', ?, 'open')", (ts,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, status) VALUES ('r-dead', ?, ?, 'sc', 's', "
            "1, 'anthropic', 'claude-sonnet-4-5', 'text', 872880, 'held')",
            (ts, ts[:10]))
        conn.commit()
    recovered = recover_stale_spend_holds(db5)
    with sqlite3.connect(str(db5.path)) as conn:
        status, note = conn.execute(
            "SELECT status, note FROM spend_reservations WHERE id='r-dead'"
        ).fetchone()
        n_rows = conn.execute(
            "SELECT COUNT(*) FROM spend_reservations").fetchone()[0]
    probe = BudgetEnforcer("probe", 5.0, 25.0, db5)
    _check("a dead hold is classified uncertain, kept, and still counted",
           recovered == ["r-dead"] and status == "uncertain" and n_rows == 1
           and probe.spent_today_usd() == 0.87288,
           f"status={status}; today ${probe.spent_today_usd():.6f}; note: {note[:60]}")
    _check("clean books reconcile empty", reconcile_spend_books(db5) == [])
    try:
        resolve_uncertain_hold(db5, "r-dead", 0.0, "")
        _check("hold resolution demands a reason", False)
    except ValueError:
        _check("hold resolution demands a reason", True)
    resolve_uncertain_hold(db5, "r-dead", 0.0, "consoles checked (gate)")
    _check("an audited $0 reconciliation releases the headroom",
           probe.spent_today_usd() == 0.0)
    _check("an operator reconciliation is NOT a two-book mismatch",
           reconcile_spend_books(db5) == [],
           "no global lock after resolve-hold (defect fixed 2026-08-28)")
    with sqlite3.connect(str(db5.path)) as conn:
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, status) VALUES ('r-billed', ?, ?, 'sc', "
            "'s', 1, 'openai', 'gpt-4o', 'text', 401920, 'held')",
            (ts, ts[:10]))
        conn.commit()
    recover_stale_spend_holds(db5)
    resolve_uncertain_hold(db5, "r-billed", 0.30, "console shows $0.30 (gate)")
    _check("a nonzero reconciliation keeps counting against the day cap",
           probe.spent_today_usd() == 0.30 and reconcile_spend_books(db5) == [],
           f"today ${probe.spent_today_usd():.6f} after reconciling to $0.30")

    with sqlite3.connect(str(db5.path)) as conn:
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, settled_usd_micro, status, ai_call_id) "
            "VALUES ('r-bad', ?, ?, 'sc', 's', 1, 'openai', 'gpt-4o', "
            "'text', 100, 60, 'settled', 'no-such-call')", (ts, ts[:10]))
        conn.commit()
    problems = reconcile_spend_books(db5)
    try:
        BudgetEnforcer("s3", 5.0, 25.0, db5).reserve(
            1, provider="kimi", model="kimi-k3", kind="text", attempt_no=1)
        _check("a book mismatch engages a GLOBAL lock (fail closed)", False)
    except SafetyLockHalt:
        _check("a book mismatch engages a GLOBAL lock (fail closed)", True,
               f"problems: {problems}")

    # ------------------------------------------------------------------
    _section(6, "spend-scope identity + lifecycle")
    sid, spec = str(uuid.uuid4()), str(uuid.uuid4())
    fs = fabrication_scope_id(sid, spec)
    _check("fabrication scope is a FULL deterministic uuid5",
           fs == fabrication_scope_id(sid, spec) and len(fs) == 36
           and fs != fabrication_scope_id(sid, str(uuid.uuid4())), fs)
    s1 = "aaaaaaaa-1111-1111-1111-111111111111"
    s2 = "aaaaaaaa-2222-2222-2222-222222222222"
    _check("identities sharing an 8-char prefix cannot collide",
           fabrication_scope_id(s1, spec) != fabrication_scope_id(s2, spec))
    _check("intake scope is stable over the full intake id",
           intake_scope_id("intake-x") == intake_scope_id("intake-x")
           and intake_scope_id("intake-x") != intake_scope_id("intake-y"))

    db6 = _tmp_db()
    e1 = BudgetEnforcer("sA", 1.0, 25.0, db6, scope_id=fs,
                        scope_kind="fabrication")
    e1.reserve(usd_to_micro(0.6), provider="openai", model="gpt-4o",
               kind="text", attempt_no=1)
    e1.close_scope()
    e2 = BudgetEnforcer("sA", 1.0, 25.0, db6, scope_id=fs,
                        scope_kind="fabrication")
    try:
        e2.reserve(usd_to_micro(0.6), provider="openai", model="gpt-4o",
                   kind="text", attempt_no=1)
        _check("a re-POST reopens the SAME scope and the $ accumulates", False)
    except BudgetHalt:
        _check("a re-POST reopens the SAME scope and the $ accumulates", True,
               "$0.60 held + $0.60 requested > $1.00 run cap")

    digest = "d" * 64
    c1 = BudgetEnforcer("c1", 5.0, 25.0, db6, scope_id=str(uuid.uuid4()),
                        scope_kind="critique", design_ref=digest)
    c1.reserve(100, provider="openai", model="gpt-4o", kind="vision",
               attempt_no=1)
    _check("a restarted critique finds and resumes its OPEN scope",
           latest_open_scope(db6, "critique", digest) == c1.scope_id)
    c1.close_scope()
    _check("a closed critique scope is NOT resumed — the next run is new",
           latest_open_scope(db6, "critique", digest) is None)

    # ------------------------------------------------------------------
    _section(7, "the operator surface + the rename is total")
    import os as _os

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import routes_logs
    from app.db.database import get_default_db, reset_default_db

    tmp = Path(tempfile.mkdtemp(prefix="gate_pr2_api_")) / "api.db"
    _os.environ["LUXURYFORM_DB"] = str(tmp)
    reset_default_db()
    get_default_db().init_db()
    app = FastAPI()
    app.include_router(routes_logs.router, prefix="/api")
    with TestClient(app) as client:
        body = client.get("/api/logs/budget").json()
    reset_default_db()
    _os.environ.pop("LUXURYFORM_DB", None)
    _check("/api/logs/budget reports run_cap_usd + holds + locks",
           body["caps"].get("run_cap_usd") == caps.run_cap_usd
           and "session_cap_usd" not in body["caps"]
           and "open_holds" in body and "active_safety_locks" in body,
           json.dumps(body["caps"]))

    # The spend truth model on the operator surfaces: a $0.30 reconciled
    # orphan (dead hold, console-verified) must reach /api/ops/costs and
    # /api/logs/budget explicitly, be counted once, and leave the ordinary
    # ai_calls<->sessions reconciliation clean.
    from app.api import routes_ops

    # A FRESH throwaway file — never the default ./data/luxuryform.db.
    tmp2 = Path(tempfile.mkdtemp(prefix="gate_pr2_ops_")) / "ops.db"
    _os.environ["LUXURYFORM_DB"] = str(tmp2)
    reset_default_db()
    api_db = get_default_db()
    api_db.init_db()
    ts7 = _now()
    with sqlite3.connect(str(api_db.path)) as conn:
        conn.execute("INSERT INTO sessions (id, started_at, status, "
                     "total_cost_usd) VALUES ('s7', ?, 'active', 0)", (ts7,))
        conn.execute("INSERT INTO spend_scopes (id, kind, created_at, "
                     "status) VALUES ('sc7', 'council', ?, 'open')", (ts7,))
        conn.execute(
            "INSERT INTO spend_reservations (id, created_at, day_utc, "
            "scope_id, session_id, attempt_no, provider, model, kind, "
            "reserved_usd_micro, status) VALUES ('r-orphan', ?, ?, 'sc7', "
            "'s7', 1, 'openai', 'gpt-4o', 'text', 401920, 'held')",
            (ts7, ts7[:10]))
        conn.commit()
    recover_stale_spend_holds(api_db)
    resolve_uncertain_hold(api_db, "r-orphan", 0.30, "console shows $0.30 (gate)")
    app2 = FastAPI()
    app2.include_router(routes_ops.router, prefix="/api")
    app2.include_router(routes_logs.router, prefix="/api")
    with TestClient(app2) as client:
        costs = client.get("/api/ops/costs").json()
        page = client.get("/api/logs/budget").json()
    reset_default_db()
    _os.environ.pop("LUXURYFORM_DB", None)
    rec = costs.get("reconciled_unmatched_spend", {})
    _check("a $0.30 reconciled orphan is in the Operations total, explicitly",
           costs.get("total_usd") == 0.3 and costs.get("ai_calls_usd") == 0
           and costs.get("reconciled_usd") == 0.3 and rec.get("count") == 1
           and rec["rows"][0]["reservation_id"] == "r-orphan"
           and rec["rows"][0]["ai_call_id"] is None
           and costs["reconciliation"]["clean"] is True,
           f"total ${costs.get('total_usd')} = ai_calls ${costs.get('ai_calls_usd')}"
           f" + reconciled ${costs.get('reconciled_usd')}; reconciliation clean")
    _check("the budget page lists it and counts it for today's cap",
           [r["reservation_id"] for r in page.get("reconciled_unmatched_spend", [])]
           == ["r-orphan"] and page.get("spent_today_usd") == 0.3,
           f"spent_today ${page.get('spent_today_usd')}")

    stale: list[str] = []
    for py in sorted((REPO_ROOT / "backend" / "app").rglob("*.py")):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if "session_cap_usd" in code:
                stale.append(f"{py.relative_to(REPO_ROOT)}:{i}")
    _check("no backend code line still uses session_cap_usd",
           stale == [], ", ".join(stale) or "clean")

    # ------------------------------------------------------------------
    print()
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — PR-2 auto gate: all sections passed at $0, no network, "
          "no AI call, no AI-written code executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
