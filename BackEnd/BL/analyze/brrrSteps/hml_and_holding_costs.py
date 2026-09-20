"""BRRRR step: hard-money points and interest (with its three-way split), and every holding-period
cost and income accrued before the refi."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import calc_hml_interest, calc_holding_costs, DAYS_PER_MONTH


class HmlAndHoldingCosts(NamedTuple):
    hml_points: Decimal
    hml_per_diem: Decimal
    hml_interest: Decimal                 # total until the refi
    prepaid_interest_buy: Decimal         # collected at the buy closing
    hml_interest_paid_monthly: Decimal    # paid on the 1st of each month
    hml_interest_accrued_into_refi_payoff: Decimal
    holding_costs: Decimal                # taxes + insurance + HOA until the refi
    utilities_until_rented: Decimal
    pre_refi_rental_income: Decimal


def hml_and_holding_costs_step(payload, hml_amount, timeline) -> HmlAndHoldingCosts:
    hml_annual_interest_rate_percent = payload.HML_interest_rate
    hml_points = payload.HML_points / Decimal("100.0") * hml_amount
    hml_interest = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, payload.days_until_refi)
    hml_per_diem = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, 1)
    prepaid_interest_buy = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, timeline.hml_interest_days_prepaid_at_purchase_closing)
    hml_interest_accrued_into_refi_payoff = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, timeline.hml_interest_days_accrued_into_refi_payoff)
    # The remainder, so the three slices always add back to the total exactly.
    hml_interest_paid_monthly = hml_interest - prepaid_interest_buy - hml_interest_accrued_into_refi_payoff
    holding_costs = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi)
    utilities_until_rented = payload.monthly_utilities_until_rented * Decimal(payload.days_until_rented) / DAYS_PER_MONTH
    pre_refi_rental_income = payload.rent * Decimal(timeline.days_tenant_occupied_before_refi) / DAYS_PER_MONTH
    return HmlAndHoldingCosts(
        hml_points=hml_points,
        hml_per_diem=hml_per_diem,
        hml_interest=hml_interest,
        prepaid_interest_buy=prepaid_interest_buy,
        hml_interest_paid_monthly=hml_interest_paid_monthly,
        hml_interest_accrued_into_refi_payoff=hml_interest_accrued_into_refi_payoff,
        holding_costs=holding_costs,
        utilities_until_rented=utilities_until_rented,
        pre_refi_rental_income=pre_refi_rental_income,
    )
