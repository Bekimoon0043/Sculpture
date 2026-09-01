#!/usr/bin/env python3
"""PHASE 1 ACCEPTANCE GATE — LuxuryForm Studio v1.

Runs on the host (``python scripts/gate_phase1.py`` from the repo root, venv
active) or inside Docker (``docker compose exec backend python
scripts/gate_phase1.py``). Pure stdlib + project imports.

Designed for a non-interactive agent — no prompts, no required stdin, all
output to stdout, clear exit codes. The operator's machine agent runs:

  1. git pull
  2. docker compose up --build -d
  3. docker compose exec backend python scripts/gate_phase1.py
  4. Reports the FULL verbatim output. Never summarises a gate result.

Prints a numbered transcript and exits 0 ONLY on full PASS:
  1. CONFIG & DB      — settings, provider key status, pricing version, budget
                        caps, fresh throwaway gate DB initialised.
  2. TEXT CALLS       — one real prompt to every provider, logged to ai_calls.
  3. VISION CALLS     — one real test image to every provider's vision model
                        (Amendment 5).
  4. SPEND-CAP PROOF  — offline proof that a cap breach raises BudgetHalt and
                        persists budget_events + halted jobs rows (Amendment 2).
  5. DETERMINISM      — the Amendment 1 guarantee, verbatim.
  6. VERDICT          — PASS (exit 0) or FAIL with exact reasons (exit 1).

With no API keys the gate exits 1 and says exactly which env var to set for
each provider — that honest failure is the system working as designed.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

GATE_DB_PATH = REPO_ROOT / "data" / "gate_run.db"
TEXT_PROMPT = "Reply with the word LUXURYFORM and nothing else."
VISION_PROMPT = "Describe this image in one sentence. Include the dominant color."

PASS = "PASS"
FAIL = "FAIL"


def _hline() -> None:
    print("-" * 72)


def _section(no: int, title: str) -> None:
    print()
    _hline()
    print(f"[{no}/6] {title}")
    _hline()


def main() -> int:
    import logging

    # The gate prints provider key status explicitly in section 1; silence the
    # config module's duplicate stderr warnings so the transcript stays clean.
    logging.getLogger("luxuryform.config").setLevel(logging.CRITICAL)

    failures: list[str] = []

    # ------------------------------------------------------------------
    _section(1, "CONFIG & DB")
    from app.core.config import (
        PROVIDERS,
        ConfigError,
        get_settings,
        load_config_bundle,
        provider_keys_status,
    )
    from app.db.database import Database

    try:
        settings = get_settings()
        bundle = load_config_bundle()
    except ConfigError as exc:
        print(f"FAIL — config: {exc}")
        failures.append(f"config: {exc}")
        _verdict(failures)
        return 1

    print("Provider key status (key material is never printed):")
    key_status = provider_keys_status(settings)
    for provider in PROVIDERS:
        st = key_status[provider]
        state = "configured" if st["configured"] else f"missing (set {st['env_var']} in .env)"
        print(f"  {provider:<10} {state}")
    print(f"pricing_version: {bundle.pricing.pricing_version}")
    print(
        "budget caps: run_cap_usd=${:.2f}, day_cap_usd=${:.2f}, "
        "max_vision_iterations={}, on_breach={}".format(
            bundle.budget.run_cap_usd,
            bundle.budget.day_cap_usd,
            bundle.budget.max_vision_iterations,
            bundle.budget.on_breach,
        )
    )

    # Fresh throwaway DB so the gate is repeatable.
    os.environ["LUXURYFORM_DB"] = str(GATE_DB_PATH)
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(GATE_DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()
    GATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = Database(GATE_DB_PATH)
    db.init_db()
    print(f"gate DB: fresh {GATE_DB_PATH} (deleted first, schema applied) — WAL mode")
    print(f"{PASS} — section 1: config loaded, DB initialised")

    # One session for this whole gate run.
    from app.core.budget import BudgetEnforcer, BudgetHalt
    from app.db.models import AICallRow, BudgetEventRow, JobRow, SessionRow
    from sqlalchemy import select

    gate_session_id = f"gate-{uuid.uuid4()}"
    with db.get_session() as s:
        s.add(
            SessionRow(
                id=gate_session_id,
                started_at=datetime.now(timezone.utc).isoformat(),
                ended_at=None,
                status="active",
                total_cost_usd=0.0,
            )
        )
    enforcer = BudgetEnforcer(
        gate_session_id,
        bundle.budget.run_cap_usd,
        bundle.budget.day_cap_usd,
        db,
        scope_id=gate_session_id,
        scope_kind="gate",
    )
    from app.ai.providers import build_providers
    from app.ai.provider import ProviderError

    providers = build_providers(settings, bundle, db, budget=enforcer)

    # ------------------------------------------------------------------
    _section(2, "TEXT CALLS — 'Reply with the word LUXURYFORM and nothing else.'")
    text_ok: dict[str, bool] = {}
    for name in PROVIDERS:
        provider = providers[name]
        if not key_status[name]["configured"]:
            env_var = key_status[name]["env_var"]
            print(f"FAIL — {name}: not configured (set {env_var} in .env)")
            failures.append(f"{name} text: not configured (set {env_var} in .env)")
            text_ok[name] = False
            continue
        try:
            resp = provider.complete(
                TEXT_PROMPT,
                purpose="gate_phase1_text",
                max_tokens=64,
                session_id=gate_session_id,
            )
        except ProviderError as exc:
            print(f"FAIL — {name}: {exc.raw_message}")
            failures.append(f"{name} text: {exc.raw_message}")
            text_ok[name] = False
            continue
        except BudgetHalt as halt:
            print(f"FAIL — {name}: spend cap halted the call: {halt.reason}")
            failures.append(f"{name} text: budget halt: {halt.reason}")
            text_ok[name] = False
            continue
        print(
            f"OK — {name}: model={resp.model} response={resp.text!r} "
            f"tokens(in/out)={resp.tokens_in}/{resp.tokens_out} "
            f"latency={resp.latency_ms:.0f}ms cost=${resp.cost_usd:.6f} "
            f"(pricing {resp.pricing_version})"
        )
        text_ok[name] = True

    print()
    print(f"ai_calls rows persisted for session {gate_session_id} (proof of log):")
    with db.get_session() as s:
        rows = s.execute(
            select(AICallRow)
            .where(AICallRow.session_id == gate_session_id)
            .order_by(AICallRow.ts)
        ).scalars().all()
    if not rows:
        print("  (no rows — no provider calls were made)")
    for r in rows:
        print(
            f"  id={r.id} provider={r.provider} model={r.model} status={r.status} "
            f"tokens={r.tokens_in}/{r.tokens_out} cost=${r.cost_usd:.6f} "
            f"purpose={r.purpose}"
        )

    # ------------------------------------------------------------------
    _section(3, "VISION CALLS (Amendment 5)")
    import make_test_image
    from PIL import Image

    image_path = REPO_ROOT / "scripts" / "assets" / "gate_test_image.png"
    if not image_path.exists():
        make_test_image.generate(image_path)
    with Image.open(image_path) as img:
        width, height = img.size
    image_bytes = image_path.stat().st_size
    print(f"test image: {image_path} ({image_bytes} bytes, {width}x{height})")

    vision_ok: dict[str, bool] = {}
    for name in PROVIDERS:
        provider = providers[name]
        if not key_status[name]["configured"]:
            env_var = key_status[name]["env_var"]
            print(f"FAIL — {name} vision: not configured (set {env_var} in .env)")
            failures.append(f"{name} vision: not configured (set {env_var} in .env)")
            vision_ok[name] = False
            continue
        try:
            resp = provider.vision(
                VISION_PROMPT,
                image_path,
                purpose="gate_phase1_vision",
                max_tokens=128,
                session_id=gate_session_id,
            )
        except ProviderError as exc:
            print(f"FAIL — {name} vision: {exc.raw_message}")
            print(
                "  ACTION: record this provider's vision failure in "
                "LIMITATIONS.md now."
            )
            failures.append(f"{name} vision: {exc.raw_message}")
            vision_ok[name] = False
            continue
        except BudgetHalt as halt:
            print(f"FAIL — {name} vision: spend cap halted the call: {halt.reason}")
            failures.append(f"{name} vision: budget halt: {halt.reason}")
            vision_ok[name] = False
            continue
        print(
            f"OK — {name} vision: model={resp.model} accepted {image_bytes} bytes "
            f"({width}x{height}) response={resp.text!r} "
            f"tokens(in/out)={resp.tokens_in}/{resp.tokens_out} "
            f"cost=${resp.cost_usd:.6f}"
        )
        vision_ok[name] = True

    # ------------------------------------------------------------------
    _section(4, "SPEND-CAP PROOF (Amendment 2) — offline, no network")
    print(
        f"max_vision_iterations={bundle.budget.max_vision_iterations} loaded and "
        "validated from config/budget.yaml (enforced in Phase 5)"
    )
    # ADR-061: the cap proof now runs the REAL reservation path — a hold is
    # taken and settled (one atomic transaction: ai_calls row + reservation
    # + session ledger), then the next reservation must refuse with its
    # evidence committed. All offline; nothing dispatches.
    from app.core.budget import usd_to_micro

    proof_session_id = f"gate-cap-proof-{uuid.uuid4()}"
    proof = BudgetEnforcer(
        proof_session_id,
        run_cap_usd=0.03,
        day_cap_usd=bundle.budget.day_cap_usd,
        db=db,
        scope_id=proof_session_id,
        scope_kind="gate",
    )
    with db.get_session() as s:
        s.add(
            SessionRow(
                id=proof_session_id,
                started_at=datetime.now(timezone.utc).isoformat(),
                ended_at=None,
                status="active",
                total_cost_usd=0.0,
            )
        )
    r1 = proof.reserve(usd_to_micro(0.02), provider="offline_synthetic",
                       model="none", kind="text", attempt_no=1)
    proof.settle_success(
        r1,
        ts=datetime.now(timezone.utc).isoformat(),
        provider="offline_synthetic", model="none",
        purpose="gate_cap_proof_synthetic",
        prompt="(offline synthetic spend for the cap proof — no API call made)",
        response="", tokens_in=0, tokens_out=0, cached_input_tokens=0,
        cache_write_input_tokens=0, latency_ms=0.0, cost_usd=0.02,
        pricing_version=bundle.pricing.pricing_version,
    )
    print("synthetic spend settled through the ledger: $0.020000 against a "
          "run cap of $0.030000")
    cap_proof_passed = False
    try:
        proof.reserve(usd_to_micro(0.02), provider="offline_synthetic",
                      model="none", kind="text", attempt_no=1)
        print("FAIL — cap proof: reserve($0.02) over the run cap did NOT "
              "raise BudgetHalt")
        failures.append("cap proof: BudgetHalt not raised over the run cap")
    except BudgetHalt as halt:
        cap_proof_passed = True
        print(f"BudgetHalt raised as required. Reason: {halt.reason}")
    with db.get_session() as s:
        events = s.execute(
            select(BudgetEventRow).where(BudgetEventRow.session_id == proof_session_id)
        ).scalars().all()
        jobs = s.execute(
            select(JobRow).where(JobRow.session_id == proof_session_id)
        ).scalars().all()
    print("persisted budget_events rows:")
    for e in events:
        print(f"  id={e.id} type={e.event_type} detail={e.detail}")
    print("persisted jobs rows (halted state):")
    for j in jobs:
        print(
            f"  id={j.id} type={j.job_type} status={j.status} "
            f"halt_reason={j.halt_reason}"
        )
        print(f"    state_json={j.state_json}")
    if cap_proof_passed and events and any(j.status == "halted_budget" for j in jobs):
        print(f"{PASS} — section 4: cap breach halted the run and persisted state")
    else:
        if not (events and any(j.status == "halted_budget" for j in jobs)):
            print("FAIL — cap proof: breach rows were not persisted correctly")
            failures.append("cap proof: budget_events/jobs rows missing")

    # ------------------------------------------------------------------
    _section(5, "DETERMINISM STATEMENT (Amendment 1)")
    from app.core.seeds import DETERMINISM_STATEMENT

    print(f'"{DETERMINISM_STATEMENT}"')
    print()
    print(
        "This gate does NOT and will never test brief-level reproducibility; "
        "determinism starts at the persisted Design Spec."
    )

    # ------------------------------------------------------------------
    _section(6, "VERDICT")
    return _verdict(failures)


def _verdict(failures: list[str]) -> int:
    if failures:
        print(f"PHASE 1 GATE: FAIL — {'; '.join(failures)}")
        print()
        print(
            "Note: provider FAILs above name the exact env var to set in .env. "
            "With all three keys set, re-run this script (expected API cost "
            "$0.01–0.05 per run)."
        )
        return 1
    print("PHASE 1 GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
