"""BRRRR step: closing / points / reserve figures for the DSCR refinance leg.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from decimal import Decimal

from BL.analyze.common.deal_math import thousands_to_dollars


def refi_terms_step(payload, arv):
    """Closing/points/reserve figures for the DSCR refinance leg. No breakdown entries."""
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    closing_cost_refi = thousands_to_dollars(payload.closing_cost_refi_in_thousands)
    ltv = payload.ltv_as_precent/Decimal("100")
    refi_points_in_cash = (payload.refi_points / Decimal("100")) * arv * ltv
    cash_reserve_in_cash = thousands_to_dollars(payload.cash_reserve_in_thousands)
    return closing_costs_buy, closing_cost_refi, ltv, refi_points_in_cash, cash_reserve_in_cash
