"""BRRRR step: debt service coverage ratio.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_num
from BL.analyze.common.deal_math import calcDSCR


def dscr_step(payload, breakdown, mortgage_payment):
    dscr =  calcDSCR(payload.rent, payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, mortgage_payment)
    # Decompose PITIA only for the formula narrative (matches calcDSCR internals).
    _brrr_pitia = mortgage_payment + payload.annual_property_taxes / Decimal("12.0") + payload.annual_insurance / Decimal("12.0") + payload.montly_hoa
    breakdown.add(
        "dscr",
        "DSCR",
        dscr,
        (f"Rent ({fmt_money(payload.rent)}) / PITIA ({fmt_money(_brrr_pitia)} = Mortgage + Taxes/12 + Ins/12 + HOA) = {fmt_num(dscr)}"
         if _brrr_pitia else "PITIA is 0 → DSCR undefined"),
    )
    return dscr
