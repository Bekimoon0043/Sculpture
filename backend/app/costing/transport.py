"""Trip allocation — a deterministic conservative feasible allocation.

PR-4 (ADR-067). Until this slice the transport line printed
``max(ceil(mass/payload), ceil(modules/per_trip))`` — a LOWER BOUND on the
trip count presented as the trip count. Four 6 t modules at a 10 t payload
disprove it: no two share a truck, so the real answer is four trips where
the bound said three. That failure case is preserved verbatim in ADR-067
and in the tests; the formula never returns.

This module loads the trucks the way a yard actually does:

* modules sorted by mass DESCENDING, ties broken by module id ASCENDING —
  so the allocation is a pure function of the module set, never of input
  order;
* each module goes on the FIRST trip that still has room for it under BOTH
  limits — the payload in kg and the bed count — first-fit-decreasing;
* every capacity comparison uses the unrounded masses (``math.fsum``);
  rounding is display-only, done by the BOM renderer, never here.

The result is FEASIBLE (every trip obeys both limits) and CONSERVATIVE
(it may use more trips than the cleverest packing would). It is described
only as "a deterministic conservative feasible allocation" — operator
amendment 3, binding — and never as the lowest count achievable.

Two invariants are gated INDEPENDENTLY of the packing loop
(``verify_allocation``, also called by ``gate_pr4_auto.py`` on the
printed result): every module id appears exactly once across the trips,
and the trip loads sum exactly to the input masses.

No geometry, no I/O, no rates — pure arithmetic over (id, mass) pairs the
assembler already measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

#: The one judgement value in PR-4 [J]: how far the per-module masses may
#: disagree with the validation report's total before the BOM refuses to
#: load a trip from them. Deliberately tighter than segmentation's own
#: volume-conservation tolerance, so a real bookkeeping defect cannot hide
#: inside a legitimate measurement band.
MODULE_MASS_AGREEMENT_PCT = 0.1

#: What the BOM prints for how the trips were produced. The wording is the
#: operator's (amendment 3): feasible and conservative, with the method
#: named — never a claim that the count is the lowest achievable.
METHOD_LABEL = ("a deterministic conservative feasible allocation "
                "(first-fit-decreasing: heaviest module first, ties by "
                "module id, first trip with room under both limits)")


class AllocationInputError(ValueError):
    """The module list or a capacity is malformed — refused loudly, never
    allocated around. Empty/duplicate ids, non-finite or non-positive
    masses, invalid payloads and non-positive/non-integral bed counts all
    land here (operator safeguards, PR-4 approval)."""


class NoFeasibleAllocation(ValueError):
    """A module exceeds the truck payload, so NO valid allocation exists.
    Names the module and both numbers — amendment 3's refusal case."""

    def __init__(self, module_id: str, mass_kg: float,
                 payload_kg: float) -> None:
        self.module_id = module_id
        self.mass_kg = float(mass_kg)
        self.payload_kg = float(payload_kg)
        super().__init__(
            f"module {module_id} weighs {self.mass_kg:,.3f} kg and the "
            f"truck payload is {self.payload_kg:,.3f} kg — no trip can "
            f"carry it. Split the design further (a smaller "
            f"fabrication.max_module_m) or supply a larger "
            f"install.truck_payload_kg")


class AllocationVerificationError(RuntimeError):
    """The independent invariant gate failed — an allocation claimed
    something its own numbers do not support. This is an internal defect
    and it fails LOUDLY: a wrong allocation silently priced would put real
    steel on a road illegally."""


@dataclass(frozen=True)
class Trip:
    """One truck load, fully stated: which modules, their masses, the
    exact load, and what capacity was left on both limits."""

    index: int                              # 1-based, in loading order
    module_ids: tuple[str, ...]
    module_masses_kg: tuple[float, ...]     # unrounded, same order as ids
    load_kg: float                          # exact fsum of the masses
    remaining_payload_kg: float             # payload - load, unrounded
    remaining_module_slots: int             # bed count - modules aboard


@dataclass(frozen=True)
class TripAllocation:
    payload_kg: float
    modules_per_trip: int
    trips: tuple[Trip, ...]
    total_mass_kg: float                    # exact fsum of the input masses
    method: str = "first_fit_decreasing_v1"

    @property
    def trip_count(self) -> int:
        return len(self.trips)

    @property
    def method_label(self) -> str:
        return METHOD_LABEL


def _validate_capacities(payload_kg: float, modules_per_trip: float) -> int:
    if not isinstance(payload_kg, (int, float)) or isinstance(payload_kg, bool) \
            or not math.isfinite(payload_kg) or payload_kg <= 0:
        raise AllocationInputError(
            f"truck payload must be a finite positive number of kg, "
            f"got {payload_kg!r}")
    if not isinstance(modules_per_trip, (int, float)) \
            or isinstance(modules_per_trip, bool) \
            or not math.isfinite(float(modules_per_trip)) \
            or float(modules_per_trip) < 1 \
            or not float(modules_per_trip).is_integer():
        raise AllocationInputError(
            f"modules per trip must be a positive whole number, "
            f"got {modules_per_trip!r}")
    return int(modules_per_trip)


