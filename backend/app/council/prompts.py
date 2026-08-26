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


def primitive_index_surface() -> str:
    """Live Phase 6 primitive index for Designer/Geometrist prompts.

    The schema intentionally leaves massing.elements[].primitive as a string:
    the LIVE registry is the source of truth for what can be fabricated in
    this checkout. Keeping this text generated from PRIMITIVES preserves the
    anti-drift property ADR-026 depends on.
    """
    from app.geometry.registry import PRIMITIVES

    lines = ["LIVE PRIMITIVE INDEX - choose ONLY these primitive ids:"]
    for primitive_id, module in sorted(PRIMITIVES.items()):
        accepts = []
        if getattr(module, "CAN_PARENT_STACK", False):
            accepts.append("can parent stack_on")
        if getattr(module, "CAN_PARENT_INSERT", False):
            accepts.append("can parent concentric_insert")
        accepts_text = ", ".join(accepts) if accepts else "cannot parent children"
        lines.append(f"- {primitive_id}: {module.PURPOSE}; {accepts_text}")
    lines.append(
        "If the brief needs a shape not listed here, approximate it with the "
        "listed primitives or state the limitation in assumptions; do not "
        "invent a primitive id."
    )
    return "\n".join(lines)


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
        f"{primitive_index_surface()}\n\n"
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


# ---------------------------------------------------------------------------
# Phase 4 — GEOMETRIST code generation (the fabrication stage)
# ---------------------------------------------------------------------------

