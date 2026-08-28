"""Segmentation — an oversized element becomes fabricable modules
(Phase 6 slice C2, ADR-056; plan §4.3, NEXT.md W-3b).

Before this module, an element wider than the project's declared
``fabrication.max_module_m`` was REFUSED: a 5 m basalt basin weighs
11,346 kg as one piece, no crane in Addis picks it, so the platform said
no. Segmentation turns that no into "yes, in nine modules of 1.08 to
1.47 t with 8.4 m of seam between them".

THE RULE THAT MAKES THIS HONEST: nothing here is predicted. The cut is a
real OpenCASCADE split of the real solid, and every number reported is
measured off the pieces that come out of it:

  * the module COUNT is the number of connected solids after cutting,
    never n_x * n_y * n_z. A hollow tube cut on a 3 x 3 x 2 grid gives
    SIXTEEN pieces, not the eighteen the product predicts — the centre
    cells are bore, not material. A predicted count overstates the crane
    picks and the seams, and would do it silently.
  * volume is conserved EXACTLY (measured delta 0.00000000% on every
    shape in the registry); anything above CONSERVATION_TOLERANCE_PCT is
    a construction defect and raises.
  * a seam is an INTERFACE, counted once, not a pair of cut faces
    counted twice. Four quarters of a basin share four interfaces, not
    eight. Double-counting doubles the seam bill; half-counting quietly
    under-quotes it, which is the worse of the two.

WHAT THIS DELIBERATELY REFUSES: a ring of blades or petals. Running saw
planes through a 24-blade array produces 25 fragments whose smallest is
0.9 kg against a largest of 2,685.7 kg — those are chopped-off blade tips,
not modules, and a cost model built on them would be confidently wrong.
Such primitives declare ``SEGMENTATION_MODE = "discrete_array"`` and are
refused BY NAME with the reason. Their real decomposition (hub plus N
separately-cast blades) is a different slice; see LIMITATIONS.md §11.

SECURITY NOTE: reachable from sandboxed AI code through registry.assemble
-> assembly.assemble. Keep the public surface benign — no file, network
or process access.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

#: A primitive whose shape is a continuous mass: cut it with saw planes.
MODE_PLANAR_GRID = "planar_grid"
#: A primitive that is already an array of discrete pieces around a hub.
#: Planar cuts fragment it; refused rather than fragmented.
MODE_DISCRETE_ARRAY = "discrete_array"

SEGMENTATION_MODES = (MODE_PLANAR_GRID, MODE_DISCRETE_ARRAY)

#: |sum(module volumes) - element volume| / element volume, in percent.
#: A plane cut adds and removes nothing, so agreement is exact to the
#: kernel's own quadrature; this is a defect trip, not a tolerance budget.
CONSERVATION_TOLERANCE_PCT = 1e-6

#: A face counts as lying ON a split plane when every one of its vertices
#: is within this of the plane. Cut faces come out of OCCT exactly on the
#: plane; this only absorbs float representation.
PLANE_TOLERANCE_MM = 1e-6

#: Decimal places used to pair the two halves of one interface by
#: (centre, area). 3 dp of a millimetre is a micrometre — far finer than
#: any real seam, and coarse enough that float noise cannot unpair two
#: faces that OCCT cut from the same plane.
MATCH_DP = 3

#: JUDGEMENT (ADR-056): the largest grid this module will attempt.
#: A 6 m basin at a 0.1 m module limit predicts 60 x 60 x 9 cells, which
#: is tens of thousands of boolean operations and would hang the build.
#: 256 cells keeps the worst case near the 25-solid case measured at
#: 0.92 s, i.e. tens of seconds rather than hours. Raise it if a real
#: project needs a finer split; it is a guard, not an engineering bound.
MAX_PREDICTED_CELLS = 256

_AXES = ("x", "y", "z")
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


# ---------------------------------------------------------------------------
# per-axis module limits (PR-1, ADR-059)
# ---------------------------------------------------------------------------
# The Design Spec has ALWAYS declared max_module_m as {x, y, z}
# (schemas/design_spec_v1.json requires the object); the platform used to
# collapse it to max(x,y,z), silently gating the two tighter axes against
# the loosest. These helpers are the one shared vocabulary for the three
# enforcement sites (pre-cut decision, post-cut check, fabrication gate) —
# they must never diverge, or a breach on the tight axis reads as a pass.

def normalize_module_limit_m(value: Any, *,
                             allow_scalar: bool) -> dict[str, float]:
    """Validate a max_module_m value into {"x","y","z"} metres.

    ``allow_scalar`` is True ONLY at the assemble() compatibility boundary,
    where a Designer/API scalar deliberately means a CUBIC envelope
    (Amendment 2 of the PR-1 approval). The Design-Spec mapper must pass
    allow_scalar=False: the spec schema requires the object, and accepting
    a scalar there would re-open the collapse this exists to close.

    Rejected loudly, naming the offence: missing or extra keys, booleans,
    non-numeric values, non-finite values, zero and negatives.
    """
    if isinstance(value, dict):
        keys = set(value.keys())
        if keys != set(_AXES):
            raise ValueError(
                f"fabrication.max_module_m must carry exactly the keys "
                f"x, y, z; got {sorted(keys)!r}"
            )
        out: dict[str, float] = {}
        for axis in _AXES:
            out[axis] = _positive_finite(value[axis],
                                         f"fabrication.max_module_m.{axis}")
        return out
    if allow_scalar:
        side = _positive_finite(value, "fabrication.max_module_m")
        return {axis: side for axis in _AXES}
    raise ValueError(
        f"fabrication.max_module_m must be the Design Spec object "
        f"{{x, y, z}} in metres; got {value!r}"
    )


def _positive_finite(value: Any, name: str) -> float:
    # bool is an int subclass — True would silently become a 1 m limit.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number in metres, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if number <= 0:
        raise ValueError(f"{name} must be > 0 m, got {value!r}")
    return number


def limit_m_to_mm(limit_m: dict[str, float]) -> dict[str, float]:
    return {axis: float(limit_m[axis]) * 1000.0 for axis in _AXES}


def axes_fit_mm(bbox_mm: Any, limit_mm: dict[str, float],
                eps: float = 1e-6) -> bool:
    """True when every bbox extent fits ITS OWN axis limit."""
    return all(
        float(bbox_mm[_AXIS_INDEX[axis]]) <= limit_mm[axis] + eps
        for axis in _AXES
    )


def binding_axis_mm(bbox_mm: Any,
                    limit_mm: dict[str, float]) -> tuple[str, float, float]:
    """(axis, extent_mm, axis_limit_mm) of the BINDING axis.

    The binding axis is the greatest utilization ratio extent/limit —
    NOT the largest absolute extent, which under unequal limits can name
    the wrong axis. Ties break deterministically x -> y -> z (strict >
    while iterating _AXES in order keeps the first).
    """
    best_axis = "x"
    best_ratio = -1.0
    for axis in _AXES:
        ratio = float(bbox_mm[_AXIS_INDEX[axis]]) / limit_mm[axis]
        if ratio > best_ratio:
            best_ratio = ratio
            best_axis = axis
    return (best_axis, float(bbox_mm[_AXIS_INDEX[best_axis]]),
            limit_mm[best_axis])


def format_limit_m(limit_m: dict[str, float]) -> str:
    """Human text: '2.4 m (cubic)' or 'x 2.4 m / y 2.4 m / z 2.2 m'."""
    values = [limit_m[axis] for axis in _AXES]
    if len({f"{v:g}" for v in values}) == 1:
        return f"{values[0]:g} m (cubic)"
    return " / ".join(f"{axis} {limit_m[axis]:g} m" for axis in _AXES)


# ---------------------------------------------------------------------------
# plane arithmetic
# ---------------------------------------------------------------------------

def band_count(extent_mm: float, limit_mm: float) -> int:
    """How many bands an extent must be cut into to fit a module limit.

    ``ceil(extent / limit)``, with an epsilon so that an extent which is
    EXACTLY the limit (or a float hair over it) stays one band instead of
    being split into two useless halves.
    """
    if limit_mm <= 0:
        raise ValueError(f"module limit must be > 0 mm, got {limit_mm!r}")
    return max(1, int(math.ceil(extent_mm / float(limit_mm) - 1e-9)))


def plane_offsets(bbox_min_mm: float, extent_mm: float,
                  limit_mm: float) -> list[float]:
    """Interior split-plane positions along one axis, evenly spaced.

    Even spacing (rather than "fill full-size modules then leave an
    off-cut") minimises the HEAVIEST module, and the heaviest module is
    what binds against both max_module_m and max_lift_kg. Recorded as a
    judgement call in ADR-056: a workshop buying fixed stock may prefer
    maximum-size-first, which produces full slabs plus a remnant.
    """
    n = band_count(extent_mm, limit_mm)
    return [bbox_min_mm + extent_mm * i / n for i in range(1, n)]


# ---------------------------------------------------------------------------
# kernel helpers
# ---------------------------------------------------------------------------

def _solids_of(obj: Any) -> list[Any]:
    """Unwrap whatever build123d's split() returned into a list of solids."""
    getter = getattr(obj, "solids", None)
    if getter is None:
        return [obj]
    found = getter()
    return list(found) if found else [obj]


def _sort_key(solid: Any) -> tuple[float, float, float, float]:
    bb = solid.bounding_box()
    return (round(float(bb.min.X), 6), round(float(bb.min.Y), 6),
            round(float(bb.min.Z), 6), round(float(solid.volume), 6))


def _canonical(solids: list[Any]) -> list[Any]:
    """Deterministic order. OCCT's own output order is not a contract, and
    Amendment 1 (byte-identical STEP) dies the day one is assumed."""
    return sorted(solids, key=_sort_key)


def _cut(pieces: list[Any], axis: str, offset: float) -> list[Any]:
    from build123d import Keep, Plane, split

    z_dir = tuple(1.0 if a == axis else 0.0 for a in _AXES)
    origin = tuple(float(offset) if a == axis else 0.0 for a in _AXES)
    plane = Plane(origin=origin, z_dir=z_dir)
    out: list[Any] = []
    for piece in pieces:
        out.extend(_solids_of(split(piece, bisect_by=plane, keep=Keep.BOTH)))
    return _canonical(out)


def _faces_on_plane(solid: Any, axis: str, offset: float) -> list[Any]:
    """Planar faces of ``solid`` lying wholly in the plane axis=offset.

    Every vertex must be on the plane AND the surface normal at the face
    centre must be the plane normal — a curved face that merely touches
    the plane is not a cut face and must not be billed as seam.
    """
    idx = _AXIS_INDEX[axis]
    found: list[Any] = []
    for face in solid.faces():
        verts = face.vertices()
        if not verts:
            continue
        if any(abs(float(tuple(v)[idx]) - offset) > PLANE_TOLERANCE_MM
               for v in verts):
            continue
        centre = face.center()
        if abs(float(tuple(centre)[idx]) - offset) > PLANE_TOLERANCE_MM:
            continue
        normal = face.normal_at(centre)
        if abs(abs(float(tuple(normal)[idx])) - 1.0) > 1e-6:
            continue
        found.append(face)
    return found


def _face_key(face: Any) -> tuple[float, float, float, float]:
    c = tuple(face.center())
    return (round(float(c[0]), MATCH_DP), round(float(c[1]), MATCH_DP),
            round(float(c[2]), MATCH_DP), round(float(face.area), MATCH_DP))


def _face_perimeter_mm(face: Any) -> float:
    """Total boundary length — outer wire AND any inner wires. A weld or a
    mortar joint runs around every boundary of the mating face, not only
    the outside one."""
    return sum(float(e.length) for e in face.edges())


def _interfaces_on_plane(modules: list[Any], axis: str,
                         offset: float) -> tuple[list[Any], int]:
    """The distinct interfaces created by one split plane.

    Every module lies wholly on one side of every applied plane, so the
    two halves of an interface can be paired by (centre, area): OCCT cuts
    both from the same plane, so the mating faces are geometrically
    identical.

    A face present on only ONE side is not an interface — it is a
    pre-existing face of the solid that happens to lie in the cut plane
    (a basin floor whose top surface coincides with a Z plane, say).
    Excluding it is correct; its count is returned so the coincidence is
    visible rather than silent.
    """
    idx = _AXIS_INDEX[axis]
    pos: dict[tuple[float, ...], Any] = {}
    neg: dict[tuple[float, ...], Any] = {}
    for module in modules:
        bb = module.bounding_box()
        lo = float(tuple(bb.min)[idx])
        hi = float(tuple(bb.max)[idx])
        if lo >= offset - PLANE_TOLERANCE_MM:
            side = pos
        elif hi <= offset + PLANE_TOLERANCE_MM:
            side = neg
        else:                                    # pragma: no cover - defect
            raise RuntimeError(
                f"module straddles the split plane {axis}={offset:.6f} mm "
                f"(bbox {lo:.6f} .. {hi:.6f}) — the cut did not take"
            )
        for face in _faces_on_plane(module, axis, offset):
            side[_face_key(face)] = face
    matched = set(pos) & set(neg)
    unmatched = (len(pos) - len(matched)) + (len(neg) - len(matched))
    return [pos[k] for k in sorted(matched)], unmatched


# ---------------------------------------------------------------------------
# the result
# ---------------------------------------------------------------------------

#: Decimal places the persisted module record carries. A nanometre of
#: extent and a microgram of mass are orders of magnitude below any
#: fabrication tolerance in materials.yaml (the finest is 316L at +/-0.5
#: mm per face), so the extra digits are float noise in a record humans
#: read and the BOM quotes from.
RECORD_DP = 6


def _module_record(index: int, volume_mm3: float, bbox: Any,
                   density_kg_per_m3: float) -> dict[str, Any]:
    return {
        "index": index,
        "volume_mm3": round(volume_mm3, RECORD_DP),
        "mass_kg": round(volume_mm3 * 1e-9 * float(density_kg_per_m3),
                         RECORD_DP),
        "bbox_mm": [round(float(bbox.size.X), RECORD_DP),
                    round(float(bbox.size.Y), RECORD_DP),
                    round(float(bbox.size.Z), RECORD_DP)],
        "bbox_min_mm": [round(float(bbox.min.X), RECORD_DP),
                        round(float(bbox.min.Y), RECORD_DP),
                        round(float(bbox.min.Z), RECORD_DP)],
    }


@dataclass
class SegmentResult:
    """One element's segmentation, all of it measured."""

    mode: str
    grid: dict[str, int]
    plane_offsets_mm: dict[str, list[float]]
    modules: list[dict[str, Any]]
    seam_count: int
    seam_length_mm: float
    seam_area_mm2: float
    unmatched_face_count: int
    element_volume_mm3: float
    volume_delta_pct: float
    #: Wall-clock cost of the cut. DELIBERATELY NOT in as_dict(): the
    #: manifest is sealed into the LUXEXCHANGE package and its content
    #: digest must be reproducible across two exports of the same design
    #: (ADR-035/037). A timing in there changes the digest every run —
    #: which it did, until the Phase 9A tests caught it on 2026-08-27.
    #: Read it off this object, never out of the manifest.
    duration_ms: float = 0.0
    #: only set when the element could NOT be segmented
    refusal: str | None = None
    _extra: dict[str, Any] = field(default_factory=dict)

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def predicted_cells(self) -> int:
        return self.grid["x"] * self.grid["y"] * self.grid["z"]

    @property
    def heaviest_module_kg(self) -> float:
        return max((m["mass_kg"] for m in self.modules), default=0.0)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "mode": self.mode,
            "grid": dict(self.grid),
            "plane_offsets_mm": {k: [round(v, 6) for v in vs]
                                 for k, vs in self.plane_offsets_mm.items()},
            "module_count": self.module_count,
            "predicted_cells": self.predicted_cells,
            "modules": self.modules,
            "seam_count": self.seam_count,
            "seam_length_mm": round(self.seam_length_mm, 6),
            "seam_area_mm2": round(self.seam_area_mm2, 6),
            "unmatched_face_count": self.unmatched_face_count,
            "element_volume_mm3": round(self.element_volume_mm3, 6),
            "volume_delta_pct": self.volume_delta_pct,
            "heaviest_module_kg": round(self.heaviest_module_kg, 6),
        }
        if self.refusal is not None:
            out["refusal"] = self.refusal
        out.update(self._extra)
        return out

    def canonical_json(self) -> str:
        """The record, canonically ordered — the determinism assertion's
        subject, and identical to what reaches the manifest."""
        return json.dumps(self.as_dict(), sort_keys=True,
                          separators=(",", ":"))


