"""BRRRR step: thousands->dollars basis plus rehab contingency."""

from decimal import Decimal

from BL.analyze.common.deal_math import thousands_to_dollars


def dollar_basis_step(payload):
    arv = thousands_to_dollars(payload.arv_in_thousands)
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency
    return arv, purchase_price, rehab_cost_base, contingency, rehab_cost
