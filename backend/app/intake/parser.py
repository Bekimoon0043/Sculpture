"""Brief parser — one logged, budget-capped provider call (Phase 12).

The parser FILLS THE FORM; it never decides. Its output is merged onto the
draft with one hard rule: a field the operator has touched is never
overwritten by a machine (operator > parsed). Everything it extracts
carries the brief sentence it came from, so the operator can check the
parser's work against the client's own words in the UI.

Reuses the exact provider path the Council uses — `AIProvider.complete`
through `call_log.execute` — so every parse is logged with prompt, response,
tokens, latency and cost (Rule 8), and is subject to the same budget caps.
Without API keys the parse fails honestly and the form still works by hand.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.intake.models import IntakeV1, Sourced

log = logging.getLogger("luxuryform.intake")

#: The parse is cheap extraction, not design — it runs on the researcher
#: seat's primary provider (council.yaml), which the operator already tuned
#: for exactly this class of work.
PARSER_ROLE = "researcher"
PARSER_MAX_TOKENS = 1400

#: Every leaf the parser may fill, with its expected JSON type. Anything
#: outside this list in the reply is DROPPED — the model cannot invent new
#: fields, and a field it cannot find must be omitted, not guessed.
_PARSEABLE: dict[str, dict[str, str]] = {
    "project": {"project_type": "string", "name": "string", "setting": "string"},
    "site": {
        "city": "string", "country": "string", "indoor": "boolean",
        "altitude_m": "number", "design_wind_speed_m_s": "number",
        "allowable_bearing_kpa": "number", "freeze_risk": "boolean",
        "dust_exposure": "string", "water_available": "boolean",
        "access_notes": "string",
    },
    "dimensions": {"height_m": "number", "footprint_m": "number"},
    "water": {
        "has_water": "boolean", "flow_l_per_min": "number",
        "operating_depth_mm": "number", "nozzle_bore_mm": "number",
        "recirculating": "boolean", "behavior": "string",
    },
    "materials": {"preferred": "array of material-id strings",
                  "forbidden": "array of material-id strings"},
    "culture": {"inspiration": "string", "motifs": "string",
                "forbidden_motifs": "string", "brand_tone": "string"},
    "budget": {"currency": "string", "amount_min": "number",
               "amount_max": "number", "contingency_pct": "number",
               "deadline": "string"},
}


def parse_prompt(brief: str, material_ids: list[str]) -> str:
    field_lines = []
    for section, fields in _PARSEABLE.items():
        for name, typ in fields.items():
            field_lines.append(f"  {section}.{name}: {typ}")
    return (
        "You extract structured intake data from a client brief for a company "
        "that builds monumental fountains and sculptures.\n\n"
        "Reply with ONE JSON object and nothing else. For every field you can "
        "find in the brief, emit:\n"
        '  "<section>.<field>": {"value": <value>, "quote": "<the exact brief '
        'sentence you took it from>"}\n\n'
        "HARD RULES:\n"
        "- OMIT any field the brief does not state. Never guess, never infer "
        "a default. An omitted field stays honestly unknown.\n"
        "- Units are SI: metres, millimetres, litres per minute. Convert if "
        "the brief uses other units, and keep the original wording in quote.\n"
        f"- materials.* values must come from this id list when they match: "
        f"{', '.join(material_ids)}. A material outside the list goes in as "
        "free text.\n"
        "- water.behavior is one of: jet, cascade, sheet, still, mist.\n"
        "- project.setting is one of: public, private.\n\n"
        "FIELDS:\n" + "\n".join(field_lines) + "\n\n"
        "BRIEF:\n" + brief.strip()
    )


def _extract_json(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if "\n" in t:
            t = t.split("\n", 1)[1]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the parser reply")
    return json.loads(t[start : end + 1])


def merge_parsed(intake: IntakeV1, parsed: dict[str, Any]) -> tuple[IntakeV1, dict[str, int]]:
    """Merge a parser reply onto a draft. Returns (intake, counts).

    Rules:
      * operator-sourced fields are never overwritten (the operator's word
        beats the machine's reading, always);
      * unknown fields in the reply are dropped, with a count, so the UI can
        say "the parser proposed 2 fields outside the schema" instead of
        silently discarding them;
      * a type mismatch drops the field rather than coercing a guess.
    """
    applied = 0
    skipped_operator = 0
    dropped = 0
    for dotted, payload in parsed.items():
        if not isinstance(payload, dict) or "value" not in payload:
            dropped += 1
            continue
        parts = dotted.split(".")
        if len(parts) != 2 or parts[0] not in _PARSEABLE or parts[1] not in _PARSEABLE[parts[0]]:
            dropped += 1
            continue
        section, name = parts
        current: Sourced[Any] = getattr(getattr(intake, section), name)
        if current.source == "operator":
            skipped_operator += 1
            continue
        value = payload["value"]
        if value is None:
            dropped += 1
            continue
        expected = _PARSEABLE[section][name]
        ok = (
            (expected == "string" and isinstance(value, str))
            or (expected == "boolean" and isinstance(value, bool))
            or (expected == "number" and isinstance(value, (int, float))
                and not isinstance(value, bool))
            or (expected.startswith("array") and isinstance(value, list))
        )
        if not ok:
            dropped += 1
            continue
        quote = payload.get("quote")
        setattr(
            getattr(intake, section), name,
            Sourced(value=value, source="parsed",
                    quote=str(quote) if quote else None),
        )
        applied += 1
    return intake, {
        "applied": applied,
        "kept_operator": skipped_operator,
        "dropped": dropped,
    }


def run_parse(
    provider,
    *,
    brief: str,
    intake: IntakeV1,
    material_ids: list[str],
    session_id: str,
) -> tuple[IntakeV1, dict[str, Any]]:
    """One provider call -> merged intake + an honest accounting of it."""
    resp = provider.complete(
        parse_prompt(brief, material_ids),
        purpose="intake_parse",
        max_tokens=PARSER_MAX_TOKENS,
        session_id=session_id,
    )
    parsed = _extract_json(resp.text)
    merged, counts = merge_parsed(intake, parsed)
    log.info(
        "intake parse: provider=%s model=%s applied=%d kept_operator=%d "
        "dropped=%d cost=$%.6f",
        resp.provider, resp.model, counts["applied"], counts["kept_operator"],
        counts["dropped"], resp.cost_usd,
    )
    return merged, {
        **counts,
        "provider": resp.provider,
        "model": resp.model,
        "cost_usd": resp.cost_usd,
        "tokens_in": resp.tokens_in,
        "tokens_out": resp.tokens_out,
    }
