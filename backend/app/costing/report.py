"""Render a BOM as the document the operator hands a client — or refuses to.

The rendering rule follows the operator's: every money line prints its
formula and the config path of the rate that produced it, on the same line
block. Anything that could not be computed prints in a separate section that
says WHO has to act, so the document never mixes "we owe you a number" with
"you owe us a rate".
"""

from __future__ import annotations

from app.costing.bom import (
    COMPUTED,
    MISSING_RATE,
    NOT_APPLICABLE,
    NOT_COMPUTABLE,
    Bom,
)
from app.costing.budget import BudgetCheck

_W = 78


def _rule(ch: str = "-") -> str:
    return ch * _W


def render_bom(bom: Bom, budget: BudgetCheck | None = None) -> str:
    out: list[str] = []
    a = out.append

    a(_rule("="))
    a("BILL OF MATERIALS")
    a(_rule("="))
    a(f"design        : {bom.design_id or '(unsaved)'}")
    a(f"spec_hash     : {bom.spec_hash or '(none)'}")
    a(f"material      : {bom.material_id}")
    a(f"rate card     : costing.yaml {bom.costing_version}")
    a(f"generated     : {bom.generated_at}")
    a("")
    a("COST DRIVERS (measured by the validation gate — not re-measured here)")
    for k, v in bom.drivers.items():
        a(f"  {k:20} {v}")
    # Slice C2 (ADR-056): say in one line what the workshop actually makes
    # and what the crane actually picks, because "9 modules, heaviest 1.5 t"
    # is the sentence the operator reads before anything else on this page.
    count = bom.drivers.get("module_count")
    if isinstance(count, int) and count >= 1:
        a("")
        a("WHAT SHIPS")
        pick = bom.drivers.get("crane_pick_kg")
        a(f"  modules              {count}")
        a(f"  heaviest single pick {pick} kg"
          + ("  (the whole piece — nothing is split)" if count == 1 else
             "  (a module, not the assembled fountain)"))
        seam = bom.drivers.get("seam_length_m")
        if seam is not None:
            joint = bom.drivers.get("joint_seam_length_m") or 0.0
            a(f"  seam to join         {seam:,.3f} m run"
              f"  ({float(seam) - float(joint):,.3f} m cut + "
              f"{float(joint):,.3f} m at element joints)")
            area = bom.drivers.get("seam_area_m2")
            if area is not None:
                a(f"  bedded seam face     {area:,.4f} m2")
    if bom.fx_used:
        a("")
        a("FX")
        for fx in bom.fx_used:
            a(f"  {fx}")

    for group, title in (("fabrication", "FABRICATION"), ("install", "INSTALL")):
        rows = [ln for ln in bom.lines if ln.group == group]
        if not rows:
            continue
        a("")
        a(_rule())
        a(title)
        a(_rule())
        for ln in rows:
            if ln.status == COMPUTED:
                a(f"  {ln.label}")
                a(f"    formula : {ln.formula}")
                a(f"    rate    : {ln.rate_text}   [{ln.rate_path}]")
                usd = f"{ln.amount_usd:,.2f} USD" if ln.amount_usd is not None \
                    else "USD n/a (no FX)"
                a(f"    amount  : {ln.amount_native:,.2f} {ln.currency}"
                  f"   =  {usd}")
            elif ln.status == NOT_APPLICABLE:
                a(f"  {ln.label}: not applicable — {ln.blocker}")
            else:
                tag = ("RATE MISSING" if ln.status == MISSING_RATE
                       else "NOT COMPUTABLE")
                a(f"  {ln.label}: [{tag}]")
                a(f"    formula : {ln.formula}")
                a(f"    blocked : {ln.blocker}")
            a("")

    a(_rule("="))
    if bom.complete:
        a("TOTALS")
        a(_rule("="))
        for line in bom.total_formula:
            a(f"  {line}")
    else:
        a("NO TOTAL — THIS BOM IS INCOMPLETE")
        a(_rule("="))
        a("  A total is not produced from partial costs. Nothing here is")
        a("  estimated, and nothing is defaulted to zero.")
        if bom.missing_rates:
            a("")
            a(f"  YOU SUPPLY — {len(bom.missing_rates)} rate(s) still null in "
              "config/costing.yaml:")
            for p in bom.missing_rates:
                a(f"    - {p}")
        if bom.not_computable:
            a("")
            a(f"  WE BUILD — {len(bom.not_computable)} line(s) whose DRIVER "
              "does not exist yet:")
            for ln in bom.lines:
                if ln.status == NOT_COMPUTABLE:
                    a(f"    - {ln.line_id}: {ln.blocker}")

    if budget is not None:
        a("")
        a(_rule("="))
        a(f"BUDGET CONSTRAINT: {budget.status.upper()}")
        a(_rule("="))
        a(f"  {budget.formula}")
        if budget.status == "pass":
            a(f"  headroom: {budget.headroom_usd:,.2f} USD")
        if budget.reason:
            a(f"  {budget.reason}")

    a("")
    return "\n".join(out)
