"""Flip step: total cash needed for the deal, unbuffered and buffered."""

from BL.analyze.common.deal_math import calc_down_payment_in_cash, get_total_cash_needed_for_deal


def total_cash_needed_step(payload, purchase_price, closing_costs_buy, hml_points, rehab_cost, total_operating, total_hml_interest):
    down_payment_cash = calc_down_payment_in_cash(payload.down_payment, purchase_price)
    cash_needed = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, total_operating, closing_costs_buy, hml_points, rehab_cost, total_hml_interest, payload.use_HM_for_rehab)
    return down_payment_cash, cash_needed
