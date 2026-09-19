"""BRRRR step: the dates and day counts of the deal, all derived from the buy closing date.

Without a buy closing date nothing date-driven is computed: the interest split collapses to
"all of it paid monthly", the prepaid windows are 0 and the dates are None. That is what
lets a deal without dates re-analyze exactly as the date-free engine did.

Hard-money interest is paid in arrears on the 1st, so the days until the refi split three
ways: prepaid at the purchase closing (closing day through month end), paid monthly, and
accrued from the 1st of the refi month through the day before the payoff.
"""

from datetime import date, timedelta
from typing import NamedTuple, Optional

from BL.analyze.common.deal_math import days_through_month_end


class Timeline(NamedTuple):
    buy_closing_date: Optional[date]
    refi_closing_date: Optional[date]
    tenant_occupied_date: Optional[date]
    prepaid_days_buy: int          # HML interest collected at the buy closing
    monthly_interest_days: int     # HML interest paid on the 1st of each month
    accrued_days_at_payoff: int    # HML interest inside the payoff at the refi
    prepaid_days_refi: int         # DSCR interest collected at the refi closing
    days_rented_before_refi: int   # tenant in place before the refi


def timeline_step(payload) -> Timeline:
    buy = payload.buy_closing_date
    days_until_refi = int(payload.days_until_refi)
    days_until_rented = int(payload.days_until_rented)
    days_rented = max(0, days_until_refi - days_until_rented)
    if buy is None:
        return Timeline(None, None, None, 0, days_until_refi, 0, 0, days_rented)
    refi = buy + timedelta(days=days_until_refi)
    tenant = buy + timedelta(days=days_until_rented)
    prepaid_buy = min(days_through_month_end(buy), days_until_refi)
    same_month = (refi.year, refi.month) == (buy.year, buy.month)
    accrued = 0 if same_month else refi.day - 1
    monthly = days_until_refi - prepaid_buy - accrued
    return Timeline(buy, refi, tenant, prepaid_buy, monthly, accrued, days_through_month_end(refi), days_rented)
