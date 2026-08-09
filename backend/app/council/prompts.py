"""Council prompt builders (Phase 3, build step 2).

One builder per role. Prompts carry the full accumulated context the role
needs (Rule 8: the exact text is persisted per call in council_calls). Every
JSON-producing role gets the schema inline and an explicit "JSON only"
instruction; the orchestrator enforces it with bounded re-ask.
"""

from __future__ import annotations

import json

from app.ai.provider import CACHE_BREAK  # ADR-024: see provider.py

_JSON_ONLY = (
    "Respond with ONLY a single JSON object. No markdown fences, no prose "
    "before or after. The FIRST character of your reply must be '{'."
)


def researcher_prompt(brief: str) -> str:
    return (
        "You are the RESEARCHER of the LuxuryForm design council. Given the "
        "client brief below, produce a compact context brief for the design "
        "team: site and cultural considerations, precedent monumental "
        "fountains/sculptures relevant to the brief, material and climate "
        "constraints, and hydraulic basics (pump/flow envelope for the "
        "implied scale). Plain prose, under 600 words.\n\n"
        f"CLIENT BRIEF:\n{brief}"
    )


def designer_prompt(brief: str, research: str, alternative_no: int,
                    schema_json: str) -> str:
    # Static prefix FIRST (identical across all 6 designer calls in a
    # session; the schema alone is ~2.9k tokens — over the 1024-token
    # cacheable minimum), then the cache break, then the per-call variant.
    return (
        "You are the DESIGNER of the LuxuryForm design council. Produce one "
        "Design Spec alternative for the client brief below, as a single "
        "JSON object VALIDATING against the attached Design Spec v1 JSON "
        "Schema. Fill every required field; meta.created_by is 'DESIGNER'; "
        "meta.provider is the provider you are running on (your best "
        "judgement); meta.seed: pick any integer; meta.designdna_precedents "
        "may be []. State real numbers (dimensions, flow rates, wall "
        "thicknesses) — never placeholders.\n\n"
        f"{_JSON_ONLY}\n\n"
        f"JSON SCHEMA:\n{schema_json}\n\n"
        f"CLIENT BRIEF:\n{brief}\n\nRESEARCH CONTEXT:\n{research}"
        f"{CACHE_BREAK}"
        f"Produce ALTERNATIVE {alternative_no} of 3 now: "
        f"meta.alternative_no is {alternative_no}. Make this alternative "
        "genuinely distinct in concept from a typical first answer."
    )


def designer_reask_suffix(errors: list[str]) -> str:
    return (
        "\n\nYour previous reply FAILED validation. Fix it and resend the "
        "complete corrected JSON object only. Validation errors:\n- "
        + "\n- ".join(errors)
    )


def _session_context(brief: str, candidates_summary: str) -> str:
    """Shared context prefix for the post-designer roles — byte-identical
    across geometrist/engineer/critic/arbiter calls so it can be a cache
    prefix (ADR-024)."""
    return (
        f"CLIENT BRIEF:\n{brief}\n\n"
        f"CANDIDATE DESIGN SPECS (digest):\n{candidates_summary}"
        f"{CACHE_BREAK}"
    )


def geometrist_prompt(brief: str, candidates_summary: str) -> str:
    return (
        _session_context(brief, candidates_summary)
        + "You are the GEOMETRIST of the LuxuryForm design council. For each "
        "Design Spec candidate above, give a feasibility pass: can the "
        "geometry kernel plausibly build it (primitive coverage, wall "
        "thickness vs material minimums, overhangs, assembly)? Flag any "
        "candidate that must be simplified, with the specific parameters. "
        "Plain prose, one short paragraph per candidate."
    )


def engineer_prompt(brief: str, candidates_summary: str,
                    geometrist_notes: str) -> str:
    return (
        _session_context(brief, candidates_summary)
        + "You are the ENGINEER of the LuxuryForm design council. Write an "
        "engineering review of the Design Spec candidates above: structure "
        "(loads, overturning, foundation), hydraulics (pump head, flow, "
        "nozzle sizing), fabrication (material process fit). Give every "
        "verdict with real numbers. Respond with a JSON object: "
        '{"summary": str, "per_spec": [{"spec_id": str, "verdict": '
        '"pass"|"pass_with_notes"|"fail", "notes": str}]}.\n\n'
        f"{_JSON_ONLY}\n\nGEOMETRIST NOTES:\n{geometrist_notes}"
    )


def critic_prompt(brief: str, candidates_summary: str,
                  engineering_review: str) -> str:
    return (
        _session_context(brief, candidates_summary)
        + "You are the CRITIC of the LuxuryForm design council. Produce the "
        "defect list for the Design Spec candidates above. Every defect: "
        "unique id, severity (minor|major|fatal), the spec_id it applies "
        "to, and a concrete description with real numbers. Find real "
        "defects — an empty list is a failed review. Respond with a JSON "
        'object: {"defects": [{"id": str, "severity": str, "spec_id": str, '
        '"defect": str}]}.\n\n'
        f"{_JSON_ONLY}\n\nENGINEERING REVIEW:\n{engineering_review}"
    )


def arbiter_prompt(brief: str, candidates_summary: str,
                   engineering_review: str, defect_list: str) -> str:
    return (
        _session_context(brief, candidates_summary)
        + "You are the ARBITER of the LuxuryForm design council. Your decision "
        "is BINDING. From the Design Spec candidates below, choose EXACTLY 3 "
        "DISTINCT specs (pairwise different designs, not near-duplicates), "
        "ranked best-first. Rank 1 is the design the geometry engine will "
        "build. Respond with a JSON object: {\"chosen_spec_ids\": [3 spec_id "
        'strings, ranked], "confidence": number 0..1, "rationale": str, '
        '"disagreement_register": [{"topic": str, "positions": object, '
        '"resolution": str}], "stated_differences": {spec_id: str}}. '
        "Surface material disagreements between the reviews in the register "
        "— never average them away.\n\n"
        f"{_JSON_ONLY}\n\n"
        f"ENGINEERING REVIEW:\n{engineering_review}\n\n"
        f"DEFECT LIST:\n{defect_list}"
    )


def arbiter_reask_suffix(errors: list[str]) -> str:
    return (
        "\n\nYour previous reply was not a valid binding decision. Resend "
        "the complete corrected JSON object only. Problems:\n- "
        + "\n- ".join(errors)
    )


def candidates_summary(specs: list[dict]) -> str:
    """Compact per-candidate digest for downstream roles (full JSON would
    blow the context; the persisted rows carry the full specs)."""
    parts = []
    for s in specs:
        meta = s["meta"]
        parts.append(
            f"- spec_id={meta['spec_id']} provider={meta.get('provider')} "
            f"alternative_no={meta.get('alternative_no')} "
            f"concept={s.get('form_language', {}).get('concept', '?')!r} "
            f"elements={len(s.get('massing', {}).get('elements', []))}"
        )
    return "\n".join(parts)
