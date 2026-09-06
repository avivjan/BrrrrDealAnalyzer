"""BRRRR step: post-refi equity and net profit.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct


def equity_and_net_profit_step(payload, breakdown, arv, ltv, cash_reserve_in_cash, cash_out_from_deal):
    # Cash reserve is treated as an immediate principal paydown on the DSCR
    # loan, so the post-refi loan balance is `arv*ltv - cash_reserve`. That
    # paydown converts cash_out into equity 1:1, leaving net_profit unchanged
    # (CoC and ROI still drop because more capital is tied up in the deal).
    equity = arv * (1 - ltv) + cash_reserve_in_cash
    breakdown.add(
        ["net_profit", "roi", "equity"],
        "Equity (post-refi)",
        equity,
        f"ARV ({fmt_money(arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Cash Reserve ({fmt_money(cash_reserve_in_cash)}) = {fmt_money(equity)}",
    )
    net_profit = equity + cash_out_from_deal
    breakdown.add(
        ["net_profit", "roi"],
        "Net Profit",
        net_profit,
        f"Equity ({fmt_money(equity)}) + Cash Out ({fmt_money(cash_out_from_deal)}) = {fmt_money(net_profit)}",
    )
    return equity, net_profit
