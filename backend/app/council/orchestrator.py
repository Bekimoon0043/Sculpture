"""The Council orchestrator (Phase 3, build step 2).

Runs one Council session end to end per PHASE_3_PLAN.md §1:

    brief -> RESEARCHER (kimi||openai) -> DESIGNER 3 alternatives x 2
    providers (6 raw candidates, schema-validated with bounded re-ask) ->
    GEOMETRIST (anthropic||kimi) -> ENGINEER (openai||anthropic) ->
    CRITIC (dynamic rule: never a producer provider) -> ARBITER
    (openai||anthropic) -> BINDING decision: exactly 3 distinct ranked
    specs + confidence + disagreement register.

Provider access goes through the CouncilDispatcher protocol — production
wires it to the real provider layer (call_log.execute: budget pre-check,
pricing, persistence); tests inject a scripted dispatcher, so ALL
orchestration logic is provable offline at $0.

Hard rules enforced in CODE (never delegated to the models):
  - Design Specs must validate against schemas/design_spec_v1.json;
    invalid -> bounded re-ask (MAX_ATTEMPTS total tries), then the
    candidate is recorded schema_valid=0 and excluded from the Arbiter.
  - The Critic never runs on a provider that produced a candidate spec
    (dynamic rule from council.yaml, resolved per session; if fewer than
    two providers remain eligible the session runs DEGRADED and says so).
  - The Arbiter decision must name exactly 3 DISTINCT, in-session spec ids
    and a confidence in [0, 1] — invalid -> bounded re-ask, then the
    session FAILS (no fabricated decision).
  - Explicit parent-first flush ordering (SQLAlchemy UOW does not order
    cross-mapper inserts without relationships — ADR lesson from step 1).
  - A BudgetHalt aborts the session honestly: status=halted_budget, every
    call up to the halt persisted, the halt re-raised.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import jsonschema

from app.council import prompts
from app.council.replay import canonical_spec_hash
from app.core.budget import BudgetHalt
from app.core.config import PROVIDERS, PricingConfig, REPO_ROOT
from app.db.database import Database
from app.db.models import (
    ArbiterDecisionRow,
    CouncilCallRow,
    CouncilSessionRow,
    DefectListRow,
    DesignSpecRow,
    EngineeringReviewRow,
)

log = logging.getLogger("luxuryform.council")

SCHEMA_PATH = REPO_ROOT / "schemas" / "design_spec_v1.json"

#: Total tries per JSON-producing call (initial + 2 re-asks). Our own design
#: decision — bounded so a non-complying model burns at most 3 calls.
MAX_ATTEMPTS = 3

#: max_tokens per role call (designer emits a full spec; arbiter a decision).
MAX_TOKENS = 8192


class OrchestratorError(RuntimeError):
    """The Council could not complete honestly (e.g. Arbiter never produced
    a valid binding decision within the re-ask bound)."""


@dataclass
class DispatchOutcome:
    """What a dispatcher returns for one provider call."""

    provider: str
    model: str
    text: str
    tokens_in: int             # uncached input, normalised (ADR-022)
    tokens_out: int
    latency_ms: float
    cost_usd: float
    pricing_version: str
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    status: str = "ok"           # ok | error
    error: str | None = None


class CouncilDispatcher(Protocol):
    """One provider call. Production: real SDKs via call_log.execute.
    Tests: scripted responses. Same contract."""

    def dispatch(
        self,
        *,
        role: str,
        side: str,
        provider: str,
        prompt: str,
        session_id: str,
        max_tokens: int,
    ) -> DispatchOutcome: ...


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict:
    """Parse the model's reply as one JSON object, tolerating stray fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        # drop a leading language tag line like "json"
        if "\n" in t:
            t = t.split("\n", 1)[1]
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(t[start : end + 1])


def _validate_live_primitives(spec: dict) -> list[str]:
    """Return live-registry validation errors for massing.elements.

    JSON Schema proves the Design Spec shape. This check proves the spec uses
    primitives the current geometry registry can actually fabricate. That is
    deliberately code-level validation: Phase 6 widens the registry one gated
    slice at a time, and the prompt/schema must not carry a stale enum.
    """
    from app.geometry.registry import PRIMITIVES

    available = ", ".join(sorted(PRIMITIVES))
    errors: list[str] = []
    elements = spec.get("massing", {}).get("elements", [])
    for i, element in enumerate(elements):
        primitive = element.get("primitive")
        element_id = element.get("element_id", f"element[{i}]")
        if primitive not in PRIMITIVES:
            errors.append(
                f"massing.elements[{i}] {element_id!r} uses primitive "
                f"{primitive!r}, which is not in the live registry "
                f"(available: {available})"
            )
    return errors


