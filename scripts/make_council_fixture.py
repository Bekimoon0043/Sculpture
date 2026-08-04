"""Regenerate tests/fixtures/council_session_v1.json (SYNTHETIC Council fixture).

Run from the repo root with the backend environment active:

    python scripts/make_council_fixture.py

The fixture is hand-authored synthetic data (Phase 3 build step 1): it exists
so the replay pipeline and the $0 offline gate can be developed before any
live Council session has run. Build step 4 replaces/augments it with the
captured first live session. NEVER hand-edit the fixture without re-running
this script — replay recomputes canonical spec hashes and fails loudly on a
stale recorded hash (that check is deliberate).
"""

import sys, copy, json, uuid, hashlib
import pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from tests.test_design_spec_schema import valid_example_spec

def canonical(spec):
    content = {k: v for k, v in spec.items() if k != "meta"}
    meta = {k: v for k, v in spec.get("meta", {}).items() if k != "spec_hash"}
    content["meta"] = meta
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

base = valid_example_spec()
specs = []
variants = [
    ("anthropic", 1, 42, "Monumental abstracted lotus rising from a still basin", 6.0),
    ("openai",    2, 77, "Interlocking basalt monolith ring with central jet", 5.2),
    ("anthropic", 3, 103, "Folded 316L ribbon cascade over a stepped plinth", 6.8),
]
for provider, alt, seed, concept, dia in variants:
    s = copy.deepcopy(base)
    s["meta"]["spec_id"] = str(uuid.uuid4())
    s["meta"]["provider"] = provider
    s["meta"]["alternative_no"] = alt
    s["meta"]["seed"] = seed
    s["form_language"]["concept"] = concept
    s["massing"]["elements"][0]["parameters"]["diameter"]["value"] = dia
    s["meta"]["spec_hash"] = "sha256:" + canonical(s)
    specs.append(s)

spec_ids = [s["meta"]["spec_id"] for s in specs]

session_id = str(uuid.uuid4())
T0 = "2026-08-04T10:00:00+00:00"

def call(role, side, provider, model, tin, tout, ms, resp):
    return {
        "id": str(uuid.uuid4()), "role": role, "side": side,
        "provider": provider, "model": model, "ts": T0,
        "prompt": f"[{role} prompt — synthetic fixture text]",
        "response": resp,
        "tokens_in": tin, "tokens_out": tout, "latency_ms": ms,
        "status": "ok", "error": None,
    }

calls = [
    call("researcher", "primary", "kimi", "kimi-k3", 4200, 9800, 41200.0,
         "Site and precedent research digest (synthetic)."),
    call("researcher", "parallel", "openai", "gpt-4o", 4200, 2100, 8300.0,
         "Site and precedent research digest, second opinion (synthetic)."),
]
for i, s in enumerate(specs):
    calls.append(call("designer", "primary", "anthropic", "claude-sonnet-4-5",
                      6100 + i * 300, 3400, 15700.0,
                      f"Design Spec alternative {i+1} JSON (synthetic; persisted in design_specs)."))
    calls.append(call("designer", "parallel", "openai", "gpt-4o",
                      6100 + i * 300, 3200, 12400.0,
                      f"Design Spec alternative {i+1} critique-draft JSON (synthetic)."))
calls += [
    call("geometrist", "primary", "anthropic", "claude-sonnet-4-5", 9400, 2600, 13100.0,
         "All six candidates validated against design_spec_v1.json; three shortlisted (synthetic)."),
    call("geometrist", "parallel", "kimi", "kimi-k3", 9400, 8100, 38600.0,
         "Independent schema + fabricability check, concurring with reservations (synthetic)."),
    call("engineer", "primary", "openai", "gpt-4o", 11200, 2900, 14900.0,
         "Hydraulic/structural review of the three bound specs (synthetic)."),
    call("engineer", "parallel", "anthropic", "claude-sonnet-4-5", 11200, 2700, 16200.0,
         "Independent engineering review, flags pump head margin on alt 3 (synthetic)."),
    call("critic", "primary", "openai", "gpt-4o", 12800, 2400, 11800.0,
         "Defect list: 7 defects across the three specs, none fatal (synthetic)."),
    call("critic", "parallel", "kimi", "kimi-k3", 12800, 7600, 35400.0,
         "Independent defect list, adds maintenance-access defect on alt 2 (synthetic)."),
    call("arbiter", "primary", "openai", "gpt-4o", 15600, 3100, 17400.0,
         "Binding decision: rank alt 1 > alt 3 > alt 2, confidence 0.78 (synthetic)."),
    call("arbiter", "parallel", "anthropic", "claude-sonnet-4-5", 15600, 2900, 16800.0,
         "Concurrence with ranking; registers disagreement on alt 2 maintainability (synthetic)."),
]

