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
  * per-MODULE mass against fabrication.max_lift_kg and bounding box
    against fabrication.max_module_m — computed per spec from the declared
    limits, never tabulated (plan §5; the two dead schema fields become
    load-bearing here). Slice C2 (ADR-056) put segmentation between the
    element and the limit: what a crane lifts is a module, not an element.

SECURITY NOTE: this module is reachable from sandboxed AI code via
registry.assemble — keep its public surface benign (no file, network, or
process access).
"""

from __future__ import annotations

from typing import Any

from app.core.config import Material
from app.geometry.mass_model import (
    FREEFORM_INTEGRITY_GATE,
    LEGACY_COMPLETE_MASS_PRIMITIVES,
    MassTruth,
    assembly_mass_truth,
)
from app.geometry.primitives import PRIMITIVES
from app.geometry.primitives.base import ConstraintViolation, load_materials
from app.geometry.segmentation import (
    MODE_DISCRETE_ARRAY,
    MODE_PLANAR_GRID,
    axes_fit_mm,
    binding_axis_mm,
    format_limit_m,
    joint_contact_mm,
    limit_m_to_mm,
    normalize_module_limit_m,
    refused_result,
    segment_solid,
    whole_element_result,
)

#: |sum(members) - sum(intersections) - fused| / fused, in percent. The
#: volumes are exact B-rep quadratures of the SAME solids that get fused,
#: so agreement is numerical; a breach means unintended element overlap.
VOLUME_CONSERVATION_TOLERANCE_PCT = 0.2

_JOINT_TYPES = ("stack_on", "concentric_insert")


def build_segmentation(
    ordered_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    validated: dict[str, Any],
    solids: dict[str, Any],
    joints: list[dict[str, Any]],
    materials: dict[str, Material],
    *,
    max_module_m: dict[str, float] | None,
    joint_solids: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-element modules + both classes of seam (slice C2, ADR-056).

    An element is CUT only when it exceeds the declared module limit. An
    element inside the limit is one module and costs no boolean, so the
    common build path is untouched.

    With no ``max_module_m`` declared the platform has no basis on which to
    choose a split, so every element ships whole and says so. That keeps
    the pre-C2 behaviour exactly: without a module limit an over-mass
    element is still refused, because nothing here can invent the limit it
    would have been cut to.
    """
    limit_mm = limit_m_to_mm(max_module_m) if max_module_m is not None else None
    per_element: dict[str, Any] = {}
    not_segmentable: list[str] = []

    for eid in ordered_ids:
        module = PRIMITIVES[by_id[eid]["primitive"]]
        mode = getattr(module, "SEGMENTATION_MODE", MODE_PLANAR_GRID)
        density = float(materials[validated[eid].material_id].density_kg_per_m3)
        solid = solids[eid]
        bb = solid.bounding_box()
        dims = [float(bb.size.X), float(bb.size.Y), float(bb.size.Z)]

        # PR-1 (ADR-059): every axis binds on ITS OWN limit. The old check
        # compared max(extents) to one scalar, so an element breaching only
        # the tight axis of a non-cubic envelope was never cut.
        if limit_mm is None or axes_fit_mm(dims, limit_mm):
            result = whole_element_result(
                solid, density_kg_per_m3=density, mode=mode)
        elif mode == MODE_DISCRETE_ARRAY:
            not_segmentable.append(eid)
            axis, extent, axis_limit = binding_axis_mm(dims, limit_mm)
            result = refused_result(
                solid, density_kg_per_m3=density, mode=mode,
                refusal=(
                    f"bounding box {dims[0]:.0f} x {dims[1]:.0f} x "
                    f"{dims[2]:.0f} mm exceeds max_module_m "
                    f"{format_limit_m(max_module_m)} on the {axis} axis "
                    f"({extent:.0f} mm vs {axis_limit:g} mm), and "
                    f"{by_id[eid]['primitive']} is "
                    f"{MODE_DISCRETE_ARRAY}: it is already a ring of separate "
                    "pieces on a hub, so saw planes through it produce "
                    "fragments, not modules. Reduce the array's diameter, or "
                    "model the hub and the blades as separate elements"
                ),
            )
        else:
            result = segment_solid(
                solid, limit_mm, density_kg_per_m3=density)
        per_element[eid] = result.as_dict()

    split_count = sum(e["seam_count"] for e in per_element.values())
    split_length = sum(e["seam_length_mm"] for e in per_element.values())
    split_area = sum(e["seam_area_mm2"] for e in per_element.values())

    # Element-to-element joints are seams too: a basin sunk into a plinth is
    # a real run of bedding or weld. The contact plane sits at the child's
    # base plus the declared overlap — both already recorded above — so the
    # same cut-and-pair machinery measures it.
    joint_length = 0.0
    joint_area = 0.0
    joint_records: list[dict[str, Any]] = []
    for joint in joints:
        child = str(joint["child"])
        contact_z = float(solids[child].bounding_box().min.Z) + \
            float(joint["overlap_mm"])
        length, area = joint_contact_mm(
            (joint_solids or {}).get(child), contact_z)
        joint_length += length
        joint_area += area
        joint_records.append({
            "child": child, "parent": str(joint["parent"]),
            "type": joint["type"], "contact_z_mm": round(contact_z, 6),
            "length_mm": round(length, 6), "area_mm2": round(area, 6),
        })

    module_count = sum(e["module_count"] for e in per_element.values())
    heaviest = max(
        (m["mass_kg"] for e in per_element.values() for m in e["modules"]),
        default=0.0,
    )
    if max_module_m is None:
        basis = ("no fabrication.max_module_m declared — each element ships "
                 "as one module; nothing was cut")
    else:
        basis = (f"fabrication.max_module_m = {format_limit_m(max_module_m)}"
                 f", each axis binding on its own limit, axis-aligned "
                 f"planar grid")
    return {
        "schema": "assembly_segmentation_v1",
        "basis": basis,
        "max_module_mm": limit_mm,
        "elements": per_element,
        "module_count": module_count,
        "heaviest_module_kg": round(heaviest, 6),
        "not_segmentable": not_segmentable,
        "seams": {
            "split": {"count": split_count,
                      "length_mm": round(split_length, 6),
                      "area_mm2": round(split_area, 6)},
            # Joint seams carry a real area as well as a run: both are read
            # off the actual contact face of the overlap solid, so neither
            # is inferred from intersection volume / overlap depth (which
            # is right for a prismatic overlap and wrong for a tapered one).
            "joint": {"count": len(joint_records),
                      "length_mm": round(joint_length, 6),
                      "area_mm2": round(joint_area, 6),
                      "joints": joint_records},
            "total_length_mm": round(split_length + joint_length, 6),
        },
    }


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


