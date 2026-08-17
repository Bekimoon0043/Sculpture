"""The budget constraint — binding, not advisory (operator requirement).

"The budget constraint check becomes real, not advisory — same treatment as
the basin_diameter hard constraint."

Same TREATMENT: it refuses, it carries the real numbers in the message, and
it cannot be ignored. ``BudgetViolation`` mirrors ``ConstraintViolation`` in
registry.py deliberately, down to the message shape.

**Placement, stated openly because it differs from `basin_diameter`.**
`basin_diameter` is enforced inside `registry.validate_params`, which runs
INSIDE the ADR-005 sandbox on AI-written code and drives the Phase 4 repair
loop. Cost cannot live there, for reasons that are practical rather than
architectural:

  * the sandbox has no network and no rate card, so `costing.yaml` is not
    reachable from inside it;
  * the GEOMETRIST has no rates in its prompt, so a cost rejection would
    burn its three bounded repair attempts guessing at a budget it cannot
    compute — exactly the failure ADR-029 recorded, where the model spent
    two of three attempts failing an arithmetic it had been told but could
    not solve;
  * a cost depends on the FINISHED validated solid (mass, surface area),
    which does not exist until after the build the constraint would gate.

So the refusal happens at the BOM boundary, on the completed design, before
anything reaches a client: an over-budget design is refused and cannot be
exported as a quote. That is binding in the sense that matters — no priced
document leaves the platform for a design that breaks the budget — while
keeping geometric constraints geometric. If the operator wants it inside the
geometry loop as well, the pieces are here; it needs rates in the sandbox and
in the geometrist prompt first, and that is a deliberate decision, not a
line-move.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.costing.bom import Bom
from app.costing.rates import MONEY_DP, FxConversion, MissingFx, fx_for


class BudgetViolation(ValueError):
    """Raised when a completed BOM exceeds the spec's budget ceiling.

    Mirrors registry.ConstraintViolation: every message carries the real
    computed numbers, so the operator can act on it directly.
    """

    def __init__(self, message: str, total_usd: float, ceiling_usd: float,
                 over_usd: float, over_pct: float) -> None:
        super().__init__(message)
        self.message = message
        self.total_usd = total_usd
        self.ceiling_usd = ceiling_usd
        self.over_usd = over_usd
        self.over_pct = over_pct


@dataclass
class BudgetCheck:
    status: str          # "pass" | "fail" | "not_performed"
    formula: str
    total_usd: float | None = None
    ceiling_usd: float | None = None
    ceiling_native: float | None = None
    ceiling_currency: str | None = None
    fx_text: str | None = None
    headroom_usd: float | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status, "formula": self.formula,
            "total_usd": self.total_usd, "ceiling_usd": self.ceiling_usd,
            "ceiling_native": self.ceiling_native,
            "ceiling_currency": self.ceiling_currency,
            "fx": self.fx_text, "headroom_usd": self.headroom_usd,
            "reason": self.reason,
        }


def check_budget(bom: Bom, budget: dict, costing) -> BudgetCheck:
    """Compare a BOM total against the spec's `constraints.budget`.

    An INCOMPLETE BOM returns `not_performed` — never `pass`. A budget check
    that silently passes because half the cost lines are missing is worse
    than no check: it would tell the operator a design is affordable on the
    strength of costs nobody has computed.
    """
    if not bom.complete or bom.total_usd is None:
        blockers = []
        if bom.missing_rates:
            blockers.append(f"{len(bom.missing_rates)} missing rate(s)")
        if bom.not_computable:
            blockers.append(f"{len(bom.not_computable)} not-computable line(s)")
        return BudgetCheck(
            status="not_performed",
            formula="cannot compare an incomplete BOM against a ceiling",
            reason=("the BOM has no total: " + ", ".join(blockers) +
                    ". A budget check is never reported as PASS on partial "
                    "costs."),
        )

    amount = budget.get("amount")
    currency = budget.get("currency")
    fx_date = budget.get("fx_date")
    if amount is None or currency is None:
        return BudgetCheck(
            status="not_performed",
            formula="no budget ceiling in the spec",
            reason="constraints.budget is missing amount or currency",
        )

    fx = fx_for(costing, currency)
    if isinstance(fx, MissingFx):
        return BudgetCheck(
            status="not_performed",
            formula=f"ceiling {amount:,.2f} {currency} -> USD needs an FX rate",
            reason=(f"{fx.reason}. The spec quotes the budget in {currency} "
                    f"(fx_date {fx_date}); supply that rate in costing.yaml."),
        )
    assert isinstance(fx, FxConversion)

    ceiling_usd = fx.to_usd(float(amount))
    headroom = round(ceiling_usd - bom.total_usd, MONEY_DP)
    formula = (
        f"total {bom.total_usd:,.2f} USD vs ceiling {amount:,.2f} {currency} "
        f"/ {fx.rate:g} {currency}/USD (as of {fx.as_of}) = "
        f"{ceiling_usd:,.2f} USD")

    if bom.total_usd > ceiling_usd:
        over = round(bom.total_usd - ceiling_usd, MONEY_DP)
        over_pct = round(over / ceiling_usd * 100.0, 3) if ceiling_usd else 0.0
        raise BudgetViolation(
            message=(
                f"budget exceeded: total {bom.total_usd:,.2f} USD > ceiling "
                f"{ceiling_usd:,.2f} USD (= {amount:,.2f} {currency} at "
                f"{fx.rate:g} {currency}/USD as of {fx.as_of}) — over by "
                f"{over:,.2f} USD ({over_pct:g}%)"),
            total_usd=bom.total_usd, ceiling_usd=ceiling_usd,
            over_usd=over, over_pct=over_pct)

    return BudgetCheck(
        status="pass", formula=formula, total_usd=bom.total_usd,
        ceiling_usd=ceiling_usd, ceiling_native=float(amount),
        ceiling_currency=currency, fx_text=str(fx), headroom_usd=headroom)
