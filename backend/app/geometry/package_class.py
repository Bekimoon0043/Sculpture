"""LF-103A — package classification: CLEAN / PRE-FABRICATION / REFUSED.

The export boundary's verdict engine (ADR-062 amendment 2, ADR-063). Three
rules govern everything here:

1. **Persisted evidence only.** Classification is a pure function of the
   gate reports stored at validation time. It never re-reads
   `config/gate_profiles.yaml` — re-reading would evaluate today's signing
   state against yesterday's verdict and silently launder an unwarranted
   package the moment an operator flips `signed_off: true`.
2. **Fail closed.** Absent, empty, duplicate-ambiguous, mixed-profile,
   unsigned or identity-less evidence is PRE-FABRICATION — never CLEAN.
   `worst_status([]) == "pass"` is the trap this module exists to disarm.
3. **CLEAN is builder/test-only until the validation-run identity debt
   closes** (LF-103A final condition 1): CLEAN additionally requires every
   layered report to carry one shared `validation_basis` identity, which
   no production row has today. LF-102 must not make CLEAN reachable
   before that identity exists.

This module lives in the geometry layer, not in a router, so the builder
(`luxexchange.py`) and the API can share it without circular imports
(final condition 3).
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CLASS_CLEAN = "clean"
CLASS_PRE_FABRICATION = "pre_fabrication"
CLASS_REFUSED = "refused"
#: A sealed package whose manifest carries no valid class. Never served as
#: clean; download refuses with the one re-export action. Bytes untouched.
LEGACY_UNCLASSIFIED = "legacy_unclassified"

#: The only values a sealed manifest may carry. Anything else — missing,
#: invalid, unreadable, contradictory — is LEGACY_UNCLASSIFIED.
KNOWN_SEALED_CLASSES = frozenset({CLASS_CLEAN, CLASS_PRE_FABRICATION})

#: Formats a workshop can machine or cut from. Raw STEP is fabrication-
#: capable — it is never "just a viewing artifact" (owner ruling,
#: 2026-09-01). Mesh-tier files (GLB/OBJ/PLY) are triangulated
#: approximations and remain downloadable as marked diagnostics.
FABRICATION_CAPABLE_FORMATS = frozenset({"STEP", "BREP", "STL", "DXF", "SVG"})

#: The evidence a design must carry. The mesh evidence accepts exactly one
#: row: `assembly_mesh` preferred, legacy `mesh` as compatibility alias.
REQUIRED_LAYERED_GATES = ("structure_static_v1", "hydraulics", "fabrication")
MESH_GATE = "assembly_mesh"
LEGACY_MESH_GATE = "mesh"

#: FF-A1 (ADR-065): the only names a manifest's persisted
#: required_validation_gates snapshot may carry today. An unknown
#: required name fails closed at classification — it can never have
#: passing evidence.
KNOWN_REQUIRED_GATES = frozenset({"freeform_integrity_v1"})

_KNOWN_STATUSES = frozenset({"pass", "warn", "fail", "needs_input"})

_ENTRY_MARK = "PRE-FABRICATION"
_DIAGNOSTIC_MARK = "DIAGNOSTIC-NOT-FOR-FABRICATION"


class PackageRefused(RuntimeError):
    """Raised by the package builder itself when the verdict is REFUSED —
    the internal-call bypass is closed at the seal, not only at the route."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = list(reasons)
        super().__init__(
            "fabrication package refused: validation FAILED — "
            + "; ".join(self.reasons[:5])
        )


# ---------------------------------------------------------------------------
# Role ownership — a documented deterministic mapping, never free-text
# parsing (LF-103A final condition 5). Vocabulary = the B-8 approver roles.
# First match wins; the fallback never invents a discipline.
# ---------------------------------------------------------------------------

