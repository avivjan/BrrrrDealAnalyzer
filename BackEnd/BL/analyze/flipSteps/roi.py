"""Flip step: ROI and annualized ROI.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct, fmt_num


def roi_and_annualized_step(payload, breakdown, net_profit, total_cash_invested):
    # No cash invested: the return is unbounded. Reuse the engine's sentinels
    # (-1 = +∞, -2 = -∞, same as the BRRRR CoC/ROI) so every renderer decodes
    # them the same way; a break-even deal with no cash in is a genuine 0%.
    if total_cash_invested > 0:
        roi = (net_profit / total_cash_invested) * Decimal("100.0")
        _roi_formula = f"Net Profit ({fmt_money(net_profit)}) / Total Cash Invested ({fmt_money(total_cash_invested)}) × 100 = {fmt_pct(roi)}"
    elif net_profit > 0:
        roi = Decimal("-1")
        _roi_formula = f"Total Cash Invested is 0 with Net Profit {fmt_money(net_profit)} → ROI = ∞"
    elif net_profit < 0:
        roi = Decimal("-2")
        _roi_formula = f"Total Cash Invested is 0 with Net Profit {fmt_money(net_profit)} → ROI = -∞"
    else:
        roi = Decimal("0")
        _roi_formula = "Total Cash Invested is 0 and Net Profit is 0 → ROI = 0%"
    breakdown.add(["roi", "annualized_roi"], "ROI", roi, _roi_formula)

    years = payload.holding_time_months / Decimal("12.0")
    if total_cash_invested <= 0:
        annualized_roi = roi  # the sentinel (or 0) carries through unchanged
        _ann_formula = "ROI is unbounded (no cash invested) → Annualized ROI carries the same sentinel"
    elif years > 0:
        annualized_roi = roi / years
        _ann_formula = f"ROI ({fmt_pct(roi)}) / Holding Years ({fmt_num(years)}) = {fmt_pct(annualized_roi)}"
    else:
        annualized_roi = Decimal("0")
        _ann_formula = "Holding time is 0 → Annualized ROI = 0%"
    breakdown.add("annualized_roi", "Annualized ROI", annualized_roi, _ann_formula)
    return roi, annualized_roi