class CouncilOrchestrator:
    def __init__(
        self,
        db: Database,
        pricing: PricingConfig,
        dispatcher: CouncilDispatcher,
        council_config,  # CouncilConfig
    ) -> None:
        self._db = db
        self._pricing = pricing
        self._dispatcher = dispatcher
        self._roles = council_config.roles
        self._schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self._schema_json = json.dumps(self._schema)

    # -- plumbing ---------------------------------------------------------

    def _pair(self, role: str) -> tuple[str, str | None]:
        """Static (primary, parallel) providers for a role from council.yaml."""
        ra = self._roles[role]
        return ra.primary, ra.parallel

    def _call(self, session_id: str, role: str, side: str, provider: str,
              prompt: str, optional: bool = False) -> DispatchOutcome:
        """Dispatch one call and persist its council_calls row (Rule 8).

        ``optional=True`` (ADR-023): a failed NON-CRITICAL call degrades the
        session instead of aborting it — the dispatch exception is caught,
        persisted as an error council_calls row (the failure is never
        invisible), and returned with status="error". BudgetHalt is NEVER
        optional: it always propagates.
        """
        try:
            outcome = self._dispatcher.dispatch(
                role=role, side=side, provider=provider, prompt=prompt,
                session_id=session_id, max_tokens=MAX_TOKENS,
            )
        except BudgetHalt:
            raise
        except Exception as exc:
            if not optional:
                raise
            outcome = DispatchOutcome(
                provider=provider, model="", text="",
                tokens_in=0, tokens_out=0, latency_ms=0.0, cost_usd=0.0,
                pricing_version=self._pricing.pricing_version,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
        with self._db.get_session() as s:
            s.add(
                CouncilCallRow(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    ts=_utc_now_iso(),
                    role=role,
                    side=side,
                    provider=outcome.provider,
                    model=outcome.model,
                    prompt=prompt,
                    response=outcome.text,
                    tokens_in=outcome.tokens_in,
                    tokens_out=outcome.tokens_out,
                    cached_input_tokens=outcome.cached_input_tokens,
                    cache_write_input_tokens=outcome.cache_write_input_tokens,
                    latency_ms=outcome.latency_ms,
                    cost_usd=outcome.cost_usd,
                    pricing_version=outcome.pricing_version,
                    status=outcome.status,
                    error=outcome.error,
                )
            )
        return outcome

    # -- role stages --------------------------------------------------------

    def _run_designers(self, session_id: str, brief: str, research: str) -> tuple[list[dict], bool, bool]:
        """3 alternatives x 2 providers; schema-validate; bounded re-ask.
        Returns (valid candidate specs, any_provider_failure, any_reask).

        A failed designer CALL (provider outage, ADR-023) does not re-ask and
        does not abort: it skips that alternative — the <3-valid check in
        run_session aborts honestly if the pool shrinks too far, and the
        session is flagged degraded."""
        primary, parallel = self._pair("designer")
        valid_specs: list[dict] = []
        seen_spec_ids: set[str] = set()
        any_failure = False
        any_reask = False
        for alternative_no in (1, 2, 3):
            for side, provider in (("primary", primary), ("parallel", parallel)):
                base_prompt = prompts.designer_prompt(
                    brief, research, alternative_no, self._schema_json
                )
                errors: list[str] = []
                spec: dict | None = None
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    prompt = base_prompt + (
                        prompts.designer_reask_suffix(errors) if errors else ""
                    )
                    outcome = self._call(session_id, "designer", side, provider,
                                         prompt, optional=True)
                    if outcome.status != "ok":
                        any_failure = True
                        log.warning(
                            "designer %s alt %d call failed: %s",
                            provider, alternative_no, outcome.error,
                        )
                        break  # provider outage — no re-ask, skip alternative
                    try:
                        candidate = _extract_json(outcome.text)
                        jsonschema.validate(instance=candidate, schema=self._schema)
                        primitive_errors = _validate_live_primitives(candidate)
                        if primitive_errors:
                            errors = [
                                "live registry violation: "
                                + "; ".join(primitive_errors)
                            ]
                            continue
                        spec = candidate
                        if attempt > 1:
                            any_reask = True  # self-correction, not degradation
                        break
                    except (ValueError, json.JSONDecodeError) as exc:
                        errors = [f"reply is not a JSON object: {exc}"]
                    except jsonschema.ValidationError as exc:
                        errors = [f"schema violation: {exc.message}"]
                if spec is None:
                    # Record the failed candidate honestly (schema_valid=0);
                    # it never reaches the Arbiter. (Call failures already
                    # logged above; this line is for validation failures.)
                    if not errors:
                        continue
                    log.warning(
                        "designer %s alt %d failed validation after %d attempts",
                        provider, alternative_no, MAX_ATTEMPTS,
                    )
                    continue
                meta = spec["meta"]
                if meta["spec_id"] in seen_spec_ids:
                    # A provider re-issued an id we already persisted — skip
                    # rather than PK-crash the session.
                    log.warning("designer %s alt %d returned duplicate spec_id %s — skipped",
                                provider, alternative_no, meta["spec_id"])
                    continue
                seen_spec_ids.add(meta["spec_id"])
                valid_specs.append(spec)
                with self._db.get_session() as s:
                    s.add(
                        DesignSpecRow(
                            id=meta["spec_id"],
                            created_at=_utc_now_iso(),
                            session_id=session_id,
                            provider=provider,  # dispatch truth, not model claim
                            alternative_no=alternative_no,
                            spec_json=json.dumps(spec, sort_keys=True),
                            spec_hash=canonical_spec_hash(spec),
                            seed=meta["seed"],
                            schema_valid=1,
                        )
                    )
        return valid_specs, any_failure, any_reask

    def _resolve_critic_providers(self, valid_specs: list[dict]) -> tuple[list[str], bool]:
        """Dynamic rule: never a provider that produced a candidate spec.
        Returns (providers_to_run, reduced_coverage).

        ADR-025: reduced coverage here is the never-a-producer rule working
        as designed, NOT degradation — with the static designer pair
        (anthropic+openai) the critic primary is always a producer, so the
        critic always runs single-provider. Flagging that as degraded made
        the badge meaningless (every healthy session flagged it)."""

        producers = {sp["meta"].get("provider") for sp in valid_specs}
        primary, parallel = self._pair("critic")
        ordered = [p for p in (primary, parallel) if p] + [
            p for p in PROVIDERS if p not in (primary, parallel)
        ]
        eligible = [p for p in ordered if p not in producers]
        run = eligible[:2]
        return run, len(run) < 2

    def _run_arbiter(self, session_id: str, brief: str, valid_specs: list[dict],
                     review_text: str, defects_text: str) -> tuple[dict, bool]:
        """Bounded re-ask until a valid binding decision or fail loudly.
        Returns (decision, reasked) — reasked marks self-correction (ADR-025)."""
        primary, parallel = self._pair("arbiter")
        summary = prompts.candidates_summary(valid_specs)
        valid_ids = {sp["meta"]["spec_id"] for sp in valid_specs}
        base = prompts.arbiter_prompt(brief, summary, review_text, defects_text)
        errors: list[str] = []
        decision: dict | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            prompt = base + (prompts.arbiter_reask_suffix(errors) if errors else "")
            outcome = self._call(session_id, "arbiter", "primary", primary, prompt)
            decision, errors = self._validate_decision(outcome.text, valid_ids)
            if decision is not None:
                break
        reasked = attempt > 1
        if decision is None:
            raise OrchestratorError(
                f"Arbiter produced no valid binding decision after "
                f"{MAX_ATTEMPTS} attempts; last problems: {errors}"
            )
        # Parallel arbiter: concurrence / disagreement input (recorded; the
        # register in the decision already carries the disagreements).
        if parallel:
            self._call(
                session_id, "arbiter", "parallel", parallel,
                base + "\n\nYou are the PARALLEL arbiter: concur or state "
                "your disagreement explicitly in the same JSON shape.",
            )
        return decision, reasked

    def _validate_decision(self, text: str, valid_ids: set[str]) -> tuple[dict | None, list[str]]:
        try:
            decision = _extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            return None, [f"reply is not a JSON object: {exc}"]
        problems: list[str] = []
        chosen = decision.get("chosen_spec_ids")
        if not isinstance(chosen, list) or len(chosen) != 3 or len(set(chosen or [])) != 3:
            problems.append("chosen_spec_ids must be exactly 3 distinct ids")
        elif set(chosen) - valid_ids:
            problems.append("chosen_spec_ids must come from this session's valid specs")
        conf = decision.get("confidence")
        if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
            problems.append("confidence must be a number in [0, 1]")
        if not decision.get("rationale"):
            problems.append("rationale is required")
        if "disagreement_register" not in decision:
            problems.append("disagreement_register is required (may be [])")
        return (decision if not problems else None), problems

    # -- the session --------------------------------------------------------

    def run_session(self, brief: str, session_id: str | None = None) -> str:
        """Run one full Council session. Returns the council session id.

        ``session_id`` lets the caller (the live API route) pre-generate the
        id so the BudgetEnforcer watches the SAME session rows the calls are
        written to — session-cap accounting is blind otherwise.
        """
        if not brief.strip():
            raise OrchestratorError("empty brief")
        session_id = session_id or str(uuid.uuid4())
        now = _utc_now_iso()
        with self._db.get_session() as s:
            s.add(
                CouncilSessionRow(
                    id=session_id,
                    created_at=now,
                    brief_text=brief,
                    status="running",
                    started_at=now,
                    ended_at=None,
                    total_cost_usd=0.0,
                    pricing_version=self._pricing.pricing_version,
                    arbiter_confidence=None,
                    degraded=0,
                )
            )
            s.flush()  # parent first — see module docstring

        degraded = 0    # a provider FAILURE left a seat empty/reduced (ADR-025)
        corrected = 0   # a bounded re-ask succeeded — self-correction, not degradation
        optional_failures: list[str] = []

        def _optional(role: str, side: str, provider: str, prompt: str):
            """Optional call: failure degrades the session, never aborts."""
            out = self._call(session_id, role, side, provider, prompt,
                             optional=True)
            if out.status != "ok":
                optional_failures.append(f"{role}/{side}/{provider}")
            return out

        try:
            # RESEARCHER — both sides optional: if both fail, designers work
            # from the brief alone and the session is flagged degraded.
            primary, parallel = self._pair("researcher")
            research_prompt = prompts.researcher_prompt(brief)
            research_out = _optional("researcher", "primary", primary,
                                     research_prompt)
            research = research_out.text
            if parallel:
                par_out = _optional("researcher", "parallel", parallel,
                                    research_prompt)
                if research_out.status != "ok":
                    research = par_out.text  # fall back to the parallel side
            if not research:
                degraded = 1
                research = ("(researcher unavailable — provider failures; "
                            "designers work from the brief alone)")

            # DESIGNER x 3 alternatives x 2 providers (failures just shrink
            # the valid-candidate pool; <3 valid aborts below)
            valid_specs, designer_failures, designer_reask = self._run_designers(
                session_id, brief, research
            )
            if designer_failures:
                degraded = 1
            if designer_reask:
                corrected = 1
            if len(valid_specs) < 3:
                raise OrchestratorError(
                    f"only {len(valid_specs)} valid Design Spec candidates; "
                    "the Arbiter needs at least 3"
                )
            summary = prompts.candidates_summary(valid_specs)

            # GEOMETRIST
            primary, parallel = self._pair("geometrist")
            geo_out = _optional("geometrist", "primary", primary,
                                prompts.geometrist_prompt(brief, summary))
            geo = geo_out.text or "(geometrist unavailable — provider failure)"
            if parallel:
                _optional("geometrist", "parallel", parallel,
                          prompts.geometrist_prompt(brief, summary))

            # ENGINEER
            primary, parallel = self._pair("engineer")
            eng_prompt = prompts.engineer_prompt(brief, summary, geo)
            review_primary = _optional("engineer", "primary", primary, eng_prompt)
            if review_primary.status == "ok":
                self._persist_payload(session_id, EngineeringReviewRow, primary,
                                      "primary", review_primary.text)
            if parallel:
                out = _optional("engineer", "parallel", parallel, eng_prompt)
                if out.status == "ok":
                    self._persist_payload(session_id, EngineeringReviewRow,
                                          parallel, "parallel", out.text)

            # CRITIC (dynamic rule)
            critic_providers, critic_reduced = self._resolve_critic_providers(valid_specs)
            if critic_reduced:
                # ADR-025: the never-a-producer rule excludes the critic
                # primary by design — informational, NOT degradation.
                log.info("critic running single-provider (producer exclusion): %s",
                         critic_providers)
            if not critic_providers:
                raise OrchestratorError(
                    "no eligible critic provider (every provider produced a candidate)"
                )
            review_text = (review_primary.text
                           or "(engineer review unavailable — provider failure)")
            crit_prompt = prompts.critic_prompt(brief, summary, review_text)
            defects_text = ""
            for i, provider in enumerate(critic_providers):
                side = "primary" if i == 0 else "parallel"
                out = _optional("critic", side, provider, crit_prompt)
                if out.status == "ok":
                    self._persist_payload(session_id, DefectListRow, provider,
                                          side, out.text)
                    if not defects_text:
                        defects_text = out.text
            if not defects_text:
                defects_text = "(critic unavailable — provider failures)"


            if optional_failures:
                degraded = 1

            # ARBITER (binding — the one stage whose failure DOES abort:
            # without a binding decision there is no session outcome)
            decision, arbiter_reask = self._run_arbiter(session_id, brief, valid_specs,
                                                        review_text, defects_text)
            if arbiter_reask:
                corrected = 1
            chosen = decision["chosen_spec_ids"]
            hashes = {}
            with self._db.get_session() as s:
                for sp in s.query(DesignSpecRow).filter_by(session_id=session_id):
                    hashes[sp.id] = sp.spec_hash
            chosen_hashes = [hashes[c] for c in chosen]
            if len(set(chosen_hashes)) != 3:
                raise OrchestratorError(
                    "Arbiter chose 3 ids but their canonical hashes are not "
                    "distinct — near-duplicate specs bound; refusing"
                )
            with self._db.get_session() as s:
                s.add(
                    ArbiterDecisionRow(
                        id=str(uuid.uuid4()),
                        created_at=_utc_now_iso(),
                        session_id=session_id,
                        chosen_spec_ids_json=json.dumps(chosen),
                        confidence=float(decision["confidence"]),
                        rationale=decision["rationale"],
                        disagreement_register_json=json.dumps(
                            decision.get("disagreement_register", []), sort_keys=True
                        ),
                        binding=1,
                    )
                )

            self._finalize(session_id, "completed", degraded,
                           float(decision["confidence"]), corrected)
            return session_id
        except BudgetHalt:
            # Amendment 2: the enforcer stopped a dispatch. Mark honestly,
            # keep every persisted call, re-raise.
            self._finalize(session_id, "halted_budget", degraded, None, corrected)
            raise
        except Exception:
            self._finalize(session_id, "failed", degraded, None, corrected)
            raise

    def _persist_payload(self, session_id: str, row_cls, provider: str,
                         side: str, text: str) -> None:
        """Engineering review / defect list rows: parsed JSON if possible,
        raw text wrapped if not (never dropped)."""
        try:
            payload = _extract_json(text)
        except (ValueError, json.JSONDecodeError):
            payload = {"raw": text, "parse_warning": "reply was not clean JSON"}
        with self._db.get_session() as s:
            s.add(
                row_cls(
                    id=str(uuid.uuid4()),
                    created_at=_utc_now_iso(),
                    session_id=session_id,
                    provider=provider,
                    side=side,
                    payload_json=json.dumps(payload, sort_keys=True),
                )
            )

    def _finalize(self, session_id: str, status: str, degraded: int,
                  confidence: float | None, corrected: int) -> None:
        with self._db.get_session() as s:
            sess = s.get(CouncilSessionRow, session_id)
            total = (
                s.query(CouncilCallRow)
                .filter_by(session_id=session_id)
                .with_entities(CouncilCallRow.cost_usd)
                .all()
            )
            sess.total_cost_usd = round(sum(c for (c,) in total), 6)
            sess.status = status
            sess.degraded = degraded
            sess.corrected = corrected
            sess.arbiter_confidence = confidence
            sess.ended_at = _utc_now_iso()
