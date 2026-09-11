"""Flip step: HML amount, points and interest over the holding period."""

from decimal import Decimal

from BL.analyze.common.deal_math import get_HML_amount


def hml_costs_step(payload, purchase_price, rehab_cost):
    hml_amount = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    hml_points = (payload.HML_points / Decimal("100.0")) * hml_amount
    monthly_interest = (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * hml_amount
    total_hml_interest = monthly_interest * payload.holding_time_months
    return hml_amount, hml_points, monthly_interest, total_hml_interest
