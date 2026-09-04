"""FF-A1 (ADR-065): the incomplete-mass truth model.

One module, one interpretation rule, consumed by every reader of mass.
The platform-wide contract (owner corrections, 2026-09-03):

  * ``total_mass_kg`` is ``None`` when incomplete — NEVER zero.
  * ``known_geometry_mass_kg`` may be shown only WITH its incomplete
    basis (the ``missing_mass_inputs`` names travel with it).
  * Every mass-dependent computation (centroid, overturning, bearing,
    lift, crane, costing, quote, BOM) returns needs_input /
    not_computable when the total is incomplete.
  * Unknown, malformed or inconsistent mass-model data FAILS CLOSED as
    incomplete.

BACKWARD COMPATIBILITY (the digest policy, ADR-065): manifests emit the
explicit ``mass_model`` block ONLY for incomplete-capable primitives.
Absent mass fields mean "complete" for exactly one narrow case: a
persisted manifest composed entirely of the frozen legacy set below.
That set is a PERMANENT VERSIONING SEAM — it is how every byte of every
pre-FF-A1 design stays identical forever. It looks like a D-10 frozen
list; it is not one: it must never grow, because growing it would change
how old evidence is read. New primitives declare their own mass truth.

Units: kilograms, SI, explicit. A bare number is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The ten primitives that existed before the mass model did. Their mass
#: is complete by construction (solid geometry x density is the whole
#: story). FROZEN FOREVER — see the module docstring.
LEGACY_COMPLETE_MASS_PRIMITIVES = frozenset({
    "tiered_cascade", "basin_round", "plinth", "sculptural_column",
    "basin_rect", "stepped_monolith", "water_wall", "torus_ring",
    "blade_fin_array", "lotus_petal_array",
})

#: The production free-form geometry-integrity gate (ADR-065). For any
#: design whose persisted manifest REQUIRES it, a missing, failed or
#: indeterminate row REFUSES export (owner ruling 2026-09-03).
FREEFORM_INTEGRITY_GATE = "freeform_integrity_v1"

#: Every gate name a manifest may declare in required_validation_gates.
#: An unknown required name can never have passing evidence, so it fails
#: closed at classification.
KNOWN_REQUIRED_GATES = frozenset({FREEFORM_INTEGRITY_GATE})

#: Sentinel returned when the manifest's required_validation_gates key is
#: present but not a list of strings — classification must refuse.
MALFORMED_REQUIRED_GATES = "__malformed_required_validation_gates__"


@dataclass(frozen=True)
class MassTruth:
    """The truth about a mass figure. ``total_mass_kg`` is a property so
    it can never be set inconsistently with ``mass_complete``."""

    mass_complete: bool
    known_geometry_mass_kg: float
    missing_mass_inputs: tuple[str, ...]

    @property
    def total_mass_kg(self) -> float | None:
        """None — never 0.0 — when the mass is incomplete."""
        return self.known_geometry_mass_kg if self.mass_complete else None

    def wire(self) -> dict[str, Any]:
        """The explicit serialized block for manifests and APIs."""
        return {
            "mass_complete": self.mass_complete,
            "known_geometry_mass_kg": round(self.known_geometry_mass_kg, 3),
            "missing_mass_inputs": list(self.missing_mass_inputs),
            "total_mass_kg": (round(self.known_geometry_mass_kg, 3)
                              if self.mass_complete else None),
        }

    def basis_text(self) -> str:
        """The label that must accompany any display of the known mass."""
        if self.mass_complete:
            return "complete (geometry x density)"
        return ("known-geometry mass only — incomplete; missing: "
                + "; ".join(self.missing_mass_inputs))


def _incomplete(known_kg: float, *reasons: str) -> MassTruth:
    return MassTruth(mass_complete=False,
                     known_geometry_mass_kg=max(float(known_kg), 0.0),
                     missing_mass_inputs=tuple(reasons))


def _parse_block(block: Any, fallback_known_kg: float) -> MassTruth:
    """Strict parse of an explicit mass_model block. Anything unknown,
    malformed or internally inconsistent fails closed as incomplete with
    the defect named — never an exception that a caller could swallow,
    never a silently-complete reading."""
    if not isinstance(block, dict):
        return _incomplete(fallback_known_kg,
                           "mass_model is not an object (malformed)")
    complete = block.get("mass_complete")
    known = block.get("known_geometry_mass_kg")
    missing = block.get("missing_mass_inputs")
    total = block.get("total_mass_kg")
    problems: list[str] = []
    if not isinstance(complete, bool):
        problems.append("mass_complete is not a boolean")
    if not isinstance(known, (int, float)) or isinstance(known, bool) \
            or float(known) < 0:
        problems.append("known_geometry_mass_kg is not a non-negative number")
        known = fallback_known_kg
    if not isinstance(missing, list) or not all(
            isinstance(m, str) and m for m in missing):
        problems.append("missing_mass_inputs is not a list of names")
        missing = []
    if problems:
        return _incomplete(float(known),
                           *(f"mass model malformed: {p}" for p in problems))
    if complete and missing:
        return _incomplete(float(known),
                           "mass model inconsistent: mass_complete=true but "
                           "missing_mass_inputs is non-empty: "
                           + "; ".join(missing))
    if not complete and not missing:
        return _incomplete(float(known),
                           "mass model inconsistent: mass_complete=false "
                           "with no missing_mass_inputs named")
    if complete and total is not None and \
            abs(float(total) - float(known)) > 1e-6:
        return _incomplete(float(known),
                           f"mass model inconsistent: total_mass_kg "
                           f"{total} != known_geometry_mass_kg {known}")
    if not complete and total not in (None,):
        return _incomplete(float(known),
                           f"mass model inconsistent: incomplete mass "
                           f"carries total_mass_kg {total} (must be null)")
    if complete:
        return MassTruth(True, float(known), ())
    return MassTruth(False, float(known), tuple(missing))


def element_mass_truth(element: dict[str, Any]) -> MassTruth:
    """The mass truth of one manifest element.

    Explicit block wins (strict parse). Absent block: complete ONLY for
    the frozen legacy primitives; any other primitive fails closed."""
    known = float(element.get("mass_kg") or 0.0)
    block = element.get("mass_model")
    if block is not None:
        return _parse_block(block, known)
    primitive = str(element.get("primitive"))
    if primitive in LEGACY_COMPLETE_MASS_PRIMITIVES:
        return MassTruth(True, known, ())
    return _incomplete(
        known,
        f"mass model for primitive '{primitive}' — not a legacy "
        "complete-mass primitive and no explicit mass_model block persisted")


def assembly_mass_truth(manifest: dict[str, Any]) -> MassTruth:
    """Aggregate truth over every element of one assembly manifest."""
    elements = list(manifest.get("elements") or [])
    if not elements:
        return _incomplete(0.0, "manifest has no elements")
    truths = [element_mass_truth(e) for e in elements]
    known = sum(t.known_geometry_mass_kg for t in truths)
    missing: list[str] = []
    for t in truths:
        for m in t.missing_mass_inputs:
            if m not in missing:
                missing.append(m)
    if missing:
        return MassTruth(False, known, tuple(missing))
    return MassTruth(True, known, ())


def required_validation_gates(manifest: dict[str, Any]) -> tuple[str, ...]:
    """The persisted validation-applicability snapshot (ADR-065).

    Absent key -> no extra gates (the legacy world). A well-formed list
    of known gate names -> those names. ANYTHING else -> the malformed
    sentinel, which classification refuses — export decisions read this
    persisted snapshot, never today's registry or config."""
    if not isinstance(manifest, dict):
        return (MALFORMED_REQUIRED_GATES,)
    raw = manifest.get("required_validation_gates")
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(
            isinstance(g, str) and g for g in raw):
        return (MALFORMED_REQUIRED_GATES,)
    return tuple(dict.fromkeys(raw))
