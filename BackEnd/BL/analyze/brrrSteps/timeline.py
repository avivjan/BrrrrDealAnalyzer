"""BRRRR step: the dates and day counts of the deal, all derived from the buy closing date (mandatory).

Hard-money interest is paid in arrears on the 1st, so the days until the refi split three
ways: prepaid at the purchase closing (closing day through month end), paid monthly, and
accrued into the payoff. A month is paid monthly on the 1st after it only when that 1st falls
strictly before the refi; otherwise the payoff carries it (a refi on Jul 1 pays June inside the
payoff). The purchase month is never paid on the first 1st: it was prepaid at closing.

Every other monthly item before the refi is paid on real 1sts too, never prorated by days / 30.
A window "(A, B]" is after A, up to and including B:

* HOA and insurance paid monthly: the 1sts in (closing, refi].
* Rent collected (money in): the 1sts in (tenant occupied, refi].
* Utilities: the 1sts in (closing, min(tenant occupied, refi)], plus the next 1st for the last bill
  in arrears, only when it is on or before the refi. Utilities never run past the refi.
"""

from datetime import date, timedelta
from typing import NamedTuple

from BL.analyze.common.deal_math import days_in_month, days_through_month_end, first_of_month_dates, first_of_next_month, last_day_of_previous_month


class Timeline(NamedTuple):
    contract_date: date
    buy_closing_date: date
    refi_closing_date: date
    tenant_occupied_date: date
    rehab_completed_date: date
    # Hard-money interest: the days until the refi, split by when they are paid.
    hml_interest_days_prepaid_at_purchase_closing: int   # closing day through the end of that month
    hml_interest_days_paid_monthly: int                   # the months paid on the 1st after them, strictly before the refi
    hml_interest_days_accrued_into_refi_payoff: int       # the rest, inside the payoff
    hml_interest_monthly_payment_dates: tuple[date, ...]  # each 1st paying the month before it
    # DSCR-loan interest collected at the refi closing: refi day through the end of that month.
    dscr_interest_days_prepaid_at_refi_closing: int
    # The 1sts of the monthly items before the refi.
    first_of_month_dates_after_closing_through_refi: tuple[date, ...]   # HOA and insurance paid monthly
    utility_bill_dates_until_refi: tuple[date, ...]
    rent_collection_dates_before_refi: tuple[date, ...]


def timeline_step(payload) -> Timeline:
    buy_closing_date = payload.buy_closing_date
    days_until_refi = int(payload.days_until_refi)

    refi_closing_date = buy_closing_date + timedelta(days=days_until_refi)
    tenant_occupied_date = buy_closing_date + timedelta(days=int(payload.days_until_rented))
    rehab_completed_date = buy_closing_date + timedelta(days=int(payload.days_until_rehab_completed))

    first_of_month_dates_after_closing_through_refi = tuple(first_of_month_dates(buy_closing_date, refi_closing_date))
    # The first 1st after closing pays the purchase month, already prepaid at closing: no payment.
    hml_interest_monthly_payment_dates = tuple(payment_date for payment_date in first_of_month_dates_after_closing_through_refi[1:]
                                               if payment_date < refi_closing_date)
    hml_interest_days_prepaid_at_purchase_closing = min(days_through_month_end(buy_closing_date), days_until_refi)
    hml_interest_days_paid_monthly = sum(days_in_month(last_day_of_previous_month(payment_date)) for payment_date in hml_interest_monthly_payment_dates)
    hml_interest_days_accrued_into_refi_payoff = days_until_refi - hml_interest_days_prepaid_at_purchase_closing - hml_interest_days_paid_monthly

    utilities_stop_on = min(tenant_occupied_date, refi_closing_date)
    utility_bill_in_arrears_date = first_of_next_month(utilities_stop_on)
    utility_bill_dates_until_refi = tuple(first_of_month_dates(buy_closing_date, utilities_stop_on)) + (
        (utility_bill_in_arrears_date,) if utility_bill_in_arrears_date <= refi_closing_date else ())

    return Timeline(
        contract_date=payload.contract_date,
        buy_closing_date=buy_closing_date,
        refi_closing_date=refi_closing_date,
        tenant_occupied_date=tenant_occupied_date,
        rehab_completed_date=rehab_completed_date,
        hml_interest_days_prepaid_at_purchase_closing=hml_interest_days_prepaid_at_purchase_closing,
        hml_interest_days_paid_monthly=hml_interest_days_paid_monthly,
        hml_interest_days_accrued_into_refi_payoff=hml_interest_days_accrued_into_refi_payoff,
        hml_interest_monthly_payment_dates=hml_interest_monthly_payment_dates,
        dscr_interest_days_prepaid_at_refi_closing=days_through_month_end(refi_closing_date),
        first_of_month_dates_after_closing_through_refi=first_of_month_dates_after_closing_through_refi,
        utility_bill_dates_until_refi=utility_bill_dates_until_refi,
        rent_collection_dates_before_refi=tuple(first_of_month_dates(tenant_occupied_date, refi_closing_date)),
    )
