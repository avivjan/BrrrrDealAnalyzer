"""Flip step: operating costs during holding, and total holding costs.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money


def operating_and_holding_costs_step(payload, breakdown, total_hml_interest):
    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    monthly_operating = monthly_taxes + monthly_insurance + payload.montly_hoa + payload.monthly_utilities
    total_operating = monthly_operating * payload.holding_time_months
    breakdown.add(
        ["net_profit", "total_holding_costs"],
        "Total Operating Costs (during holding)",
        total_operating,
        f"(Taxes/12 ({fmt_money(monthly_taxes)}) + Insurance/12 ({fmt_money(monthly_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) + Utilities ({fmt_money(payload.monthly_utilities)})) × {payload.holding_time_months} mos = {fmt_money(total_operating)}",
    )

    total_holding_costs = total_hml_interest + total_operating
    breakdown.add(
        ["net_profit", "total_holding_costs"],
        "Total Holding Costs",
        total_holding_costs,
        f"HML Interest ({fmt_money(total_hml_interest)}) + Operating ({fmt_money(total_operating)}) = {fmt_money(total_holding_costs)}",
    )
    return total_operating, total_holding_costs
