"""Phase 6 slice C2 — segmentation, on real geometry only.

Every number in this file is either measured by the kernel or derived by
hand arithmetic written out in the test. Nothing is mocked: a mock that
returns the module count it was told to return proves nothing about
whether a 5 m basin can be cut into pieces a crane can lift.
"""

from __future__ import annotations

import math

import pytest

from app.geometry.assembly import assemble
from app.geometry.primitives import PRIMITIVES
from app.geometry.primitives.base import ConstraintViolation
from app.geometry.segmentation import (
    MAX_PREDICTED_CELLS,
    MODE_DISCRETE_ARRAY,
    MODE_PLANAR_GRID,
    plane_offsets,
    segment_solid,
)

BASALT_DENSITY = 2700.0


def _cubic(limit_mm: float) -> dict[str, float]:
    """PR-1 (ADR-059): the kernel takes per-axis mm; a cube is the
    compatibility meaning of the Designer's single number."""
    return {"x": limit_mm, "y": limit_mm, "z": limit_mm}


def _basin(**over):
    raw = {"diameter_mm": 5000, "height_mm": 700, "wall_mm": 150,
           "material_id": "basalt_slab"}
    raw.update(over)
    module = PRIMITIVES["basin_round"]
    return module.build(module.validate(raw))


# --- the plane arithmetic ---------------------------------------------------

def test_plane_offsets_are_even_and_interior():
    # extent 5000 mm at a 2400 mm limit -> ceil(5000/2400) = 3 bands, so 2
    # interior planes on a bbox that runs -2500 .. +2500.
    offs = plane_offsets(-2500.0, 5000.0, 2400.0)
    assert len(offs) == 2
    assert offs[0] == pytest.approx(-2500.0 + 5000.0 / 3.0, abs=1e-9)
    assert offs[1] == pytest.approx(-2500.0 + 2 * 5000.0 / 3.0, abs=1e-9)
    edges = [-2500.0] + offs + [2500.0]
    for a, b in zip(edges, edges[1:]):
        assert b - a <= 2400.0 + 1e-9


def test_an_exact_fit_is_not_split():
    assert plane_offsets(0.0, 2400.0, 2400.0) == []
    assert plane_offsets(0.0, 2400.0000000001, 2400.0) == []


# --- conservation and the measured (never predicted) count ------------------

def test_segmentation_conserves_volume_exactly():
    solid = _basin()
    before = float(solid.volume)
    result = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    after = sum(m["volume_mm3"] for m in result.modules)
    assert result.volume_delta_pct < 1e-6, result.volume_delta_pct
    assert after == pytest.approx(before, rel=1e-12)


def test_a_five_metre_basin_becomes_liftable_modules():
    solid = _basin()
    whole_kg = float(solid.volume) * 1e-9 * BASALT_DENSITY
    assert whole_kg > 11_000, whole_kg          # no crane picks this
    result = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    assert result.module_count == 9
    assert result.grid == {"x": 3, "y": 3, "z": 1}
    heaviest = max(m["mass_kg"] for m in result.modules)
    assert heaviest < 1500, heaviest
    for m in result.modules:
        assert max(m["bbox_mm"]) <= 2400.0 + 1e-9


def test_module_count_is_measured_not_predicted():
    """A hollow tube's centre cells are bore, not material.

    grid 3 x 3 x 2 predicts 18 cells; the truth is 16 solids. A count
    computed as n_x * n_y * n_z would overstate both the pieces and the
    crane picks by two.
    """
    module = PRIMITIVES["plinth"]
    solid = module.build(module.validate(
        {"top_diameter_mm": 3000, "height_mm": 1200, "wall_mm": 150,
         "material_id": "basalt_slab"}))
    result = segment_solid(solid, _cubic(1000.0), density_kg_per_m3=BASALT_DENSITY)
    assert result.grid == {"x": 3, "y": 3, "z": 2}
    assert result.predicted_cells == 18
    assert result.module_count == 16
    assert result.volume_delta_pct < 1e-6


# --- the seam, against hand arithmetic --------------------------------------

