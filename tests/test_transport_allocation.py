"""PR-4 (ADR-067): the trip allocator — a deterministic conservative
feasible allocation, proven by loading, not bounded by arithmetic.

The old transport line printed max(ceil(mass/payload), ceil(modules/per_trip))
— a LOWER BOUND presented as a trip count. Amendment 3 (operator, binding):
the BOM says "a deterministic conservative feasible allocation", prints every
trip's module IDs, masses, load and remaining capacity, refuses any module
over the payload, and reports not_computable when no valid allocation exists.

Every test here uses real numbers on both sides of every assertion.
"""

from __future__ import annotations

import math
import random

import pytest

from app.costing.transport import (
    AllocationInputError,
    AllocationVerificationError,
    NoFeasibleAllocation,
    Trip,
    TripAllocation,
    allocate_trips,
    verify_allocation,
)

# ---------------------------------------------------------------------------
# the operator's four adversarial cases (amendment 3 / PR-4 approval)
# ---------------------------------------------------------------------------


def test_module_over_payload_is_refused_naming_the_module():
    """Adversarial case 1: a module no truck can carry stops the line dead."""
    with pytest.raises(NoFeasibleAllocation) as exc:
        allocate_trips([("m_small", 1000.0), ("m_big", 6000.0)],
                       payload_kg=5000.0, modules_per_trip=4)
    msg = str(exc.value)
    assert "m_big" in msg
    assert "6,000" in msg          # the module's mass
    assert "5,000" in msg          # the payload it exceeds
    assert exc.value.module_id == "m_big"
    assert exc.value.mass_kg == 6000.0
    assert exc.value.payload_kg == 5000.0


def test_lower_bound_is_beaten_four_six_tonne_modules_need_four_trucks():
    """Adversarial case 2: the case that disproves the old formula.

    masses [6000 x 4] at payload 10000, 4 modules per trip:
      old lower bound = max(ceil(24000/10000)=3, ceil(4/4)=1) = 3
      reality: no two 6 t modules share a 10 t truck -> 4 trips.
    """
    modules = [(f"m{i}", 6000.0) for i in range(1, 5)]
    old_bound = max(math.ceil(24000.0 / 10000.0), math.ceil(4 / 4))
    assert old_bound == 3  # what the old line would have printed
    alloc = allocate_trips(modules, payload_kg=10000.0, modules_per_trip=4)
    assert alloc.trip_count == 4
    assert alloc.trip_count > old_bound
    for trip in alloc.trips:
        assert len(trip.module_ids) == 1
        assert trip.load_kg == 6000.0


def test_bed_space_binds_when_weight_is_plentiful():
    """Adversarial case 3: five light modules, two to a bed -> 3 trips."""
    modules = [(f"m{i}", 1000.0) for i in range(1, 6)]
    alloc = allocate_trips(modules, payload_kg=1_000_000.0, modules_per_trip=2)
    assert alloc.trip_count == 3
    assert [len(t.module_ids) for t in alloc.trips] == [2, 2, 1]
    # weight was never the constraint: every trip has payload to spare
    for t in alloc.trips:
        assert t.remaining_payload_kg > 900_000.0
    assert alloc.trips[0].remaining_module_slots == 0
    assert alloc.trips[2].remaining_module_slots == 1


def test_weight_binds_when_bed_space_is_plentiful():
    """Adversarial case 4: three 1.5 t modules at 2 t payload -> 3 trips."""
    modules = [(f"m{i}", 1500.0) for i in range(1, 4)]
    alloc = allocate_trips(modules, payload_kg=2000.0, modules_per_trip=10)
    assert alloc.trip_count == 3
    for t in alloc.trips:
        assert len(t.module_ids) == 1
        assert t.remaining_module_slots == 9
        assert t.remaining_payload_kg == 500.0


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------

_MIXED = [
    ("b1#0", 1300.0), ("b1#1", 1300.0), ("b1#2", 1300.0), ("b1#3", 1300.0),
    ("b1#4", 1300.0), ("b1#5", 1300.0), ("b1#6", 1300.0), ("b1#7", 1300.0),
    ("b1#8", 946.137), ("p1#0", 2375.044),
]


def test_identical_input_gives_identical_allocation():
    a = allocate_trips(list(_MIXED), 12000.0, 4)
    b = allocate_trips(list(_MIXED), 12000.0, 4)
    assert a == b


def test_input_order_does_not_change_the_allocation():
    """The allocation is a function of the module SET, not the input order."""
    shuffled = list(_MIXED)
    random.Random(0).shuffle(shuffled)
    assert shuffled != _MIXED  # the shuffle actually moved something
    assert allocate_trips(shuffled, 12000.0, 4) == \
        allocate_trips(list(_MIXED), 12000.0, 4)


def test_equal_masses_tie_break_by_module_id_ascending():
    alloc = allocate_trips([("b", 100.0), ("a", 100.0), ("c", 100.0)],
                           payload_kg=100.0, modules_per_trip=4)
    assert [t.module_ids for t in alloc.trips] == [("a",), ("b",), ("c",)]


# ---------------------------------------------------------------------------
# capacity comparisons are UNROUNDED (operator safeguard)
# ---------------------------------------------------------------------------


