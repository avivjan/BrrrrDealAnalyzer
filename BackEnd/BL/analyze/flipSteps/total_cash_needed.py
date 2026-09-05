"""Flip step: total cash needed for the deal, unbuffered and buffered.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import get_total_cash_needed_for_deal


def total_cash_needed_step(
    payload, breakdown, purchase_price, closing_costs_buy, hml_amount, hml_points_cash, rehab_cost,
    total_operating, total_hml_interest,
):
    down_payment_cash = (payload.down_payment / Decimal("100.0")) * purchase_price
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Down Payment (cash)",
        down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(purchase_price)}) = {fmt_money(down_payment_cash)}",
    )
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Closing Costs (Buy)",
        closing_costs_buy,
        f"{fmt_money(closing_costs_buy)}",
    )
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "HML Points (cash)",
        hml_points_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_amount)}) = {fmt_money(hml_points_cash)}",
    )

    total_cash_needed_without_buffer, total_cash_needed_with_buffer = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, total_operating, closing_costs_buy, hml_points_cash, rehab_cost, total_hml_interest, payload.use_HM_for_rehab)
    rehab_cash = rehab_cost if not payload.use_HM_for_rehab else Decimal("0")
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Rehab Cash (out-of-pocket)",
        rehab_cash,
        (f"Rehab ({fmt_money(rehab_cost)}) is financed via HM → no out-of-pocket = {fmt_money(rehab_cash)}"
         if payload.use_HM_for_rehab
         else f"Rehab ({fmt_money(rehab_cost)}) paid in cash = {fmt_money(rehab_cash)}"),
    )
    breakdown.add(
        "total_cash_needed",
        "HML Interest (cash, during holding)",
        total_hml_interest,
        f"Monthly Interest × {payload.holding_time_months} mos = {fmt_money(total_hml_interest)}",
    )
    breakdown.add(
        "total_cash_needed",
        "Operating Costs (during holding)",
        total_operating,
        f"Monthly Operating × {payload.holding_time_months} mos = {fmt_money(total_operating)}",
    )
    breakdown.add(
        "total_cash_needed",
        "Total Cash Needed",
        total_cash_needed_without_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(hml_points_cash)}) + Rehab Cash ({fmt_money(rehab_cash)}) + HML Interest ({fmt_money(total_hml_interest)}) + Operating ({fmt_money(total_operating)}) = {fmt_money(total_cash_needed_without_buffer)}",
    )
    # Buffered version mirrors `get_total_cash_needed_for_deal` internals:
    # operating × 1.5, interest × 1.5, closing × 1.1.
    _flip_buffered_closing = closing_costs_buy * Decimal("1.1")
    _flip_buffered_interest = total_hml_interest * Decimal("1.5")
    _flip_buffered_operating = total_operating * Decimal("1.5")
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Closing × 1.1 buffer",
        _flip_buffered_closing,
        f"Closing ({fmt_money(closing_costs_buy)}) × 1.1 = {fmt_money(_flip_buffered_closing)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "HML Interest × 1.5 buffer",
        _flip_buffered_interest,
        f"HML Interest ({fmt_money(total_hml_interest)}) × 1.5 = {fmt_money(_flip_buffered_interest)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Operating × 1.5 buffer",
        _flip_buffered_operating,
        f"Operating ({fmt_money(total_operating)}) × 1.5 = {fmt_money(_flip_buffered_operating)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Total Cash Needed (Buffered)",
        total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing×1.1 ({fmt_money(_flip_buffered_closing)}) + HML Points ({fmt_money(hml_points_cash)}) + Rehab Cash ({fmt_money(rehab_cash)}) + HML Interest×1.5 ({fmt_money(_flip_buffered_interest)}) + Operating×1.5 ({fmt_money(_flip_buffered_operating)}) = {fmt_money(total_cash_needed_with_buffer)}",
    )
    return total_cash_needed_without_buffer, total_cash_needed_with_buffer, down_payment_cash, rehab_cash
