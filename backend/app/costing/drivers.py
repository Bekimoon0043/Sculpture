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
            f"total_mass_kg={report.total_mass_kg:.3f})"
        )
    mass_kg = float(report.total_mass_kg)
    volume_m3 = float(report.volume_mm3) / _MM3_PER_M3
    surface_area_m2 = float(report.surface_area_mm2) / _MM2_PER_M2

    def _unavailable(reason: str, pick: float, monolithic: bool) -> CostDrivers:
        return CostDrivers(
            mass_kg=mass_kg, volume_m3=volume_m3,
            surface_area_m2=surface_area_m2,
            crane_pick_kg=pick, monolithic=monolithic,
            module_count=None, seam_length_m=None, seam_area_m2=None,
            joint_seam_length_m=None,
            unavailable={"module_count": reason, "seam_length_m": reason,
                         "seam_area_m2": reason},
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
        unavailable=None,
    )
