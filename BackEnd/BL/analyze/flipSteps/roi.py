"""Flip step: ROI and annualized ROI.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct, fmt_num


def roi_and_annualized_step(payload, breakdown, net_profit, total_cash_invested):
    roi = (net_profit / total_cash_invested) * Decimal("100.0") if total_cash_invested > 0 else Decimal("0")
    breakdown.add(
        ["roi", "annualized_roi"],
        "ROI",
        roi,
        (f"Net Profit ({fmt_money(net_profit)}) / Total Cash Invested ({fmt_money(total_cash_invested)}) × 100 = {fmt_pct(roi)}"
         if total_cash_invested > 0 else "Total Cash Invested is 0 → ROI = 0%"),
    )
    years = payload.holding_time_months / Decimal("12.0")
    annualized_roi = (roi / years) if years > 0 else Decimal("0")
    breakdown.add(
        "annualized_roi",
        "Annualized ROI",
        annualized_roi,
        (f"ROI ({fmt_pct(roi)}) / Holding Years ({fmt_num(years)}) = {fmt_pct(annualized_roi)}"
         if years > 0 else "Holding time is 0 → Annualized ROI = 0%"),
    )
    return roi, annualized_roi