fixture = {
    "fixture_version": "1.0.0",
    "synthetic": True,
    "note": ("SYNTHETIC hand-authored fixture (Phase 3 build step 1) — used to "
             "develop the replay pipeline and offline gate at $0 before any live "
             "session exists. Replaced/augmented by the captured first live "
             "session at build step 4. Prompt/response bodies are placeholders; "
             "token counts are realistic-order synthetic values. Costs are NOT "
             "recorded here: replay recomputes them from tokens x pricing.yaml."),
    "session": {
        "id": session_id,
        "brief_text": ("A monumental fountain for a roundabout in Hawassa: "
                       "Ethiopian lotus motif, basalt and bronze, visible by "
                       "night, maintainable by a two-person crew."),
        "started_at": T0,
        "ended_at": "2026-08-04T10:06:30+00:00",
        "degraded": 0,
    },
    "calls": calls,
    "design_specs": [{"spec": s} for s in specs],
    "engineering_reviews": [
        {"id": str(uuid.uuid4()), "provider": "openai", "side": "primary",
         "payload": {
             "summary": "All three specs are buildable; alt 3 pump head margin is thin.",
             "per_spec": [
                 {"spec_id": spec_ids[0], "verdict": "pass",
                  "notes": "Lotus cascade hydraulics within envelope; basin wall 3mm ok in 316L."},
                 {"spec_id": spec_ids[1], "verdict": "pass_with_notes",
                  "notes": "Basalt monolith ring needs foundation check; jet nozzle access poor."},
                 {"spec_id": spec_ids[2], "verdict": "pass_with_notes",
                  "notes": "Ribbon cascade: specify pump with >=20% head margin."},
             ],
         }},
        {"id": str(uuid.uuid4()), "provider": "anthropic", "side": "parallel",
         "payload": {
             "summary": "Concurs with primary; adds seismic note for the monolith ring.",
             "per_spec": [
                 {"spec_id": spec_ids[0], "verdict": "pass", "notes": "Concur."},
                 {"spec_id": spec_ids[1], "verdict": "pass_with_notes",
                  "notes": "Add seismic overturning check; Hawassa is low-risk but non-zero."},
                 {"spec_id": spec_ids[2], "verdict": "pass", "notes": "Head margin note accepted."},
             ],
         }},
    ],
    "defect_lists": [
        {"id": str(uuid.uuid4()), "provider": "openai", "side": "primary",
         "payload": {
             "defects": [
                 {"id": "D1", "severity": "major", "spec_id": spec_ids[2],
                  "defect": "Pump head margin under 10% — undersized for dry-season flow."},
                 {"id": "D2", "severity": "minor", "spec_id": spec_ids[1],
                  "defect": "Jet nozzle not reachable without draining basin."},
                 {"id": "D3", "severity": "minor", "spec_id": spec_ids[0],
                  "defect": "Night lighting glare toward traffic not addressed."},
             ],
         }},
        {"id": str(uuid.uuid4()), "provider": "kimi", "side": "parallel",
         "payload": {
             "defects": [
                 {"id": "D4", "severity": "major", "spec_id": spec_ids[1],
                  "defect": "Maintenance access to ring interior not shown."},
                 {"id": "D5", "severity": "minor", "spec_id": spec_ids[2],
                  "defect": "Ribbon edge sharpness vs public contact not resolved."},
             ],
         }},
    ],
    "arbiter_decision": {
        "id": str(uuid.uuid4()),
        "chosen_spec_ids": [spec_ids[0], spec_ids[2], spec_ids[1]],
        "confidence": 0.78,
        "rationale": ("Alternative 1 (lotus) is the strongest cultural and "
                      "hydraulic fit with zero major defects. Alternative 3 "
                      "follows contingent on the pump up-spec. Alternative 2 "
                      "is retained third: two majors (maintenance access, "
                      "nozzle reachability) are both fixable in detailing."),
        "disagreement_register": [
            {"topic": "Alt 2 maintainability",
             "positions": {"openai": "two majors, fixable in detailing",
                           "anthropic": "maintenance access is a concept-level flaw"},
             "resolution": "recorded; ranked third, not rejected"},
            {"topic": "Alt 3 pump margin",
             "positions": {"engineer-openai": "thin margin", "engineer-anthropic": "acceptable with up-spec"},
             "resolution": "binding condition: >=20% head margin"},
        ],
    },
}

out = str(REPO_ROOT / "tests" / "fixtures" / "council_session_v1.json")
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(fixture, open(out, "w"), indent=2, ensure_ascii=False)
print("fixture written;", len(calls), "calls;", len(specs), "specs; session", session_id)

# self-check: validate specs against the schema
import jsonschema
schema = json.load(open(REPO_ROOT / "schemas" / "design_spec_v1.json"))
for s in specs:
    jsonschema.validate(instance=s, schema=schema)
print("all 3 specs validate against design_spec_v1.json")
