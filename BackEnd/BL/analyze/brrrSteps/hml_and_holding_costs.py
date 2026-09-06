"""BRRRR step: HML interest/points and holding costs accrued before refi.

Called by `calculate_brrr_results` in `BL/analyze/analyzeBRRR.py`.
"""

from decimal import Decimal

from BL.analyze.common.deal_math import (
    get_HML_amount,
    calc_holding_costs,
    calc_HML_interest_in_cash,
)


def upfront_hml_and_holding_costs_step(payload, purchase_price, rehab_cost):
    """HML interest/points accrued before refi, and holding costs until refi.
    No breakdown entries here -- these feed the "cash out" and "total cash
    needed" steps, which document them."""
    HML_interest_in_cash = calc_HML_interest_in_cash(purchase_price, payload.down_payment, rehab_cost, payload.days_until_refi, payload.HML_interest_rate, payload.use_HM_for_rehab)
    HML_points_in_cash = payload.HML_points/Decimal("100.0") * get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    holding_cost_until_refi = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi)
    return HML_interest_in_cash, HML_points_in_cash, holding_cost_until_refi