def test_seam_area_and_length_match_hand_arithmetic():
    """Basin d5000, wall 150, height 700, floor = wall = 150, quartered.

    One interface cut face is the L-section of floor + wall on a half
    plane. Read off the profile, in mm:

      floor strip : 2500 long x 150 thick          = 375,000 mm2
      wall above  : 150 thick x (700 - 150) high   =  82,500 mm2
      total area                                   = 457,500 mm2

      perimeter   : 2500 + 700 + 150 + 550 + 2350 + 150 = 6,400 mm
    """
    solid = _basin()
    result = segment_solid(solid, _cubic(2500.0), density_kg_per_m3=BASALT_DENSITY)
    assert result.module_count == 4
    # 4 quarters share 4 interfaces (2 per plane), NOT the 8 cut faces.
    assert result.seam_count == 4
    assert result.seam_area_mm2 == pytest.approx(4 * 457_500.0, rel=1e-9)
    assert result.seam_length_mm == pytest.approx(4 * 6_400.0, rel=1e-9)
    assert result.unmatched_face_count == 0


def test_an_unsplit_solid_has_no_seam():
    solid = _basin(diameter_mm=2000, height_mm=400)
    result = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    assert result.module_count == 1
    assert result.seam_count == 0
    assert result.seam_length_mm == 0.0


# --- determinism ------------------------------------------------------------

def test_the_same_cut_twice_is_byte_identical():
    """The determinism the platform actually claims: same input, same code
    path, identical output."""
    solid = _basin()
    a = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    b = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    assert a.canonical_json() == b.canonical_json()


def test_plane_order_does_not_change_the_engineering():
    """Order-independence is GEOMETRIC, not bit-exact — measured, and the
    reason the assertion is written this way.

    Cutting z-y-x instead of x-y-z gave a module extent of
    1666.6666666666677 mm where x-y-z gave 1666.6666666666667 mm: the same
    nanometre, different last bits. The module count, the masses and the
    seam totals are identical to far better than any fabrication
    tolerance, so that is what is asserted. Bit-identity is asserted only
    where it is claimed (the test above, and the STEP hash, which
    segmentation never touches).
    """
    solid = _basin()
    a = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY)
    b = segment_solid(solid, _cubic(2400.0), density_kg_per_m3=BASALT_DENSITY,
                      axis_order=("z", "y", "x"))
    assert a.module_count == b.module_count
    assert a.grid == b.grid
    assert a.seam_count == b.seam_count
    assert a.seam_length_mm == pytest.approx(b.seam_length_mm, rel=1e-9)
    assert a.seam_area_mm2 == pytest.approx(b.seam_area_mm2, rel=1e-9)
    for ma, mb in zip(a.modules, b.modules):
        assert ma["mass_kg"] == pytest.approx(mb["mass_kg"], rel=1e-9)
        assert ma["bbox_mm"] == pytest.approx(mb["bbox_mm"], rel=1e-9)


# --- capability declarations ------------------------------------------------

def test_every_primitive_declares_a_segmentation_mode():
    for pid, module in sorted(PRIMITIVES.items()):
        mode = getattr(module, "SEGMENTATION_MODE", None)
        assert mode in (MODE_PLANAR_GRID, MODE_DISCRETE_ARRAY), pid


def test_the_arrays_are_the_discrete_ones():
    assert PRIMITIVES["blade_fin_array"].SEGMENTATION_MODE == MODE_DISCRETE_ARRAY
    assert PRIMITIVES["lotus_petal_array"].SEGMENTATION_MODE == MODE_DISCRETE_ARRAY
    assert PRIMITIVES["basin_round"].SEGMENTATION_MODE == MODE_PLANAR_GRID


def test_a_runaway_module_limit_is_refused_with_the_numbers():
    solid = _basin()
    with pytest.raises(ValueError) as exc:
        segment_solid(solid, _cubic(100.0), density_kg_per_m3=BASALT_DENSITY)
    text = str(exc.value)
    assert "50" in text                       # ceil(5000/100) per axis
    assert str(MAX_PREDICTED_CELLS) in text


# --- per-axis limits (PR-1, ADR-059) ----------------------------------------

def _tall_column():
    """d600 x h2300 solid basalt column: fits x/y of a 2.4 m envelope but
    stands 100 mm over a 2.2 m truck height. (basin_round's own height
    envelope caps at 900 mm — a column is the honest tall shape.)"""
    module = PRIMITIVES["sculptural_column"]
    return module.build(module.validate(
        {"diameter_mm": 600, "height_mm": 2300,
         "material_id": "basalt_slab"}))


