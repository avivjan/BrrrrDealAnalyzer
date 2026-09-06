"""Flip step: agent fees and selling closing costs.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import thousands_to_dollars


def selling_costs_step(payload, breakdown, sale_price):
    agent_fees_percent = payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee
    selling_costs = sale_price * (agent_fees_percent / Decimal("100.0")) + thousands_to_dollars(payload.selling_closing_costs_in_thousands)
    breakdown.add(
        "net_profit",
        "Selling Costs",
        selling_costs,
        f"Sale Price ({fmt_money(sale_price)}) × Agent Fees {fmt_pct(agent_fees_percent)} + Closing ({fmt_money(thousands_to_dollars(payload.selling_closing_costs_in_thousands))}) = {fmt_money(selling_costs)}",
    )
    return selling_costs
