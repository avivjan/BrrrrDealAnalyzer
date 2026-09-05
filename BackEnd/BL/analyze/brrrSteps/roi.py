"""BRRRR step: return on investment.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import calc_roi


def roi_step(breakdown, cash_out_from_deal, cash_flow, net_profit):
    roi = calc_roi(cash_out_from_deal, cash_flow, net_profit)
    if cash_out_from_deal >= 0:
        _brrr_roi_formula = f"Cash Out ({fmt_money(cash_out_from_deal)}) ≥ 0 → no equity at risk (∞)"
    elif cash_flow <= 0:
        _brrr_roi_formula = f"Cash Flow ({fmt_money(cash_flow)}) ≤ 0 → ROI undefined (-∞)"
    else:
        _brrr_roi_formula = f"(Annual Cash Flow ({fmt_money(cash_flow * 12)}) + Net Profit ({fmt_money(net_profit)})) / |Cash Out| ({fmt_money(abs(cash_out_from_deal))}) × 100 = {fmt_pct(roi)}"
    breakdown.add("roi", "ROI", roi, _brrr_roi_formula)
    return roi
