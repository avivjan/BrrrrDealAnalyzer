"""BRRRR step: cash out at refinance, and the ROUTI variant.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from decimal import Decimal

from BL.analyze.common.calc_breakdown import fmt_money, fmt_pct
from BL.analyze.common.deal_math import (
    get_HML_amount,
    calc_cash_out_from_deal,
    calc_cash_out_routi,
)


def cash_out_at_refi_step(
    payload, breakdown, arv, ltv, purchase_price, rehab_cost, closing_costs_buy,
    HML_points_in_cash, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash,
    cash_reserve_in_cash, holding_cost_until_refi,
):
    cash_out_from_deal = calc_cash_out_from_deal(arv, ltv, payload.down_payment, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash, payload.use_HM_for_rehab, holding_cost_until_refi, cash_reserve_in_cash)
    # Decompose the helper's inputs only for the formula narrative (no math change).
    _brrr_loan_amount = arv * ltv
    breakdown.add(
        ["cash_out", "equity"],
        "Refi Loan Amount",
        _brrr_loan_amount,
        f"ARV ({fmt_money(arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(_brrr_loan_amount)}",
    )
    _brrr_hml_payoff = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    breakdown.add(
        "cash_out",
        "HML Payoff at Refi",
        _brrr_hml_payoff,
        (f"Purchase Loan + Rehab ({fmt_money(_brrr_hml_payoff)}) — full HM stack carried into refi"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(purchase_price)}) = {fmt_money(_brrr_hml_payoff)}"),
    )
    _brrr_down_payment_cash = (payload.down_payment / Decimal("100")) * purchase_price
    _brrr_total_cash_invested = _brrr_down_payment_cash + closing_costs_buy + HML_points_in_cash + rehab_cost * (1 - int(payload.use_HM_for_rehab)) + HML_interest_in_cash + holding_cost_until_refi
    breakdown.add(
        "cash_out",
        "Total Cash Invested (pre-refi)",
        _brrr_total_cash_invested,
        f"Down Payment ({fmt_money(_brrr_down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(HML_points_in_cash)}) + Rehab Out-of-Pocket ({fmt_money(rehab_cost * (1 - int(payload.use_HM_for_rehab)))}) + HML Interest ({fmt_money(HML_interest_in_cash)}) + Holding ({fmt_money(holding_cost_until_refi)}) = {fmt_money(_brrr_total_cash_invested)}",
    )
    breakdown.add(
        ["net_profit", "roi", "cash_on_cash", "cash_out"],
        "Cash Out from Deal",
        cash_out_from_deal,
        f"Refi Loan ({fmt_money(_brrr_loan_amount)}) − HML Payoff ({fmt_money(_brrr_hml_payoff)}) − Refi Closing ({fmt_money(closing_cost_refi)}) − Refi Points ({fmt_money(refi_points_in_cash)}) − Cash Reserve ({fmt_money(cash_reserve_in_cash)}) − Total Cash Invested ({fmt_money(_brrr_total_cash_invested)}) = {fmt_money(cash_out_from_deal)}",
    )
    cash_out_routi = calc_cash_out_routi(arv, ltv, payload.down_payment, purchase_price, rehab_cost, closing_cost_refi, refi_points_in_cash, payload.use_HM_for_rehab, cash_reserve_in_cash)
    return cash_out_from_deal, cash_out_routi, _brrr_loan_amount, _brrr_hml_payoff, _brrr_down_payment_cash
