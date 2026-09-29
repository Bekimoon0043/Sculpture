"""PR-6 (ADR-074): per-element costing, joints owned once, budget bound.

Amendment 4, tested line by line:
  * a two-material assembly prices BOTH materials, each element in its own;
  * every joint is billed ONCE — to the owner the rule names — and the
    seam identity  sum(seam lines) == split + joint  holds to 1e-6;
  * crane / crew / transport appear exactly once, on assembly numbers;
  * finishing bills EXPOSED skin (element area minus joint contact), and
    an element with no recorded skin is not_computable — never a share;
  * the owner rule null -> MISSING_RATE naming joints.cross_material_owner;
    each enum value -> computed on the right side; both-sides is disproved;
  * a single-material design through build_assembly_bom equals build_bom
    line for line (so the LUXEXCHANGE digest of existing designs is safe);
  * the budget ceiling comes from the confirmed intake when no query
    parameter is given, an explicit parameter wins, a draft never binds.
Fixture numbers carry no engineering meaning; they prove arithmetic.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml

from app.core.config import CostingConfig, Material
from app.costing.bom import (
    COMPUTED,
    ELEMENT_SEP,
    MISSING_RATE,
    NOT_COMPUTABLE,
    build_assembly_bom,
    build_bom,
)
from app.costing.budget import (
    BUDGET_SOURCE_INTAKE,
    budget_from_intake,
    check_budget,
)
from app.costing.drivers import (
    NEEDS_ELEMENT_AREA,
    drivers_for_assembly,
    drivers_per_element,
)
from app.costing.joints import OWNER_RULE_PATH, JointOwner, UnownedJoint, joint_owner
from app.costing.report import render_bom
from app.geometry.validate import AssemblyValidationReport, VolumeCrossCheck

REPO_COSTING = Path(__file__).resolve().parents[1] / "config" / "costing.yaml"

# --- fixtures ---------------------------------------------------------------

#: plinth p1 (concrete) with basin b1 (basalt) stacked on it. The numbers are
#: round so every identity below is checkable by hand.
P1_VOL_MM3 = 1.0e9          # 1 m3
B1_VOL_MM3 = 2.0e9          # 2 m3
P1_AREA_MM2 = 6.0e6         # 6 m2 skin
B1_AREA_MM2 = 10.0e6        # 10 m2 skin
JOINT_AREA_MM2 = 0.5e6      # 0.5 m2 contact face
JOINT_LEN_MM = 3000.0       # 3 m run
B1_SPLIT_LEN_MM = 4000.0    # 4 m of segmentation cuts inside b1
B1_SPLIT_AREA_MM2 = 0.8e6
CONCRETE_KG_M3 = 2400.0
BASALT_KG_M3 = 2700.0
P1_MASS = P1_VOL_MM3 * 1e-9 * CONCRETE_KG_M3   # 2400 kg
B1_MASS = B1_VOL_MM3 * 1e-9 * BASALT_KG_M3     # 5400 kg


def _manifest(*, with_area: bool = True, with_seg: bool = True) -> dict:
    elements = [
        {"element_id": "p1", "primitive": "plinth",
         "material_id": "cast_concrete_c35_45",
         "volume_mm3": P1_VOL_MM3, "mass_kg": P1_MASS},
        {"element_id": "b1", "primitive": "basin_round",
         "material_id": "basalt_slab",
         "volume_mm3": B1_VOL_MM3, "mass_kg": B1_MASS},
    ]
    if with_area:
        elements[0]["surface_area_mm2"] = P1_AREA_MM2
        elements[1]["surface_area_mm2"] = B1_AREA_MM2
    m: dict = {
        "schema": "assembly_manifest_v1",
        "elements": elements,
        "joints": [{"child": "b1", "parent": "p1", "type": "stack_on",
                    "overlap_mm": 10.0, "floor_mm": 30.0}],
        "total_mass_kg": P1_MASS + B1_MASS,
    }
    if with_seg:
        m["segmentation"] = {
            "schema": "assembly_segmentation_v1",
            "module_count": 3, "heaviest_module_kg": 2700.0,
            "not_segmentable": [],
            "elements": {
                "p1": {"module_count": 1, "seam_count": 0,
                       "seam_length_mm": 0.0, "seam_area_mm2": 0.0,
                       "modules": [{"index": 0, "mass_kg": P1_MASS}]},
                "b1": {"module_count": 2, "seam_count": 1,
                       "seam_length_mm": B1_SPLIT_LEN_MM,
                       "seam_area_mm2": B1_SPLIT_AREA_MM2,
                       "modules": [{"index": 0, "mass_kg": 2700.0},
                                   {"index": 1, "mass_kg": 2700.0}]},
            },
            "seams": {
                "split": {"count": 1, "length_mm": B1_SPLIT_LEN_MM,
                          "area_mm2": B1_SPLIT_AREA_MM2},
                "joint": {"count": 1, "length_mm": JOINT_LEN_MM,
                          "area_mm2": JOINT_AREA_MM2,
                          "joints": [{"child": "b1", "parent": "p1",
                                      "type": "stack_on",
                                      "contact_z_mm": 500.0,
                                      "length_mm": JOINT_LEN_MM,
                                      "area_mm2": JOINT_AREA_MM2}]},
                "total_length_mm": B1_SPLIT_LEN_MM + JOINT_LEN_MM,
            },
        }
    return m


def _report(total: float | None = P1_MASS + B1_MASS) -> AssemblyValidationReport:
    return AssemblyValidationReport(
        glb_path="/tmp/a.glb", element_count=2, joint_count=1,
        watertight=True, winding_consistent=True, body_count=1,
        volume_mm3=P1_VOL_MM3 + B1_VOL_MM3,
        surface_area_mm2=P1_AREA_MM2 + B1_AREA_MM2 - 2 * JOINT_AREA_MM2,
        degenerate_face_count=0, face_count=1000,
        element_masses_kg={"p1": P1_MASS, "b1": B1_MASS},
        total_mass_kg=total,
        volume_crosscheck=VolumeCrossCheck(
            trimesh_volume_mm3=3.0e9, build123d_volume_mm3=3.0e9,
            delta_pct=0.0, tolerance_pct=2.0, within_tolerance=True),
        passed=True)


def _material(name: str, density: float) -> Material:
    return Material(name=name, category="stone", density_kg_per_m3=density,
                    min_wall_mm=20, max_wall_mm=250, min_clearance_mm=40,
                    joint_overlap_mm=10, min_feature_mm=15,
                    min_internal_radius_mm=10, stock_size_mm=None)


@pytest.fixture
def materials() -> dict[str, Material]:
    return {"cast_concrete_c35_45": _material("Concrete", CONCRETE_KG_M3),
            "basalt_slab": _material("Basalt", BASALT_KG_M3)}


@pytest.fixture
def empty_costing() -> CostingConfig:
    with open(REPO_COSTING, encoding="utf-8") as fh:
        return CostingConfig(**yaml.safe_load(fh))


def _fill(raw: dict, *, seam_basalt: float = 300.0, seam_concrete: float = 100.0,
          seam_per: str = "m", owner: str | None = "parent") -> dict:
    for mid, m in raw["materials"].items():
        m["buy_price"] = {"amount": 100.0, "currency": "ETB", "per": "kg"}
        m["waste_factor_pct"] = 10.0
        m["fabrication"]["method"] = "hand_carve"
        m["fabrication"]["labor"] = {"amount": 200.0, "currency": "ETB",
                                     "per": "hour"}
        m["fabrication"]["hours_per_m3"] = 40.0
        m["finishing"] = {"amount": 500.0, "currency": "ETB", "per": "m2"}
        m["seam"] = {"amount": seam_basalt if mid == "basalt_slab"
                     else seam_concrete, "currency": "ETB", "per": seam_per}
    raw["workshop"]["overhead_pct"] = 15.0
    raw["install"]["crew_day_rate"] = {"amount": 1000.0, "currency": "ETB",
                                       "per": "crew_day"}
    raw["install"]["crew_size"] = 4
    raw["install"]["days_per_tonne"] = 0.5
    raw["install"]["transport"] = {"amount": 8000.0, "currency": "ETB",
                                   "per": "trip"}
    raw["install"]["truck_payload_kg"] = 12000.0
    raw["install"]["modules_per_trip"] = 4
    raw["contingency_pct"] = 10.0
    raw["markup_pct"] = 20.0
    raw["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": "2026-08-01"}
    raw["joints"] = {"cross_material_owner": owner}
    return raw


@pytest.fixture
def filled(empty_costing) -> CostingConfig:
    return CostingConfig(**_fill(empty_costing.model_dump()))


def _build(costing, materials, manifest=None, report=None):
    manifest = manifest or _manifest()
    report = report or _report()
    assembly = drivers_for_assembly(report, manifest)
    elements, joints = drivers_per_element(report, manifest)
    return build_assembly_bom(costing, assembly, elements, joints, materials,
                              design_id="d-test", spec_hash="abc")


def _line(bom, line_id):
    return next(ln for ln in bom.lines if ln.line_id == line_id)



# --- per-element drivers: one measurement path, exposed skin --------------

def test_per_element_drivers_read_the_manifest_never_apportion():
    elements, joints = drivers_per_element(_report(), _manifest())
    by_id = {e.element_id: e for e in elements}
    assert set(by_id) == {"p1", "b1"}
    assert by_id["p1"].material_id == "cast_concrete_c35_45"
    assert by_id["b1"].material_id == "basalt_slab"
    assert by_id["p1"].volume_m3 == pytest.approx(1.0)
    assert by_id["b1"].mass_kg == pytest.approx(B1_MASS)
    # exposed = element skin minus THIS element's joint contact face
    assert by_id["p1"].exposed_area_m2 == pytest.approx(6.0 - 0.5)
    assert by_id["b1"].exposed_area_m2 == pytest.approx(10.0 - 0.5)
    # segmentation cuts are per element; the joint is NOT in them
    assert by_id["b1"].split_seam_length_m == pytest.approx(4.0)
    assert by_id["p1"].split_seam_length_m == pytest.approx(0.0)
    assert len(joints) == 1
    j = joints[0]
    assert (j.parent_id, j.child_id) == ("p1", "b1")
    assert (j.parent_material, j.child_material) == (
        "cast_concrete_c35_45", "basalt_slab")
    assert j.length_m == pytest.approx(3.0)
    assert j.area_m2 == pytest.approx(0.5)


def test_element_without_recorded_skin_is_not_computable_not_a_share(
        filled, materials):
    bom = _build(filled, materials, manifest=_manifest(with_area=False))
    for eid in ("p1", "b1"):
        ln = _line(bom, f"{eid}{ELEMENT_SEP}finishing")
        assert ln.status == NOT_COMPUTABLE
        assert ln.blocker == NEEDS_ELEMENT_AREA
    assert bom.complete is False and bom.total_usd is None


def test_incomplete_mass_still_refuses_per_element():
    from app.costing.drivers import IncompleteMassError
    with pytest.raises(IncompleteMassError):
        drivers_per_element(_report(total=None), _manifest())


# --- Amendment 4: both materials, joint once, install once -----------------

def test_two_material_assembly_prices_both_materials(filled, materials):
    bom = _build(filled, materials)
    mats = {ln.drivers_used.get("material_id") for ln in bom.lines
            if ELEMENT_SEP in ln.line_id and not ln.line_id.startswith("joint")}
    assert mats == {"cast_concrete_c35_45", "basalt_slab"}
    assert bom.material_id == "basalt_slab+cast_concrete_c35_45"
    # no line is priced at a material the design does not contain
    for ln in bom.lines:
        if ln.rate_path and ln.rate_path.startswith("materials."):
            assert ln.rate_path.split(".")[1] in mats
    # each element's purchase line uses ITS mass
    assert _line(bom, "p1/material_purchase").drivers_used["mass_kg"] == \
        pytest.approx(P1_MASS)
    assert _line(bom, "b1/material_purchase").drivers_used["mass_kg"] == \
        pytest.approx(B1_MASS)


def test_joint_is_billed_exactly_once_and_seam_identity_holds(filled, materials):
    bom = _build(filled, materials)
    joint_lines = [ln for ln in bom.lines if ln.line_id.startswith("joint/")]
    assert len(joint_lines) == 1
    j = joint_lines[0]
    assert j.status == COMPUTED
    # owner = parent (concrete) per the fixture rule; the reason is printed
    assert j.rate_path == "materials.cast_concrete_c35_45.seam"
    assert "parent" in j.drivers_used["owner_reason"]
    assert "owner: cast_concrete_c35_45" in j.formula
    # the seam identity: sum of all seam quantities == split + joint
    seam_m = sum(ln.drivers_used.get("seam_length_m", 0.0) for ln in bom.lines
                 if ln.line_id.endswith("/seam_welding")
                 and ln.status == COMPUTED)
    seam_m += j.drivers_used["length_m"]
    assert seam_m == pytest.approx((B1_SPLIT_LEN_MM + JOINT_LEN_MM) / 1000.0,
                                   abs=1e-6)
    # and the joint appears under exactly ONE rate_path, never both
    seam_paths = [ln.rate_path for ln in bom.lines
                  if "seam" in (ln.rate_path or "") and ln.status == COMPUTED]
    assert seam_paths.count("materials.cast_concrete_c35_45.seam") == 1
    # b1's own seam line is its 4 m of cuts only — not the joint
    b1_seam = _line(bom, "b1/seam_welding")
    assert b1_seam.drivers_used["seam_length_m"] == pytest.approx(4.0)


def test_shared_install_block_appears_once_on_assembly_numbers(filled, materials):
    bom = _build(filled, materials)
    for lid in ("install_crane", "install_crew", "install_transport"):
        assert [ln.line_id for ln in bom.lines].count(lid) == 1
    crew = _line(bom, "install_crew")
    assert crew.drivers_used["mass_tonnes"] == pytest.approx(
        (P1_MASS + B1_MASS) / 1000.0)
    transport = _line(bom, "install_transport")
    assert transport.status == COMPUTED
    # the crane pick is the heaviest MODULE from the manifest, not an element
    assert bom.drivers["crane_pick_kg"] == pytest.approx(2700.0)


def test_total_matches_hand_arithmetic(filled, materials):
    bom = _build(filled, materials)
    assert bom.complete, (bom.missing_rates, bom.not_computable)
    fab = sum(ln.amount_usd for ln in bom.lines
              if ln.group == "fabrication" and ln.amount_usd is not None)
    ins = sum(ln.amount_usd for ln in bom.lines
              if ln.group == "install" and ln.amount_usd is not None)
    fab, ins = round(fab, 6), round(ins, 6)
    oh = round(fab * 0.15, 6)
    base = round(fab + oh + ins, 6)
    cont = round(base * 0.10, 6)
    mk = round((base + cont) * 0.20, 6)
    assert bom.total_usd == pytest.approx(base + cont + mk, abs=1e-6)
    # hand check of ONE line: p1 purchase = 2400 kg x 1.10 x 100 ETB / 140
    p1 = _line(bom, "p1/material_purchase")
    assert p1.amount_usd == pytest.approx(2400 * 1.10 * 100 / 140, abs=1e-6)
    # and finishing on EXPOSED skin: b1 = 9.5 m2 x 500 ETB / 140
    assert _line(bom, "b1/finishing").amount_usd == pytest.approx(
        9.5 * 500 / 140, abs=1e-6)



# --- the owner rule --------------------------------------------------------

def test_owner_rule_null_makes_the_joint_a_missing_rate_naming_the_path(
        empty_costing, materials):
    raw = _fill(empty_costing.model_dump(), owner=None)
    costing = CostingConfig(**raw)
    assert costing.joints.cross_material_owner is None
    bom = _build(costing, materials)
    j = next(ln for ln in bom.lines if ln.line_id.startswith("joint/"))
    assert j.status == MISSING_RATE
    assert j.rate_path == OWNER_RULE_PATH
    assert OWNER_RULE_PATH in bom.missing_rates
    assert bom.total_usd is None
    # NEITHER side was billed for the joint
    for ln in bom.lines:
        if ln.line_id.endswith("/seam_welding") and ln.status == COMPUTED:
            assert ln.drivers_used["seam_length_m"] != pytest.approx(
                (B1_SPLIT_LEN_MM + JOINT_LEN_MM) / 1000.0)


@pytest.mark.parametrize("rule,expected", [
    ("parent", "cast_concrete_c35_45"),
    ("child", "basalt_slab"),
    ("stronger_rate", "basalt_slab"),      # 300 > 100 per m
])
def test_each_owner_rule_bills_exactly_one_side(empty_costing, materials,
                                                rule, expected):
    costing = CostingConfig(**_fill(empty_costing.model_dump(), owner=rule))
    bom = _build(costing, materials)
    j = next(ln for ln in bom.lines if ln.line_id.startswith("joint/"))
    assert j.status == COMPUTED
    assert j.rate_path == f"materials.{expected}.seam"
    assert j.drivers_used["owner_material"] == expected
    assert rule in j.drivers_used["owner_reason"]


def test_stronger_rate_tie_goes_to_parent_and_says_so(empty_costing):
    costing = CostingConfig(**_fill(empty_costing.model_dump(),
                                    owner="stronger_rate",
                                    seam_basalt=250.0, seam_concrete=250.0))
    o = joint_owner(costing, "cast_concrete_c35_45", "basalt_slab")
    assert isinstance(o, JointOwner)
    assert o.material_id == "cast_concrete_c35_45"
    assert "tie -> parent" in o.reason


def test_stronger_rate_cannot_compare_mismatched_units(empty_costing):
    raw = _fill(empty_costing.model_dump(), owner="stronger_rate")
    raw["materials"]["basalt_slab"]["seam"]["per"] = "m2"
    o = joint_owner(CostingConfig(**raw), "cast_concrete_c35_45", "basalt_slab")
    assert isinstance(o, UnownedJoint)
    assert "different unit" in o.reason


def test_stronger_rate_with_a_null_seam_is_unowned_naming_that_seam(
        empty_costing):
    raw = _fill(empty_costing.model_dump(), owner="stronger_rate")
    raw["materials"]["basalt_slab"]["seam"]["amount"] = None
    o = joint_owner(CostingConfig(**raw), "cast_concrete_c35_45", "basalt_slab")
    assert isinstance(o, UnownedJoint)
    assert o.missing_path == "materials.basalt_slab.seam"


def test_same_material_joint_never_consults_the_rule(empty_costing):
    costing = CostingConfig(**_fill(empty_costing.model_dump(), owner=None))
    o = joint_owner(costing, "basalt_slab", "basalt_slab")
    assert isinstance(o, JointOwner) and o.material_id == "basalt_slab"


def test_billing_both_sides_would_overstate_the_joint(filled, materials):
    """The disproof: billing the joint on BOTH seam rates = 3 m x (300+100)
    = 1200 ETB; billing once to the parent = 3 m x 100 = 300 ETB. The BOM
    carries the second number and nothing near the first."""
    bom = _build(filled, materials)
    j = next(ln for ln in bom.lines if ln.line_id.startswith("joint/"))
    assert j.amount_native == pytest.approx(300.0)
    both_sides = 3.0 * (300.0 + 100.0)
    joint_native_total = sum(ln.amount_native or 0.0 for ln in bom.lines
                             if ln.line_id.startswith("joint/"))
    assert joint_native_total < both_sides


def test_invalid_owner_rule_fails_loudly(empty_costing):
    raw = _fill(empty_costing.model_dump(), owner="whoever")
    with pytest.raises(Exception, match="cross_material_owner"):
        CostingConfig(**raw)


def test_template_lists_the_owner_rule_as_missing(empty_costing):
    assert OWNER_RULE_PATH in empty_costing.missing_entries()
    assert empty_costing.costing_version == "2026-09-v3"



# --- single-material regression: build_assembly_bom vs build_bom -----------

def test_single_material_assembly_bom_agrees_with_build_bom(filled, materials):
    """A one-material design must price the same money through either path
    (the route keeps calling build_bom for it, so its sealed LUXEXCHANGE
    BOM never moves; this equivalence is what makes that honest)."""
    m = _manifest()
    for e in m["elements"]:
        e["material_id"] = "basalt_slab"
    report = _report()
    assembly = drivers_for_assembly(report, m)
    single = build_bom(filled, assembly, "basalt_slab",
                       materials["basalt_slab"], design_id="d", spec_hash="s",
                       now_iso="2026-09-28T00:00:00+00:00")
    elements, joints = drivers_per_element(report, m)
    multi = build_assembly_bom(filled, assembly, elements, joints, materials,
                               design_id="d", spec_hash="s",
                               now_iso="2026-09-28T00:00:00+00:00")
    for lid in ("install_crane", "install_crew", "install_transport"):
        assert _line(single, lid).amount_usd == _line(multi, lid).amount_usd
    for base in ("material_purchase", "fabrication_labour"):
        s = _line(single, base).amount_usd
        mm = sum(_line(multi, f"{e}/{base}").amount_usd for e in ("p1", "b1"))
        assert mm == pytest.approx(s, abs=1e-6)
    # seams: single bills split+joint on one rate; multi bills each
    # element's split + the joint once on the SAME material — same money.
    s_seam = _line(single, "seam_welding").amount_usd
    m_seam = sum(ln.amount_usd for ln in multi.lines
                 if (ln.line_id.endswith("/seam_welding")
                     or ln.line_id.startswith("joint/"))
                 and ln.amount_usd is not None)
    assert m_seam == pytest.approx(s_seam, abs=1e-6)
    assert "elements" not in single.as_dict()
    assert "elements" in multi.as_dict()


# --- rendering ---------------------------------------------------------------

def test_render_shows_each_element_in_its_material_and_install_once(
        filled, materials):
    text = render_bom(_build(filled, materials))
    assert "FABRICATION — p1 (cast_concrete_c35_45)" in text
    assert "FABRICATION — b1 (basalt_slab)" in text
    assert "JOINTS (each billed ONCE" in text
    assert text.count("INSTALL (shared") == 1
    assert "owner: cast_concrete_c35_45" in text
    assert "TOTALS" in text


def test_render_incomplete_multi_material_prints_no_total(empty_costing,
                                                          materials):
    text = render_bom(_build(empty_costing, materials))
    assert "NO TOTAL — THIS BOM IS INCOMPLETE" in text
    assert "TOTALS\n" not in text
    assert OWNER_RULE_PATH in text


# --- the budget binds from the confirmed intake ------------------------------

def _intake(amount=2_000_000.0, currency="ETB", amount_source="operator"):
    return {"budget": {
        "amount_max": {"value": amount, "source": amount_source},
        "currency": {"value": currency, "source": "parsed"},
    }}


def test_confirmed_intake_supplies_the_ceiling_with_its_source():
    b = budget_from_intake(_intake(), "confirmed", "int-1")
    assert b is not None
    assert b["amount"] == 2_000_000.0 and b["currency"] == "ETB"
    assert b["source"] == BUDGET_SOURCE_INTAKE
    assert "int-1" in b["source_detail"] and "operator" in b["source_detail"]


def test_draft_intake_never_binds():
    assert budget_from_intake(_intake(), "draft", "int-1") is None


def test_intake_without_amount_or_currency_never_binds():
    assert budget_from_intake(_intake(amount=None), "confirmed", "i") is None
    assert budget_from_intake(_intake(currency=None), "confirmed", "i") is None


def test_budget_check_carries_the_source(filled, materials):
    bom = _build(filled, materials)
    check = check_budget(bom, budget_from_intake(_intake(), "confirmed", "i"),
                         filled)
    assert check.status == "pass"
    assert check.source == BUDGET_SOURCE_INTAKE
    assert "ceiling from: confirmed brief intake" in render_bom(bom, check)


def test_incomplete_bom_budget_is_not_performed_never_pass(empty_costing,
                                                           materials):
    bom = _build(empty_costing, materials)
    check = check_budget(bom, budget_from_intake(_intake(), "confirmed", "i"),
                         empty_costing)
    assert check.status == "not_performed"

