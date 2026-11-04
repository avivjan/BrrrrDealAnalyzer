"""BRRRR step: hard-money points and interest (with its three-way split), and the holding-period
costs and income before the refi: HOA, utilities and rent, each a whole monthly amount on every real
1st of its window (`timeline.py`), never prorated. Taxes and insurance are not here: they are paid as
the bills and deposits they really are (`property_tax_bucket.py`, `insurance.py`)."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import calc_hml_interest, calc_hml_monthly_interest_payment


class HmlAndHoldingCosts(NamedTuple):
    hml_points: Decimal
    hml_per_diem: Decimal
    hml_interest: Decimal                 # total until the refi: prepaid + paid monthly + accrued into the payoff
    prepaid_interest_buy: Decimal         # collected at the buy closing (per diem, the rest of the purchase month)
    hml_interest_monthly_payment: Decimal # one full month: amount x rate / 12 (1% at 12%), whatever the month's length
    hml_interest_paid_monthly: Decimal    # paid on the 1st of each month: the monthly payment x the payment 1sts
    hml_interest_accrued_into_refi_payoff: Decimal
    hoa_dues_until_refi: Decimal          # HOA x the 1sts in (closing, refi]
    utilities_until_rented: Decimal       # utilities x the utility bill 1sts until the refi
    pre_refi_rental_income: Decimal       # rent x the 1sts in (tenant occupied, refi]


def hml_and_holding_costs_step(payload, hml_amount, timeline) -> HmlAndHoldingCosts:
    hml_annual_interest_rate_percent = payload.HML_interest_rate
    hml_points = payload.HML_points / Decimal("100.0") * hml_amount
    hml_per_diem = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, 1)
    # The partial months are per diem on their real days; every full month in between is rate / 12.
    prepaid_interest_buy = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, timeline.hml_interest_days_prepaid_at_purchase_closing)
    hml_interest_accrued_into_refi_payoff = calc_hml_interest(hml_amount, hml_annual_interest_rate_percent, timeline.hml_interest_days_accrued_into_refi_payoff)
    hml_interest_monthly_payment = calc_hml_monthly_interest_payment(hml_amount, hml_annual_interest_rate_percent)
    hml_interest_paid_monthly = hml_interest_monthly_payment * len(timeline.hml_interest_monthly_payment_dates)
    hml_interest = prepaid_interest_buy + hml_interest_paid_monthly + hml_interest_accrued_into_refi_payoff
    hoa_dues_until_refi = payload.montly_hoa * len(timeline.first_of_month_dates_after_closing_through_refi)
    utilities_until_rented = payload.monthly_utilities_until_rented * len(timeline.utility_bill_dates_until_refi)
    pre_refi_rental_income = payload.rent * len(timeline.rent_collection_dates_before_refi)
    return HmlAndHoldingCosts(
        hml_points=hml_points,
        hml_per_diem=hml_per_diem,
        hml_interest=hml_interest,
        prepaid_interest_buy=prepaid_interest_buy,
        hml_interest_monthly_payment=hml_interest_monthly_payment,
        hml_interest_paid_monthly=hml_interest_paid_monthly,
        hml_interest_accrued_into_refi_payoff=hml_interest_accrued_into_refi_payoff,
        hoa_dues_until_refi=hoa_dues_until_refi,
        utilities_until_rented=utilities_until_rented,
        pre_refi_rental_income=pre_refi_rental_income,
    )
