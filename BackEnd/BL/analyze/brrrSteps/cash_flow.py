"""BRRRR step: net operating income and monthly cash flow.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money


def cash_flow_step(payload, breakdown, operating_expenses, mortgage_payment):
    net_operating_income = payload.rent - operating_expenses
    breakdown.add(
        "cash_flow",
        "Net Operating Income (NOI)",
        net_operating_income,
        f"Rent ({fmt_money(payload.rent)}) − Operating Expenses ({fmt_money(operating_expenses)}) = {fmt_money(net_operating_income)}",
    )
    cash_flow = net_operating_income - mortgage_payment
    breakdown.add(
        ["cash_flow", "roi", "cash_on_cash"],
        "Monthly Cash Flow",
        cash_flow,
        f"NOI ({fmt_money(net_operating_income)}) − Mortgage ({fmt_money(mortgage_payment)}) = {fmt_money(cash_flow)}",
    )
    return cash_flow
