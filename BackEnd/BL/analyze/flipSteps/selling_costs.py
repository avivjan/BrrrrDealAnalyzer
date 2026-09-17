"""Flip step: agent fees and selling closing costs."""

from decimal import Decimal

from BL.analyze.common.deal_math import thousands_to_dollars


def selling_costs_step(payload, sale_price):
    agent_fees_percent = payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee
    selling_closing_costs = thousands_to_dollars(payload.selling_closing_costs_in_thousands)
    selling_costs = sale_price * (agent_fees_percent / Decimal("100.0")) + selling_closing_costs
    return agent_fees_percent, selling_closing_costs, selling_costs
