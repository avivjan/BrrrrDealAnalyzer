"""BRRRR step: monthly operating expenses.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import calc_montly_operating_expenses


def operating_expenses_step(payload, breakdown):
    operating_expenses = calc_montly_operating_expenses(payload)
    breakdown.add(
        "cash_flow",
        "Monthly Operating Expenses",
        operating_expenses,
        f"Rent ({fmt_money(payload.rent)}) × (Vacancy {fmt_pct(payload.vacancy_percent)} + Mgmt {fmt_pct(payload.property_managment_fee_precentages_from_rent)} + Maint {fmt_pct(payload.maintenance_percent)} + CapEx {fmt_pct(payload.capex_percent_of_rent)}) + Taxes ({fmt_money(payload.annual_property_taxes)})/12 + Insurance ({fmt_money(payload.annual_insurance)})/12 + HOA ({fmt_money(payload.montly_hoa)}) = {fmt_money(operating_expenses)}",
    )
    return operating_expenses
