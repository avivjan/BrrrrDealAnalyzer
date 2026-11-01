"""The Cash Needed schedule (Lowest ARV) as the reports show it: the same lines in the HTML report and the PDF.

Reads `cash_needed_schedule_at_lowest_arv` off the calculator result (a `model_dump()`, so Decimals and dates,
or the JSON form of it, so strings) and formats every value like the website's popup does: the dated rows,
the rehab cushion among them (a hold on the purchase closing date).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple, Optional

CASH_NEEDED_RESULT_KEY = "total_cash_needed_for_deal"
CASH_NEEDED_SCHEDULE_TITLE = "Cash schedule (Lowest ARV)"


class CashNeededScheduleReportRow(NamedTuple):
    date_text: str
    description: str
    signed_amount_text: str
    is_money_in: bool


class CashNeededScheduleReport(NamedTuple):
    dated_rows: list[CashNeededScheduleReportRow]


def _as_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _money_text(amount) -> str:
    # Imported here: `deal_pdf` imports this module to draw the same block.
    from BL.reports.common.deal_pdf import format_value_like_calculation_popup
    return format_value_like_calculation_popup("money", float(Decimal(str(amount))))


def _date_text(value) -> str:
    day = _as_date(value)
    return f"{day:%b} {day.day}, {day.year}"


def resolve_cash_needed_schedule_report(result: dict) -> Optional[CashNeededScheduleReport]:
    """The schedule's report lines, or None when the result carries no schedule (a FLIP, an older result)."""
    schedule = result.get("cash_needed_schedule_at_lowest_arv")
    if not schedule:
        return None
    return CashNeededScheduleReport(dated_rows=[
        CashNeededScheduleReportRow(
            date_text=_date_text(row["date"]),
            description=str(row["description"]),
            signed_amount_text=_money_text(row["signed_amount_dollars"]),
            is_money_in=Decimal(str(row["signed_amount_dollars"])) > 0,
        )
        for row in schedule["dated_cash_rows"]
    ])
