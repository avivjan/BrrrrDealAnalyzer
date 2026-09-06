"""Flip step: HML amount, points and interest over the holding period.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import get_HML_amount


def hml_costs_step(payload, breakdown, purchase_price, rehab_cost):
    hml_amount = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    breakdown.add(
        "total_hml_interest",
        "HML Amount",
        hml_amount,
        (f"Purchase Loan + Rehab ({fmt_money(hml_amount)}) — full HM stack"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(purchase_price)}) = {fmt_money(hml_amount)}"),
    )
    hml_points_cash = (payload.HML_points / Decimal("100.0")) * hml_amount
    breakdown.add(
        "net_profit",
        "HML Points (cash)",
        hml_points_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_amount)}) = {fmt_money(hml_points_cash)}",
    )

    monthly_interest = (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * hml_amount
    breakdown.add(
        "total_hml_interest",
        "Monthly HML Interest",
        monthly_interest,
        f"HML Amount ({fmt_money(hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 12 = {fmt_money(monthly_interest)}",
    )
    total_hml_interest = monthly_interest * payload.holding_time_months
    breakdown.add(
        ["net_profit", "total_hml_interest", "total_holding_costs"],
        "Total HML Interest (over holding period)",
        total_hml_interest,
        f"Monthly Interest ({fmt_money(monthly_interest)}) × {payload.holding_time_months} mos = {fmt_money(total_hml_interest)}",
    )
    return hml_amount, hml_points_cash, total_hml_interest