def validate_modules(modules: Sequence[tuple[str, float]]) -> None:
    """Reject malformed module records before any trip is loaded."""
    if not modules:
        raise AllocationInputError("no modules to allocate — an empty "
                                   "module list has no trips")
    seen: set[str] = set()
    for entry in modules:
        try:
            mid, mass = entry
        except (TypeError, ValueError):
            raise AllocationInputError(
                f"a module record must be an (id, mass_kg) pair, "
                f"got {entry!r}") from None
        if not isinstance(mid, str) or not mid.strip():
            raise AllocationInputError(
                f"a module id must be a non-empty string, got {mid!r}")
        if mid in seen:
            raise AllocationInputError(
                f"module id {mid!r} appears more than once — every module "
                f"is one physical piece and ships exactly once")
        seen.add(mid)
        if not isinstance(mass, (int, float)) or isinstance(mass, bool) \
                or not math.isfinite(float(mass)) or float(mass) <= 0:
            raise AllocationInputError(
                f"module {mid!r} has mass {mass!r} — a module mass must be "
                f"a finite positive number of kg")


def allocate_trips(modules: Sequence[tuple[str, float]], payload_kg: float,
                   modules_per_trip: float) -> TripAllocation:
    """First-fit-decreasing over the measured module masses.

    Deterministic: the result depends only on the module SET and the two
    capacities. Raises :class:`NoFeasibleAllocation` when a module exceeds
    the payload, :class:`AllocationInputError` on malformed input, and
    :class:`AllocationVerificationError` if its own result fails the
    independent invariant gate (which would be an internal defect).
    """
    validate_modules(modules)
    per_trip = _validate_capacities(payload_kg, modules_per_trip)
    payload = float(payload_kg)

    order = sorted(((str(mid), float(mass)) for mid, mass in modules),
                   key=lambda m: (-m[1], m[0]))

    loads: list[list[tuple[str, float]]] = []
    for mid, mass in order:
        if mass > payload:
            raise NoFeasibleAllocation(mid, mass, payload)
        for trip in loads:
            if len(trip) >= per_trip:
                continue
            # the candidate load is re-summed with fsum, not accumulated,
            # so the comparison is exact and order-independent
            if math.fsum([m for _, m in trip] + [mass]) <= payload:
                trip.append((mid, mass))
                break
        else:
            loads.append([(mid, mass)])

    trips = []
    for i, trip in enumerate(loads, start=1):
        masses = tuple(m for _, m in trip)
        load = math.fsum(masses)
        trips.append(Trip(
            index=i,
            module_ids=tuple(mid for mid, _ in trip),
            module_masses_kg=masses,
            load_kg=load,
            remaining_payload_kg=payload - load,
            remaining_module_slots=per_trip - len(trip),
        ))

    allocation = TripAllocation(
        payload_kg=payload, modules_per_trip=per_trip,
        trips=tuple(trips),
        total_mass_kg=math.fsum(m for _, m in modules),
    )
    verify_allocation(modules, payload, per_trip, allocation)
    return allocation


def verify_allocation(modules: Sequence[tuple[str, float]], payload_kg: float,
                      modules_per_trip: int,
                      allocation: TripAllocation) -> None:
    """The independent gate on any allocation, tamper-evident by design.

    Checks, from the allocation's OWN printed content and the original
    module list — never from the packing loop's internal state:

      1. ID PARTITION — every input module id appears on exactly one trip,
         and no trip carries an id that was never input.
      2. MASS CONSERVATION — each trip's load equals the fsum of its own
         module masses, those masses match the input records, and the trip
         loads fsum exactly to the input total (fsum is order-independent,
         so 'exactly' means exactly).
      3. CAPACITIES — every load <= payload and every module count <= the
         bed count, compared unrounded.
    """
    by_id = {}
    for mid, mass in modules:
        by_id[str(mid)] = float(mass)

    placed: list[str] = []
    for trip in allocation.trips:
        if len(trip.module_ids) != len(trip.module_masses_kg):
            raise AllocationVerificationError(
                f"trip {trip.index} lists {len(trip.module_ids)} ids but "
                f"{len(trip.module_masses_kg)} masses")
        if len(trip.module_ids) > modules_per_trip:
            raise AllocationVerificationError(
                f"trip {trip.index} carries {len(trip.module_ids)} modules "
                f"over the bed count of {modules_per_trip}")
        for mid, mass in zip(trip.module_ids, trip.module_masses_kg):
            if mid not in by_id:
                raise AllocationVerificationError(
                    f"trip {trip.index} carries unknown module {mid!r}")
            if float(mass) != by_id[mid]:
                raise AllocationVerificationError(
                    f"trip {trip.index} records module {mid} at "
                    f"{mass!r} kg but the input says {by_id[mid]!r} kg")
            placed.append(mid)
        load = math.fsum(trip.module_masses_kg)
        if trip.load_kg != load:
            raise AllocationVerificationError(
                f"trip {trip.index} claims a load of {trip.load_kg!r} kg "
                f"but its modules sum to {load!r} kg")
        if load > float(payload_kg):
            raise AllocationVerificationError(
                f"trip {trip.index} is loaded to {load:,.3f} kg over the "
                f"{float(payload_kg):,.3f} kg payload")

    if sorted(placed) != sorted(by_id):
        missing = sorted(set(by_id) - set(placed))
        extra_or_dup = sorted(mid for mid in set(placed)
                              if placed.count(mid) > 1)
        raise AllocationVerificationError(
            f"the trips do not partition the modules: "
            f"missing={missing}, duplicated={extra_or_dup}")

    total = math.fsum(by_id.values())
    trip_total = math.fsum(t.load_kg for t in allocation.trips)
    if trip_total != total:
        raise AllocationVerificationError(
            f"mass is not conserved: trips carry {trip_total!r} kg, the "
            f"modules total {total!r} kg")