def registry_surface(used_primitives=None) -> str:
    """The fabrication API documentation embedded in every code-gen prompt.

    Generated from the LIVE registry so the prompt can never drift from the
    code (Phase 6 widens the vocabulary by editing registry.py — this text
    follows automatically).

    Two-tier (slice A2, plan §3): the INDEX always lists every primitive;
    full parameter tables are emitted only for ``used_primitives`` — the
    ids the Design Spec names, computed in code, never chosen by the model.
    With no usable selection (None, empty, or only unknown/legacy names)
    the FULL surface is emitted, so cascade fabrications and pre-A2
    callers are unchanged. Deterministic for a given selection: the same
    spec produces byte-identical surface text on every attempt (ADR-024's
    static prefix within a fabrication run).
    """
    from app.geometry.registry import CASCADE_PARAMETERS, PRIMITIVES

    detail_ids = sorted(set(used_primitives or ()) & set(PRIMITIVES))
    if not detail_ids:
        detail_ids = sorted(PRIMITIVES)
    cascade_detail = "tiered_cascade" in detail_ids

    lines = [
        "FABRICATION API (module `registry` — the ONLY geometry vocabulary "
        "you may use):",
        "",
        "  solid, validated = registry.cascade_fountain(params: dict, "
        "seed: int = 0)",
        "    Builds the tiered-cascade fountain primitive: round base basin,",
        "    central column with plumbing bore, N stacked dishes — ONE",
        "    watertight fused solid. Raises ConstraintViolation listing",
        "    EVERY violated range/constraint with real numbers.",
        "",
        "  solid, manifest = registry.assemble(elements: list[dict], "
        "seed: int = 0, fabrication: dict | None = None)",
        "    Builds a Phase 6 assembly from declared primitive elements.",
        "    The program DECLARES elements and joints; trusted registry code",
        "    performs every placement and boolean. Returns ONE watertight",
        "    fused solid plus an assembly_manifest_v1 dict with per-element",
        "    mass, joints, volume conservation, fabrication limits, and",
        "    body_count_brep.",
        "",
        "  elements = registry.assembly_plan_from_spec(spec)",
        "    Trusted Slice A1 mapper: converts Design Spec massing.elements",
        "    into the assembly plan shape above, including dimension-object",
        "    unit conversion, parameter aliases and parent_id -> joint type.",
        "",
        "  fabrication = registry.fabrication_limits_from_spec(spec)",
        "    Extracts max_lift_kg and scalar max_module_m from the Design",
        "    Spec fabrication limits for registry.assemble.",
        "",
        "PRIMITIVE INDEX (live registry):",
    ]
    for primitive_id, module in sorted(PRIMITIVES.items()):
        accepts = []
        if getattr(module, "CAN_PARENT_STACK", False):
            accepts.append("stack_on parent")
        if getattr(module, "CAN_PARENT_INSERT", False):
            accepts.append("concentric_insert parent")
        accepts_text = ", ".join(accepts) if accepts else "cannot parent children"
        lines.append(
            f"  {primitive_id}: {module.PURPOSE}; accepts {accepts_text}; "
            f"{len(module.PARAMETERS)} parameters"
        )
    lines += [
        "",
        "ASSEMBLY PLAN SHAPE:",
        "  elements is a list of dicts. Each element has:",
        "    element_id: unique string; fuse order is sorted by this id",
        "    primitive: one of the live registry ids above",
        "    parameters: dict validated by that primitive's table below",
        "    joint: absent on exactly one root element; otherwise:",
        "      {\"type\": \"stack_on\"|\"concentric_insert\", "
        "\"parent\": element_id, \"overlap_mm\": optional}",
        "  stack_on: child base stands on parent top face and sinks overlap",
        "    into it. Use for basin_on_plinth, sculpture_on_plinth, etc.",
        "  concentric_insert: child shares a basin's axis and stands on the",
        "    basin floor, sunk by overlap. In slice A1 only basin_round",
        "    accepts inserts.",
        "  Omit overlap_mm unless the spec needs a larger interference; the",
        "    assembler uses the material joint-overlap floor. Never use 0.",
        "  Pass fabrication={\"max_lift_kg\": spec[\"fabrication\"]"
        "[\"max_lift_kg\"], \"max_module_m\": spec[\"fabrication\"]"
        "[\"max_module_m\"]} when those keys exist so crane/module limits",
        "    bind per element with real numbers.",
        "",
        "ASSEMBLY RETURN CONTRACT:",
        "  For an assembly, call registry.assembly_plan_from_spec(spec), then",
        "  registry.assemble(elements, seed=seed, fabrication=fabrication).",
        "  Return solid, manifest, seed. The runner carries the manifest as",
        "  params, so validation/costing can see the real",
        "  material_id, per-element mass and fabrication limit evidence.",
        "",
        "PARAMETERS (all keys optional except as constrained; omit to use "
        "the default; detailed below for the primitives THIS spec uses — "
        "the index above lists everything):",
    ]
    if cascade_detail:
        for name, spec in CASCADE_PARAMETERS.items():
            rng = ""
            if spec.get("min") is not None or spec.get("max") is not None:
                rng = f" [{spec['min']}..{spec['max']}]"
            lines.append(
                f"  {name} ({spec['type']}, {spec['unit']}, default "
                f"{spec['default']}{rng}) — {spec['notes']}"
            )
    for primitive_id in detail_ids:
        if primitive_id == "tiered_cascade":
            continue
        module = PRIMITIVES[primitive_id]
        lines.append("")
        lines.append(f"  {primitive_id}:")
        for name, spec in module.PARAMETERS.items():
            rng = ""
            if spec.get("min") is not None or spec.get("max") is not None:
                rng = f" [{spec['min']}..{spec['max']}]"
            lines.append(
                f"    {name} ({spec['type']}, {spec['unit']}, default "
                f"{spec['default']}{rng}) - {spec['notes']}"
            )

    lines += [
        "",
        "HARD CONSTRAINTS (validated with real numbers; violations raise):",
        "  Assembly A. exactly ONE root element; every non-root has a joint",
        "  Assembly B. primitive ids must exist in the live registry",
        "  Assembly C. every declared joint must overlap by the material",
        "     joint floor or more; tangency/zero overlap is refused",
        "  Assembly D. non-joined elements must not intersect or touch",
        "  Assembly E. fused result must have body_count 1 and pass volume",
        "     conservation against declared joint intersections",
        "  Assembly F. max_lift_kg and max_module_m are checked per element",
        "  Assembly G. stack_on children must land on a REAL SEAT: the",
        "     radial bearing at the joint plane >= the material joint floor",
        "     (a lip narrower than the tolerance stack can vanish in",
        "     fabrication — e.g. a basin must not perch on a hollow",
        "     plinth's thin rim)",
    ]
    if cascade_detail:
        lines += [
            "  1. basin_diameter_mm >= widest_dish + 2*basin_wall_mm + "
            "min_clearance_mm",
            "     (widest_dish = tier_top_diameter_mm + (tiers-1)"
            "*tier_diameter_step_mm)",
            "  2. basin_wall_mm inside the material's WALL ENVELOPE below",
            "  3. lip_fillet_mm < dish_depth_mm / 2",
            "  4. column_diameter_mm >= bore_diameter_mm + 2*column_wall_mm",
            "     (column_wall_mm defaults to basin_wall_mm; set it "
            "independently — per-member walls, ADR-032)",
            "  5. lip_fillet_mm < basin_wall_mm",
            "  6. tier_spacing_mm >= dish_depth_mm",
            "  7. min_clearance_mm >= the material's CLEARANCE FLOOR below",
        ]
    lines += [
        "",
        "SLICE A1 WORKING COMPOSITION EXAMPLE:",
        "  elements = [",
        "    {\"element_id\": \"p1\", \"primitive\": \"plinth\",",
        "     \"parameters\": {\"top_diameter_mm\": 700, \"height_mm\": 300,",
        "                    \"material_id\": \"basalt_slab\"}},",
        "    {\"element_id\": \"b1\", \"primitive\": \"basin_round\",",
        "     \"parameters\": {\"diameter_mm\": 600, \"height_mm\": 300,",
        "                    \"wall_mm\": 25, \"floor_mm\": 60,",
        "                    \"material_id\": \"basalt_slab\"},",
        "     \"joint\": {\"type\": \"stack_on\", \"parent\": \"p1\"}},",
        "    {\"element_id\": \"c1\", \"primitive\": \"sculptural_column\",",
        "     \"parameters\": {\"diameter_mm\": 100, \"height_mm\": 400,",
        "                    \"material_id\": \"basalt_slab\"},",
        "     \"joint\": {\"type\": \"concentric_insert\", \"parent\": \"b1\"}},",
        "  ]",
        "  solid, manifest = registry.assemble(elements, seed=seed,",
        "      fabrication=fabrication_limits)",
        "  Prefer the trusted mapper in generated programs:",
        "      elements = registry.assembly_plan_from_spec(spec)",
        "      fabrication_limits = registry.fabrication_limits_from_spec(spec)",
        "      solid, manifest = registry.assemble(elements, seed=seed,",
        "          fabrication=fabrication_limits)",
    ]
    if cascade_detail:
        lines += [
            "",
            "UNITS AND SOLVING ORDER — read this before choosing numbers:",
            "  * min_clearance_mm is DIAMETRAL: the physical radial gap between",
            "    the widest dish rim and the basin inner wall is HALF of it.",
            "  * Constraint 1 is satisfied EXACTLY at equality, and equality at",
            "    clearance 0 means the dish rim TOUCHES the basin wall. That",
            "    fuses to a solid that is not watertight and the build is",
            "    rejected. Never drive min_clearance_mm down to make constraint",
            "    1 fit: it has a hard per-material floor (constraint 7).",
            "  * When the basin diameter is fixed by the brief, constraint 1",
            "    binds the DISHES, not the clearance. Solve it in this order:",
            "      widest_dish <= basin_diameter_mm - 2*basin_wall_mm"
            " - min_clearance_mm",
            "    then pick tier_top_diameter_mm and tier_diameter_step_mm so",
            "    that tier_top + (tiers-1)*step lands at or under that number.",
        ]
    lines += [
        "",
        "MATERIAL ENVELOPES (materials.yaml — ADR-027 walls, ADR-029 "
        "clearance floors):",
    ]
    from app.core.config import load_config_bundle

    for mat_id, mat in sorted(
        load_config_bundle().materials.materials.items()
    ):
        lines.append(
            f"  {mat_id} ({mat.name}): basin_wall_mm {mat.min_wall_mm:g}.."
            f"{mat.max_wall_mm:g} mm | min_clearance_mm >= "
            f"{mat.min_clearance_mm:g} mm "
            f"({mat.min_clearance_mm / 2:g} mm radial)"
        )
    return "\n".join(lines)


