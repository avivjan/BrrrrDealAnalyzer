"""BRRRR step: hard-money points and interest (with its three-way split), and every holding-period
cost and income accrued before the refi."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import calc_hml_interest, calc_holding_costs, DAYS_PER_MONTH


class HmlAndHolding(NamedTuple):
    hml_points: Decimal
    hml_per_diem: Decimal
    hml_interest: Decimal                 # total until the refi
    prepaid_interest_buy: Decimal         # collected at the buy closing
    hml_monthly_interest_paid: Decimal    # paid on the 1st of each month
    hml_accrued_interest_at_payoff: Decimal
    holding_costs: Decimal                # taxes + insurance + HOA until the refi
    utilities_until_rented: Decimal
    pre_refi_rental_income: Decimal


def hml_and_holding_costs_step(payload, hml_amount, timeline) -> HmlAndHolding:
    rate = payload.HML_interest_rate
    hml_points = payload.HML_points / Decimal("100.0") * hml_amount
    hml_interest = calc_hml_interest(hml_amount, rate, payload.days_until_refi)
    hml_per_diem = calc_hml_interest(hml_amount, rate, 1)
    prepaid_interest_buy = calc_hml_interest(hml_amount, rate, timeline.prepaid_days_buy)
    accrued_at_payoff = calc_hml_interest(hml_amount, rate, timeline.accrued_days_at_payoff)
    # The remainder, so the three slices always add back to the total exactly.
    monthly_paid = hml_interest - prepaid_interest_buy - accrued_at_payoff
    holding_costs = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi)
    utilities_until_rented = payload.monthly_utilities_until_rented * Decimal(payload.days_until_rented) / DAYS_PER_MONTH
    pre_refi_rental_income = payload.rent * Decimal(timeline.days_rented_before_refi) / DAYS_PER_MONTH
    return HmlAndHolding(
        hml_points, hml_per_diem, hml_interest, prepaid_interest_buy, monthly_paid, accrued_at_payoff,
        holding_costs, utilities_until_rented, pre_refi_rental_income,
    )