def test_capacity_comparison_uses_unrounded_masses():
    """5.0004 + 5.0004 = 10.0008 kg > 10 kg payload. Displayed at one
    decimal both read 5.0 and 'fit' — the comparison must not."""
    alloc = allocate_trips([("m1", 5.0004), ("m2", 5.0004)],
                           payload_kg=10.0, modules_per_trip=4)
    assert alloc.trip_count == 2
    # and the converse: an unrounded sum that DOES fit shares one trip
    alloc2 = allocate_trips([("m1", 5.0004), ("m2", 4.9995)],
                            payload_kg=10.0, modules_per_trip=4)
    assert alloc2.trip_count == 1


# ---------------------------------------------------------------------------
# input rejection (operator safeguards, verbatim)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modules,payload,per_trip", [
    ([], 1000.0, 4),                                   # no modules at all
    ([("", 100.0)], 1000.0, 4),                        # empty id
    ([("   ", 100.0)], 1000.0, 4),                     # whitespace id
    ([("m1", 100.0), ("m1", 200.0)], 1000.0, 4),       # duplicate id
    ([("m1", float("nan"))], 1000.0, 4),               # non-finite mass
    ([("m1", float("inf"))], 1000.0, 4),               # non-finite mass
    ([("m1", 0.0)], 1000.0, 4),                        # non-positive mass
    ([("m1", -5.0)], 1000.0, 4),                       # negative mass
    ([("m1", 100.0)], 0.0, 4),                         # zero payload
    ([("m1", 100.0)], -10.0, 4),                       # negative payload
    ([("m1", 100.0)], float("nan"), 4),                # non-finite payload
    ([("m1", 100.0)], float("inf"), 4),                # non-finite payload
    ([("m1", 100.0)], 1000.0, 0),                      # zero bed count
    ([("m1", 100.0)], 1000.0, -1),                     # negative bed count
    ([("m1", 100.0)], 1000.0, 2.5),                    # fractional bed count
])
def test_malformed_inputs_are_rejected(modules, payload, per_trip):
    with pytest.raises(AllocationInputError):
        allocate_trips(modules, payload, per_trip)


def test_an_integral_float_bed_count_is_accepted():
    alloc = allocate_trips([("m1", 100.0)], 1000.0, 4.0)
    assert alloc.modules_per_trip == 4


# ---------------------------------------------------------------------------
# the two independently gated invariants: ID partition + mass conservation
# ---------------------------------------------------------------------------


def test_every_module_id_appears_exactly_once_across_the_trips():
    rng = random.Random(42)
    modules = [(f"e{i % 3}#{i}", round(rng.uniform(50.0, 4000.0), 6))
               for i in range(13)]
    alloc = allocate_trips(modules, payload_kg=6000.0, modules_per_trip=3)
    placed = [mid for t in alloc.trips for mid in t.module_ids]
    assert sorted(placed) == sorted(mid for mid, _ in modules)
    assert len(placed) == len(set(placed)) == 13


def test_mass_is_conserved_and_every_capacity_holds():
    rng = random.Random(7)
    modules = [(f"m{i}", round(rng.uniform(50.0, 4000.0), 6))
               for i in range(17)]
    payload, per_trip = 6000.0, 4
    alloc = allocate_trips(modules, payload, per_trip)
    assert alloc.total_mass_kg == math.fsum(m for _, m in modules)
    assert math.fsum(t.load_kg for t in alloc.trips) == pytest.approx(
        alloc.total_mass_kg, abs=1e-9)
    for t in alloc.trips:
        assert t.load_kg == math.fsum(t.module_masses_kg)
        assert t.load_kg <= payload
        assert len(t.module_ids) <= per_trip
        assert t.remaining_payload_kg == payload - t.load_kg


def test_verify_allocation_catches_a_dropped_module():
    modules = [("m1", 3000.0), ("m2", 2000.0), ("m3", 1000.0)]
    alloc = allocate_trips(modules, 6000.0, 3)
    # forge an allocation that silently lost m3
    forged = TripAllocation(
        payload_kg=6000.0, modules_per_trip=3,
        trips=(Trip(index=1, module_ids=("m1", "m2"),
                    module_masses_kg=(3000.0, 2000.0), load_kg=5000.0,
                    remaining_payload_kg=1000.0, remaining_module_slots=1),),
        total_mass_kg=5000.0, method=alloc.method)
    with pytest.raises(AllocationVerificationError):
        verify_allocation(modules, 6000.0, 3, forged)


def test_verify_allocation_catches_an_overloaded_trip():
    modules = [("m1", 4000.0), ("m2", 3000.0)]
    forged = TripAllocation(
        payload_kg=6000.0, modules_per_trip=3,
        trips=(Trip(index=1, module_ids=("m1", "m2"),
                    module_masses_kg=(4000.0, 3000.0), load_kg=7000.0,
                    remaining_payload_kg=-1000.0, remaining_module_slots=1),),
        total_mass_kg=7000.0, method="first_fit_decreasing_v1")
    with pytest.raises(AllocationVerificationError):
        verify_allocation(modules, 6000.0, 3, forged)


def test_the_allocation_is_described_as_feasible_never_as_fewest():
    """Amendment 3 wording, enforced at the source: the method string the
    BOM prints says 'deterministic conservative feasible allocation' and
    never claims the count is the lowest achievable."""
    alloc = allocate_trips([("m1", 100.0)], 1000.0, 4)
    label = alloc.method_label
    assert "deterministic conservative feasible allocation" in label
    for banned in ("minimal", "minimum", "optimal", "fewest"):
        assert banned not in label.lower()
