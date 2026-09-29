"""Who owns a seam between two elements — one rule, one reason, never both.

PR-6 (ADR-074), operator Amendment 4 verbatim: "cross-material joints —
each joint's owning rate defined or explicitly selected, never
double-billed, never silently one side."

A joint between two elements of the SAME material is that material's seam,
priced on its own ``materials.<id>.seam`` rate — nothing to decide. A joint
between two DIFFERENT materials has two candidate rates, and which workshop
bears the seam is a commercial fact of LuxuryCon, not arithmetic. So the
rule lives in ``costing.yaml joints.cross_material_owner`` and ships null:
while it is null this module returns ``UnownedJoint`` naming that path, the
BOM prints the joint as RATE MISSING, and no side is billed.

Every decision this module makes carries its reason in prose, so the BOM
line can print it and the operator can dispute it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import CostAmount, CostingConfig

#: Path the operator fills to make cross-material joints computable.
OWNER_RULE_PATH = "joints.cross_material_owner"


@dataclass(frozen=True)
class JointOwner:
    """The one material whose seam rate bills this joint, and why."""

    material_id: str
    rate_path: str
    reason: str


@dataclass(frozen=True)
class UnownedJoint:
    """No honest owner: the operator has not set the rule (or a needed
    seam rate is null, so 'stronger_rate' cannot compare). Carries the
    exact path to fill."""

    missing_path: str
    reason: str


def _seam(costing: CostingConfig, material_id: str) -> CostAmount | None:
    rates = costing.materials.get(material_id)
    return rates.seam if rates is not None else None


def joint_owner(costing: CostingConfig, parent_material: str,
                child_material: str) -> JointOwner | UnownedJoint:
    """Decide which material's seam rate owns the parent/child joint.

    Same material: trivially that material — the rule is not consulted.
    Different materials: apply ``joints.cross_material_owner``; null means
    UNOWNED, never a guess.
    """
    if parent_material == child_material:
        return JointOwner(
            material_id=parent_material,
            rate_path=f"materials.{parent_material}.seam",
            reason=(f"both elements are {parent_material}; a same-material "
                    f"joint is that material's own seam"),
        )

    rule = costing.joints.cross_material_owner
    if rule is None:
        return UnownedJoint(
            missing_path=OWNER_RULE_PATH,
            reason=(f"joint between {parent_material} (parent) and "
                    f"{child_material} (child) crosses materials and "
                    f"costing.yaml {OWNER_RULE_PATH} is null — no side is "
                    f"billed until the workshop's rule is set"),
        )
    if rule == "parent":
        return JointOwner(
            material_id=parent_material,
            rate_path=f"materials.{parent_material}.seam",
            reason=(f"{OWNER_RULE_PATH} = parent: the {parent_material} "
                    f"element the {child_material} is joined onto bears "
                    f"the seam"),
        )
    if rule == "child":
        return JointOwner(
            material_id=child_material,
            rate_path=f"materials.{child_material}.seam",
            reason=(f"{OWNER_RULE_PATH} = child: the joined-on "
                    f"{child_material} element bears the seam"),
        )

    # stronger_rate — compare the two seam rates per unit. Both must exist
    # AND be quoted per the same unit in the same currency, or the
    # comparison is not honest and the joint stays unowned naming the gap.
    p_seam = _seam(costing, parent_material)
    c_seam = _seam(costing, child_material)
    for mid, seam in ((parent_material, p_seam), (child_material, c_seam)):
        if seam is None or seam.amount is None:
            return UnownedJoint(
                missing_path=f"materials.{mid}.seam",
                reason=(f"{OWNER_RULE_PATH} = stronger_rate needs both seam "
                        f"rates to compare, and costing.yaml materials.{mid}"
                        f".seam is null"),
            )
    assert p_seam is not None and c_seam is not None
    if p_seam.per != c_seam.per or p_seam.currency != c_seam.currency:
        return UnownedJoint(
            missing_path=OWNER_RULE_PATH,
            reason=(f"{OWNER_RULE_PATH} = stronger_rate cannot compare "
                    f"{p_seam.amount:g} "
                    f"{p_seam.currency}/{p_seam.per} ({parent_material}) "
                    f"with {c_seam.amount:g} {c_seam.currency}/{c_seam.per} "
                    f"({child_material}): different unit or currency. Set "
                    f"the rule to parent or child, or quote both seams the "
                    f"same way"),
        )
    if c_seam.amount > p_seam.amount:
        winner, w_seam, loser, l_seam = (
            child_material, c_seam, parent_material, p_seam)
    else:
        # ties go to the parent — stated, so it is a rule, not an accident
        winner, w_seam, loser, l_seam = (
            parent_material, p_seam, child_material, c_seam)
    tie = " (tie -> parent)" if c_seam.amount == p_seam.amount else ""
    return JointOwner(
        material_id=winner,
        rate_path=f"materials.{winner}.seam",
        reason=(f"{OWNER_RULE_PATH} = stronger_rate: {winner} seam "
                f"{w_seam.amount:g} {w_seam.currency}/{w_seam.per} >= "
                f"{loser} seam {l_seam.amount:g} {l_seam.currency}/"
                f"{l_seam.per}{tie}"),
    )