# ---------------------------------------------------------------------------
# the operation
# ---------------------------------------------------------------------------

def segment_solid(solid: Any, limit_mm: dict[str, float], *,
                  density_kg_per_m3: float,
                  axis_order: tuple[str, ...] = _AXES) -> SegmentResult:
    """Cut one placed solid into modules that each fit ``limit_mm``.

    ``limit_mm`` is PER-AXIS — {"x","y","z"} in millimetres (PR-1,
    ADR-059). The kernel takes exactly one shape; scalar-to-cubic
    compatibility lives at the assemble() boundary, never here.

    ``axis_order`` is a DIAGNOSTIC, not a tuning knob: production always
    cuts x then y then z, and the gate uses this argument to prove the
    result does not depend on that choice.

    MEASURED, and the reason the check is stated the way it is (ADR-056):
    the set of connected components of (solid n cell) is genuinely
    order-independent — counts, masses and seam totals agree to better
    than 1e-9 relative — but OCCT's split is NOT bit-exact under
    reordering. Cutting z-y-x gave a module extent of 1666.6666666666677
    mm where x-y-z gave 1666.6666666666667 mm: the same nanometre,
    different last bits. So order-independence is asserted as a geometric
    identity at 1e-9 relative, and BIT-identity is asserted only where it
    is actually claimed — same inputs, same code path, across processes.
    Amendment 1 is untouched either way: segmentation never touches the
    fused solid the STEP is exported from.

    Raises ValueError if the requested grid exceeds MAX_PREDICTED_CELLS,
    RuntimeError if volume is not conserved.
    """
    import time

    t0 = time.perf_counter()
    bb = solid.bounding_box()
    extents = {"x": float(bb.size.X), "y": float(bb.size.Y),
               "z": float(bb.size.Z)}
    lows = {"x": float(bb.min.X), "y": float(bb.min.Y), "z": float(bb.min.Z)}
    grid = {a: band_count(extents[a], limit_mm[a]) for a in _AXES}
    offsets = {a: plane_offsets(lows[a], extents[a], limit_mm[a])
               for a in _AXES}
    predicted = grid["x"] * grid["y"] * grid["z"]
    if predicted > MAX_PREDICTED_CELLS:
        limit_text = " x ".join(f"{limit_mm[a]:.0f}" for a in _AXES)
        raise ValueError(
            f"segmentation refused: a {extents['x']:.0f} x {extents['y']:.0f} "
            f"x {extents['z']:.0f} mm element at a {limit_text} mm module "
            f"limit needs a {grid['x']} x {grid['y']} x {grid['z']} grid = "
            f"{predicted} cells, over the {MAX_PREDICTED_CELLS}-cell ceiling. "
            "Raise fabrication.max_module_m, or split the design into more "
            "elements — no count is produced from a grid that was never cut"
        )

    element_volume = float(solid.volume)
    pieces = [solid]
    for axis in axis_order:
        for offset in offsets[axis]:
            pieces = _cut(pieces, axis, offset)
    modules = _canonical(pieces)

    seam_count = 0
    seam_length = 0.0
    seam_area = 0.0
    unmatched = 0
    for axis in _AXES:
        for offset in offsets[axis]:
            faces, missed = _interfaces_on_plane(modules, axis, offset)
            unmatched += missed
            for face in faces:
                seam_count += 1
                seam_length += _face_perimeter_mm(face)
                seam_area += float(face.area)

    records: list[dict[str, Any]] = []
    total = 0.0
    for i, module in enumerate(modules):
        vol = float(module.volume)
        total += vol
        mbb = module.bounding_box()
        records.append(_module_record(i, vol, mbb, density_kg_per_m3))

    delta_pct = (abs(total - element_volume) / element_volume * 100.0
                 if element_volume else 0.0)
    if delta_pct > CONSERVATION_TOLERANCE_PCT:
        raise RuntimeError(
            f"segmentation lost volume: {len(modules)} modules sum to "
            f"{total:.6f} mm3 but the element measures {element_volume:.6f} "
            f"mm3 (delta {delta_pct:.8f}% > {CONSERVATION_TOLERANCE_PCT:g}%) "
            "— the split produced geometry that is not the original solid"
        )

    return SegmentResult(
        mode=MODE_PLANAR_GRID,
        grid=grid,
        plane_offsets_mm=offsets,
        modules=records,
        seam_count=seam_count,
        seam_length_mm=seam_length,
        seam_area_mm2=seam_area,
        unmatched_face_count=unmatched,
        element_volume_mm3=element_volume,
        volume_delta_pct=delta_pct,
        duration_ms=(time.perf_counter() - t0) * 1000.0,
    )


