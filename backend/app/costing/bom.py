"""The BOM — one traceable line per cost, and no total until every line is real.

Line statuses are four, deliberately distinct, because they tell the operator
DIFFERENT things about who has to act:

  computed        driver x rate, both present. The only status that carries money.
  missing_rate    the driver exists; the RATE is null in costing.yaml.
                  -> the operator supplies a number. Names the exact path.
  not_computable  the rate may exist, but the DRIVER cannot be measured yet.
                  -> WE build something (segmentation). Names what is required.
  not_applicable  legitimately does not apply (no crane, hand work, not cast).

Conflating the first two would be the fabricated-capability failure Rule 2
forbids; conflating the middle two would hand the operator homework that is
actually ours.

**No total is produced unless every line is `computed` or `not_applicable`.**
A partial subtotal presented as a total is precisely the untraceable number
the operator says they cannot defend to a client, so the BOM refuses to
produce one and says which lines stopped it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import CostingConfig, Material
from app.costing.drivers import (
    NEEDS_ELEMENT_AREA,
    NEEDS_SEGMENTATION,
    CostDrivers,
    ElementDrivers,
    JointDrivers,
)
from app.costing.transport import (
    MODULE_MASS_AGREEMENT_PCT,
    AllocationInputError,
    NoFeasibleAllocation,
    allocate_trips,
    validate_modules,
)
from app.costing.rates import (
    MONEY_DP,
    FxConversion,
    MissingFx,
    MissingRate,
    Rate,
    fx_for,
    pct,
    resolve,
    scalar,
)

COMPUTED = "computed"
MISSING_RATE = "missing_rate"
NOT_COMPUTABLE = "not_computable"
NOT_APPLICABLE = "not_applicable"

#: buy_price units we can drive from validation numbers TODAY.
_MASS_UNITS = {"kg"}
_VOLUME_UNITS = {"m3"}
#: units that need a nesting/segmentation count we do not have.
_COUNT_UNITS = {"slab", "sheet", "piece"}


@dataclass
class CostLine:
    line_id: str
    label: str
    group: str
    status: str
    formula: str
    drivers_used: dict[str, object] = field(default_factory=dict)
    rate_path: str | None = None
    rate_text: str | None = None
    amount_native: float | None = None
    currency: str | None = None
    amount_usd: float | None = None
    fx_text: str | None = None
    blocker: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "line_id": self.line_id, "label": self.label, "group": self.group,
            "status": self.status, "formula": self.formula,
            "drivers_used": self.drivers_used,
            "rate_path": self.rate_path, "rate": self.rate_text,
            "amount_native": self.amount_native, "currency": self.currency,
            "amount_usd": self.amount_usd, "fx": self.fx_text,
            "blocker": self.blocker,
        }


@dataclass
class Bom:
    design_id: str
    spec_hash: str
    material_id: str
    costing_version: str
    generated_at: str
    drivers: dict[str, object]
    lines: list[CostLine]
    complete: bool
    missing_rates: list[str]
    not_computable: list[str]
    fx_used: list[str]
    subtotal_fabrication_usd: float | None = None
    overhead_usd: float | None = None
    subtotal_install_usd: float | None = None
    base_usd: float | None = None
    contingency_usd: float | None = None
    markup_usd: float | None = None
    total_usd: float | None = None
    total_formula: list[str] = field(default_factory=list)
    #: PR-6 (ADR-074): a multi-material BOM carries its per-element and
    #: per-joint drivers. Both stay OUT of as_dict() when empty so every
    #: single-material BOM serialises byte-for-byte as before — the sealed
    #: LUXEXCHANGE digest of existing single-material designs must not move.
    elements: list[dict[str, object]] = field(default_factory=list)
    joints: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "design_id": self.design_id, "spec_hash": self.spec_hash,
            "material_id": self.material_id,
            "costing_version": self.costing_version,
            "generated_at": self.generated_at,
            "drivers": self.drivers,
            "lines": [line.as_dict() for line in self.lines],
            "complete": self.complete,
            "missing_rates": self.missing_rates,
            "not_computable": self.not_computable,
            "fx_used": self.fx_used,
            "totals": {
                "subtotal_fabrication_usd": self.subtotal_fabrication_usd,
                "overhead_usd": self.overhead_usd,
                "subtotal_install_usd": self.subtotal_install_usd,
                "base_usd": self.base_usd,
                "contingency_usd": self.contingency_usd,
                "markup_usd": self.markup_usd,
                "total_usd": self.total_usd,
            },
            "total_formula": self.total_formula,
        }
        if self.elements or self.joints:
            out["elements"] = self.elements
            out["joints"] = self.joints
        return out


# ---------------------------------------------------------------------------


class _Builder:
    def __init__(self, costing: CostingConfig, drivers: CostDrivers,
                 material_id: str, material: Material,
                 element_id: str | None = None) -> None:
        self.c = costing
        self.d = drivers
        self.material_id = material_id
        self.material = material
        # PR-6 (ADR-074): set when this builder prices ONE element of an
        # assembly. Only the wording of the "nothing to join" explanation
        # depends on it — the arithmetic is identical either way — but the
        # design-scope sentence ("no element joints") is FALSE for an element
        # of a design that does have element joints, and this text is shown to
        # the client in the rendered BOM.
        self.element_id = element_id
        self.rates = costing.materials.get(material_id)
        self.lines: list[CostLine] = []
        self._fx_cache: dict[str, FxConversion | MissingFx] = {}

    # -- helpers ---------------------------------------------------------
    def _fx(self, currency: str) -> FxConversion | MissingFx:
        if currency not in self._fx_cache:
            self._fx_cache[currency] = fx_for(self.c, currency)
        return self._fx_cache[currency]

    def _money(self, line_id: str, label: str, group: str, quantity: float,
               qty_text: str, rate: Rate | MissingRate,
               drivers_used: dict[str, object]) -> CostLine:
        """quantity x rate, fully traced — or an honest missing_rate line."""
        if isinstance(rate, MissingRate):
            return self._add(CostLine(
                line_id=line_id, label=label, group=group, status=MISSING_RATE,
                formula=f"{qty_text} x <rate not supplied>",
                drivers_used=drivers_used, rate_path=rate.path,
                rate_text=str(rate), currency=rate.currency,
                blocker=f"costing.yaml {rate.path} is null — supply a number",
            ))
        native = round(quantity * rate.value, MONEY_DP)
        fx = self._fx(rate.currency)
        line = CostLine(
            line_id=line_id, label=label, group=group, status=COMPUTED,
            formula=f"{qty_text} x {rate.value:g} {rate.currency}/{rate.per} "
                    f"= {native:,.2f} {rate.currency}",
            drivers_used=drivers_used, rate_path=rate.path, rate_text=str(rate),
            amount_native=native, currency=rate.currency,
        )
        if isinstance(fx, FxConversion):
            line.amount_usd = fx.to_usd(native)
            line.fx_text = str(fx)
        else:
            line.fx_text = str(fx)
            line.blocker = fx.reason
        return self._add(line)

    def _blocked(self, line_id: str, label: str, group: str, status: str,
                 formula: str, blocker: str,
                 rate_path: str | None = None) -> CostLine:
        return self._add(CostLine(
            line_id=line_id, label=label, group=group, status=status,
            formula=formula, blocker=blocker, rate_path=rate_path,
        ))

    def _add(self, line: CostLine) -> CostLine:
        self.lines.append(line)
        return line

    # -- the lines -------------------------------------------------------
    def material_purchase(self) -> None:
        r = self.rates
        path = f"materials.{self.material_id}.buy_price"
        rate = resolve(path, r.buy_price)
        waste_path = f"materials.{self.material_id}.waste_factor_pct"
        waste = pct(waste_path, r.waste_factor_pct)

        unit = r.buy_price.per
        if unit in _COUNT_UNITS:
            # Basalt is quoted per SLAB and 316L per SHEET in the template.
            # A slab/sheet count needs nesting the geometry into stock sizes,
            # which needs segmentation — refuse rather than divide by a
            # nominal slab and call it a count.
            self._blocked(
                "material_purchase", f"Material — {self.material.name}",
                "fabrication", NOT_COMPUTABLE,
                formula=(
                    f"<{unit} count> x (1 + waste) x rate — a {unit} count "
                    f"cannot be derived from mass or volume"
                ),
                blocker=(
                    f"buy_price is quoted per {unit}, and a {unit} count is "
                    f"NOT what segmentation produces (ADR-056). Two things "
                    f"are still missing, neither of them segmentation: "
                    f"materials.yaml {self.material_id}.stock_size_mm carries "
                    f"a length and a width but no THICKNESS, so a stock "
                    f"volume cannot be formed; and nesting a formed shell "
                    f"onto flat stock needs the surface unrolled, which the "
                    f"kernel does not do for a doubly-curved revolve. "
                    f"Supply buy_price per kg or per m3 and this line "
                    f"computes immediately — it is the largest line on the "
                    f"BOM."
                ),
                rate_path=path,
            )
            return

        if isinstance(waste, MissingRate):
            self._blocked(
                "material_purchase", f"Material — {self.material.name}",
                "fabrication", MISSING_RATE,
                formula=f"quantity x (1 + <waste not supplied>) x rate",
                blocker=f"costing.yaml {waste_path} is null — supply a number",
                rate_path=waste_path,
            )
            return

        factor = 1.0 + waste.value / 100.0
        if unit in _MASS_UNITS:
            qty = self.d.mass_kg * factor
            qty_text = (f"mass {self.d.mass_kg:,.3f} kg x (1 + waste "
                        f"{waste.value:g}%) = {qty:,.3f} kg")
            used = {"mass_kg": round(self.d.mass_kg, 3),
                    "waste_factor_pct": waste.value}
        elif unit in _VOLUME_UNITS:
            qty = self.d.volume_m3 * factor
            qty_text = (f"volume {self.d.volume_m3:,.6f} m3 x (1 + waste "
                        f"{waste.value:g}%) = {qty:,.6f} m3")
            used = {"volume_m3": round(self.d.volume_m3, 6),
                    "waste_factor_pct": waste.value}
        else:
            self._blocked(
                "material_purchase", f"Material — {self.material.name}",
                "fabrication", NOT_COMPUTABLE,
                formula=f"<unsupported buy_price unit {unit!r}>",
                blocker=f"buy_price per {unit!r} has no driver in this platform",
                rate_path=path)
            return
        self._money("material_purchase", f"Material — {self.material.name}",
                    "fabrication", qty, qty_text, rate, used)

    def fabrication(self) -> None:
        r = self.rates
        mid = self.material_id
        hpm3 = scalar(f"materials.{mid}.fabrication.hours_per_m3",
                      r.fabrication.hours_per_m3, "h/m3")
        method = r.fabrication.method or "<method not supplied>"

        if isinstance(hpm3, MissingRate):
            for lid, lbl, p in (
                ("fabrication_labour", "Fabrication — labour",
                 f"materials.{mid}.fabrication.labor"),
                ("fabrication_machine", "Fabrication — machine",
                 f"materials.{mid}.fabrication.machine"),
            ):
                self._blocked(lid, lbl, "fabrication", MISSING_RATE,
                              formula="volume x <hours_per_m3 not supplied> x rate",
                              blocker=f"costing.yaml {hpm3.path} is null — "
                                      "supply a number",
                              rate_path=hpm3.path)
            return

        hours = self.d.volume_m3 * hpm3.value
        hours_text = (f"volume {self.d.volume_m3:,.6f} m3 x "
                      f"{hpm3.value:g} h/m3 = {hours:,.3f} h")
        used = {"volume_m3": round(self.d.volume_m3, 6),
                "hours_per_m3": hpm3.value, "hours": round(hours, 3),
                "method": method}

        self._money("fabrication_labour", "Fabrication — labour", "fabrication",
                    hours, hours_text,
                    resolve(f"materials.{mid}.fabrication.labor",
                            r.fabrication.labor), used)

        machine_path = f"materials.{mid}.fabrication.machine"
        if r.fabrication.machine.amount is None:
            # costing.yaml's own convention: "null if hand work". Honoured
            # rather than flagged, exactly as missing_entries() does.
            self._blocked(
                "fabrication_machine", "Fabrication — machine", "fabrication",
                NOT_APPLICABLE,
                formula=f"{hours:,.3f} h x n/a",
                blocker=f"{machine_path} is null = hand work "
                        f"(method: {method}) — no machine charge",
                rate_path=machine_path)
        else:
            self._money("fabrication_machine", "Fabrication — machine",
                        "fabrication", hours, hours_text,
                        resolve(machine_path, r.fabrication.machine), used)

    def mold_pattern(self) -> None:
        mid = self.material_id
        path = f"materials.{mid}.fabrication.mold_pattern"
        r = self.rates
        method = r.fabrication.method
        if r.fabrication.mold_pattern.amount is None and method != "cast":
            self._blocked(
                "mold_pattern", "Fabrication — mould / pattern", "fabrication",
                NOT_APPLICABLE, formula="n/a",
                blocker=f"{path} is null and method is {method or '<not supplied>'} "
                        "— mould/pattern applies to cast work only",
                rate_path=path)
            return
        self._blocked(
            "mold_pattern", "Fabrication — mould / pattern", "fabrication",
            NOT_COMPUTABLE,
            formula="<piece count> x rate per piece",
            blocker=("a piece count is a module count, and " + NEEDS_SEGMENTATION),
            rate_path=path)

    def finishing(self) -> None:
        mid = self.material_id
        self._money(
            "finishing", "Finishing", "fabrication",
            self.d.surface_area_m2,
            f"surface area {self.d.surface_area_m2:,.4f} m2",
            resolve(f"materials.{mid}.finishing", self.rates.finishing),
            {"surface_area_m2": round(self.d.surface_area_m2, 4)})

    def install(self) -> None:
        inst = self.c.install
        dpt = scalar("install.days_per_tonne", inst.days_per_tonne, "days/t")
        crew = scalar("install.crew_size", inst.crew_size, "people")

        if isinstance(dpt, MissingRate) or isinstance(crew, MissingRate):
            missing = dpt if isinstance(dpt, MissingRate) else crew
            self._blocked(
                "install_crew", "Install — crew", "install", MISSING_RATE,
                formula="mass_t x <days_per_tonne> x <crew_size> x crew_day_rate",
                blocker=f"costing.yaml {missing.path} is null — supply a number",
                rate_path=missing.path)
        else:
            days = self.d.mass_tonnes * dpt.value
            qty = days * crew.value
            qty_text = (
                f"mass {self.d.mass_tonnes:,.3f} t x {dpt.value:g} days/t "
                f"= {days:,.3f} days x crew {crew.value:g} = {qty:,.3f} crew-days")
            self._money("install_crew", "Install — crew", "install", qty,
                        qty_text,
                        resolve("install.crew_day_rate", inst.crew_day_rate),
                        {"mass_tonnes": round(self.d.mass_tonnes, 3),
                         "days_per_tonne": dpt.value, "crew_size": crew.value,
                         "crew_days": round(qty, 3)})

        # Crane — driven by the pick weight, which is a validation number.
        crane_path = "install.crane_day_rate"
        if inst.crane_day_rate.amount is None:
            self._blocked(
                "install_crane", "Install — crane", "install", NOT_APPLICABLE,
                formula="n/a",
                blocker=f"{crane_path} is null = no crane on this job "
                        f"(pick weight would be {self.d.crane_pick_kg:,.1f} kg)",
                rate_path=crane_path)
        elif isinstance(dpt, MissingRate):
            self._blocked(
                "install_crane", "Install — crane", "install", MISSING_RATE,
                formula="<days> x crane_day_rate",
                blocker=f"costing.yaml {dpt.path} is null — supply a number",
                rate_path=dpt.path)
        else:
            days = self.d.mass_tonnes * dpt.value
            self._money(
                "install_crane", "Install — crane", "install", days,
                f"pick weight {self.d.crane_pick_kg:,.1f} kg; "
                f"{days:,.3f} crane-days",
                resolve(crane_path, inst.crane_day_rate),
                {"crane_pick_kg": round(self.d.crane_pick_kg, 1),
                 "monolithic_pick": self.d.monolithic,
                 "days": round(days, 3)})

        self.transport()

    def transport(self) -> None:
        """Trips — LOADED, not bounded, since PR-4 (ADR-067).

        Slice C2 (ADR-056) made trips real; PR-4 makes them honest. The
        C2 line printed a lower bound as a trip count, and four 6 t
        modules at a 10 t payload disprove it (four trucks, not three) —
        the old formula and its failure case are preserved in ADR-067 and
        never return here. Now the measured module masses are loaded
        first-fit-decreasing under BOTH limits, compared unrounded, and
        every trip prints its modules, load and remaining capacity. The
        count is a deterministic conservative feasible allocation — the
        BOM never calls it the lowest achievable. Both capacities remain
        the operator's numbers and neither is defaulted: without them this
        is a MISSING_RATE (his to supply), not a NOT_COMPUTABLE (ours to
        build).
        """
        inst = self.c.install
        line_head = ("install_transport", "Install — transport", "install")
        if self.d.module_count is None:
            self._blocked(
                *line_head, NOT_COMPUTABLE,
                formula="<trip allocation> x rate — the modules do not "
                        "exist yet",
                blocker=(self.d.unavailable or {}).get(
                    "module_count", NEEDS_SEGMENTATION),
                rate_path="install.transport")
            return

        base_formula = (f"{self.d.module_count} modules, "
                        f"{self.d.mass_kg:,.1f} kg -> <trip allocation> "
                        f"x rate")
        if self.d.module_masses_kg is None:
            self._blocked(
                *line_head, NOT_COMPUTABLE, formula=base_formula,
                blocker=(self.d.unavailable or {}).get(
                    "module_masses_kg",
                    "per-module masses were never recorded for this design "
                    "— rebuild it once and the assembler records every "
                    "module's measured mass"),
                rate_path="install.transport")
            return

        modules = [(mid, float(m)) for mid, m in self.d.module_masses_kg]
        try:
            validate_modules(modules)
        except AllocationInputError as exc:
            self._blocked(
                *line_head, NOT_COMPUTABLE, formula=base_formula,
                blocker=f"the stored per-module masses are unusable: {exc}",
                rate_path="install.transport")
            return

        # Independent conservation guard: the modules must agree with the
        # validation report the operator signed off before any trip is
        # loaded from them. MODULE_MASS_AGREEMENT_PCT is a judgement value
        # [J], recorded in transport.py.
        module_total = math.fsum(m for _, m in modules)
        tolerance_kg = abs(self.d.mass_kg) * MODULE_MASS_AGREEMENT_PCT / 100.0
        if abs(module_total - self.d.mass_kg) > tolerance_kg:
            self._blocked(
                *line_head, NOT_COMPUTABLE, formula=base_formula,
                blocker=(
                    f"the per-module masses sum to {module_total:,.3f} kg "
                    f"but the validation report says "
                    f"{self.d.mass_kg:,.3f} kg — "
                    f"{abs(module_total - self.d.mass_kg):,.3f} kg apart, "
                    f"over the {MODULE_MASS_AGREEMENT_PCT:g}% agreement "
                    f"bound. No trip is loaded from numbers that disagree; "
                    f"rebuild the design"),
                rate_path="install.transport")
            return

        payload = scalar("install.truck_payload_kg", inst.truck_payload_kg,
                         "kg per trip")
        per_trip = scalar("install.modules_per_trip", inst.modules_per_trip,
                          "modules per trip")
        for capacity in (payload, per_trip):
            if isinstance(capacity, MissingRate):
                self._blocked(
                    *line_head, MISSING_RATE, formula=base_formula,
                    blocker=f"costing.yaml {capacity.path} is null — "
                            "supply a number",
                    rate_path=capacity.path)
                return

        try:
            allocation = allocate_trips(modules, float(payload.value),
                                        per_trip.value)
        except NoFeasibleAllocation as exc:
            self._blocked(
                *line_head, NOT_COMPUTABLE,
                formula=(f"{self.d.module_count} modules, "
                         f"{self.d.mass_kg:,.1f} kg -> <no feasible trip> "
                         f"x rate"),
                blocker=str(exc), rate_path="install.transport")
            return
        except AllocationInputError as exc:
            # a supplied capacity with a nonsense VALUE (not null) — the
            # operator corrects the rate card, so this is his side
            self._blocked(
                *line_head, MISSING_RATE, formula=base_formula,
                blocker=(f"costing.yaml install.truck_payload_kg / "
                         f"install.modules_per_trip cannot load a trip: "
                         f"{exc} — correct the rate card"),
                rate_path="install.truck_payload_kg")
            return

        trips = allocation.trip_count
        qty_text = (
            f"{self.d.module_count} modules, {self.d.mass_kg:,.1f} kg "
            f"loaded onto {trips} trip(s) — {allocation.method_label}; "
            f"payload {float(payload.value):,.0f} kg, "
            f"{allocation.modules_per_trip} modules per bed, every "
            f"capacity compared unrounded")
        self._money(
            *line_head, trips, qty_text,
            resolve("install.transport", inst.transport),
            {"module_count": self.d.module_count,
             "mass_kg": round(self.d.mass_kg, 1),
             "trips": trips,
             "payload_kg": float(payload.value),
             "modules_per_trip": allocation.modules_per_trip,
             "allocation_method": allocation.method_label,
             "allocation": [
                 {"trip": t.index,
                  "modules": [{"id": mid, "mass_kg": round(m, 3)}
                              for mid, m in zip(t.module_ids,
                                                t.module_masses_kg)],
                  "load_kg": round(t.load_kg, 3),
                  "remaining_payload_kg": round(t.remaining_payload_kg, 3),
                  "remaining_module_slots": t.remaining_module_slots}
                 for t in allocation.trips]})

    def seams(self) -> None:
        """Joining the modules — real since slice C2 (ADR-056).

        The seam is MEASURED off the cut faces the kernel actually
        produced, both the run and the bedded area, so the rate's own
        per-unit decides which drives the line: a welded 316L seam is
        billed per metre of run, a bedded basalt joint per square metre
        of face. The platform never picks for the workshop.
        """
        path = f"materials.{self.material_id}.seam"
        entry = self.rates.seam if self.rates is not None else None
        if entry is None:
            self._blocked(
                "seam_welding", "Fabrication — seams", "fabrication",
                MISSING_RATE,
                formula="<seam> x rate",
                blocker=(f"costing.yaml has no {path} entry — add a seam "
                         f"amount/currency/per block under "
                         f"materials.{self.material_id}, quoted per m (run) "
                         f"or per m2 (bedded face)"),
                rate_path=path)
            return

        if self.d.seam_length_m is None:
            self._blocked(
                "seam_welding", "Fabrication — seams", "fabrication",
                NOT_COMPUTABLE,
                formula="<seam> x rate",
                blocker=(self.d.unavailable or {}).get(
                    "seam_length_m", NEEDS_SEGMENTATION),
                rate_path=path)
            return

        rate = resolve(path, entry)
        unit = entry.per
        joint_m = self.d.joint_seam_length_m or 0.0
        if unit == "m":
            qty = self.d.seam_length_m
            qty_text = (f"seam run {qty:,.3f} m ({qty - joint_m:,.3f} m from "
                        f"segmentation cuts + {joint_m:,.3f} m at element "
                        f"joints)")
            used = {"seam_length_m": round(qty, 3),
                    "joint_seam_length_m": round(joint_m, 3)}
        elif unit == "m2":
            if self.d.seam_area_m2 is None:
                self._blocked(
                    "seam_welding", "Fabrication — seams", "fabrication",
                    NOT_COMPUTABLE,
                    formula="<seam area m2> x rate",
                    blocker=(self.d.unavailable or {}).get(
                        "seam_area_m2", NEEDS_SEGMENTATION),
                    rate_path=path)
                return
            qty = self.d.seam_area_m2
            qty_text = (f"bedded seam face {qty:,.4f} m2 (segmentation cut "
                        f"faces + element joint contact faces, both measured "
                        f"off the real geometry)")
            used = {"seam_area_m2": round(qty, 4)}
        else:
            self._blocked(
                "seam_welding", "Fabrication — seams", "fabrication",
                NOT_COMPUTABLE,
                formula=f"<unsupported seam unit {unit!r}>",
                blocker=(f"a seam is quoted per m (run) or per m2 (bedded "
                         f"face); costing.yaml {path} says per {unit!r}"),
                rate_path=path)
            return

        if self.d.seam_length_m == 0.0:
            if self.element_id is None:
                blocker = ("this design has no seams: one module and no "
                           "element joints, so there is nothing to join")
            else:
                blocker = (f"element {self.element_id} is one module with no "
                           f"segmentation cut, so there is nothing to join "
                           f"inside it; any element JOINT it takes part in is "
                           f"billed once under JOINTS")
            self._blocked(
                "seam_welding", "Fabrication — seams", "fabrication",
                NOT_APPLICABLE,
                formula=f"{qty_text} x rate",
                blocker=blocker,
                rate_path=path)
            return
        self._money("seam_welding", "Fabrication — seams", "fabrication",
                    qty, qty_text, rate, used)


def build_bom(costing: CostingConfig, drivers: CostDrivers, material_id: str,
              material: Material, design_id: str = "", spec_hash: str = "",
              now_iso: str | None = None) -> Bom:
    """Assemble the full BOM. Never raises on missing rates — it REPORTS."""
    if material_id not in costing.materials:
        raise ValueError(
            f"costing.yaml has no rates block for material {material_id!r} "
            f"(has: {', '.join(sorted(costing.materials))})")

    b = _Builder(costing, drivers, material_id, material)
    b.material_purchase()
    b.fabrication()
    b.mold_pattern()
    b.seams()
    b.finishing()
    b.install()

    return _finish_totals(
        costing, b.lines, drivers.as_dict(), material_id,
        design_id=design_id, spec_hash=spec_hash, now_iso=now_iso)


def _finish_totals(costing: CostingConfig, lines: list[CostLine],
                   drivers_dict: dict[str, object], material_id: str, *,
                   design_id: str, spec_hash: str, now_iso: str | None,
                   elements: list[dict[str, object]] | None = None,
                   joints: list[dict[str, object]] | None = None) -> Bom:
    """Shared tail of every BOM: missing/blocked census, then totals ONLY
    when every line is computed or not_applicable (unchanged rule)."""
    missing = sorted({ln.rate_path for ln in lines
                      if ln.status == MISSING_RATE and ln.rate_path})
    blocked = sorted({ln.line_id for ln in lines if ln.status == NOT_COMPUTABLE})

    # Percentages are rates too, and they gate the totals.
    overhead = pct("workshop.overhead_pct", costing.workshop.get("overhead_pct"))
    conting = pct("contingency_pct", costing.contingency_pct)
    markup = pct("markup_pct", costing.markup_pct)
    for r in (overhead, conting, markup):
        if isinstance(r, MissingRate):
            missing.append(r.path)
    missing = sorted(set(missing))

    fx_used = sorted({ln.fx_text for ln in lines if ln.fx_text})
    fx_broken = any(ln.status == COMPUTED and ln.amount_usd is None
                    for ln in lines)

    bom = Bom(
        design_id=design_id, spec_hash=spec_hash, material_id=material_id,
        costing_version=costing.costing_version,
        generated_at=now_iso or datetime.now(timezone.utc).isoformat(),
        drivers=drivers_dict, lines=lines,
        complete=False, missing_rates=missing, not_computable=blocked,
        fx_used=fx_used,
        elements=list(elements or []), joints=list(joints or []),
    )

    if missing or blocked or fx_broken:
        return bom  # INCOMPLETE — no totals, deliberately

    fab = round(sum(ln.amount_usd or 0.0 for ln in lines
                    if ln.group == "fabrication"), MONEY_DP)
    oh = round(fab * overhead.value / 100.0, MONEY_DP)
    ins = round(sum(ln.amount_usd or 0.0 for ln in lines
                    if ln.group == "install"), MONEY_DP)
    base = round(fab + oh + ins, MONEY_DP)
    cont = round(base * conting.value / 100.0, MONEY_DP)
    mk = round((base + cont) * markup.value / 100.0, MONEY_DP)

    bom.complete = True
    bom.subtotal_fabrication_usd = fab
    bom.overhead_usd = oh
    bom.subtotal_install_usd = ins
    bom.base_usd = base
    bom.contingency_usd = cont
    bom.markup_usd = mk
    bom.total_usd = round(base + cont + mk, MONEY_DP)
    bom.total_formula = [
        f"fabrication subtotal = {fab:,.2f} USD",
        f"overhead = {fab:,.2f} x {overhead.value:g}% "
        f"({overhead.path}) = {oh:,.2f} USD",
        f"install subtotal = {ins:,.2f} USD",
        f"base = {fab:,.2f} + {oh:,.2f} + {ins:,.2f} = {base:,.2f} USD",
        f"contingency = {base:,.2f} x {conting.value:g}% "
        f"({conting.path}) = {cont:,.2f} USD",
        f"markup = ({base:,.2f} + {cont:,.2f}) x {markup.value:g}% "
        f"({markup.path}) = {mk:,.2f} USD",
        f"TOTAL = {base:,.2f} + {cont:,.2f} + {mk:,.2f} = "
        f"{bom.total_usd:,.2f} USD",
    ]
    return bom


# ---------------------------------------------------------------------------
# PR-6 (ADR-074): the multi-material assembly BOM
# ---------------------------------------------------------------------------

#: Line-id separator between an element and its line: "b1/finishing".
ELEMENT_SEP = "/"


def _element_scope(e: ElementDrivers) -> CostDrivers:
    """Element-scoped CostDrivers so the per-material fabrication lines
    reuse the SAME _Builder arithmetic as a single-material design.

    Seams here are the element's own segmentation cuts only — joints are
    billed separately, once, by their owner. Finishing is NOT taken from
    this object (build_assembly_bom bills the EXPOSED skin itself), and
    the install-group fields are irrelevant at element scope: install
    runs ONCE at assembly level and never through this object.
    """
    return CostDrivers(
        mass_kg=e.mass_kg, volume_m3=e.volume_m3,
        surface_area_m2=e.surface_area_m2 or 0.0,
        crane_pick_kg=e.mass_kg, monolithic=(e.module_count == 1),
        module_count=e.module_count,
        seam_length_m=e.split_seam_length_m,
        seam_area_m2=e.split_seam_area_m2,
        joint_seam_length_m=0.0 if e.split_seam_length_m is not None else None,
        module_masses_kg=None,
        unavailable=dict(e.unavailable or {}) or None,
    )


def _element_lines(costing: CostingConfig, e: ElementDrivers,
                   material: Material) -> list[CostLine]:
    """This element's fabrication lines, in ITS material, ids prefixed."""
    b = _Builder(costing, _element_scope(e), e.material_id, material,
                 element_id=e.element_id)
    b.material_purchase()
    b.fabrication()
    b.mold_pattern()
    b.seams()           # this element's segmentation cuts only
    fin_path = f"materials.{e.material_id}.finishing"
    if e.exposed_area_m2 is None:
        reason = (e.unavailable or {}).get(
            "exposed_area_m2",
            (e.unavailable or {}).get("surface_area_m2", NEEDS_ELEMENT_AREA))
        b._blocked("finishing", "Finishing", "fabrication", NOT_COMPUTABLE,
                   formula="<exposed area m2> x rate", blocker=reason,
                   rate_path=fin_path)
    else:
        full = e.surface_area_m2 or 0.0
        b._money("finishing", "Finishing", "fabrication", e.exposed_area_m2,
                 (f"exposed skin {e.exposed_area_m2:,.4f} m2 (element "
                  f"{full:,.4f} m2 minus {full - e.exposed_area_m2:,.4f} m2 "
                  f"of joint contact faces)"),
                 resolve(fin_path, costing.materials[e.material_id].finishing),
                 {"exposed_area_m2": round(e.exposed_area_m2, 4),
                  "surface_area_m2": round(full, 4)})
    for ln in b.lines:
        if ln.line_id == "seam_welding":
            ln.label = "Fabrication — seams (segmentation cuts)"
        ln.line_id = f"{e.element_id}{ELEMENT_SEP}{ln.line_id}"
        ln.label = f"{e.element_id} ({e.material_id}) — {ln.label}"
        ln.drivers_used = {"element_id": e.element_id,
                           "material_id": e.material_id,
                           **(ln.drivers_used or {})}
    return b.lines