def test_the_z_axis_binds_on_its_own_limit():
    """THE PR-1 proof: a 2.4 x 2.4 x 2.2 m envelope must split a module
    whose Z exceeds 2.2 m even though its X and Y fit.

    Under the old collapse this became a single 2.4 m cubic limit and the
    column shipped whole, 100 mm too tall for the declared truck.
    """
    solid = _tall_column()
    limit = {"x": 2400.0, "y": 2400.0, "z": 2200.0}
    result = segment_solid(solid, limit, density_kg_per_m3=BASALT_DENSITY)
    assert result.grid == {"x": 1, "y": 1, "z": 2}
    assert result.module_count >= 2
    for m in result.modules:
        assert m["bbox_mm"][2] <= 2200.0 + 1e-9

    # The SAME solid under the old collapsed value max(2.4, 2.4, 2.2) =
    # a 2.4 cubic envelope is NOT split — the difference between these
    # two results is exactly the defect PR-1 closes.
    collapsed = segment_solid(solid, _cubic(2400.0),
                              density_kg_per_m3=BASALT_DENSITY)
    assert collapsed.module_count == 1


def test_the_kernel_takes_exactly_one_limit_shape():
    """The kernel is strict: scalar-to-cubic compatibility lives at
    assemble() alone, never inside segment_solid."""
    solid = _basin(diameter_mm=2000, height_mm=400)
    with pytest.raises(TypeError):
        segment_solid(solid, 2400.0, density_kg_per_m3=BASALT_DENSITY)


def test_a_zero_axis_is_refused_per_axis():
    solid = _basin(diameter_mm=2000, height_mm=400)
    with pytest.raises(ValueError) as exc:
        segment_solid(solid, {"x": 2400.0, "y": 0.0, "z": 2400.0},
                      density_kg_per_m3=BASALT_DENSITY)
    assert "module limit must be > 0" in str(exc.value)


# --- the assembler now gates on modules, not elements -----------------------

_OVERSIZE_PLAN = [
    {"element_id": "b1", "primitive": "basin_round",
     "parameters": {"diameter_mm": 5000, "height_mm": 700, "wall_mm": 150,
                    "material_id": "basalt_slab"}},
]


def test_an_oversized_basin_now_builds_as_modules():
    _, manifest = assemble(
        _OVERSIZE_PLAN, seed=0,
        fabrication={"max_module_m": 2.4, "max_lift_kg": 2000},
        strict=True,
    )
    seg = manifest["segmentation"]
    assert seg["module_count"] == 9
    assert seg["heaviest_module_kg"] < 2000
    assert seg["elements"]["b1"]["mode"] == MODE_PLANAR_GRID
    assert manifest["fabrication_limit_violations"] == []


def test_an_oversized_basin_is_still_refused_without_a_module_limit():
    with pytest.raises(ConstraintViolation) as exc:
        assemble(_OVERSIZE_PLAN, seed=0,
                 fabrication={"max_lift_kg": 2000}, strict=True)
    text = "; ".join(exc.value.violations)
    assert "max_lift_kg" in text and "11" in text


def test_an_oversized_array_is_refused_by_name():
    plan = [
        {"element_id": "a1", "primitive": "blade_fin_array",
         "parameters": {"hub_diameter_mm": 900, "blade_count": 24,
                        "blade_length_mm": 700,
                        "material_id": "stainless_316l_sheet"}},
    ]
    with pytest.raises(ConstraintViolation) as exc:
        assemble(plan, seed=0,
                 fabrication={"max_module_m": 0.8, "max_lift_kg": 5000},
                 strict=True)
    text = "; ".join(exc.value.violations)
    assert "a1" in text
    assert MODE_DISCRETE_ARRAY in text
    assert "2300" in text          # the real bbox, in the refusal


