"""BRRRR step: closing / points / reserve figures for the DSCR refinance leg."""

from decimal import Decimal

from BL.analyze.common.deal_math import thousands_to_dollars


def refi_terms_step(payload, arv):
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    closing_costs_refi = thousands_to_dollars(payload.closing_cost_refi_in_thousands)
    ltv = payload.ltv_as_precent/Decimal("100")
    refi_points = (payload.refi_points / Decimal("100")) * arv * ltv
    cash_reserve = thousands_to_dollars(payload.cash_reserve_in_thousands)
    return closing_costs_buy, closing_costs_refi, ltv, refi_points, cash_reserve
