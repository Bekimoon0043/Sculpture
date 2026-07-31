"""Units wrapper tests (Rule 6): conversions, unknown units, bare floats."""

from __future__ import annotations

import pytest

from app.core.units import (
    Quantity,
    UnitConversionError,
    UnknownUnitError,
    ensure_quantity,
)


def test_mm_to_m():
    q = Quantity(250, "mm").to_m()
    assert q.unit == "m"
    assert q.value == pytest.approx(0.25)


def test_m_to_mm():
    q = Quantity(1.5, "m").to_mm()
    assert q.unit == "mm"
    assert q.value == pytest.approx(1500.0)


def test_identity_conversion():
    assert Quantity(3.2, "L").to_L().value == pytest.approx(3.2)
    assert Quantity(90, "deg").to_deg().value == pytest.approx(90.0)
    assert Quantity(412, "kg").to_kg().value == pytest.approx(412.0)
    assert Quantity(2.5, "L_per_s").to_L_per_s().value == pytest.approx(2.5)


def test_unknown_unit_raises():
    with pytest.raises(UnknownUnitError):
        Quantity(1.0, "furlong")


def test_unknown_target_unit_raises():
    with pytest.raises(UnknownUnitError):
        Quantity(1.0, "m").to("furlong")


def test_cross_dimension_conversion_raises():
    with pytest.raises(UnitConversionError):
        Quantity(10, "kg").to_m()
    with pytest.raises(UnitConversionError):
        Quantity(10, "m").to_L_per_s()


def test_non_numeric_value_rejected():
    with pytest.raises(TypeError):
        Quantity("three", "m")  # type: ignore[arg-type]


def test_bare_float_rejected_where_quantity_expected():
    with pytest.raises(TypeError):
        ensure_quantity(1.5)
    with pytest.raises(TypeError):
        ensure_quantity(None)


def test_ensure_quantity_passes_quantities_through():
    q = Quantity(1.0, "m")
    assert ensure_quantity(q) is q
