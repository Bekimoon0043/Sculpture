"""Rate resolution and dated FX — the traceability half of the costing layer.

Operator rule 3: "Every cost line shows its formula and its source rate. A
number I cannot trace is a number I cannot defend to a client."
Operator rule 4: "NEVER invent or estimate a rate. If one is missing, the
report says so explicitly and does not guess."

Both are enforced structurally: a rate is only ever obtained through
``resolve()``, which returns EITHER a fully-traced ``Rate`` (value, currency,
per-unit AND the dotted config path it came from) or a ``MissingRate`` naming
that same path. There is no third outcome and no default argument anywhere in
this module — a caller cannot accidentally receive a number that has no
provenance.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import CostAmount, CostingConfig

#: Money is rounded to 6 decimal places platform-wide (ADR-003).
MONEY_DP = 6


@dataclass(frozen=True)
class Rate:
    """A rate that exists, with the config path that produced it."""

    path: str
    value: float
    currency: str
    per: str

    def __str__(self) -> str:
        return f"{self.value:g} {self.currency}/{self.per}"


@dataclass(frozen=True)
class MissingRate:
    """A rate that is null in costing.yaml. Carries the path to fill in."""

    path: str
    currency: str | None = None
    per: str | None = None

    def __str__(self) -> str:
        return f"MISSING: costing.yaml {self.path}"


def resolve(path: str, amount: CostAmount) -> Rate | MissingRate:
    """The ONLY way to obtain a rate. Null amount -> MissingRate, never 0."""
    if amount.amount is None:
        return MissingRate(path=path, currency=amount.currency, per=amount.per)
    return Rate(path=path, value=amount.amount,
                currency=amount.currency, per=amount.per)


@dataclass(frozen=True)
class FxConversion:
    """A dated conversion. ``rate`` is units of ``currency`` per 1 USD."""

    currency: str
    rate: float
    as_of: str
    path: str

    def to_usd(self, amount: float) -> float:
        return round(amount / self.rate, MONEY_DP)

    def __str__(self) -> str:
        return f"{self.rate:g} {self.currency}/USD as of {self.as_of}"


@dataclass(frozen=True)
class MissingFx:
    currency: str
    path: str
    reason: str

    def __str__(self) -> str:
        return f"MISSING FX: {self.reason} ({self.path})"


def fx_for(costing: CostingConfig, currency: str) -> FxConversion | MissingFx:
    """Dated FX for one currency. USD is the reporting currency, rate 1.

    A rate without an ``as_of`` date is treated as MISSING, not as usable:
    an undated FX figure is exactly the stale number the anti-stale-data rule
    exists to prevent (same treatment as pricing.yaml's pricing_version).
    """
    if currency == "USD":
        return FxConversion(currency="USD", rate=1.0, as_of="n/a (reporting currency)",
                            path="(none — USD is the reporting currency)")
    entry = costing.fx_rates.get(currency)
    if entry is None:
        return MissingFx(
            currency=currency, path=f"fx_rates.{currency}",
            reason=f"no fx_rates entry for {currency}",
        )
    if entry.rate is None:
        return MissingFx(
            currency=currency, path=f"fx_rates.{currency}.rate",
            reason=f"fx_rates.{currency}.rate is null",
        )
    if entry.as_of is None:
        return MissingFx(
            currency=currency, path=f"fx_rates.{currency}.as_of",
            reason=(
                f"fx_rates.{currency}.rate is set but as_of is null — an "
                "undated FX rate is not usable"
            ),
        )
    return FxConversion(currency=currency, rate=entry.rate,
                        as_of=entry.as_of, path=f"fx_rates.{currency}")


def pct(path: str, value: float | None) -> Rate | MissingRate:
    """A percentage from the rate card, traced the same way as money."""
    if value is None:
        return MissingRate(path=path, currency="%", per="of subtotal")
    return Rate(path=path, value=value, currency="%", per="of subtotal")


def scalar(path: str, value: float | None, unit: str) -> Rate | MissingRate:
    """A dimensioned scalar (hours_per_m3, days_per_tonne, crew_size)."""
    if value is None:
        return MissingRate(path=path, currency=unit, per="")
    return Rate(path=path, value=value, currency=unit, per="")
