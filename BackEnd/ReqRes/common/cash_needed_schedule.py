"""Response models of the dated Cash Needed schedule (Lowest-ARV scenario), part of `analyzeBRRRRes`.

Built from `BL/analyze/brrrSteps/cash_needed_schedule.py`. Each dated row maps 1:1 to a future
liquidity-timeline transaction (`frontend/src/types/liquidity.ts`: effective_date, description, a
signed amount). The rehab cushion is one of the rows: a hold you postpone until you mark it done.
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


class CashNeededScheduleMilestoneRes(BaseModel):
    """One key date of the deal, shown among the cash rows. A marker, not cash."""

    date: calendar_date = Field(..., description="The day of the milestone (ISO).")
    milestone_key: str = Field(..., description=(
        "contract_signed, purchase_closed, rehab_completed, tenant_moved_in, property_tax_bill_paid_on_november_30 or refi_closed."))
    description: str = Field(..., description="The milestone as shown, e.g. 'Purchase closing'.")


class CashNeededScheduleAtLowestArvRes(BaseModel):
    """When every dollar of Cash Needed moves, in the Lowest-ARV (conservative) scenario. No running balance and
    no peak: cash troughs are managed globally in the liquidity timeline."""

    dated_cash_rows: list[CashNeededScheduleRowRes] = Field(..., description=(
        "One row per individual cash item, in date order (then sequence_within_day), the rehab cushion included (a hold "
        "on the purchase closing date). Money in as late as reasonable, money out as early as reasonable; no money-out "
        "row falls after the refi closing."))
    deal_milestones: list[CashNeededScheduleMilestoneRes] = Field(default_factory=list, description=(
        "The deal's key dates in date order, shown among the cash rows (a milestone first on a shared day). Not cash: "
        "never part of Cash Needed or the liquidity import. The Nov 30 tax bill is one only inside the hold."))