def _joint_line(costing: CostingConfig, shared: _Builder,
                j: JointDrivers) -> None:
    """One joint, billed ONCE to its owner — or an honest MISSING_RATE."""
    from app.costing.joints import UnownedJoint, joint_owner

    lid = f"joint{ELEMENT_SEP}{j.child_id}->{j.parent_id}"
    label = (f"Joint {j.child_id} ({j.child_material}) onto "
             f"{j.parent_id} ({j.parent_material})")
    owner = joint_owner(costing, j.parent_material, j.child_material)
    if isinstance(owner, UnownedJoint):
        shared._blocked(lid, label, "fabrication", MISSING_RATE,
                        formula=(f"joint {j.length_m:,.3f} m run / "
                                 f"{j.area_m2:,.4f} m2 face x <owner unset>"),
                        blocker=owner.reason, rate_path=owner.missing_path)
        return
    seam = costing.materials[owner.material_id].seam
    if seam is None:
        shared._blocked(lid, label, "fabrication", MISSING_RATE,
                        formula="<joint> x rate",
                        blocker=(f"costing.yaml has no {owner.rate_path} "
                                 f"entry ({owner.reason})"),
                        rate_path=owner.rate_path)
        return
    rate = resolve(owner.rate_path, seam)
    if seam.per == "m":
        qty, qty_text = j.length_m, f"joint run {j.length_m:,.3f} m"
        used: dict[str, object] = {"length_m": round(j.length_m, 3)}
    elif seam.per == "m2":
        qty, qty_text = j.area_m2, f"joint contact face {j.area_m2:,.4f} m2"
        used = {"area_m2": round(j.area_m2, 4)}
    else:
        shared._blocked(lid, label, "fabrication", NOT_COMPUTABLE,
                        formula=f"<unsupported seam unit {seam.per!r}>",
                        blocker=(f"a seam is quoted per m or per m2; "
                                 f"costing.yaml {owner.rate_path} says per "
                                 f"{seam.per!r}"),
                        rate_path=owner.rate_path)
        return
    ln = shared._money(lid, label, "fabrication", qty, qty_text, rate,
                       {"owner_material": owner.material_id,
                        "owner_reason": owner.reason,
                        "joint_type": j.joint_type, **used})
    ln.formula += f"  [owner: {owner.material_id} — {owner.reason}]"


