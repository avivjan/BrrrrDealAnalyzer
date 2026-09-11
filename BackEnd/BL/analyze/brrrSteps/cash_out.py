"""BRRRR step: cash out at refinance (net of what was invested) and the ROUTI wire."""

from BL.analyze.common.deal_math import (
    calc_down_payment_in_cash,
    calc_total_cash_invested,
    calc_cash_out_routi,
    calc_cash_out_from_deal,
)


def cash_out_at_refi_step(
    payload, arv, ltv, purchase_price, rehab_cost, closing_costs_buy,
    hml_points, hml_interest, closing_costs_refi, refi_points, cash_reserve, holding_costs,
):
    loan_amount = arv * ltv
    down_payment_cash = calc_down_payment_in_cash(payload.down_payment, purchase_price)
    total_cash_invested = calc_total_cash_invested(payload.down_payment, purchase_price, closing_costs_buy, hml_points, rehab_cost, hml_interest, payload.use_HM_for_rehab, holding_costs)
    cash_out_routi = calc_cash_out_routi(arv, ltv, payload.down_payment, purchase_price, rehab_cost, closing_costs_refi, refi_points, payload.use_HM_for_rehab, cash_reserve)
    cash_out = calc_cash_out_from_deal(arv, ltv, payload.down_payment, purchase_price, closing_costs_buy, hml_points, rehab_cost, hml_interest, closing_costs_refi, refi_points, payload.use_HM_for_rehab, holding_costs, cash_reserve)
    return loan_amount, down_payment_cash, total_cash_invested, cash_out_routi, cash_out
