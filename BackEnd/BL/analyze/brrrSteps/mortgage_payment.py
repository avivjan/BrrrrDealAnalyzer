"""BRRRR step: monthly mortgage payment on the DSCR loan.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import calc_mortgage_payment


def mortgage_payment_step(payload, breakdown, arv, ltv, loan_amount):
    mortgage_payment = calc_mortgage_payment(arv, ltv, payload.interest_rate, payload.loan_term_years)
    breakdown.add(
        ["cash_flow", "dscr"],
        "Monthly Mortgage Payment",
        mortgage_payment,
        f"Amortize Loan ({fmt_money(loan_amount)} = ARV {fmt_money(arv)} × LTV {fmt_pct(payload.ltv_as_precent)}) at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(mortgage_payment)}",
    )
    return mortgage_payment