_ROLE_MAP: tuple[tuple[str, str, str], ...] = (
    # (gate_name, check substring, role)
    ("structure_static_v1", "ground_bearing",
     "geotechnical survey + structural engineer"),
    ("structure_static_v1", "", "structural engineer"),
    ("hydraulics", "", "MEP/fountain engineer"),
    ("fabrication", "rigging", "rigging reviewer"),
    ("fabrication", "", "workshop/fabricator"),
    (MESH_GATE, "", "structural engineer"),
    (LEGACY_MESH_GATE, "", "structural engineer"),
)

_ROLE_FALLBACK = "qualified professional review required"


def role_for(gate_name: str, check: str) -> str:
    """The professional who owns one unresolved check. Deterministic table
    lookup; an unknown gate/check yields the fallback, never a guess."""
    for gate, needle, role in _ROLE_MAP:
        if gate_name == gate and (needle == "" or needle in check):
            return role
    return _ROLE_FALLBACK


# ---------------------------------------------------------------------------
# Deterministic row selection
# ---------------------------------------------------------------------------

def select_reports(
    rows: list[tuple[str, str, str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """One report per gate from raw (gate_name, created_at, id, report) rows.

    Duplicates resolve by `created_at DESC, id DESC` — explicitly, because
    the DB has no uniqueness constraint and dict-collapse order would be
    undefined. If both `assembly_mesh` and legacy `mesh` exist, the modern
    row wins and the alias is dropped.
    """
    picked: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for gate_name, created_at, row_id, report in rows:
        key = (str(created_at), str(row_id))
        current = picked.get(gate_name)
        if current is None or key > (current[0], current[1]):
            picked[gate_name] = (str(created_at), str(row_id), report)
    reports = {name: entry[2] for name, entry in picked.items()}
    if MESH_GATE in reports and LEGACY_MESH_GATE in reports:
        del reports[LEGACY_MESH_GATE]
    return reports


# ---------------------------------------------------------------------------
# Status of one stored report — the _row_status ladder, never inventing pass
# ---------------------------------------------------------------------------

def report_status(gate_name: str, report: dict[str, Any]) -> str:
    if not isinstance(report, dict):
        return "needs_input"
    status = report.get("status")
    if status in _KNOWN_STATUSES:
        return str(status)
    # A mesh report: `passed` there really is a two-state verdict.
    if report.get("schema") is None and "watertight" in report and isinstance(
            report.get("passed"), bool):
        return "pass" if report["passed"] else "fail"
    return "needs_input"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass
class Classification:
    package_class: str
    reasons: list[str] = field(default_factory=list)
    #: Every check with status != pass, plus synthesized rows for missing
    #: evidence — the exact content of ENGINEERING_WARRANT.txt.
    warrant_rows: list[dict[str, Any]] = field(default_factory=list)
    gate_statuses: dict[str, str] = field(default_factory=dict)


def _mesh_report(reports: dict[str, Any]) -> tuple[str | None, Any]:
    if MESH_GATE in reports:
        return MESH_GATE, reports[MESH_GATE]
    if LEGACY_MESH_GATE in reports:
        return LEGACY_MESH_GATE, reports[LEGACY_MESH_GATE]
    return None, None


def classify_reports(
    reports: dict[str, dict[str, Any]],
    *,
    geometry_hash_matches: bool | None = None,
    required_validation_gates: tuple[str, ...] | list[str] = (),
) -> Classification:
    """Classify a design's persisted evidence.

    `geometry_hash_matches`: whether the sha256 of the STEP being sealed
    equals the design's persisted geometry_hash. `None` means "not
    verified", which — like everything unproven here — caps at
    PRE-FABRICATION (validation rows carry no cryptographic run identity;
    see the module docstring and ADR-063).

    `required_validation_gates` (FF-A1, ADR-065): the PERSISTED
    applicability snapshot from the design's assembly manifest — never
    today's registry or config. For every gate named here, a MISSING,
    FAILED or INDETERMINATE row REFUSES (owner ruling 2026-09-03): a
    marked PRE-FABRICATION package of possibly self-intersecting CAD is
    still CAD in a workshop's hands. An unknown or malformed required
    name can never have passing evidence, so it refuses too. Legacy
    manifests carry no snapshot and are untouched by this parameter.
    Its rows share the same structural run linkage — and the same D-24
    identity gap — as every other row; this parameter does not and must
    not make CLEAN reachable.
    """
    reasons: list[str] = []
    warrant: list[dict[str, Any]] = []
    statuses: dict[str, str] = {}

    reports = dict(reports or {})
    mesh_name, mesh = _mesh_report(reports)

    # -- extra required gates (persisted applicability, ADR-065) -----------
    extra_refusals: list[str] = []
    for gate in tuple(required_validation_gates or ()):
        if gate not in KNOWN_REQUIRED_GATES:
            statuses[gate] = "needs_input"
            extra_refusals.append(
                f"required validation gate {gate!r} is unknown or the "
                "persisted required_validation_gates snapshot is malformed "
                "— fails closed (ADR-065)")
            warrant.append(_missing_row(gate))
            continue
        report = reports.get(gate)
        if report is None:
            statuses[gate] = "needs_input"
            extra_refusals.append(
                f"{gate}: MISSING — this design's persisted manifest "
                "requires geometry-integrity evidence and none exists")
            warrant.append(_missing_row(gate))
            continue
        raw_status = report.get("status") if isinstance(report, dict) else None
        if raw_status == "pass":
            statuses[gate] = "pass"
            continue
        if raw_status == "fail":
            statuses[gate] = "fail"
            fail_rows = [r for r in _check_rows(gate, report)
                         if r.get("status") == "fail"]
            for row in fail_rows:
                warrant.append(row)
                extra_refusals.append(
                    f"{gate}: {row['check']} FAIL "
                    f"(value {row.get('value')}, limit {row.get('limit')} "
                    f"{row.get('units') or ''})".rstrip())
            if not fail_rows:
                extra_refusals.append(f"{gate}: FAIL")
            continue
        statuses[gate] = "needs_input"
        extra_refusals.append(
            f"{gate}: INDETERMINATE (status {raw_status!r}) — the "
            "integrity stack could not reach a verdict; fails closed "
            "(ADR-065)")
        for row in _check_rows(gate, report):
            if row.get("status") != "pass":
                warrant.append(row)
    if extra_refusals:
        return Classification(CLASS_REFUSED, extra_refusals, warrant,
                              statuses)

    # -- collect statuses; missing evidence is needs_input, never pass -----
    if mesh_name is None:
        statuses[MESH_GATE] = "needs_input"
        reasons.append(
            "no mesh validation evidence (assembly_mesh or legacy mesh) "
            "exists for this design")
        warrant.append(_missing_row(MESH_GATE))
    else:
        statuses[mesh_name] = report_status(mesh_name, mesh)

    layered: dict[str, dict[str, Any]] = {}
    for gate in REQUIRED_LAYERED_GATES:
        report = reports.get(gate)
        if report is None:
            statuses[gate] = "needs_input"
            reasons.append(f"no {gate} validation report exists for this design")
            warrant.append(_missing_row(gate))
            continue
        layered[gate] = report
        statuses[gate] = report_status(gate, report)

    # -- REFUSED: any fail anywhere ----------------------------------------
    failing = [g for g, s in statuses.items() if s == "fail"]
    if failing:
        for gate in failing:
            report = reports.get(gate) or {}
            for row in _check_rows(gate, report):
                if row.get("status") == "fail":
                    warrant.append(row)
                    # Name the check and its real numbers — a refusal that
                    # only says "FAIL" gives the operator nothing to fix.
                    reasons.append(
                        f"{gate}: {row['check']} FAIL "
                        f"(value {row.get('value')}, limit {row.get('limit')} "
                        f"{row.get('units') or ''})".rstrip())
        for gate in failing:
            if not any(r.startswith(f"{gate}: ") for r in reasons):
                reasons.append(f"{gate}: FAIL")
        return Classification(CLASS_REFUSED, reasons, warrant, statuses)

    # -- warrant rows: every non-pass check --------------------------------
    downgraded = False
    for gate, report in layered.items():
        for row in _check_rows(gate, report):
            if row.get("status") != "pass":
                warrant.append(row)
            if row.get("status") == "warn" and row.get("on_violation") == "fail":
                downgraded = True

    # -- CLEAN preconditions, all of them ----------------------------------
    clean = all(s == "pass" for s in statuses.values())
    if clean and len(layered) == len(REQUIRED_LAYERED_GATES):
        unsigned = [g for g, r in layered.items()
                    if r.get("profile_signed_off") is not True]
        profiles = {r.get("gate_profile_id") for r in layered.values()}
        versions = {r.get("gate_profiles_version") for r in layered.values()}
        bases = {r.get("validation_basis") for r in layered.values()}
        if unsigned:
            reasons.append(
                "gate profile not signed off at validation time for: "
                + ", ".join(sorted(unsigned)))
        if len(profiles) != 1 or None in profiles:
            reasons.append(
                f"validation evidence is not one coherent basis: mixed or "
                f"absent gate_profile_id {sorted(map(str, profiles))}")
        if len(versions) != 1 or None in versions:
            reasons.append(
                f"validation evidence is not one coherent basis: mixed or "
                f"absent gate_profiles_version {sorted(map(str, versions))}")
        if len(bases) != 1 or None in bases:
            reasons.append(
                "validation reports carry no shared validation-run identity "
                "(validation_basis) — CLEAN requires it and no production "
                "row has one yet (ADR-063; debt open)")
        if geometry_hash_matches is not True:
            reasons.append(
                "the STEP being sealed was not verified against the "
                "design's persisted geometry_hash")
        if downgraded:
            reasons.append(
                "at least one threshold breach was downgraded to warn by an "
                "unsigned profile")
        if not reasons:
            return Classification(CLASS_CLEAN, [], [], statuses)
    else:
        if not clean:
            reasons.extend(
                f"{g}: {s}" for g, s in sorted(statuses.items()) if s != "pass")
        if downgraded:
            reasons.append(
                "at least one threshold breach was downgraded to warn by an "
                "unsigned profile")

    return Classification(CLASS_PRE_FABRICATION, reasons, warrant, statuses)


def _check_rows(gate: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for check in report.get("checks") or []:
        if not isinstance(check, dict):
            continue
        rows.append({
            "gate": gate,
            "check": str(check.get("check", "")),
            "status": check.get("status"),
            "on_violation": check.get("on_violation"),
            "value": check.get("value"),
            "limit": check.get("limit"),
            "units": check.get("units"),
            "basis": check.get("basis"),
            "message": check.get("message"),
            "role": role_for(gate, str(check.get("check", ""))),
        })
    return rows


def _missing_row(gate: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "check": f"{gate}.report_present",
        "status": "needs_input",
        "on_violation": "fail",
        "value": None, "limit": None, "units": None,
        "basis": "LF-103A required-gate set (ADR-063)",
        "message": (
            f"no {gate} validation report exists for this design — run a "
            "full build so every gate is evaluated"),
        "role": role_for(gate, ""),
    }


# ---------------------------------------------------------------------------
# The warrant — deterministic bytes, a pure function of its inputs
# ---------------------------------------------------------------------------

def warrant_text(design_id: str, seed: int, result: Classification) -> str:
    """ENGINEERING_WARRANT.txt. No clock, no uuid, no unsorted dict —
    sealed into the byte-reproducible package."""
    lines = [
        "ENGINEERING WARRANT — PRE-FABRICATION PACKAGE",
        "=" * 60,
        f"design_id : {design_id}",
        f"seed      : {int(seed)}",
        f"class     : {result.package_class.upper()}",
        "",
        "This package is PRE-FABRICATION. It is NOT fabrication-ready and",
        "must not be built from. Every geometry file in it is marked",
        "PRE-FABRICATION in its filename. The checks below are unresolved;",
        "each names the professional input required before this design may",
        "carry any fabrication claim.",
        "",
    ]
    if result.reasons:
        lines.append("WHY THIS PACKAGE IS NOT CLEAN")
        lines.append("-" * 60)
        for reason in sorted(set(result.reasons)):
            lines.append(f"* {reason}")
        lines.append("")

    rows = sorted(
        result.warrant_rows,
        key=lambda r: (str(r.get("gate")), str(r.get("check"))),
    )
    if rows:
        lines.append("UNRESOLVED CHECKS")
        lines.append("-" * 60)
        for row in rows:
            lines.append(f"[{row.get('gate')}] {row.get('check')} "
                         f"— status: {row.get('status')}")
            if row.get("value") is not None or row.get("limit") is not None:
                lines.append(
                    f"    value: {row.get('value')}  limit: {row.get('limit')}"
                    f"  units: {row.get('units') or '-'}")
            if row.get("basis"):
                lines.append(f"    basis: {row.get('basis')}")
            if row.get("message"):
                lines.append(f"    detail: {row.get('message')}")
            lines.append(f"    professional input: {row.get('role')}")
        lines.append("")

    lines.extend([
        "SAFE NEXT ACTIONS",
        "-" * 60,
        "* Supply the missing inputs named above (intake / Design Spec /",
        "  gate profile values), rebuild, and re-validate.",
        "* Threshold values must be approved and signed off by the named",
        "  professional before a clean fabrication package is possible",
        "  (config/gate_profiles.yaml, signed_off).",
        "* Re-export after rebuilding; this warrant regenerates from the",
        "  new validation evidence.",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Marking helpers — filenames and entry names, never content bytes
# ---------------------------------------------------------------------------

def marked_entry_name(name: str) -> str:
    """`exports/assembly.step` -> `exports/assembly.PRE-FABRICATION.step`."""
    path = Path(name)
    if path.suffix:
        return str(path.with_suffix(f".{_ENTRY_MARK}{path.suffix}")).replace(
            "\\", "/")
    return f"{name}.{_ENTRY_MARK}"


def download_filename(design_id: str, base_name: str, package_class: str) -> str:
    """Content-Disposition filename for one artifact download.

    Marking is filename-only — the bytes are always canonical. REFUSED
    mesh-tier downloads are DIAGNOSTIC; anything not proven clean is
    PRE-FABRICATION-marked (LF-103A final condition 2).
    """
    path = Path(base_name)
    stem, suffix = path.stem, path.suffix
    if package_class == CLASS_CLEAN:
        return f"{stem}_{design_id}{suffix}"
    if package_class == CLASS_REFUSED:
        return f"{stem}_{design_id}_{_DIAGNOSTIC_MARK}{suffix}"
    return f"{stem}_{design_id}_{_ENTRY_MARK}{suffix}"


def package_download_filename(design_id: str, package_class: str) -> str:
    if package_class == CLASS_CLEAN:
        return f"luxexchange_{design_id}.zip"
    return f"luxexchange_{design_id}_{_ENTRY_MARK}.zip"


# ---------------------------------------------------------------------------
# Sealed-manifest reading — strict enum, fails closed (final condition 3)
# ---------------------------------------------------------------------------

def read_sealed_package_class(zip_path: Path) -> str:
    """The class a sealed package claims, or LEGACY_UNCLASSIFIED.

    Only the two known sealed enum values are accepted. Missing file,
    unreadable zip, missing manifest, missing key, or any unknown value
    fails closed — the caller must refuse to serve it as clean.
    """
    try:
        with zipfile.ZipFile(Path(zip_path)) as zf:
            manifest = json.loads(zf.read("luxexchange_v1.json"))
    except Exception:
        return LEGACY_UNCLASSIFIED
    value = manifest.get("package_class") if isinstance(manifest, dict) else None
    if value in KNOWN_SEALED_CLASSES:
        return str(value)
    return LEGACY_UNCLASSIFIED
