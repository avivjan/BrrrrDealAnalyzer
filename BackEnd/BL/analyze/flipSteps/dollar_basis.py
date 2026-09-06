"""Flip step: thousands->dollars basis and rehab cost with contingency.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import thousands_to_dollars


def dollar_basis_and_rehab_cost_step(payload, breakdown):
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency
    breakdown.add(
        "net_profit",
        "Rehab Cost (with contingency)",
        rehab_cost,
        f"Base ({fmt_money(rehab_cost_base)}) + Contingency {fmt_pct(payload.rehab_contingency_percent)} ({fmt_money(contingency)}) = {fmt_money(rehab_cost)}",
    )
    sale_price = thousands_to_dollars(payload.sale_price_in_thousands)
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    return purchase_price, sale_price, closing_costs_buy, rehab_cost
