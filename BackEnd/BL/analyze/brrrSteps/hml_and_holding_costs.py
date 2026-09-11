"""BRRRR step: hard-money amount, interest and points, and holding costs, all accrued before the refi."""

from decimal import Decimal

from BL.analyze.common.deal_math import (
    get_HML_amount,
    calc_holding_costs,
    calc_HML_interest_in_cash,
)


def upfront_hml_and_holding_costs_step(payload, purchase_price, rehab_cost):
    hml_amount = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    hml_interest = calc_HML_interest_in_cash(purchase_price, payload.down_payment, rehab_cost, payload.days_until_refi, payload.HML_interest_rate, payload.use_HM_for_rehab)
    hml_points = payload.HML_points/Decimal("100.0") * hml_amount
    holding_costs = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi)
    return hml_amount, hml_interest, hml_points, holding_costs