def whole_element_result(solid: Any, *, density_kg_per_m3: float,
                         mode: str) -> SegmentResult:
    """The no-cut case: this element ships as one module."""
    vol = float(solid.volume)
    bb = solid.bounding_box()
    return SegmentResult(
        mode=mode,
        grid={"x": 1, "y": 1, "z": 1},
        plane_offsets_mm={a: [] for a in _AXES},
        modules=[_module_record(0, vol, bb, density_kg_per_m3)],
        seam_count=0, seam_length_mm=0.0, seam_area_mm2=0.0,
        unmatched_face_count=0,
        element_volume_mm3=vol, volume_delta_pct=0.0,
    )


def refused_result(solid: Any, *, density_kg_per_m3: float, mode: str,
                   refusal: str) -> SegmentResult:
    """An element that is over the limit and cannot honestly be cut. It is
    still ONE piece — reporting it as several would be the fabricated
    capability Rule 2 forbids."""
    result = whole_element_result(solid, density_kg_per_m3=density_kg_per_m3,
                                  mode=mode)
    result.refusal = refusal
    return result


# ---------------------------------------------------------------------------
# joint seams — where two ELEMENTS meet
# ---------------------------------------------------------------------------

def joint_contact_mm(intersection_solid: Any,
                     contact_z_mm: float) -> tuple[float, float]:
    """The run and the face area where a child element meets its parent.

    Returns ``(length_mm, area_mm2)``.

    MEASURED ON THE INTERSECTION, and the first attempt got this wrong in
    a way worth recording (ADR-056). Sectioning the CHILD at the contact
    plane returns the child's whole outline — for a 5 m basin on a 2.2 m
    plinth that is pi x 5000 = 15.708 m of "joint" where the two solids
    only actually meet over the plinth's top annulus, pi x (2200 + 1800)
    = 12.566 m. The child's outline is not the joint; the overlap solid
    is. Its top face IS the contact footprint, exactly, for a stack_on
    (parent's top) and for a concentric_insert (parent's seat) alike.

    Measuring the real face also means the bedded AREA is exact rather
    than being inferred from intersection volume / overlap depth, which
    is right for a prismatic overlap and wrong for a tapered one.
    """
    if intersection_solid is None:
        return 0.0, 0.0
    length = 0.0
    area = 0.0
    for face in _faces_on_plane(intersection_solid, "z", float(contact_z_mm)):
        length += _face_perimeter_mm(face)
        area += float(face.area)
    return length, area
