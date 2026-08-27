"""Costing layer tests — the four operator rules, each proven.

  1. drivers come from the validation report, never re-measured
  2. multi-currency with dated FX
  3. every line carries its formula and its source rate path
  4. a missing rate is NAMED, never guessed, and kills the total

Plus the budget constraint: binding on a complete BOM, and never reported as
PASS on an incomplete one.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from app.core.config import CostingConfig, Material
from app.costing.bom import (
    COMPUTED,
    MISSING_RATE,
    NOT_APPLICABLE,
    NOT_COMPUTABLE,
    build_bom,
)
from app.costing.budget import BudgetViolation, check_budget
from app.costing.drivers import CostDrivers, drivers_from_validation
from app.costing.rates import FxConversion, MissingFx, MissingRate, Rate, fx_for, resolve
from app.costing.report import render_bom
from app.geometry.validate import ValidationReport, VolumeCrossCheck

REPO_COSTING = "config/costing.yaml"


# --- fixtures ---------------------------------------------------------------

def _report(passed: bool = True) -> ValidationReport:
    """The REAL numbers from the design that passed the Phase 4 live gate."""
    return ValidationReport(
        glb_path="/x.glb", material_id="basalt_slab", watertight=True,
        winding_consistent=True, volume_mm3=1271287346.316879,
        surface_area_mm2=42954224.45121378, euler_number=0,
        bounds_mm=[-1300.0, -1299.6, 0.0, 1300.0, 1299.6, 1710.0],
        degenerate_face_count=0, face_count=30240, mass_kg=3432.4758350555735,
        volume_crosscheck=VolumeCrossCheck(
            trimesh_volume_mm3=1271287346.316879,
            build123d_volume_mm3=1271814019.4899116,
            delta_pct=0.0414, tolerance_pct=2.0, within_tolerance=True),
        passed=passed,
    )


@pytest.fixture
def basalt() -> Material:
    return Material(name="Basalt slab", category="stone",
                    density_kg_per_m3=2700, min_wall_mm=20, max_wall_mm=250,
                    min_clearance_mm=40,
                    # slice A1 (ADR-032): signed basalt envelope values
                    joint_overlap_mm=10, min_feature_mm=15,
                    min_internal_radius_mm=10,
                    stock_size_mm=None)


@pytest.fixture
def empty_costing() -> CostingConfig:
    """The repo's real, all-null rate card — the operator's current state."""
    with open(REPO_COSTING, encoding="utf-8") as fh:
        return CostingConfig(**yaml.safe_load(fh))


@pytest.fixture
def filled_costing(empty_costing) -> CostingConfig:
    """A fully-filled card so the COMPUTED path is proven too.

    These numbers are test fixtures with no engineering meaning whatsoever —
    they exist to prove the arithmetic and the tracing, and they must never
    be copied into config/costing.yaml.
    """
    raw = empty_costing.model_dump()
    for mid in raw["materials"]:
        m = raw["materials"][mid]
        m["buy_price"] = {"amount": 100.0, "currency": "ETB", "per": "kg"}
        m["waste_factor_pct"] = 10.0
        m["fabrication"]["method"] = "hand_carve"
        m["fabrication"]["labor"] = {"amount": 200.0, "currency": "ETB",
                                     "per": "hour"}
        m["fabrication"]["hours_per_m3"] = 40.0
        m["finishing"] = {"amount": 500.0, "currency": "ETB", "per": "m2"}
        m["seam"] = {"amount": 300.0, "currency": "ETB", "per": "m"}
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
    return CostingConfig(**raw)


# --- rule 1: drivers come from validation, never re-measured ----------------

def test_drivers_are_read_from_the_validation_report(basalt):
    d = drivers_from_validation(_report())
    # exactly the report's numbers, only unit-converted
    assert d.mass_kg == pytest.approx(3432.4758350555735)
    assert d.volume_m3 == pytest.approx(1.271287346316879)
    assert d.surface_area_m2 == pytest.approx(42.95422445121378)
    # a monolithic solid is lifted whole: pick weight IS the mass
    assert d.crane_pick_kg == d.mass_kg and d.monolithic is True


def test_costing_refuses_a_design_that_failed_validation():
    with pytest.raises(ValueError, match="validation FAILED"):
        drivers_from_validation(_report(passed=False))


def test_module_count_and_seam_length_are_unavailable_not_zero():
    """A monolithic solid has no modules and no seams.

    Both must be None with a stated reason — never 0, which would
    silently price a segmented job as if it needed no modules and had no
    seams. Since slice C2 (ADR-056) the reason is no longer "we have not
    built segmentation": it is "declare a module limit and rebuild", so
    the reason names the operator's actual next action.
    """
    d = drivers_from_validation(_report())
    assert d.module_count is None and d.seam_length_m is None
    assert "max_module_m" in d.unavailable["module_count"]
    assert "guessed" in d.unavailable["module_count"]
    assert "max_module_m" in d.unavailable["seam_length_m"]


# --- rule 4: a missing rate is named, never guessed -------------------------

def test_null_rate_resolves_to_MissingRate_not_zero(empty_costing):
    r = resolve("materials.basalt_slab.buy_price",
                empty_costing.materials["basalt_slab"].buy_price)
    assert isinstance(r, MissingRate)
    assert r.path == "materials.basalt_slab.buy_price"


def test_repo_rate_card_produces_an_incomplete_bom_naming_every_gap(
        empty_costing, basalt):
    """The operator's ACTUAL costing.yaml today. Every gap named, no total."""
    bom = build_bom(empty_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    assert bom.complete is False
    assert bom.total_usd is None
    assert bom.missing_rates, "must name the null rates"
    for path in ("workshop.overhead_pct", "contingency_pct", "markup_pct"):
        assert path in bom.missing_rates
    # nothing invented anywhere
    for ln in bom.lines:
        if ln.status != COMPUTED:
            assert ln.amount_native is None and ln.amount_usd is None


def test_missing_rate_and_not_computable_are_never_conflated(
        filled_costing, basalt):
    """Different statuses mean different people act. A fully-filled card must
    still leave the segmentation-driven lines NOT_COMPUTABLE — that gap is
    ours to build, not a rate the operator forgot."""
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    by_id = {ln.line_id: ln for ln in bom.lines}
    assert by_id["install_transport"].status == NOT_COMPUTABLE
    assert by_id["seam_welding"].status == NOT_COMPUTABLE
    assert bom.missing_rates == [], bom.missing_rates
    assert bom.complete is False   # blocked by drivers, not by rates
    assert bom.total_usd is None


def test_count_priced_material_is_refused_not_divided(filled_costing, basalt):
    """basalt is quoted per SLAB in the template. A slab count needs nesting,
    so the line must refuse rather than derive a count from mass."""
    raw = filled_costing.model_dump()
    raw["materials"]["basalt_slab"]["buy_price"] = {
        "amount": 5000.0, "currency": "ETB", "per": "slab"}
    bom = build_bom(CostingConfig(**raw), drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    line = next(ln for ln in bom.lines if ln.line_id == "material_purchase")
    assert line.status == NOT_COMPUTABLE
    assert "per kg or per m3" in line.blocker
    assert line.amount_native is None


# --- rule 3: every line traces to a formula and a rate path -----------------

def test_every_computed_line_carries_formula_rate_path_and_numbers(
        filled_costing, basalt):
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    computed = [ln for ln in bom.lines if ln.status == COMPUTED]
    assert computed
    for ln in computed:
        assert ln.rate_path and ln.rate_text
        assert ln.amount_native is not None and ln.amount_usd is not None
        # the formula must END in the number the line actually charges, so a
        # reader can check the arithmetic without leaving the line
        assert ln.formula.endswith(
            f"= {ln.amount_native:,.2f} {ln.currency}"), ln.formula
        assert ln.drivers_used, "a line must say which drivers produced it"


def test_material_line_arithmetic_is_exact(filled_costing, basalt):
    """mass 3432.4758 kg x 1.10 waste x 100 ETB/kg = 377,572.34 ETB."""
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    line = next(ln for ln in bom.lines if ln.line_id == "material_purchase")
    expected = round(3432.4758350555735 * 1.10 * 100.0, 6)
    assert line.amount_native == pytest.approx(expected)
    assert line.amount_usd == pytest.approx(round(expected / 140.0, 6))
    assert "mass 3,432.476 kg" in line.formula
    assert line.rate_path == "materials.basalt_slab.buy_price"


def test_hand_work_machine_line_is_not_applicable_not_missing(
        filled_costing, basalt):
    """costing.yaml's own convention: machine null = hand work. That is a
    legitimate n/a, and must not be reported as a rate the operator forgot."""
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    line = next(ln for ln in bom.lines if ln.line_id == "fabrication_machine")
    assert line.status == NOT_APPLICABLE
    assert "hand work" in line.blocker
    assert "materials.basalt_slab.fabrication.machine" not in bom.missing_rates


# --- rule 2: multi-currency with dated FX -----------------------------------

def test_fx_requires_a_date_not_just_a_rate(filled_costing):
    raw = filled_costing.model_dump()
    raw["fx_rates"]["ETB"] = {"rate": 140.0, "as_of": None}
    fx = fx_for(CostingConfig(**raw), "ETB")
    assert isinstance(fx, MissingFx)
    assert "undated" in fx.reason


def test_fx_conversion_is_dated_and_shown(filled_costing, basalt):
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    assert any("as of 2026-08-01" in fx for fx in bom.fx_used)
    line = next(ln for ln in bom.lines if ln.status == COMPUTED)
    assert "140 ETB/USD" in line.fx_text


def test_usd_needs_no_fx_entry(filled_costing):
    fx = fx_for(filled_costing, "USD")
    assert isinstance(fx, FxConversion) and fx.rate == 1.0


# --- totals + budget --------------------------------------------------------

def _fully_computable(filled_costing):
    """Remove the two segmentation-blocked lines' blockers by supplying the
    drivers, so the TOTAL path can be proven end to end."""
    import app.costing.bom as bommod

    class _Patched(bommod._Builder):
        def seams(self):
            pass

        def install(self):
            super().install()
            self.lines = [ln for ln in self.lines
                          if ln.line_id != "install_transport"]
    return _Patched


def test_complete_bom_totals_carry_their_formula(filled_costing, basalt,
                                                 monkeypatch):
    import app.costing.bom as bommod

    monkeypatch.setattr(bommod, "_Builder", _fully_computable(filled_costing))
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    assert bom.complete is True and bom.total_usd > 0
    joined = " | ".join(bom.total_formula)
    for token in ("overhead", "15%", "contingency", "10%", "markup", "20%",
                  "TOTAL"):
        assert token in joined
    # totals reconcile
    assert bom.base_usd == pytest.approx(
        round(bom.subtotal_fabrication_usd + bom.overhead_usd
              + bom.subtotal_install_usd, 6))
    assert bom.total_usd == pytest.approx(
        round(bom.base_usd + bom.contingency_usd + bom.markup_usd, 6))


def test_budget_is_binding_and_refuses_with_real_numbers(
        filled_costing, basalt, monkeypatch):
    import app.costing.bom as bommod

    monkeypatch.setattr(bommod, "_Builder", _fully_computable(filled_costing))
    bom = build_bom(filled_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    tight = {"amount": 1000.0, "currency": "ETB", "fx_date": "2026-08-01"}
    with pytest.raises(BudgetViolation) as exc:
        check_budget(bom, tight, filled_costing)
    v = exc.value
    assert v.total_usd == bom.total_usd and v.over_usd > 0
    assert "over by" in v.message and "ETB/USD as of 2026-08-01" in v.message

    generous = {"amount": 100_000_000.0, "currency": "ETB",
                "fx_date": "2026-08-01"}
    ok = check_budget(bom, generous, filled_costing)
    assert ok.status == "pass" and ok.headroom_usd > 0


def test_incomplete_bom_budget_check_is_never_pass(empty_costing, basalt):
    """The most dangerous silent failure in this layer: a design declared
    affordable because most of its costs were never computed."""
    bom = build_bom(empty_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    check = check_budget(bom, {"amount": 1.0, "currency": "ETB",
                               "fx_date": "2026-08-01"}, empty_costing)
    assert check.status == "not_performed"
    assert check.status != "pass"
    assert "never reported as PASS on partial costs" in check.reason


# --- the rendered document --------------------------------------------------

def test_report_separates_operator_homework_from_ours(empty_costing, basalt):
    bom = build_bom(empty_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    text = render_bom(bom, check_budget(
        bom, {"amount": 1.0, "currency": "ETB", "fx_date": "2026-08-01"},
        empty_costing))
    assert "NO TOTAL — THIS BOM IS INCOMPLETE" in text
    assert "YOU SUPPLY" in text and "WE BUILD" in text
    assert "BUDGET CONSTRAINT: NOT_PERFORMED" in text
    # the drivers actually measured are shown
    assert "mass_kg" in text and "3432.476" in text


# ---------------------------------------------------------------------------
# Slice C2 (ADR-056): the assembly path — modules, seams, and the crane pick
# ---------------------------------------------------------------------------

def _assembly_report(**over):
    """A real AssemblyValidationReport shape — the one an assembly stores.

    It deliberately has NO material_id and NO single mass_kg; that is why
    costing could not read one before slice C2.
    """
    from app.geometry.validate import AssemblyValidationReport, VolumeCrossCheck
    data = {
        "glb_path": "/tmp/assembly.glb",
        "element_count": 2, "joint_count": 1,
        "watertight": True, "winding_consistent": True, "body_count": 1,
        "volume_mm3": 5.067251e9, "surface_area_mm2": 67.0381e6,
        "degenerate_face_count": 0, "face_count": 4000,
        "element_masses_kg": {"p1": 2375.044, "b1": 11346.137},
        "total_mass_kg": 13721.181,
        "volume_crosscheck": VolumeCrossCheck(
            trimesh_volume_mm3=5.067251e9, build123d_volume_mm3=5.067251e9,
            delta_pct=0.0, tolerance_pct=2.0, within_tolerance=True),
        "passed": True,
    }
    data.update(over)
    return AssemblyValidationReport(**data)


def _segmented_manifest(**over):
    seg = {
        "schema": "assembly_segmentation_v1",
        "module_count": 10,
        "heaviest_module_kg": 2375.044,
        "not_segmentable": [],
        "seams": {
            "split": {"count": 12, "length_mm": 50112.0, "area_mm2": 3531278.0},
            "joint": {"count": 1, "length_mm": 12566.371, "area_mm2": 1256637.0},
            "total_length_mm": 62678.371,
        },
    }
    seg.update(over)
    return {"schema": "assembly_manifest_v1", "segmentation": seg}


def test_assembly_drivers_read_modules_and_seams_from_the_manifest():
    from app.costing.drivers import drivers_for_assembly
    d = drivers_for_assembly(_assembly_report(), _segmented_manifest())
    assert d.module_count == 10
    assert d.monolithic is False
    # THE correction to LIMITATIONS §10: a crane picks a module, not the
    # whole 13.7-tonne fountain.
    assert d.crane_pick_kg == pytest.approx(2375.044)
    assert d.mass_kg == pytest.approx(13721.181)
    assert d.seam_length_m == pytest.approx(62.678371)
    assert d.joint_seam_length_m == pytest.approx(12.566371)
    assert d.seam_area_m2 == pytest.approx((3531278.0 + 1256637.0) / 1e6)


def test_a_pre_segmentation_manifest_asks_for_a_rebuild_not_a_guess():
    from app.costing.drivers import NEEDS_REBUILD, drivers_for_assembly
    d = drivers_for_assembly(_assembly_report(),
                             {"schema": "assembly_manifest_v1"})
    assert d.module_count is None and d.seam_length_m is None
    assert d.unavailable["module_count"] == NEEDS_REBUILD
    # the heaviest ELEMENT is still measured, so the pick is not the total
    assert d.crane_pick_kg == pytest.approx(11346.137)


def test_a_refused_element_poisons_the_module_count():
    """One element the platform could not segment means the design has no
    honest module count — not a count that quietly skips it."""
    from app.costing.drivers import drivers_for_assembly
    manifest = _segmented_manifest(not_segmentable=["a1"])
    d = drivers_for_assembly(_assembly_report(), manifest)
    assert d.module_count is None
    assert "a1" in d.unavailable["module_count"]


def test_seam_and_transport_move_from_our_homework_to_the_operators(
        empty_costing, basalt):
    """The deliverable of slice C2, stated as a status transition.

    Before: not_computable — WE had to build segmentation.
    After:  missing_rate   — the operator supplies a number.
    """
    from app.costing.drivers import drivers_for_assembly
    d = drivers_for_assembly(_assembly_report(), _segmented_manifest())
    bom = build_bom(empty_costing, d, "basalt_slab", basalt)
    lines = {ln.line_id: ln for ln in bom.lines}
    assert lines["seam_welding"].status == MISSING_RATE
    assert lines["seam_welding"].rate_path == "materials.basalt_slab.seam"
    assert lines["install_transport"].status == MISSING_RATE
    assert lines["install_transport"].rate_path == "install.truck_payload_kg"


def test_a_monolithic_design_still_says_who_has_to_act(empty_costing, basalt):
    """Unchanged for one fused solid: no modules, so these stay OUR side —
    but the reason now names the operator's next action."""
    bom = build_bom(empty_costing, drivers_from_validation(_report()),
                    "basalt_slab", basalt)
    lines = {ln.line_id: ln for ln in bom.lines}
    assert lines["install_transport"].status == NOT_COMPUTABLE
    assert "max_module_m" in lines["install_transport"].blocker


def test_seams_compute_per_metre_of_run(filled_costing, basalt):
    from app.costing.drivers import drivers_for_assembly
    d = drivers_for_assembly(_assembly_report(), _segmented_manifest())
    bom = build_bom(filled_costing, d, "basalt_slab", basalt)
    line = {ln.line_id: ln for ln in bom.lines}["seam_welding"]
    assert line.status == COMPUTED
    assert "62.678 m" in line.formula
    assert line.drivers_used["seam_length_m"] == pytest.approx(62.678, abs=1e-3)


def test_transport_trips_bind_on_weight_or_bed_space(filled_costing, basalt):
    """13,721 kg at 12,000 kg per trip = 2 trips by weight; 10 modules at
    4 per trip = 3 trips by bed. The worse one binds."""
    from app.costing.drivers import drivers_for_assembly
    d = drivers_for_assembly(_assembly_report(), _segmented_manifest())
    bom = build_bom(filled_costing, d, "basalt_slab", basalt)
    line = {ln.line_id: ln for ln in bom.lines}["install_transport"]
    assert line.status == COMPUTED
    assert line.drivers_used["trips"] == 3
    assert line.drivers_used["binding"] == "bed space"


def test_a_single_module_design_has_no_seam_to_bill(filled_costing, basalt):
    from app.costing.drivers import drivers_for_assembly
    manifest = _segmented_manifest(
        module_count=1,
        seams={"split": {"count": 0, "length_mm": 0.0, "area_mm2": 0.0},
               "joint": {"count": 0, "length_mm": 0.0, "area_mm2": 0.0},
               "total_length_mm": 0.0})
    d = drivers_for_assembly(_assembly_report(), manifest)
    bom = build_bom(filled_costing, d, "basalt_slab", basalt)
    line = {ln.line_id: ln for ln in bom.lines}["seam_welding"]
    assert line.status == NOT_APPLICABLE
    assert "nothing to join" in line.blocker


def test_the_rendered_document_route_is_actually_reachable_bom_text_route():
    """Regression: route ORDER decides this (found 2026-08-27, ADR-056).

    FastAPI matches in registration order and `{design_id}` matches
    "<uuid>.txt", so while the JSON route was declared first every request
    for the rendered document — the one handed to a client — came back
    404 "design <uuid>.txt not found".
    """
    from app.api.routes_costing import router

    paths = [r.path for r in router.routes if "/bom/" in getattr(r, "path", "")]
    assert "/costing/bom/{design_id}.txt" in paths
    assert "/costing/bom/{design_id}" in paths
    assert paths.index("/costing/bom/{design_id}.txt") <         paths.index("/costing/bom/{design_id}"), (
            "the .txt route must be registered BEFORE the JSON route, or the "
            "greedy path parameter swallows the suffix")