def build_assembly_bom(costing: CostingConfig,
                       assembly: CostDrivers,
                       elements: list[ElementDrivers],
                       joints: list[JointDrivers],
                       materials: dict[str, Material],
                       design_id: str = "", spec_hash: str = "",
                       now_iso: str | None = None) -> Bom:
    """One BOM for an assembly whose elements may differ in material.

    Amendment 4 (PR-6, ADR-074), enforced by construction:
      * one trusted measurement path per element — the manifest the
        assembler persisted; nothing is re-measured or apportioned;
      * finishing on EXPOSED area (element skin minus joint contact);
      * every joint billed ONCE, to the material ``joints.joint_owner``
        names, with the reason on the line; an unowned joint is a
        MISSING_RATE naming the path, never a silent side;
      * crane / crew / transport added ONCE at assembly level from the
        assembly drivers (heaviest module, total mass, module masses).
    Never raises on missing rates — it REPORTS, exactly like build_bom.
    """
    if not elements:
        raise ValueError("an assembly BOM needs at least one element")
    material_ids = sorted({e.material_id for e in elements})
    for mid in material_ids:
        if mid not in costing.materials:
            raise ValueError(
                f"costing.yaml has no rates block for material {mid!r} "
                f"(has: {', '.join(sorted(costing.materials))})")
        if mid not in materials:
            raise ValueError(f"materials.yaml has no material {mid!r}")

    lines: list[CostLine] = []
    for e in elements:
        lines.extend(_element_lines(costing, e, materials[e.material_id]))

    # Joints and the shared install block live on ONE builder over the
    # ASSEMBLY drivers; its material_id is only a label for _Builder.
    shared = _Builder(costing, assembly, material_ids[0],
                      materials[material_ids[0]])
    for j in joints:
        _joint_line(costing, shared, j)
    shared.install()
    lines.extend(shared.lines)

    drivers_dict = dict(assembly.as_dict())
    drivers_dict["materials"] = material_ids
    drivers_dict["element_count"] = len(elements)
    return _finish_totals(
        costing, lines, drivers_dict,
        material_id="+".join(material_ids),
        design_id=design_id, spec_hash=spec_hash, now_iso=now_iso,
        elements=[e.as_dict() for e in elements],
        joints=[j.as_dict() for j in joints])
