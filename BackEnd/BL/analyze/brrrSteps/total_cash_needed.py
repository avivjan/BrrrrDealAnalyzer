"""BRRRR step: total cash needed for the deal, unbuffered and buffered."""

from decimal import Decimal

from BL.analyze.common.deal_math import get_total_cash_needed_for_deal


def total_cash_needed_step(
    payload, purchase_price, closing_costs_buy, hml_points, rehab_cost, hml_interest,
    holding_costs, cash_out_routi,
):
    # Lifetime cash requirement: if the refi wire (`cash_out_routi`, already net
    # of the cash reserve) is negative, the investor brings that shortfall to
    # the refi closing table, so it counts toward the cash the deal needs.
    refi_shortfall = max(Decimal("0"), -cash_out_routi)
    cash_needed = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, holding_costs, closing_costs_buy, hml_points, rehab_cost, hml_interest, payload.use_HM_for_rehab, refi_shortfall)
    return refi_shortfall, cash_needed
