"""The assembler — declared joints in, ONE watertight fused solid out
(Phase 6 slice A1, ADR-032; plan §4).

The GEOMETRIST does not fuse. It DECLARES: an assembly plan is a list of
placed primitives with parameters and declared joints, and this trusted
module performs every transform and every boolean. Booleans are where OCCT
fails, and the model has already reasoned itself into a tangency
singularity on a single primitive (ADR-029) — free-form boolean authorship
would multiply that failure class by every joint.

THE INTERFERENCE RULE (ADR-029 generalised): every mating joint overlaps
by a real amount — joint_overlap_mm, floored per material, cross-material
joints taking the MAX of the two floors. Zero overlap is the knife edge;
the assembler computes placements to GUARANTEE the overlap and refuses any
plan that would produce a coincident-face contact.

Plan shape (one dict per element; the A2 spec->plan mapping produces this
from massing.elements):

    {
      "element_id":  str — unique; fuse order is SORTED by this (determinism)
      "primitive":   str — a key in primitives.PRIMITIVES
      "parameters":  dict — validated by the primitive's own validate()
      "joint":       ABSENT on exactly ONE root element, else:
        {
          "type":        "stack_on" | "concentric_insert"
          "parent":      the parent's element_id
          "overlap_mm":  optional — the deliberate interference; omitted =
                         the material floor; below the floor = refused
          "x_offset_mm", "y_offset_mm": optional lateral offset (stack_on)
        }
    }

Joint semantics:
  stack_on           child's base meets the parent's TOP face, sunk
                     overlap_mm into it
  concentric_insert  child shares the parent's axis and STANDS on the
                     parent's seat (top of the floor), sunk overlap_mm into
                     it; the parent's declared min_clearance_mm must fit
                     around the child (DIAMETRAL, ADR-029 convention)

Validation an assembly gets that a single solid never needed (plan §4):
  * every declared joint PROVEN to interfere (intersection volume > 0)
    before the fuse — a mis-placed element that would mesh watertight as
    two bodies is caught at the B-rep level with real numbers;
  * body_count == 1 at the B-rep level (mesh level: validate_mesh);
  * volume conservation: sum(members) - sum(joint intersections) must match
    the fused volume within VOLUME_CONSERVATION_TOLERANCE_PCT — a larger
    discrepancy means UNINTENDED interference between elements that do not
    share a declared joint;
  * per-element mass against fabrication.max_lift_kg and bounding box
    against fabrication.max_module_m — computed per spec from the declared
    limits, never tabulated (plan §5; the two dead schema fields become
    load-bearing here).

SECURITY NOTE: this module is reachable from sandboxed AI code via
registry.assemble — keep its public surface benign (no file, network, or
process access).
"""

from __future__ import annotations

from typing import Any

from app.core.config import Material
from app.geometry.primitives import PRIMITIVES
from app.geometry.primitives.base import ConstraintViolation, load_materials

#: |sum(members) - sum(intersections) - fused| / fused, in percent. The
#: volumes are exact B-rep quadratures of the SAME solids that get fused,
#: so agreement is numerical; a breach means unintended element overlap.
VOLUME_CONSERVATION_TOLERANCE_PCT = 0.2

_JOINT_TYPES = ("stack_on", "concentric_insert")