def _apply_fixtures(
    eid: str,
    el: dict[str, Any],
    module,
    p,
    solid,
    materials: dict[str, Material],
    violations: list[str],
    fixtures_out: dict[str, list[dict[str, Any]]],
):
    """Slice B (ADR-054): cut declared fixtures into ONE element, locally.

    Nozzle rings only, basin_round hosts only (it has the floor the bores
    pierce). Every bound derives from the signed sheet: the stone web
    between holes and to the wall is a projecting FEATURE and must clear
    min_feature_mm. Bore positions are deterministic: N equally spaced
    holes, phase 0, sorted evaluation order."""
    fixtures = el.get("fixtures") or []
    if not fixtures:
        return solid
    if module.PRIMITIVE_ID != "basin_round":
        violations.append(
            f"{eid}: fixtures are cut into a basin floor; only basin_round "
            f"hosts them in slice B (got {module.PRIMITIVE_ID!r})"
        )
        return solid

    import math

    from build123d import Cylinder, Pos

    mat = materials[p.material_id]
    feat = float(mat.min_feature_floor_mm(p.wall_mm))
    inner_d = float(p.diameter_mm - 2 * p.wall_mm)
    floor_t = float(p.floor_mm)
    recorded: list[dict[str, Any]] = []
    for fx in fixtures:
        if fx.get("type") != "nozzle_ring":
            violations.append(
                f"{eid}: unknown fixture type {fx.get('type')!r} — slice B "
                "knows nozzle_ring only"
            )
            continue
        n = int(fx.get("count", 0))
        bore = float(fx.get("bore_mm", 0.0))
        if n < 1:
            violations.append(f"{eid}: nozzle_ring count must be >= 1")
            continue
        if bore < 8.0:
            violations.append(
                f"{eid}: nozzle bore {bore:g} mm < the 8 mm drillable-stone "
                "floor (ADR-054, judgement)"
            )
            continue
        default_ring = inner_d / 2.0 if n > 1 else 0.0
        rd = float(fx.get("ring_diameter_mm", default_ring))
        wall_web = (inner_d - rd) / 2.0 - bore / 2.0
        if wall_web < feat:
            violations.append(
                f"{eid}: nozzle-to-wall web = (inner {inner_d:g} - ring "
                f"{rd:g})/2 - bore {bore:g}/2 = {wall_web:g} mm < the "
                f"{p.material_id} feature floor {feat:g} mm — shrink the "
                "ring, the bore, or the count"
            )
            continue
        if n > 1:
            spacing_web = rd * math.sin(math.pi / n) - bore
            if spacing_web < feat:
                violations.append(
                    f"{eid}: web between adjacent nozzle bores = ring "
                    f"{rd:g} x sin(pi/{n}) - bore {bore:g} = "
                    f"{spacing_web:g} mm < the {p.material_id} feature "
                    f"floor {feat:g} mm — fewer nozzles or a wider ring"
                )
                continue
        removed = 0.0
        for i in range(n):
            ang = 2.0 * math.pi * i / n
            cx = (rd / 2.0) * math.cos(ang)
            cy = (rd / 2.0) * math.sin(ang)
            before = float(solid.volume)
            # 1 mm overshoot both ends so the cut never leaves a skin face
            # (the cascade bore's proven pattern).
            solid = solid - Pos(cx, cy, floor_t / 2.0) * Cylinder(
                bore / 2.0, floor_t + 2.0
            )
            removed += before - float(solid.volume)
        recorded.append({
            "type": "nozzle_ring",
            "count": n,
            "bore_mm": bore,
            "ring_diameter_mm": rd,
            "removed_volume_mm3": removed,
        })
    remaining = solid.solids()
    if len(remaining) != 1:
        violations.append(
            f"{eid}: fixture cuts split the element into "
            f"{len(remaining)} bodies — a bore has severed the floor"
        )
    if recorded:
        fixtures_out[eid] = recorded
    return solid


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

    ``fabrication``: optional {"max_lift_kg": float, "max_module_m":
    {"x","y","z"} in metres — or a scalar, which deliberately means a
    CUBIC envelope (PR-1, ADR-059; the Designer's single number). Each
    axis binds on its own limit. Malformed limits (missing/extra axes,
    booleans, non-finite, zero, negative) raise ConstraintViolation}
    — the Design Spec's declared workshop limits. Checked per MODULE since
    slice C2 (ADR-056): an element over ``max_module_m`` is cut into
    modules by the kernel and the limits bind on those, so a 5 m basin
    that no crane could pick now builds as nine liftable pieces. With no
    ``max_module_m`` declared nothing is cut and each element is its own
    module, which is exactly the pre-C2 behaviour.

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
            # ADR-053: interference proves the FUSE; it does not prove a
            # SEAT. The child must land on a real annular bearing at the
            # joint plane, at least the material joint floor wide — the
            # same signed §2.1 tolerance stack: a lip narrower than it can
            # vanish entirely in fabrication. Found live 2026-08-26: a
            # 2,000 mm basin on a hollow 2,200/102 plinth passed every
            # check while bearing 1,550 kg on a 2 mm basalt lip.
            # ADR-055: a module whose base footprint depends on how deep it
            # sinks (the torus: line contact un-sunk, a real chord when
            # sunk) exposes the overlap-aware form; everything else states
            # a fixed footprint.
            if hasattr(child_mod, "base_annulus_at_overlap_mm"):
                child_out, child_in = child_mod.base_annulus_at_overlap_mm(
                    child_p, overlap
                )
            else:
                child_out, child_in = child_mod.base_annulus_mm(child_p)
            parent_out, parent_in = parent_mod.stack_top_annulus_mm(parent_p)
            d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            # Worst-angle supported width of the child's base ring: the
            # parent's outer edge closes in by the offset; the parent's
            # hole edge (when there is one) reaches in by the offset too.
            outer_support = min(child_out / 2.0, parent_out / 2.0 - d)
            inner_support = (
                child_in / 2.0 if parent_in == 0
                else max(child_in / 2.0, parent_in / 2.0 + d)
            )
            bearing = outer_support - inner_support
            if bearing < floor:
                violations.append(
                    f"{eid}: stack_on {parent_id} lands on a {bearing:.1f} mm "
                    f"radial seat, below the {floor:g} mm floor for "
                    f"{child_p.material_id} on {parent_p.material_id} "
                    f"(child base annulus ⌀{child_in:g}..{child_out:g} on "
                    f"parent top annulus ⌀{parent_in:g}..{parent_out:g} mm"
                    + (f", lateral offset {d:g} mm" if d else "")
                    + ") — a seat narrower than the fabrication tolerance "
                    "stack can vanish in the workshop (signed sheet §2.1). "
                    "Thicken the parent wall, adjust a diameter, reduce the "
                    "offset, or make the parent solid"
                )
                continue
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
    from build123d import CenterOf, Pos  # noqa: F401  (Pos used below)

    solids: dict[str, Any] = {}
    locals_by_eid: dict[str, Any] = {}
    fixtures_by_eid: dict[str, list[dict[str, Any]]] = {}
    for eid in sorted(by_id):
        el = by_id[eid]
        module = PRIMITIVES[el["primitive"]]
        local = module.build(validated[eid])
        # Slice B (ADR-054): fixtures (nozzle rings) are cut by TRUSTED code
        # in the element's local frame BEFORE placement and fuse, so element
        # masses, the scene GLB and volume conservation all see the real
        # bored solid.
        local = _apply_fixtures(
            eid, el, module, validated[eid], local, materials,
            violations, fixtures_by_eid,
        )
        locals_by_eid[eid] = local
        solids[eid] = Pos(*placements[eid]) * local
    if violations:
        raise ConstraintViolation(violations)

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
    # The overlap solids are kept, not discarded: slice C2 measures the
    # joint seam off the SAME intersection this proof computes, so the two
    # can never disagree about whether two elements touch.
    joint_solids: dict[str, Any] = {}
    for j in joints:
        try:
            inter = solids[j["child"]] & solids[j["parent"]]
            inter_vol = float(inter.volume) if inter is not None else 0.0
        except Exception:
            inter = None
            inter_vol = 0.0
        joint_solids[str(j["child"])] = inter
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
    raw_max_module = (fabrication or {}).get("max_module_m")
    # PR-1 (ADR-059): assemble() is the ONE compatibility boundary. A
    # Designer/API scalar deliberately means a cubic envelope; the Design
    # Spec object passes through per-axis; anything malformed is refused
    # loudly here, before any further work — never a TypeError downstream.
    if raw_max_module is None:
        max_module: dict[str, float] | None = None
    else:
        try:
            max_module = normalize_module_limit_m(
                raw_max_module, allow_scalar=True)
        except ValueError as exc:
            raise ConstraintViolation([str(exc)]) from exc
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
        entry = {
            "element_id": eid,
            "primitive": el["primitive"],
            "material_id": p.material_id,
            "parameters": dict(p.model_dump()),
            "fixtures": fixtures_by_eid.get(eid, []),
            "placement_mm": {"x": x, "y": y, "z": z},
            "volume_mm3": vol,
            "mass_kg": mass,
            # PR-6 (ADR-074): one trusted per-element finishing-area path.
            # This is measured while the element's real BREP is already in
            # memory, then persisted for costing. Costing never reopens or
            # reconstructs geometry and never apportions the fused skin.
            "surface_area_mm2": sum(float(face.area) for face in s.faces()),
            "bbox_mm": dims,
            "bbox_min_mm": bb_min,
            "bbox_max_mm": bb_max,
            "centroid_mm": {"x": float(com.X), "y": float(com.Y), "z": float(com.Z)},
        }
        # FF-A1 (ADR-065): every NON-legacy primitive persists an explicit
        # mass_model block — incomplete-capable ones name their missing
        # inputs, complete ones say so outright. The frozen legacy ten emit
        # NOTHING here, which is exactly how their manifests stay
        # byte-identical (mass_model.py explains the versioning seam).
        module = PRIMITIVES[el["primitive"]]
        incomplete_inputs = tuple(
            getattr(module, "INCOMPLETE_MASS_INPUTS", ()) or ())
        if incomplete_inputs:
            entry["mass_model"] = MassTruth(
                False, mass, incomplete_inputs).wire()
        elif el["primitive"] not in LEGACY_COMPLETE_MASS_PRIMITIVES:
            entry["mass_model"] = MassTruth(True, mass, ()).wire()
        # FF-A2 (ADR-066): a primitive exposing measure_wall persists its
        # calibrated-or-unavailable wall measurement in the manifest, so
        # the fabrication gate can hold geometric_wall_measurement to the
        # v4 rule from PERSISTED evidence. Measured on the LOCAL solid —
        # the junction rule is defined in the primitive's own frame.
        # Legacy primitives expose no hook: their manifests are untouched.
        measure = getattr(module, "measure_wall", None)
        if callable(measure):
            entry["wall_measurement"] = measure(p, locals_by_eid[eid])
        manifest_elements.append(entry)
    # --- segmentation (slice C2, ADR-056) -----------------------------------
    # An oversized element is no longer refused outright: it is CUT, by the
    # kernel, into modules that are then what the workshop limits bind on.
    # This must happen before the limit checks below, because "does it fit
    # the truck" and "can the crane lift it" are questions about a MODULE.
    segmentation = build_segmentation(
        ordered_ids, by_id, validated, solids, joints, materials,
        max_module_m=max_module, joint_solids=joint_solids,
    )
    for eid in ordered_ids:
        p = validated[eid]
        mat = materials[p.material_id]
        seg = segmentation["elements"][eid]
        modules = seg["modules"]
        limit_mm = limit_m_to_mm(max_module) if max_module is not None else None

        if seg.get("refusal"):
            limit_violations.append(f"{eid}: {seg['refusal']}")
        elif limit_mm is not None:
            over = [m for m in modules
                    if not axes_fit_mm(m["bbox_mm"], limit_mm)]
            for m in over:
                b = m["bbox_mm"]
                axis, extent, axis_limit = binding_axis_mm(b, limit_mm)
                limit_violations.append(
                    f"{eid}: module {m['index']} of {len(modules)} still "
                    f"measures {b[0]:.0f} x {b[1]:.0f} x {b[2]:.0f} mm after "
                    f"segmentation, over max_module_m "
                    f"{format_limit_m(max_module)} on the {axis} axis "
                    f"({extent:.0f} mm vs {axis_limit:g} mm) — axis-aligned "
                    "planes cannot reduce this shape further; split it into "
                    "separate elements"
                )

        if max_lift is not None:
            for m in modules:
                if m["mass_kg"] <= float(max_lift):
                    continue
                piece = (
                    "as one piece" if len(modules) == 1
                    else f"module {m['index']} of {len(modules)}"
                )
                hint = ""
                wall = getattr(p, "wall_mm", None)
                if wall == 0:
                    hint = (
                        " — this element is SOLID; hollowing (wall_mm inside "
                        "the material envelope) cuts mass at the same "
                        "silhouette (signed sheet §4.2: a 1.0x1.0 m basalt "
                        "plinth drops 2121 -> 1252 kg at a 180 mm wall)"
                    )
                elif len(modules) == 1 and max_module is None:
                    hint = (
                        " — no fabrication.max_module_m was declared, so this "
                        "element ships whole; declare a module limit and it "
                        "is cut into pieces the crane can take"
                    )
                limit_violations.append(
                    f"{eid}: mass {m['mass_kg']:.1f} kg {piece} > max_lift_kg "
                    f"{float(max_lift):g} (volume {m['volume_mm3']:.0f} mm3 x "
                    f"density {mat.density_kg_per_m3:g} kg/m3, "
                    f"{p.material_id})" + hint
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
        # Slice C2 (ADR-056): what the workshop actually makes and lifts.
        # Absent from manifests written before 2026-08-27; every reader
        # treats absence as "not measured", never as zero modules.
        "segmentation": segmentation,
        # ADR-034: empty in strict mode by construction (it would have
        # raised). Non-empty only on a diagnostic build, where the Phase 8
        # fabrication gate turns each entry into a failing row.
        "fabrication_limit_violations": limit_violations,
        "strict": bool(strict),
        "total_mass_kg": sum(e["mass_kg"] for e in manifest_elements),
        # NOTE (FF-A1): when any element's mass is incomplete this value is
        # REPLACED with None just below — never zero, never a partial sum
        # posing as a total (owner correction 5, ADR-065).
        "assembly_bbox_min_mm": [
            min(e["bbox_min_mm"][i] for e in manifest_elements) for i in range(3)
        ],
        "assembly_bbox_max_mm": [
            max(e["bbox_max_mm"][i] for e in manifest_elements) for i in range(3)
        ],
        "body_count_brep": 1,
    }

    # ---- FF-A1 (ADR-065): mass truth + validation applicability ----------
    # Both keys are emitted ONLY when they carry information, so every
    # manifest composed of the frozen legacy ten stays byte-identical.
    mass_truth = assembly_mass_truth({"elements": manifest_elements})
    if not mass_truth.mass_complete:
        manifest["total_mass_kg"] = None  # never zero (owner correction 5)
        manifest["mass_model"] = mass_truth.wire()
    required_gates = sorted({
        FREEFORM_INTEGRITY_GATE
        for e in manifest_elements
        if getattr(PRIMITIVES[e["primitive"]],
                   "REQUIRES_FREEFORM_INTEGRITY", False)
    })
    if required_gates:
        # The persisted applicability snapshot: export classification reads
        # THIS, never today's registry (owner correction 1).
        manifest["required_validation_gates"] = required_gates
        # FF-A2 (ADR-066): the per-component topology contract is only
        # assertable when the assembly IS one applicable primitive — a
        # fused multi-element assembly has a different (uncontracted)
        # topology, so integrity then runs its generic checks only, and
        # the report says so. Persisted here so the validation row is
        # built from the snapshot, never the live registry.
        if len(manifest_elements) == 1:
            only = PRIMITIVES[manifest_elements[0]["primitive"]]
            declared = getattr(only, "EXPECTED_TOPOLOGY", None)
            if isinstance(declared, dict) and declared:
                manifest["expected_topology"] = dict(declared)

    if return_solids:
        return fused, manifest, solids
    return fused, manifest
