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

Two of the five drivers the operator named are NOT available yet, and the
reason is the same for both: they do not exist until the object is split into
fabricable modules.

  * module_count  — needs segmentation against fabrication.max_module_m
  * seam_length_m — there are no seams until there are modules

Segmentation is Phase 6 work (PHASE_6_PLAN §4.3). Until it lands, any BOM
line that depends on those two reports `not_computable` and names what is
required, which is a different thing from a missing rate: a missing rate is
the operator's to supply, a missing driver is ours to build.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.geometry.validate import ValidationReport

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

    #: Not measurable until segmentation exists — see the module docstring.
    module_count: int | None = None
    seam_length_m: float | None = None

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
        }


#: Stable reasons, so the BOM text and the tests never drift apart.
NEEDS_SEGMENTATION = (
    "requires segmentation of the solid into fabricable modules "
    "(fabrication.max_module_m), which is Phase 6 work and is not built — "
    "no count is guessed"
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
