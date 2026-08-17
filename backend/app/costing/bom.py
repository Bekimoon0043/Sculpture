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

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import CostingConfig, Material
from app.costing.drivers import NEEDS_SEGMENTATION, CostDrivers
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

    def as_dict(self) -> dict[str, object]:
        return {
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


# ---------------------------------------------------------------------------


class _Builder:
    def __init__(self, costing: CostingConfig, drivers: CostDrivers,
                 material_id: str, material: Material) -> None:
        self.c = costing
        self.d = drivers
        self.material_id = material_id
        self.material = material
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
                    f"buy_price is quoted per {unit}; converting geometry to a "
                    f"{unit} count requires nesting into "
                    f"stock_size_mm and {NEEDS_SEGMENTATION}. "
                    f"Either supply buy_price per kg or per m3 (both are "
                    f"computable from the validation report today), or wait "
                    f"for segmentation."
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

        self._blocked(
            "install_transport", "Install — transport", "install",
            NOT_COMPUTABLE,
            formula="<trip count> x rate per trip",
            blocker=("a trip count needs the module count and its packing, and "
                     + NEEDS_SEGMENTATION),
            rate_path="install.transport")

    def seams(self) -> None:
        self._blocked(
            "seam_welding", "Fabrication — seams", "fabrication",
            NOT_COMPUTABLE,
            formula="<seam length m> x rate",
            blocker=("seam length is zero until the solid is split into "
                     "modules, and " + NEEDS_SEGMENTATION +
                     ". No seam rate exists in costing.yaml either — add one "
                     "when segmentation lands"),
            rate_path="(no seam rate in costing.yaml v1)")


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

    lines = b.lines
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
        drivers=drivers.as_dict(), lines=lines,
        complete=False, missing_rates=missing, not_computable=blocked,
        fx_used=fx_used,
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
