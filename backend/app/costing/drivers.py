"""Cost drivers — read from the validation report, never re-measured.

Operator rule 1, verbatim: "Costs derive from validation numbers the platform
ALREADY computes — mass, surface area, module count, seam length, crane pick
weight. Never a parallel measurement path."

So this module contains NO geometry. It takes a ValidationReport that the
Phase 2 validator already produced and converts its millimetre-scale numbers
into the units the rate card is quoted in. If a driver cannot be obtained
that way it is None, with a stated reason — it is never estimated, and it is
never computed by a second measurement path that could disagree with the
validation report the operator already signed off.

Two of the five drivers the operator named — module_count and
seam_length_m — did not exist until an object could be split into
fabricable modules. **Slice C2 (ADR-056) built that**, so they are real
now, but only along the path that has a segmented assembly manifest to
read them from:

  * ``drivers_from_validation(report)`` — ONE fused solid, no manifest.
    Monolithic: one module, no seams, crane picks the whole mass. This is
    the Phase 2 single-primitive path and it is unchanged.
  * ``drivers_for_assembly(report, manifest)`` — an assembly whose
    manifest carries a ``segmentation`` block. Module count, seam length
    and seam area come STRAIGHT off that block; the crane pick becomes
    the heaviest MODULE, which is what a crane actually lifts.

Neither function measures geometry. Both read numbers the assembler
already computed and persisted, so there is exactly one measurement path
and the BOM can never disagree with the validation report the operator
signed off.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.geometry.mass_model import assembly_mass_truth
from app.geometry.validate import AssemblyValidationReport, ValidationReport

#: mm3 -> m3
_MM3_PER_M3 = 1e9
#: mm2 -> m2
_MM2_PER_M2 = 1e6


@dataclass(frozen=True)
class CostDrivers:
    """Every physical quantity a cost line is allowed to be computed from."""

    mass_kg: float
    volume_m3: float
    surface_area_m2: float
    #: Heaviest single lift. For a monolithic solid this IS the total mass —
    #: stated, not assumed; it becomes the heaviest ELEMENT once assemblies
    #: exist (Phase 6) and per-element masses are measured.
    crane_pick_kg: float
    monolithic: bool

    #: Measured by segmentation (ADR-056) when the design HAS modules;
    #: None on a monolithic solid, with the reason in ``unavailable``.
    module_count: int | None = None
    seam_length_m: float | None = None
    #: Bedded/welded face area of the split seams. Stone joints are priced
    #: by area, metal seams by run — the rate's `per` unit picks.
    seam_area_m2: float | None = None
    #: Seam run created by ELEMENT-to-element joints, as opposed to
    #: segmentation cuts. Counted in seam_length_m; broken out so the BOM
    #: can say where the seam came from.
    joint_seam_length_m: float | None = None
    #: PR-4 (ADR-067): (module id, measured mass) for every module the
    #: assembler cut, id = "<element>#<index>", read STRAIGHT off the
    #: manifest's segmentation elements — never re-measured. None when the
    #: manifest never recorded them, with the reason in ``unavailable``;
    #: the transport line refuses to load a trip without them.
    module_masses_kg: tuple[tuple[str, float], ...] | None = None

    #: Why each None driver is None, keyed by driver name. Printed verbatim
    #: on any BOM line that needed it, so the report explains itself.
    unavailable: dict[str, str] | None = None

    @property
    def mass_tonnes(self) -> float:
        return self.mass_kg / 1000.0

    def as_dict(self) -> dict[str, object]:
        return {
            "mass_kg": round(self.mass_kg, 3),
            "volume_m3": round(self.volume_m3, 6),
            "surface_area_m2": round(self.surface_area_m2, 4),
            "crane_pick_kg": round(self.crane_pick_kg, 3),
            "monolithic": self.monolithic,
            "module_count": self.module_count,
            "seam_length_m": self.seam_length_m,
            "seam_area_m2": self.seam_area_m2,
            "joint_seam_length_m": self.joint_seam_length_m,
            # rounded for the record only — allocation uses the unrounded
            # tuple on the dataclass, never this dict
            "module_masses_kg": (
                {mid: round(m, 6) for mid, m in self.module_masses_kg}
                if self.module_masses_kg is not None else None),
        }


#: Stable reasons, so the BOM text and the tests never drift apart.
#: Segmentation EXISTS since slice C2 (ADR-056). What is missing on a
#: monolithic design is not the capability, it is a declared module limit
#: to cut against — which is the operator's number, not our code.
NEEDS_SEGMENTATION = (
    "this design is one fused solid, so it has no modules and no seams. "
    "Declare fabrication.max_module_m on the Design Spec and rebuild: the "
    "assembler cuts the oversized elements and measures both. No count is "
    "guessed from a bounding box"
)

#: A manifest written before 2026-08-27 has no segmentation block.
NEEDS_REBUILD = (
    "this design was built before segmentation existed (2026-08-27), so "
    "its modules and seams were never measured. Rebuild it once and the "
    "numbers arrive — nothing is inferred from the stored record"
)


class IncompleteMassError(ValueError):
    """FF-A1 (ADR-065): raised when costing is asked to price an
    INCOMPLETE mass. Material, transport and crane lines all derive from
    mass, so no honest BOM or quote exists until the named inputs do —
    the route maps this to a structured HTTP 409 not_computable."""

    def __init__(self, known_geometry_mass_kg: float,
                 missing_mass_inputs: tuple[str, ...]) -> None:
        self.known_geometry_mass_kg = round(float(known_geometry_mass_kg), 3)
        self.missing_mass_inputs = tuple(missing_mass_inputs)
        super().__init__(
            "refusing to cost an INCOMPLETE mass — known-geometry "
            f"{self.known_geometry_mass_kg} kg excludes: "
            + "; ".join(self.missing_mass_inputs))


def drivers_from_validation(report: ValidationReport) -> CostDrivers:
    """Convert an already-computed ValidationReport into cost drivers.

    Raises ValueError if the report did not pass: costing a design that
    failed validation would put a price on geometry the platform has already
    refused, which is worse than refusing to quote.
    """
    if not report.passed:
        raise ValueError(
            "refusing to cost a design whose validation FAILED — "
            "fix the geometry before pricing it "
            f"(watertight={report.watertight}, mass_kg={report.mass_kg:.3f})"
        )
    return CostDrivers(
        mass_kg=report.mass_kg,
        volume_m3=report.volume_mm3 / _MM3_PER_M3,
        surface_area_m2=report.surface_area_mm2 / _MM2_PER_M2,
        # One fused solid (Rule 6, watertight by construction) is lifted as
        # one piece, so the pick weight is the whole mass.
        crane_pick_kg=report.mass_kg,
        monolithic=True,
        module_count=None,
        seam_length_m=None,
        unavailable={
            "module_count": NEEDS_SEGMENTATION,
            "seam_length_m": NEEDS_SEGMENTATION,
        },
    )


def drivers_for_assembly(report: AssemblyValidationReport,
                         manifest: dict | None) -> CostDrivers:
    """Cost drivers for an ASSEMBLY, from its own report plus segmentation.

    An assembly does NOT produce a ValidationReport. It produces an
    AssemblyValidationReport, which deliberately carries no material_id
    and no single mass_kg — "a fused mesh has no single material, so a
    single mass_kg would be fiction for mixed-material assemblies"
    (validate.py). That is why costing could not read one: the endpoint
    parsed every stored report as a ValidationReport and raised, so
    /api/costing/bom returned HTTP 500 for every assembly ever built.
    Found and fixed 2026-08-27 (ADR-056).

    The mass, volume and surface area still come from the report, so the
    BOM and the validation gate quote the same measurement. The manifest
    adds only the decomposition: how many modules, how much seam, and
    which single piece the crane has to pick.

    A manifest with no segmentation block (written before 2026-08-27) does
    NOT fall back to treating the design as monolithic — that would
    quietly price a 9-module basin as one 11-tonne lift. It reports those
    drivers unavailable with NEEDS_REBUILD.
    """
    if not report.passed:
        raise ValueError(
            "refusing to cost an assembly whose validation FAILED — "
            "fix the geometry before pricing it "
            f"(watertight={report.watertight}, body_count={report.body_count}, "
            f"total_mass_kg={report.total_mass_kg})"
        )
    # FF-A1 (ADR-065): an incomplete mass never becomes a price. The
    # incompleteness signals are (a) a null report total — the manifest
    # persisted total_mass_kg: null — or (b) any incomplete ELEMENT in the
    # manifest. A manifest without an element list (the minimal legacy
    # shape costing has always accepted) is judged by its report total
    # alone: that total came from a legacy complete-mass manifest.
    elements = list((manifest or {}).get("elements") or [])
    truth = assembly_mass_truth({"elements": elements}) if elements else None
    if report.total_mass_kg is None or (
            truth is not None and not truth.mass_complete):
        if truth is not None and not truth.mass_complete:
            raise IncompleteMassError(truth.known_geometry_mass_kg,
                                      truth.missing_mass_inputs)
        raise IncompleteMassError(
            sum((report.element_masses_kg or {}).values()),
            ("complete mass model for this design",))
    mass_kg = float(report.total_mass_kg)
    volume_m3 = float(report.volume_mm3) / _MM3_PER_M3
    surface_area_m2 = float(report.surface_area_mm2) / _MM2_PER_M2

    def _unavailable(reason: str, pick: float, monolithic: bool) -> CostDrivers:
        return CostDrivers(
            mass_kg=mass_kg, volume_m3=volume_m3,
            surface_area_m2=surface_area_m2,
            crane_pick_kg=pick, monolithic=monolithic,
            module_count=None, seam_length_m=None, seam_area_m2=None,
            joint_seam_length_m=None, module_masses_kg=None,
            unavailable={"module_count": reason, "seam_length_m": reason,
                         "seam_area_m2": reason, "module_masses_kg": reason},
        )

    seg = (manifest or {}).get("segmentation")
    if not seg:
        # The heaviest ELEMENT is still a better pick weight than the whole
        # assembly and it is measured, so use it — but the module count and
        # the seams were never measured and are not invented.
        heaviest_element = max(
            (float(v) for v in (report.element_masses_kg or {}).values()),
            default=mass_kg,
        )
        return _unavailable(NEEDS_REBUILD, heaviest_element, monolithic=False)

    seams = seg.get("seams") or {}
    split = seams.get("split") or {}
    joint = seams.get("joint") or {}
    module_count = int(seg.get("module_count") or 0)
    heaviest = float(seg.get("heaviest_module_kg") or 0.0)

    # An element the platform refused to segment has no honest module
    # count, so the design has none either — one refused element poisons
    # the count rather than being quietly counted as a single module.
    refused = sorted(seg.get("not_segmentable") or [])
    if refused:
        return _unavailable(
            "segmentation refused " + ", ".join(refused) + ": see the "
            "fabrication gate for the shape and the reason. A module count "
            "that skipped a refused element would understate both the "
            "pieces and the seams",
            heaviest or mass_kg, monolithic=False)
    if module_count <= 0:
        return _unavailable(NEEDS_REBUILD, mass_kg, monolithic=False)

    # PR-4 (ADR-067): the per-module masses, exactly as the assembler
    # recorded them. If the record disagrees with the module count, NO
    # masses are reported — a trip loaded from a partial list would be a
    # wrong load presented as a real one.
    module_masses: list[tuple[str, float]] = []
    for eid, entry in (seg.get("elements") or {}).items():
        for m in (entry or {}).get("modules") or []:
            module_masses.append(
                (f"{eid}#{m.get('index')}", float(m.get("mass_kg", 0.0))))
    if len(module_masses) == module_count:
        masses: tuple[tuple[str, float], ...] | None = tuple(module_masses)
        unavailable = None
    else:
        masses = None
        unavailable = {"module_masses_kg": (
            f"the manifest counts {module_count} modules but records "
            f"{len(module_masses)} per-module masses, so no honest trip "
            f"can be loaded. Rebuild the design once and the assembler "
            f"records every module's measured mass")}

    return CostDrivers(
        mass_kg=mass_kg,
        volume_m3=volume_m3,
        surface_area_m2=surface_area_m2,
        # THE CORRECTION slice C2 makes to LIMITATIONS.md §10: a crane picks
        # the heaviest module, not the assembled fountain.
        crane_pick_kg=heaviest,
        monolithic=module_count == 1,
        module_count=module_count,
        seam_length_m=float(seams.get("total_length_mm") or 0.0) / 1000.0,
        seam_area_m2=(float(split.get("area_mm2") or 0.0)
                      + float(joint.get("area_mm2") or 0.0)) / _MM2_PER_M2,
        joint_seam_length_m=float(joint.get("length_mm") or 0.0) / 1000.0,
        module_masses_kg=masses,
        unavailable=unavailable,
    )


# ---------------------------------------------------------------------------
# PR-6 (ADR-074): per-element drivers for a multi-material assembly
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElementDrivers:
    """One element's own quantities, read STRAIGHT off the persisted
    manifest the assembler wrote — never re-measured here.

    ``exposed_area_m2`` is the element's full skin MINUS the contact faces
    of the joints it takes part in (both recorded by the assembler). It is
    never a proportional share of the fused total: that would spread one
    element's area over another's material. When a joint the element is
    in has no recorded contact area, ``exposed_area_m2`` is None with the
    reason in ``unavailable``.
    """

    element_id: str
    primitive: str
    material_id: str
    mass_kg: float
    volume_m3: float
    #: full element skin as measured by the mesh of THIS element alone
    surface_area_m2: float | None
    exposed_area_m2: float | None
    #: segmentation cuts INSIDE this element (never the joints)
    module_count: int | None
    split_seam_length_m: float | None
    split_seam_area_m2: float | None
    unavailable: dict[str, str] | None = None

    def as_dict(self) -> dict[str, object]:
        def _r(v: float | None, dp: int) -> float | None:
            return round(v, dp) if v is not None else None
        return {
            "element_id": self.element_id,
            "primitive": self.primitive,
            "material_id": self.material_id,
            "mass_kg": round(self.mass_kg, 3),
            "volume_m3": round(self.volume_m3, 6),
            "surface_area_m2": _r(self.surface_area_m2, 4),
            "exposed_area_m2": _r(self.exposed_area_m2, 4),
            "module_count": self.module_count,
            "split_seam_length_m": _r(self.split_seam_length_m, 3),
            "split_seam_area_m2": _r(self.split_seam_area_m2, 4),
            "unavailable": self.unavailable,
        }


@dataclass(frozen=True)
class JointDrivers:
    """One element-to-element joint as the assembler measured it."""

    parent_id: str
    child_id: str
    parent_material: str
    child_material: str
    joint_type: str
    length_m: float
    area_m2: float

    def as_dict(self) -> dict[str, object]:
        return {
            "parent_id": self.parent_id, "child_id": self.child_id,
            "parent_material": self.parent_material,
            "child_material": self.child_material,
            "joint_type": self.joint_type,
            "length_m": round(self.length_m, 3),
            "area_m2": round(self.area_m2, 4),
        }


#: Reason an element's skin area is unknown: the assembler did not persist
#: a per-element surface. Manifests written before PR-6 carry none.
NEEDS_ELEMENT_AREA = (
    "this element's own surface area was not recorded in the manifest "
    "(designs built before 2026-09-28 carry none). Rebuild the design once "
    "and the assembler records every element's skin; nothing is "
    "apportioned from the fused total"
)


def drivers_per_element(
    report: AssemblyValidationReport, manifest: dict | None,
) -> tuple[list[ElementDrivers], list[JointDrivers]]:
    """Per-element and per-joint drivers for a multi-material BOM.

    Refuses (same exceptions as ``drivers_for_assembly``) when validation
    failed or the mass is incomplete: a per-element price on a refused or
    half-known design is still a wrong number.
    """
    if not report.passed:
        raise ValueError(
            "refusing to cost an assembly whose validation FAILED — "
            "fix the geometry before pricing it "
            f"(watertight={report.watertight}, body_count={report.body_count}, "
            f"total_mass_kg={report.total_mass_kg})"
        )
    elements = list((manifest or {}).get("elements") or [])
    if not elements:
        raise ValueError(
            "per-element costing needs the assembly manifest's element list "
            "and this design's manifest has none")
    truth = assembly_mass_truth({"elements": elements})
    if report.total_mass_kg is None or not truth.mass_complete:
        raise IncompleteMassError(truth.known_geometry_mass_kg,
                                  truth.missing_mass_inputs)

    seg = (manifest or {}).get("segmentation") or {}
    seg_elements = seg.get("elements") or {}
    joint_records = ((seg.get("seams") or {}).get("joint") or {}).get(
        "joints") or []
    joints_declared = (manifest or {}).get("joints") or []
    by_child = {str(j.get("child")): j for j in joints_declared}
    material_of = {str(e["element_id"]): str(e["material_id"])
                   for e in elements}

    # Joint contact area charged against each element it touches — the
    # subtraction that turns a full skin into an EXPOSED skin.
    contact_by_element: dict[str, float] = {}
    contact_known: dict[str, bool] = {eid: True for eid in material_of}
    joints: list[JointDrivers] = []
    for rec in joint_records:
        child = str(rec.get("child"))
        parent = str(rec.get("parent"))
        area_mm2 = rec.get("area_mm2")
        length_mm = rec.get("length_mm")
        if area_mm2 is None or length_mm is None:
            contact_known[child] = False
            contact_known[parent] = False
            continue
        area_m2 = float(area_mm2) / _MM2_PER_M2
        contact_by_element[child] = contact_by_element.get(child, 0.0) + area_m2
        contact_by_element[parent] = contact_by_element.get(parent, 0.0) + area_m2
        joints.append(JointDrivers(
            parent_id=parent, child_id=child,
            parent_material=material_of.get(parent, ""),
            child_material=material_of.get(child, ""),
            joint_type=str(rec.get("type") or
                           (by_child.get(child) or {}).get("type") or ""),
            length_m=float(length_mm) / 1000.0,
            area_m2=area_m2,
        ))
    # A declared joint the segmentation block never measured (pre-C2
    # manifest) leaves both its elements' exposed area unknown.
    measured_children = {j.child_id for j in joints}
    for child, j in by_child.items():
        if child not in measured_children:
            contact_known[child] = False
            contact_known[str(j.get("parent"))] = False

    out: list[ElementDrivers] = []
    for e in elements:
        eid = str(e["element_id"])
        unavailable: dict[str, str] = {}
        area_mm2 = e.get("surface_area_mm2")
        surface_m2 = (float(area_mm2) / _MM2_PER_M2
                      if area_mm2 is not None else None)
        if surface_m2 is None:
            unavailable["surface_area_m2"] = NEEDS_ELEMENT_AREA
            exposed = None
        elif not contact_known.get(eid, True):
            exposed = None
            unavailable["exposed_area_m2"] = (
                f"a joint on {eid} has no measured contact face in the "
                f"manifest, so its exposed skin cannot be separated from "
                f"the bedded face. Rebuild the design once")
        else:
            exposed = max(surface_m2 - contact_by_element.get(eid, 0.0), 0.0)

        seg_e = seg_elements.get(eid) or {}
        if seg_e and "refusal" not in seg_e:
            module_count: int | None = int(seg_e.get("module_count") or 0)
            split_len: float | None = float(
                seg_e.get("seam_length_mm") or 0.0) / 1000.0
            split_area: float | None = float(
                seg_e.get("seam_area_mm2") or 0.0) / _MM2_PER_M2
        else:
            module_count, split_len, split_area = None, None, None
            unavailable["module_count"] = (
                (f"segmentation refused {eid}: " + str(seg_e.get("refusal")))
                if seg_e else (NEEDS_REBUILD if seg else NEEDS_SEGMENTATION))
        out.append(ElementDrivers(
            element_id=eid,
            primitive=str(e.get("primitive") or ""),
            material_id=material_of[eid],
            mass_kg=float(e["mass_kg"]),
            volume_m3=float(e["volume_mm3"]) / _MM3_PER_M3,
            surface_area_m2=surface_m2,
            exposed_area_m2=exposed,
            module_count=module_count,
            split_seam_length_m=split_len,
            split_seam_area_m2=split_area,
            unavailable=unavailable or None,
        ))
    return out, joints
