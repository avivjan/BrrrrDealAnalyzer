"""BRRRR step: cash-on-cash return.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import calc_cash_on_cash


def cash_on_cash_step(breakdown, cash_out_from_deal, cash_flow):
    cash_on_cash = calc_cash_on_cash(cash_out_from_deal, cash_flow)
    if cash_out_from_deal >= 0:
        _brrr_coc_formula = f"Cash Out ({fmt_money(cash_out_from_deal)}) ≥ 0 → no equity at risk (∞)"
    elif cash_flow <= 0:
        _brrr_coc_formula = f"Cash Flow ({fmt_money(cash_flow)}) ≤ 0 → CoC undefined (-∞)"
    else:
        _brrr_coc_formula = f"Annual Cash Flow ({fmt_money(cash_flow * 12)}) / |Cash Out| ({fmt_money(abs(cash_out_from_deal))}) × 100 = {fmt_pct(cash_on_cash)}"
    breakdown.add("cash_on_cash", "Cash on Cash", cash_on_cash, _brrr_coc_formula)
    return cash_on_cash