def test_assemble_takes_the_spec_object_and_splits_the_tall_axis():
    """End-to-end Amendment 1 rows 2/3: a per-axis dict through assemble.

    The manifest's fabrication_limits must round-trip the DICT (the
    fabricate bridge feeds it straight back into assemble), and every
    measured module must fit each axis on its own limit.
    """
    plan = [
        {"element_id": "c1", "primitive": "sculptural_column",
         "parameters": {"diameter_mm": 600, "height_mm": 2300,
                        "material_id": "basalt_slab"}},
    ]
    _, manifest = assemble(
        plan, seed=0,
        fabrication={"max_module_m": {"x": 2.4, "y": 2.4, "z": 2.2},
                     "max_lift_kg": 20000},
        strict=True,
    )
    limits = manifest["fabrication_limits"]
    assert limits["max_module_m"] == {"x": 2.4, "y": 2.4, "z": 2.2}
    modules = manifest["segmentation"]["elements"]["c1"]["modules"]
    assert len(modules) >= 2
    for m in modules:
        assert m["bbox_mm"][0] <= 2400.0 + 1e-6
        assert m["bbox_mm"][1] <= 2400.0 + 1e-6
        assert m["bbox_mm"][2] <= 2200.0 + 1e-6
    assert manifest["fabrication_limit_violations"] == []


def test_assemble_refuses_malformed_module_limits():
    """Amendment 4: refused loudly as ConstraintViolation (the routes map
    that to HTTP 422) — never TypeError, never a 500."""
    plan = [
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 2000, "height_mm": 400,
                        "wall_mm": 150, "material_id": "basalt_slab"}},
    ]
    bad_values = [
        {"x": 2.4, "y": 2.4},                       # missing axis
        {"x": 2.4, "y": 2.4, "z": 2.2, "w": 1},     # extra axis
        {"x": True, "y": 2.4, "z": 2.2},            # boolean
        {"x": "2.4", "y": 2.4, "z": 2.2},           # non-numeric
        {"x": float("nan"), "y": 2.4, "z": 2.2},    # non-finite
        {"x": 0, "y": 2.4, "z": 2.2},               # zero
        {"x": -2.4, "y": 2.4, "z": 2.2},            # negative
        True,                                        # scalar boolean
        "2.4",                                       # scalar string
        0,                                           # scalar zero
        -1,                                          # scalar negative
    ]
    for bad in bad_values:
        with pytest.raises(ConstraintViolation) as exc:
            assemble(plan, seed=0,
                     fabrication={"max_module_m": bad}, strict=True)
        assert "max_module_m" in "; ".join(exc.value.violations), bad


def test_joint_seams_are_measured_between_elements():
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 1400, "height_mm": 400,
                        "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 2000, "height_mm": 450, "wall_mm": 150,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    _, manifest = assemble(plan, seed=0, strict=False)
    seams = manifest["segmentation"]["seams"]
    assert seams["joint"]["count"] == 1
    # The plinth is a SOLID d1400 frustum (wall_mm 0), and the basin's
    # footprint covers it completely, so the contact footprint is the
    # plinth's whole d1400 top face: perimeter pi x 1400, area pi x 700^2.
    assert seams["joint"]["length_mm"] == pytest.approx(math.pi * 1400.0,
                                                        rel=1e-6)
    assert seams["joint"]["area_mm2"] == pytest.approx(math.pi * 700.0 ** 2,
                                                       rel=1e-6)


def test_the_joint_seam_is_the_contact_face_not_the_child_outline():
    """A wide basin on a narrow hollow plinth.

    The basin is 5 m across but only meets the plinth over the plinth's
    top ANNULUS (outer 2200, inner 1800). Measuring the child's own
    section would report pi x 5000 = 15.708 m of joint where there is
    really pi x (2200 + 1800) = 12.566 m — an over-count that would look
    entirely plausible on the BOM.
    """
    plan = [
        {"element_id": "p1", "primitive": "plinth",
         "parameters": {"top_diameter_mm": 2200, "height_mm": 700,
                        "wall_mm": 200, "material_id": "basalt_slab"}},
        {"element_id": "b1", "primitive": "basin_round",
         "parameters": {"diameter_mm": 5000, "height_mm": 700, "wall_mm": 150,
                        "material_id": "basalt_slab"},
         "joint": {"type": "stack_on", "parent": "p1"}},
    ]
    _, manifest = assemble(plan, seed=0, strict=False)
    joint = manifest["segmentation"]["seams"]["joint"]
    assert joint["length_mm"] == pytest.approx(math.pi * (2200.0 + 1800.0),
                                               rel=1e-6)
    assert joint["length_mm"] < math.pi * 5000.0
    assert joint["area_mm2"] == pytest.approx(
        math.pi * (1100.0 ** 2 - 900.0 ** 2), rel=1e-6)
