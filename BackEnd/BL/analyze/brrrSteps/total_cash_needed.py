"""BRRRR step: total cash needed for the deal, unbuffered and buffered.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import get_total_cash_needed_for_deal


def total_cash_needed_step(
    payload, breakdown, purchase_price, down_payment_cash, closing_costs_buy,
    HML_points_in_cash, rehab_cost, HML_interest_in_cash, holding_cost_until_refi, hml_payoff,
):
    total_cash_needed_without_buffer, total_cash_needed_with_buffer = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, holding_cost_until_refi, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, payload.use_HM_for_rehab)
    # Surface the same components the helper sums internally so the user can
    # follow each dollar that goes into the unbuffered total.
    _brrr_rehab_cash_needed = rehab_cost * (1 - int(payload.use_HM_for_rehab))
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "Down Payment (cash)",
        down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(purchase_price)}) = {fmt_money(down_payment_cash)}",
    )
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "Closing Costs (Buy)",
        closing_costs_buy,
        f"{fmt_money(closing_costs_buy)}",
    )
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "HML Points (cash)",
        HML_points_in_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_payoff)}) = {fmt_money(HML_points_in_cash)}",
    )
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "Rehab Cash (out-of-pocket)",
        _brrr_rehab_cash_needed,
        (f"Rehab ({fmt_money(rehab_cost)}) is financed via HM → no out-of-pocket = {fmt_money(_brrr_rehab_cash_needed)}"
         if payload.use_HM_for_rehab
         else f"Rehab ({fmt_money(rehab_cost)}) paid in cash = {fmt_money(_brrr_rehab_cash_needed)}"),
    )
    breakdown.add(
        "total_cash_needed_for_deal",
        "HML Interest (cash, until refi)",
        HML_interest_in_cash,
        f"{fmt_money(HML_interest_in_cash)} accrued over {payload.days_until_refi} days at {fmt_pct(payload.HML_interest_rate)}/yr ÷ 360 per diem",
    )
    breakdown.add(
        "total_cash_needed_for_deal",
        "Holding Costs (until refi)",
        holding_cost_until_refi,
        f"Taxes + Insurance + HOA accrued over {payload.days_until_refi} days = {fmt_money(holding_cost_until_refi)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal",
        "Total Cash Needed",
        total_cash_needed_without_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(HML_points_in_cash)}) + Rehab Cash ({fmt_money(_brrr_rehab_cash_needed)}) + HML Interest ({fmt_money(HML_interest_in_cash)}) + Holding ({fmt_money(holding_cost_until_refi)}) = {fmt_money(total_cash_needed_without_buffer)}",
    )
    # Buffered version applies the same multipliers the helper uses internally
    # (closing × 1.1, holding × 1.5, HML interest × 1.5, rehab × 1.5).
    _brrr_buffered_closing = closing_costs_buy * Decimal("1.1")
    _brrr_buffered_holding = holding_cost_until_refi * Decimal("1.5")
    _brrr_buffered_interest = HML_interest_in_cash * Decimal("1.5")
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "Closing × 1.1 buffer",
        _brrr_buffered_closing,
        f"Closing ({fmt_money(closing_costs_buy)}) × 1.1 = {fmt_money(_brrr_buffered_closing)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "HML Interest × 1.5 buffer",
        _brrr_buffered_interest,
        f"HML Interest ({fmt_money(HML_interest_in_cash)}) × 1.5 = {fmt_money(_brrr_buffered_interest)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "Holding × 1.5 buffer",
        _brrr_buffered_holding,
        f"Holding ({fmt_money(holding_cost_until_refi)}) × 1.5 = {fmt_money(_brrr_buffered_holding)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "Total Cash Needed (Buffered)",
        total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing×1.1 ({fmt_money(_brrr_buffered_closing)}) + HML Points ({fmt_money(HML_points_in_cash)}) + Rehab Cash ({fmt_money(_brrr_rehab_cash_needed)}) + HML Interest×1.5 ({fmt_money(_brrr_buffered_interest)}) + Holding×1.5 ({fmt_money(_brrr_buffered_holding)}) = {fmt_money(total_cash_needed_with_buffer)}",
    )
    return total_cash_needed_without_buffer, total_cash_needed_with_buffer
