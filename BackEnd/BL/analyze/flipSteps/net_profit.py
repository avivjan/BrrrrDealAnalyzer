"""Flip step: capital gains tax and net profit.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct


def net_profit_after_tax_step(payload, breakdown, gross_profit):
    cap_gains = Decimal("0")
    if gross_profit > 0:
        cap_gains = gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0"))
    breakdown.add(
        "net_profit",
        "Capital Gains Tax",
        cap_gains,
        (f"Gross Profit ({fmt_money(gross_profit)}) × {fmt_pct(payload.capital_gains_tax_rate)} = {fmt_money(cap_gains)}"
         if gross_profit > 0 else f"Gross Profit ≤ 0 → no tax owed = {fmt_money(cap_gains)}"),
    )

    net_profit = gross_profit - cap_gains
    breakdown.add(
        ["net_profit", "roi"],
        "Net Profit (after tax)",
        net_profit,
        f"Gross Profit ({fmt_money(gross_profit)}) − Capital Gains Tax ({fmt_money(cap_gains)}) = {fmt_money(net_profit)}",
    )
    return net_profit
