"""BRRRR step: thousands->dollars basis, rehab with rehab_contingency, construction budget, lowest ARV."""

from decimal import Decimal

from BL.analyze.common.deal_math import thousands_to_dollars, effective, lowest_arv_default


def dollar_basis_step(payload):
    arv = thousands_to_dollars(payload.arv_in_thousands)
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    rehab_contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + rehab_contingency
    construction_budget = thousands_to_dollars(payload.construction_loan_budget_in_thousands)
    lowest_arv = effective(
        None if payload.lowest_arv_in_thousands is None else thousands_to_dollars(payload.lowest_arv_in_thousands),
        lowest_arv_default(arv),
    )
    return arv, purchase_price, rehab_cost_base, rehab_contingency, rehab_cost, construction_budget, lowest_arv
