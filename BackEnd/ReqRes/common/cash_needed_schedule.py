"""Response models of the dated Cash Needed schedule (Lowest-ARV scenario), part of `analyzeBRRRRes`.

Built from `BL/analyze/brrrSteps/cash_needed_schedule.py`. Each dated row maps 1:1 to a future
liquidity-timeline transaction (`frontend/src/types/liquidity.ts`: effective_date, description, a
signed amount); the "must stay in the account" entries map to a dated raise of its reserve line.
Amounts are exact Decimals in whole cents (a JSON string such as "-5000.00"), never thousands.
"""

from datetime import date as calendar_date
from decimal import Decimal

from pydantic import BaseModel, Field


class CashNeededScheduleRowRes(BaseModel):
    """One individual cash item of Cash Needed, on the day it moves. Rows are never grouped by date."""

    date: calendar_date = Field(..., description="The day the money moves (ISO).")
    sequence_within_day: int = Field(..., description=(
        "The order of the rows that share this date: 0, 1, 2, ... Money out comes before money in on the same day."))
    description: str = Field(..., description="What the cash item is, e.g. 'HML interest for May 2026'.")
    signed_amount_dollars: Decimal = Field(..., description=(
        "Exact dollars in whole cents (not thousands). Positive = money comes in, negative = money goes out."))
    item_key: str = Field(..., description=(
        "Stable machine key of the item type, e.g. 'hml_interest_paid_monthly' or 'utilities' (shared by the rows of "
        "a monthly item); (item_key, date) is unique."))


class CashThatMustStayInAccountRes(BaseModel):
    """Money that is not spent but must stay in the account for a window: a reserve, never a dated row."""

    item_key: str = Field(..., description="Stable machine key, e.g. 'rehab_cushion'.")
    description: str = Field(..., description="What the money is held for.")
    amount_dollars: Decimal = Field(..., description="The amount held, in exact dollars.")
    reserve_starts_on_date: calendar_date = Field(..., description="The money must be in the account from this day (ISO)...")
    reserve_ends_on_date: calendar_date = Field(..., description="...through this day, when it is released (ISO).")


class CashNeededScheduleAtLowestArvRes(BaseModel):
    """When every dollar of Cash Needed moves, in the Lowest-ARV (conservative) scenario.

    dated_cash_rows_net_outflow_dollars + cash_that_must_stay_in_account_total_dollars = total_cash_needed_dollars
    (= total_cash_needed_for_deal), exactly. No running balance and no peak: cash troughs are managed globally
    in the liquidity timeline.
    """

    dated_cash_rows: list[CashNeededScheduleRowRes] = Field(..., description=(
        "One row per individual cash item, in date order (then sequence_within_day). Money in as late as reasonable, "
        "money out as early as reasonable; no money-out row falls after the refi closing."))
    cash_that_must_stay_in_account: list[CashThatMustStayInAccountRes] = Field(..., description=(
        "Money held, not spent: the rehab cushion, from the purchase closing to the rehab completion."))
    dated_cash_rows_net_outflow_dollars: Decimal = Field(..., description="Minus the sum of the signed dated rows, in dollars.")
    cash_that_must_stay_in_account_total_dollars: Decimal = Field(..., description="The sum of what must stay in the account, in dollars.")
    total_cash_needed_dollars: Decimal = Field(..., description=(
        "dated_cash_rows_net_outflow_dollars + cash_that_must_stay_in_account_total_dollars: equals total_cash_needed_for_deal."))