_PROGRAM_CONTRACT = """PROGRAM CONTRACT (the sandbox runner enforces it exactly):
  * Define ONE top-level function: def build(spec):  — spec is the Design
    Spec dict below; return (solid, params_dict, seed).
  * You may import ONLY: registry, math. (build123d is NOT importable —
    all geometry goes through the registry's primitives, ADR-030.)
  * You may NOT: open files, use eval/exec/getattr/__import__, access any
    attribute starting with '_', or export files yourself (the runner owns
    export — STEP and GLB are produced for you).
  * Derive the cascade parameters from the Design Spec's stated dimensions
    and material. State REAL numbers within the registry ranges — the
    primitive validates and tells you every violation with real numbers.
  * If the Design Spec needs multiple massing.elements, declare an assembly
    plan with registry.assembly_plan_from_spec(spec), then call
    registry.assemble. The model never fuses; registry code does every
    boolean.
  * For an assembly, return (solid, manifest, seed), where manifest is the
    assembly_manifest_v1 dict returned by registry.assemble.
  * seed: use spec["meta"]["seed"].
"""


def fabrication_prompt(
    spec_json: str,
    failure_history: list[str] | None = None,
    used_primitives=None,
) -> str:
    """GEOMETRIST code-generation prompt. Static prefix first (ADR-024):
    API surface + contract are identical across every attempt of one
    fabrication run (the selection depends only on the spec), so repair
    attempts read the prefix from cache; two runs over specs with
    different primitive vocabularies have different prefixes by design
    (slice A2 two-tier surface). The spec and repair history ride after
    the cache break.

    ``failure_history`` carries EVERY prior attempt's failure digest,
    oldest first (live-run defect 2026-08-10: with only the LAST digest the
    model repeated attempt 1's rejected value on attempt 3). The prompt
    states explicitly that a previously-failed value must not be repeated.
    """
    prompt = (
        "You are the GEOMETRIST of the LuxuryForm design council, writing "
        "fabrication code. Translate the Design Spec below into a Python "
        "program that builds the geometry using ONLY the fabrication API. "
        "Respond with ONLY the Python program — no markdown fences, no "
        "prose. The first line must be code or a comment.\n\n"
        f"{registry_surface(used_primitives)}\n\n{_PROGRAM_CONTRACT}"
        f"{CACHE_BREAK}"
        f"DESIGN SPEC (JSON):\n{spec_json}"
    )
    if failure_history:
        prompt += (
            "\n\nYour PREVIOUS attempt(s) FAILED. FULL failure history, "
            "oldest first:"
        )
        for i, digest in enumerate(failure_history, 1):
            prompt += f"\n--- ATTEMPT {i} FAILED ---\n{digest}"
        prompt += (
            "\n\nA previously-failed value must NOT be repeated: every "
            "parameter value named in the failures above has already been "
            "tried and rejected, so do not resubmit any of them. Correct "
            "the root cause of the LATEST failure while staying clear of "
            "every earlier failure; do not work around the rules above."
        )
    return prompt


