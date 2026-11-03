"""The Cash Needed schedule (Lowest ARV) as the reports show it: the same lines in the HTML report and the PDF.

Reads `cash_needed_schedule_at_lowest_arv` off the calculator result (a `model_dump()`, so Decimals and dates,
or the JSON form of it, so strings) and formats every value like the website's popup does: the dated rows,
the rehab cushion among them (a hold on the purchase closing date), with the deal's key dates (contract,
closing, rehab completed, tenant, the Nov 30 tax bill inside the hold, refi) between them: each a marker
listed first on its day, never cash.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple, Optional, Union

CASH_NEEDED_RESULT_KEY = "total_cash_needed_for_deal"
CASH_NEEDED_SCHEDULE_TITLE = "Cash schedule (Lowest ARV)"


class CashNeededScheduleReportRow(NamedTuple):
    date_text: str
    description: str
    signed_amount_text: str
    is_money_in: bool


class CashNeededScheduleReportMilestoneRow(NamedTuple):
    date_text: str
    description: str


class CashNeededScheduleReport(NamedTuple):
    dated_rows: list[CashNeededScheduleReportRow]
    # The cash rows and the key dates merged by date, a key date first on a shared day.
    lines_in_date_order: list[Union[CashNeededScheduleReportRow, CashNeededScheduleReportMilestoneRow]]


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
    dated_rows_with_dates = [
        (_as_date(row["date"]), CashNeededScheduleReportRow(
            date_text=_date_text(row["date"]),
            description=str(row["description"]),
            signed_amount_text=_money_text(row["signed_amount_dollars"]),
            is_money_in=Decimal(str(row["signed_amount_dollars"])) > 0,
        ))
        for row in schedule["dated_cash_rows"]
    ]
    milestones_with_dates = [
        (_as_date(milestone["date"]), CashNeededScheduleReportMilestoneRow(
            date_text=_date_text(milestone["date"]), description=str(milestone["description"])))
        for milestone in schedule.get("deal_milestones") or []
    ]
    # A stable sort on (date, cash row after key date) keeps each list's own order within a day.
    merged = sorted(
        [(line_date, 0, line) for line_date, line in milestones_with_dates] + [(line_date, 1, line) for line_date, line in dated_rows_with_dates],
        key=lambda dated_line: (dated_line[0], dated_line[1]),
    )
    return CashNeededScheduleReport(
        dated_rows=[row for _, row in dated_rows_with_dates],
        lines_in_date_order=[line for _, _, line in merged],
    )