def _resolve_plan(elements: list[dict[str, Any]], violations: list[str]):
    """Structural pass: ids, primitives, root, parents, cycles, joint types."""
    if not elements:
        violations.append("assembly plan is empty — at least one element required")
        return {}, []

    by_id: dict[str, dict[str, Any]] = {}
    for i, el in enumerate(elements):
        eid = el.get("element_id")
        if not isinstance(eid, str) or not eid:
            violations.append(f"element[{i}] has no element_id (a non-empty string)")
            continue
        if eid in by_id:
            violations.append(f"element_id {eid!r} is duplicated — ids must be unique")
            continue
        by_id[eid] = el

    roots = [eid for eid, el in by_id.items() if "joint" not in el]
    if len(roots) != 1:
        violations.append(
            f"an assembly needs exactly ONE root element (no joint); found "
            f"{len(roots)}: {sorted(roots)}"
        )

    for eid, el in sorted(by_id.items()):
        prim = el.get("primitive")
        if prim not in PRIMITIVES:
            violations.append(
                f"{eid}: primitive {prim!r} is not in the registry "
                f"(available: {', '.join(sorted(PRIMITIVES))})"
            )
        joint = el.get("joint")
        if joint is None:
            continue
        if not isinstance(joint, dict):
            violations.append(f"{eid}: joint must be a dict, got {type(joint).__name__}")
            continue
        jtype = joint.get("type")
        if jtype not in _JOINT_TYPES:
            violations.append(
                f"{eid}: joint type {jtype!r} unknown — one of {_JOINT_TYPES}"
            )
        parent = joint.get("parent")
        if parent not in by_id:
            violations.append(
                f"{eid}: joint parent {parent!r} is not an element in this plan"
            )
        elif parent == eid:
            violations.append(f"{eid}: an element cannot joint to itself")

    # Topological order (parents first); non-progress = cycle.
    order: list[str] = []
    placed: set[str] = set()
    pending = dict(by_id)
    while pending:
        progressed = False
        for eid in sorted(pending):
            el = pending[eid]
            parent = (el.get("joint") or {}).get("parent")
            if "joint" not in el or parent in placed:
                order.append(eid)
                placed.add(eid)
                del pending[eid]
                progressed = True
        if not progressed:
            unresolved = sorted(pending)
            # only report a cycle if the parents themselves exist (missing
            # parents were already reported above)
            if all((pending[e].get("joint") or {}).get("parent") in by_id
                   for e in unresolved):
                violations.append(
                    f"joint graph has a cycle among: {unresolved} — "
                    "an assembly is a tree rooted at the base element"
                )
            break
    return by_id, order


def _overlap_floor_mm(child_mat: Material, parent_mat: Material) -> float:
    """Cross-material joints take the MAX of the two floors (signed sheet §2.1)."""
    return max(child_mat.joint_overlap_mm, parent_mat.joint_overlap_mm)


