"""BRRRR step: the dates and day counts of the deal, all derived from the buy closing date (mandatory).

Hard-money interest is paid in arrears on the 1st, so the days until the refi split three
ways: prepaid at the purchase closing (closing day through month end), paid monthly, and
accrued from the 1st of the refi month through the day before the payoff.
"""

from datetime import date, timedelta
from typing import NamedTuple

from BL.analyze.common.deal_math import days_through_month_end


class Timeline(NamedTuple):
    contract_date: date
    buy_closing_date: date
    refi_closing_date: date
    tenant_occupied_date: date
    rehab_completed_date: date
    # Hard-money interest: the days until the refi, split by when they are paid.
    hml_interest_days_prepaid_at_purchase_closing: int   # closing day through the end of that month
    hml_interest_days_paid_monthly: int                   # paid on the 1st of each month in between
    hml_interest_days_accrued_into_refi_payoff: int       # 1st of the refi month through the day before the payoff
    # DSCR-loan interest collected at the refi closing: refi day through the end of that month.
    dscr_interest_days_prepaid_at_refi_closing: int
    # Days with a tenant in place before the refi (the rent that offsets holding costs).
    days_tenant_occupied_before_refi: int


def timeline_step(payload) -> Timeline:
    buy_closing_date = payload.buy_closing_date
    days_until_refi = int(payload.days_until_refi)
    days_until_rented = int(payload.days_until_rented)
    days_tenant_occupied_before_refi = max(0, days_until_refi - days_until_rented)

    refi_closing_date = buy_closing_date + timedelta(days=days_until_refi)
    tenant_occupied_date = buy_closing_date + timedelta(days=days_until_rented)
    rehab_completed_date = buy_closing_date + timedelta(days=int(payload.days_until_rehab_completed))

    hml_interest_days_prepaid_at_purchase_closing = min(days_through_month_end(buy_closing_date), days_until_refi)
    refi_closes_in_purchase_month = (refi_closing_date.year, refi_closing_date.month) == (buy_closing_date.year, buy_closing_date.month)
    hml_interest_days_accrued_into_refi_payoff = 0 if refi_closes_in_purchase_month else refi_closing_date.day - 1
    hml_interest_days_paid_monthly = days_until_refi - hml_interest_days_prepaid_at_purchase_closing - hml_interest_days_accrued_into_refi_payoff

    return Timeline(
        contract_date=payload.contract_date,
        buy_closing_date=buy_closing_date,
        refi_closing_date=refi_closing_date,
        tenant_occupied_date=tenant_occupied_date,
        rehab_completed_date=rehab_completed_date,
        hml_interest_days_prepaid_at_purchase_closing=hml_interest_days_prepaid_at_purchase_closing,
        hml_interest_days_paid_monthly=hml_interest_days_paid_monthly,
        hml_interest_days_accrued_into_refi_payoff=hml_interest_days_accrued_into_refi_payoff,
        dscr_interest_days_prepaid_at_refi_closing=days_through_month_end(refi_closing_date),
        days_tenant_occupied_before_refi=days_tenant_occupied_before_refi,
    )
