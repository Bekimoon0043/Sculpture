"""spend_admin.py — the audited operator resolution surface (PR-2, ADR-061).

The spend ledger fails CLOSED: an uncertain hold keeps consuming cap
headroom, a halted scope refuses dispatch, an active safety lock refuses
every matching paid call. NOTHING clears any of them automatically — this
script is the one deliberate, audited path, and every resolution requires
a --reason and writes a budget_events row.

Run in the backend container (or on the host from the repo root):

    docker compose exec backend python scripts/spend_admin.py list
    docker compose exec backend python scripts/spend_admin.py census
    docker compose exec backend python scripts/spend_admin.py resolve-lock  <lock_id>        --reason "..."
    docker compose exec backend python scripts/spend_admin.py resolve-scope <scope_id>       --reason "..."
    docker compose exec backend python scripts/spend_admin.py resolve-hold  <reservation_id> --actual-usd 0.00 --reason "checked all three provider consoles for the hold's window; no charge"

`resolve-hold` settles an UNCERTAIN hold to the amount you verified in the
provider's own console (0.00 = confirmed not billed). Verify BEFORE you
resolve — the consoles are the only source of truth for a dead call
(ADR-033 taught that the hard way). Cost: $0; this script never dispatches.

`census` (D-28, ADR-070) is READ-ONLY: for every settled text call in the
ledger it prints the worst billed-tokens-per-prompt-byte ratio per model,
the smallest headroom under the recorded token bound, and any violation
of the bound assumption (which the backend also turns into a GLOBAL
safety lock at startup). It writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.budget import (  # noqa: E402
    envelope_census,
    micro_to_usd,
    resolve_halted_scope,
    resolve_safety_lock,
    resolve_uncertain_hold,
)
from app.db.database import Database  # noqa: E402


def _db(path: str | None = None) -> Database:
    if path:
        db = Database(Path(path))
    else:
        data_root = (
            Path("/app/data") if Path("/app/data").exists() else REPO_ROOT / "data"
        )
        db = Database(data_root / "luxuryform.db")
    db.init_db()
    return db


def cmd_list(db: Database) -> int:
    import sqlite3

    conn = sqlite3.connect(str(db.path))
    try:
        print("ACTIVE SAFETY LOCKS (refuse matching paid dispatch):")
        rows = conn.execute(
            "SELECT id, created_at, provider, model, reason FROM "
            "spend_safety_locks WHERE status='active' ORDER BY created_at"
        ).fetchall()
        for r in rows:
            print(f"  {r[0]}  {r[1]}  {r[2] or 'GLOBAL'}/{r[3] or 'all'}  {r[4]}")
        if not rows:
            print("  (none)")

        print("\nHALTED SPEND SCOPES (sticky; dispatch refuses):")
        rows = conn.execute(
            "SELECT id, kind, created_at, note FROM spend_scopes "
            "WHERE status='halted' ORDER BY created_at"
        ).fetchall()
        for r in rows:
            print(f"  {r[0]}  [{r[1]}]  {r[2]}  {r[3] or ''}")
        if not rows:
            print("  (none)")

        print("\nUNCERTAIN HOLDS (counted at full bound until you verify the "
              "provider console):")
        rows = conn.execute(
            "SELECT id, created_at, provider, model, reserved_usd_micro, "
            "note, bound_basis FROM spend_reservations "
            "WHERE status='uncertain' ORDER BY created_at"
        ).fetchall()
        for r in rows:
            basis = "envelope bound (ADR-070)" if r[6] else \
                "context-window ceiling (pre-D-28, ADR-061)"
            print(f"  {r[0]}  {r[1]}  {r[2]}/{r[3]}  "
                  f"bound ${micro_to_usd(int(r[4])):.6f} [{basis}]  {r[5] or ''}")
        if not rows:
            print("  (none)")
        return 0
    finally:
        conn.close()


def cmd_census(db: Database) -> int:
    """READ-ONLY (D-28, ADR-070). Exit 0 with no violations, 2 otherwise."""
    report = envelope_census(db)
    print("D-28 ENVELOPE-BOUND CENSUS (read-only; ADR-070)")
    print(f"  rule: billed input tokens <= min(context window, request "
          f"UTF-8 bytes + framing margin {report['framing_margin_tokens']})")
    print(f"  framing margin status: {report['framing_margin_status']}")
    print(f"  settled text calls checked: {report['text_calls']}; vision "
          f"calls skipped (window ceiling): {report['vision_skipped']}")
    for key in sorted(report["per_model"]):
        st = report["per_model"][key]
        print(f"  {key}: calls {st['calls']} (pre-D-28 rows "
              f"{st['pre_d28_rows']}); worst billed tokens per prompt byte "
              f"{st['worst_tokens_per_prompt_byte']:.4f} "
              f"(call {st['worst_tokens_per_prompt_byte_call']}); smallest "
              f"headroom under the bound {st['worst_headroom_tokens']} tokens "
              f"(call {st['worst_headroom_call']}); violations "
              f"{st['violations']}")
    if not report["per_model"]:
        print("  (no settled text calls in this database)")
    print(f"  violations: {len(report['violations'])}")
    for v in report["violations"]:
        print(f"    VIOLATION {v['ai_call_id']} {v['provider']}/{v['model']} "
              f"{v['ts']} billed {v['billed_input_tokens']} > bound "
              f"{v['input_tokens_bound']} [{v['basis']}]")
    return 2 if report["violations"] else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audited resolution of spend locks/scopes/holds (ADR-061)."
    )
    ap.add_argument("--db", default=None,
                    help="database file (default: the platform's data/"
                         "luxuryform.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show everything that needs a decision")
    sub.add_parser("census", help="READ-ONLY D-28 bound census over history")

    p = sub.add_parser("resolve-lock", help="resolve one ACTIVE safety lock")
    p.add_argument("lock_id")
    p.add_argument("--reason", required=True)

    p = sub.add_parser("resolve-scope", help="close one HALTED spend scope")
    p.add_argument("scope_id")
    p.add_argument("--reason", required=True)

    p = sub.add_parser(
        "resolve-hold",
        help="settle one UNCERTAIN hold to the console-verified amount",
    )
    p.add_argument("reservation_id")
    p.add_argument("--actual-usd", type=float, required=True,
                   help="the amount the provider console shows (0.00 = "
                        "confirmed not billed)")
    p.add_argument("--reason", required=True)

    args = ap.parse_args()
    db = _db(args.db)

    if args.cmd == "list":
        return cmd_list(db)
    if args.cmd == "census":
        return cmd_census(db)
    try:
        if args.cmd == "resolve-lock":
            resolve_safety_lock(db, args.lock_id, args.reason)
            print(f"safety lock {args.lock_id} RESOLVED (audited): {args.reason}")
        elif args.cmd == "resolve-scope":
            resolve_halted_scope(db, args.scope_id, args.reason)
            print(f"spend scope {args.scope_id} closed (audited): {args.reason}")
        elif args.cmd == "resolve-hold":
            resolve_uncertain_hold(db, args.reservation_id, args.actual_usd,
                                   args.reason)
            print(f"hold {args.reservation_id} RECONCILED at "
                  f"${args.actual_usd:.6f} (audited; it keeps counting at "
                  f"that amount): {args.reason}")
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
