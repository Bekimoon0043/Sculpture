"""Unit-safe quantities (Rule 6: unitless numbers are a bug).

Every physical number in the platform is a ``Quantity(value, unit)`` from the
allowed unit set {m, mm, deg, kg, L, L_per_s} — the same set enforced by
``$defs/dimension`` in schemas/design_spec_v1.json. Bare floats are rejected
wherever a Quantity is expected; unknown units and cross-dimension
conversions raise immediately.
"""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_UNITS: frozenset[str] = frozenset({"m", "mm", "deg", "kg", "L", "L_per_s"})

# Units grouped by physical dimension; conversion is only legal inside a group.
_DIMENSION_GROUPS: list[frozenset[str]] = [
    frozenset({"m", "mm"}),      # length
    frozenset({"deg"}),          # angle
    frozenset({"kg"}),           # mass
    frozenset({"L"}),            # volume
    frozenset({"L_per_s"}),      # flow rate
]

# Factor to convert a unit into its group's canonical (SI) unit.
_TO_CANONICAL: dict[str, float] = {
    "m": 1.0,
    "mm": 0.001,
    "deg": 1.0,
    "kg": 1.0,
    "L": 1.0,
    "L_per_s": 1.0,
}


class UnknownUnitError(ValueError):
    """Raised when a unit is outside the allowed set."""


class UnitConversionError(ValueError):
    """Raised when converting across physical dimensions (e.g. kg -> m)."""


def _dimension_group(unit: str) -> frozenset[str]:
    for group in _DIMENSION_GROUPS:
        if unit in group:
            return group
    raise UnknownUnitError(
        f"unknown unit {unit!r}; allowed units are {sorted(ALLOWED_UNITS)}"
    )


@dataclass(frozen=True)
class Quantity:
    """A physical number that can never lose its unit."""

    value: float
    unit: str

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError(
                f"Quantity value must be a real number, got {self.value!r}"
            )
        _dimension_group(self.unit)  # raises UnknownUnitError if not allowed

    def to(self, target_unit: str) -> "Quantity":
        """Convert within the same physical dimension; raise otherwise."""
        src_group = _dimension_group(self.unit)
        dst_group = _dimension_group(target_unit)  # validates target too
        if src_group is not dst_group:
            raise UnitConversionError(
                f"cannot convert {self.unit!r} to {target_unit!r}: "
                "different physical dimensions"
            )
        canonical = self.value * _TO_CANONICAL[self.unit]
        return Quantity(canonical / _TO_CANONICAL[target_unit], target_unit)

    # Convenience converters (the "... etc." of SPEC section E).
    def to_m(self) -> "Quantity":
        return self.to("m")

    def to_mm(self) -> "Quantity":
        return self.to("mm")

    def to_deg(self) -> "Quantity":
        return self.to("deg")

    def to_kg(self) -> "Quantity":
        return self.to("kg")

    def to_L(self) -> "Quantity":
        return self.to("L")

    def to_L_per_s(self) -> "Quantity":
        return self.to("L_per_s")


def ensure_quantity(value: object) -> Quantity:
    """Type guard for functions that expect a Quantity.

    A bare float is a bug (Rule 6) — reject it loudly instead of guessing
    a unit.
    """
    if not isinstance(value, Quantity):
        raise TypeError(
            f"expected a Quantity with an explicit unit, got {value!r} "
            f"({type(value).__name__}); unitless numbers are not allowed"
        )
    return value