def assemble(
    elements: list[dict[str, Any]],
    seed: int = 0,
    fabrication: dict[str, Any] | None = None,
    materials: dict[str, Material] | None = None,
    strict: bool = True,
    return_solids: bool = False,
):
    """Validate, place, prove interference, fuse. Returns (solid, manifest).

    ``return_solids`` (Phase 14): also return the PLACED per-element solids
    as a third value ``{element_id: solid}`` — the designer workspace's
    scene GLB needs each element as its own named node, and the solids
    already exist here before the fuse. The fused solid and the manifest
    are byte-for-byte unaffected by this flag.

    Raises ConstraintViolation with EVERY violation and its real numbers, or
    RuntimeError if the fused geometry itself breaks a guarantee (body
    count, volume conservation) — the latter means a construction defect,
    not a bad parameter.

    ``fabrication``: optional {"max_lift_kg": float, "max_module_m": float}
    — the Design Spec's declared workshop limits. Checked per ELEMENT
    (today every element is one piece; segmentation is slice C).

    ``strict`` (ADR-034 — diagnostic build mode):

    * ``True`` (default, and what the AI fabrication loop uses): a breach of
      a declared fabrication LIMIT raises ConstraintViolation like every
      other violation. Generated code must be refused hard.
    * ``False`` (what the operator-facing API uses): geometry is still built
      and returned, and the limit breaches are recorded in the manifest as
      ``fabrication_limit_violations`` for the Phase 8 fabrication gate to
      report as failing rows.

    The distinction is ONLY about declared workshop limits. Geometric and
    material prerequisites — an unknown primitive, an undeclared
    interference, a wall outside the material envelope — raise in both
    modes, because without them there is no solid to look at.
    """
    materials = materials if materials is not None else load_materials()
    violations: list[str] = []

    by_id, order = _resolve_plan(elements, violations)
    if violations:
        raise ConstraintViolation(violations)

    # --- per-element parameter validation (ALL failures reported together) --
    validated: dict[str, Any] = {}
    for eid in sorted(by_id):
        el = by_id[eid]
        module = PRIMITIVES[el["primitive"]]
        try:
            validated[eid] = module.validate(el.get("parameters") or {}, materials)
        except ConstraintViolation as exc:
            violations.extend(f"{eid}: {v}" for v in exc.violations)
    if violations:
        raise ConstraintViolation(violations)

    # --- placement: joints resolved parents-first, overlap floors enforced --
    placements: dict[str, tuple[float, float, float]] = {}
    joints: list[dict[str, Any]] = []
    for eid in order:
        el = by_id[eid]
        joint = el.get("joint")
        if joint is None:
            placements[eid] = (0.0, 0.0, 0.0)
            continue

        parent_id = joint["parent"]
        if parent_id not in placements:
            # the parent's own joint was already refused above — that
            # violation carries the actionable numbers; this element cannot
            # be placed until it is fixed
            continue
        parent_el = by_id[parent_id]
        child_mod = PRIMITIVES[el["primitive"]]
        parent_mod = PRIMITIVES[parent_el["primitive"]]
        child_p, parent_p = validated[eid], validated[parent_id]
        child_mat = materials[child_p.material_id]
        parent_mat = materials[parent_p.material_id]
        px, py, pz = placements[parent_id]
        jtype = joint["type"]

        floor = _overlap_floor_mm(child_mat, parent_mat)
        overlap = joint.get("overlap_mm")
        if overlap is None:
            overlap = floor
        elif overlap < floor:
            violations.append(
                f"{eid}: joint overlap_mm={overlap:g} < the {floor:g} mm "
                f"floor for {child_p.material_id} on {parent_p.material_id} "
                f"(max of the two material floors, signed sheet §2.1) — a "
                "joint below the fabrication tolerance stack models an "
                "interference the workshop cannot guarantee; at 0 the faces "
                "are tangent and the fuse is not watertight (ADR-029)"
            )
            continue

        child_h = child_mod.height_mm(child_p)
        parent_anchors = parent_mod.anchors(parent_p)

        if jtype == "stack_on":
            if not parent_mod.CAN_PARENT_STACK:
                violations.append(
                    f"{eid}: cannot stack_on {parent_id} — primitive "
                    f"{parent_mod.PRIMITIVE_ID!r} exposes no stackable top "
                    "face (a cascade's top is a dish rim)"
                )
                continue
            parent_h = parent_mod.height_mm(parent_p)
            if overlap >= min(child_h, parent_h):
                violations.append(
                    f"{eid}: joint overlap_mm={overlap:g} must stay under "
                    f"both members' heights (child {child_h:g}, parent "
                    f"{parent_h:g} mm) — deeper is submersion, not a joint"
                )
                continue
            x = px + float(joint.get("x_offset_mm", 0.0))
            y = py + float(joint.get("y_offset_mm", 0.0))
            z = pz + parent_anchors["top"] - overlap
        else:  # concentric_insert
            if not parent_mod.CAN_PARENT_INSERT:
                violations.append(
                    f"{eid}: cannot concentric_insert into {parent_id} — "
                    f"primitive {parent_mod.PRIMITIVE_ID!r} has no interior "
                    "seat (only basins accept inserts in slice A)"
                )
                continue
            seat = parent_anchors["seat"]
            if overlap > seat:
                violations.append(
                    f"{eid}: joint overlap_mm={overlap:g} > the parent's "
                    f"floor thickness {seat:g} mm — the insert would punch "
                    f"through {parent_id}'s floor"
                )
                continue
            inner = parent_mod.inner_diameter_mm(parent_p)
            child_d = child_mod.max_outer_diameter_mm(child_p)
            clearance = getattr(parent_p, "min_clearance_mm", None)
            if clearance is None:
                clearance = parent_mat.min_clearance_mm
            if child_d + clearance > inner:
                violations.append(
                    f"{eid}: does not fit inside {parent_id} — child outer "
                    f"{child_d:g} + clearance {clearance:g} (DIAMETRAL) = "
                    f"{child_d + clearance:g} > parent inner diameter "
                    f"{inner:g} mm (ADR-029: the gap floor is the parent's "
                    "declared min_clearance_mm)"
                )
                continue
            x, y = px, py            # shared axis — concentric by definition
            z = pz + seat - overlap

        placements[eid] = (x, y, z)
        joints.append({
            "child": eid, "parent": parent_id, "type": jtype,
            "overlap_mm": float(overlap), "floor_mm": float(floor),
        })

    if violations:
        raise ConstraintViolation(violations)

    # --- build + place every solid (deterministic: pure functions of params)
    from build123d import CenterOf, Pos

    solids: dict[str, Any] = {}
    for eid in sorted(by_id):
        el = by_id[eid]
        module = PRIMITIVES[el["primitive"]]
        x, y, z = placements[eid]
        solids[eid] = Pos(x, y, z) * module.build(validated[eid])

    # --- NON-joined pairs must keep a real gap ------------------------------
    # The per-joint checks cannot see this class: in a coaxial plinth ->
    # basin -> column stack, a column inserted through the basin floor can
    # reach the PLINTH — overlap (undeclared interference) or exact tangency
    # (the ADR-029 knife edge: fuses to a non-watertight solid), depending
    # on one millimetre of floor arithmetic. Checked pairwise at the B-rep
    # level with real numbers; tangency is distance_to == 0 with zero
    # intersection volume (verified against the installed build123d).
    joined_pairs = {frozenset((j["child"], j["parent"])) for j in joints}
    ids_sorted = sorted(solids)
    for i, a in enumerate(ids_sorted):
        for b in ids_sorted[i + 1:]:
            if frozenset((a, b)) in joined_pairs:
                continue
            try:
                inter = solids[a] & solids[b]
                vol = float(inter.volume) if inter is not None else 0.0
            except Exception:
                vol = 0.0
            if vol > 1e-6:
                violations.append(
                    f"{a} and {b} interfere ({vol:.3f} mm3) WITHOUT a "
                    "declared joint — two elements occupy the same space; "
                    "declare the joint or move the members apart (in a "
                    "stacked-and-inserted chain: thicken the middle "
                    "element, e.g. the basin floor_mm, so the two joints "
                    "do not meet through it)"
                )
            elif float(solids[a].distance_to(solids[b])) <= 1e-6:
                violations.append(
                    f"{a} and {b} are TANGENT (distance 0, intersection 0) "
                    "without a declared joint — a coincident-face contact "
                    "fuses to a solid that is not watertight (ADR-029). "
                    "Open a real gap or declare a real-overlap joint"
                )
    if violations:
        raise ConstraintViolation(violations)

    # --- prove every declared joint interferes BEFORE the fuse --------------
    sum_intersections = 0.0
    for j in joints:
        try:
            inter = solids[j["child"]] & solids[j["parent"]]
            inter_vol = float(inter.volume) if inter is not None else 0.0
        except Exception:
            inter_vol = 0.0
        j["intersection_volume_mm3"] = inter_vol
        if inter_vol <= 0.0:
            violations.append(
                f"{j['child']}: declared joint to {j['parent']} does NOT "
                f"interfere (intersection volume {inter_vol:g} mm3) — the "
                "placed members never touch, so the fuse would produce a "
                "floating body, not a joint (check offsets against the "
                "parent's actual faces)"
            )
        sum_intersections += inter_vol
    if violations:
        raise ConstraintViolation(violations)

    # --- fuse, canonical order (sorted element_id — determinism, plan §4) ---
    ordered_ids = sorted(solids)
    fused = solids[ordered_ids[0]]
    for eid in ordered_ids[1:]:
        fused += solids[eid]

    parts = fused.solids()
    if len(parts) != 1:
        raise RuntimeError(
            f"assembly fused into {len(parts)} bodies, expected 1 — every "
            "joint interfered individually, so disjoint SUBGRAPHS remain: "
            "some element chain never touches the rest"
        )
    fused = parts[0]

    # --- volume conservation: catches UNDECLARED interference ---------------
    sum_members = sum(float(s.volume) for s in solids.values())
    fused_vol = float(fused.volume)
    expected = sum_members - sum_intersections
    delta_pct = abs(expected - fused_vol) / fused_vol * 100.0
    if delta_pct > VOLUME_CONSERVATION_TOLERANCE_PCT:
        raise RuntimeError(
            f"volume conservation breach: members {sum_members:.3f} - "
            f"declared intersections {sum_intersections:.3f} = "
            f"{expected:.3f} mm3, but the fused assembly measures "
            f"{fused_vol:.3f} mm3 (delta {delta_pct:.4f}% > "
            f"{VOLUME_CONSERVATION_TOLERANCE_PCT:g}%) — two elements "
            "occupy the same space without a declared joint"
        )

    # --- manifest: per-element real numbers + fabrication limit checks ------
    manifest_elements: list[dict[str, Any]] = []
    # ADR-034: limit breaches are collected SEPARATELY from geometric
    # violations, because strict=False still returns geometry for them.
    limit_violations: list[str] = []
    max_lift = (fabrication or {}).get("max_lift_kg")
    max_module = (fabrication or {}).get("max_module_m")
    for eid in ordered_ids:
        el = by_id[eid]
        p = validated[eid]
        mat = materials[p.material_id]
        s = solids[eid]
        vol = float(s.volume)
        mass = vol * 1e-9 * mat.density_kg_per_m3
        bb = s.bounding_box()
        dims = [float(bb.size.X), float(bb.size.Y), float(bb.size.Z)]
        # WORLD-SPACE extents and mass centroid. The Phase 8 structural gate
        # needs both: a placement origin is not a centre of mass (a hollow
        # basin's mass is in its walls), and a bbox SIZE cannot locate a
        # footprint that is not centred on the world origin.
        bb_min = [float(bb.min.X), float(bb.min.Y), float(bb.min.Z)]
        bb_max = [float(bb.max.X), float(bb.max.Y), float(bb.max.Z)]
        com = s.center(CenterOf.MASS)
        x, y, z = placements[eid]
        manifest_elements.append({
            "element_id": eid,
            "primitive": el["primitive"],
            "material_id": p.material_id,
            "parameters": dict(p.model_dump()),
            "placement_mm": {"x": x, "y": y, "z": z},
            "volume_mm3": vol,
            "mass_kg": mass,
            "bbox_mm": dims,
            "bbox_min_mm": bb_min,
            "bbox_max_mm": bb_max,
            "centroid_mm": {"x": float(com.X), "y": float(com.Y), "z": float(com.Z)},
        })
        if max_lift is not None and mass > float(max_lift):
            hint = ""
            wall = getattr(p, "wall_mm", None)
            if wall == 0:
                hint = (
                    " — this element is SOLID; hollowing (wall_mm inside the "
                    "material envelope) cuts mass at the same silhouette "
                    "(signed sheet §4.2: a 1.0x1.0 m basalt plinth drops "
                    "2121 -> 1252 kg at a 180 mm wall)"
                )
            limit_violations.append(
                f"{eid}: mass {mass:.1f} kg > max_lift_kg "
                f"{float(max_lift):g} (volume {vol:.0f} mm3 x density "
                f"{mat.density_kg_per_m3:g} kg/m3, {p.material_id})" + hint
            )
        if max_module is not None:
            limit_mm = float(max_module) * 1000.0
            worst = max(dims)
            if worst > limit_mm:
                limit_violations.append(
                    f"{eid}: bounding box {dims[0]:.0f} x {dims[1]:.0f} x "
                    f"{dims[2]:.0f} mm exceeds max_module_m "
                    f"{float(max_module):g} m ({limit_mm:g} mm) — "
                    "segmentation arrives in slice C; an oversized element "
                    "is refused, never silently produced"
                )
    # Geometric/material violations always raise. Limit breaches raise only
    # in strict mode (ADR-034) — otherwise they ride out in the manifest.
    if violations or (strict and limit_violations):
        raise ConstraintViolation(violations + limit_violations)

    manifest = {
        "schema": "assembly_manifest_v1",
        "seed": int(seed),
        "elements": manifest_elements,
        "joints": joints,
        "volume_conservation": {
            "sum_member_volumes_mm3": sum_members,
            "sum_joint_intersections_mm3": sum_intersections,
            "assembly_volume_mm3": fused_vol,
            "delta_pct": delta_pct,
            "tolerance_pct": VOLUME_CONSERVATION_TOLERANCE_PCT,
        },
        "fabrication_limits": {
            "max_lift_kg": max_lift,
            "max_module_m": max_module,
        },
        # ADR-034: empty in strict mode by construction (it would have
        # raised). Non-empty only on a diagnostic build, where the Phase 8
        # fabrication gate turns each entry into a failing row.
        "fabrication_limit_violations": limit_violations,
        "strict": bool(strict),
        "total_mass_kg": sum(e["mass_kg"] for e in manifest_elements),
        "assembly_bbox_min_mm": [
            min(e["bbox_min_mm"][i] for e in manifest_elements) for i in range(3)
        ],
        "assembly_bbox_max_mm": [
            max(e["bbox_max_mm"][i] for e in manifest_elements) for i in range(3)
        ],
        "body_count_brep": 1,
    }
    if return_solids:
        return fused, manifest, solids
    return fused, manifest