def vision_critique_prompt(
    spec_summary: str,
    round_no: int,
    tunable: dict[str, tuple[float, float]] | None = None,
    current: dict[str, float] | None = None,
    unit: str = "mm",
) -> str:
    """Vision critique prompt (Phase 5).

    Images are sent alongside this prompt via the provider's vision API.  The
    response must be strict JSON with bounded deltas only; prose that cannot be
    expressed as a delta goes into observations.

    ``tunable`` (path -> (min, max)) and ``current`` (path -> value) are
    OPTIONAL, but a live run should always pass them.  Without them the model
    has only the prose spec summary to infer parameter names from, and two
    models inventing two different names for the same dimension is a
    disagreement consensus cannot resolve — the loop then reads a round in
    which both models saw the same problem as "no change proposed".  Naming
    the exact allowed paths, their current values and their validated ranges
    is the single biggest lever on whether a live round produces a usable
    delta.
    """
    allow_block = ""
    if tunable:
        lines = []
        for path in sorted(tunable):
            lo, hi = tunable[path]
            now = (current or {}).get(path)
            now_txt = f"currently {now:g}{unit}, " if now is not None else ""
            lines.append(f"  {path}  ({now_txt}allowed {lo:g}..{hi:g}{unit})")
        allow_block = (
            "PARAMETER PATHS YOU MAY USE — these are the ONLY valid values "
            "for parameter_path.\nCopy one of these strings EXACTLY, "
            "character for character.  A path that is\nnot in this list is "
            "discarded, which wastes the round:\n"
            + "\n".join(lines)
            + f"\n\nEvery magnitude is in {unit}.  Do NOT convert to metres.\n\n"
        )

    return (
        "You are a VISUAL CRITIC for LuxuryForm Studio.  The image is a "
        "single contact sheet showing FOUR labelled views of the SAME "
        "fountain design (FRONT, SIDE, TOP, THREE QUARTER).  Judge it as one "
        "design seen four ways, and propose concrete, bounded parameter "
        "changes that improve proportion, silhouette and composition.  You "
        "may ONLY suggest changes to the registered parameter paths.\n\n"
        f"DESIGN SPEC SUMMARY (ROUND {round_no}):\n{spec_summary}\n\n"
        + allow_block +
        "Respond with ONLY a single JSON object.  No markdown fences, no "
        "prose outside the JSON.  The FIRST character of your reply must be '{'.\n\n"
        "JSON schema:\n"
        '{\n'
        '  "observations": ["string"],  // prose that cannot be a delta\n'
        '  "deltas": [\n'
        '    {\n'
        '      "parameter_path": "<copy one EXACTLY from the list above>",\n'
        '      "direction": "increase" | "decrease" | "set",\n'
        '      "magnitude": 120,  // number; for direction=set this is the new value\n'
        '      "unit": "mm"\n'
        '      "reason": "short reason"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "Rules:\n"
        "- Each delta must name ONE existing parameter_path from the spec.\n"
        "- Direction is relative to the CURRENT value: increase/decrease by "
        "the magnitude, or set to the magnitude.\n"
        "- Magnitudes must be small (annealing: the allowed step shrinks each "
        "round).  Round 1: ~10% of the parameter's validated range; later "
        "rounds: smaller.\n"
        "- If you cannot express a visual concern as a bounded delta, put it "
        "in observations and do NOT invent a parameter.\n"
        "- You may NOT judge engineering facts (stress, hydraulics, "
        "fabrication) — only proportion, silhouette and composition.\n"
        "- No code, no new primitive names, no parameter paths not in the spec."
    )


def extract_program(text: str) -> str:
    """Strip markdown fences / leading prose from a model reply.

    The instruction says code-only, but models fence anyway — accept
    ```python ... ``` blocks and bare code alike.
    """
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        # first fenced block (drop the language tag line if present)
        block = parts[1]
        if "\n" in block:
            first, rest = block.split("\n", 1)
            block = rest if first.strip().isalpha() else block
        return block.strip()
    return t
