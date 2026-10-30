"""The Cash Needed schedule (Lowest ARV) as the reports show it: the same lines in the HTML report and the PDF.

Reads `cash_needed_schedule_at_lowest_arv` off the calculator result (a `model_dump()`, so Decimals and dates,
or the JSON form of it, so strings) and formats every value like the website's popup does. Three blocks:
the dated rows, what must stay in the account, and the summary (dated rows total + cushion = Cash Needed).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple, Optional

CASH_NEEDED_RESULT_KEY = "total_cash_needed_for_deal"
CASH_NEEDED_SCHEDULE_TITLE = "Cash schedule (Lowest ARV)"
CASH_THAT_MUST_STAY_IN_ACCOUNT_TITLE = "Must stay in the account (not spent)"


class CashNeededScheduleReportRow(NamedTuple):
    date_text: str
    description: str
    signed_amount_text: str
    is_money_in: bool


class CashThatMustStayInAccountReportRow(NamedTuple):
    description: str
    amount_text: str
    window_text: str


class CashNeededScheduleReport(NamedTuple):
    dated_rows: list[CashNeededScheduleReportRow]
    cash_that_must_stay_in_account: list[CashThatMustStayInAccountReportRow]
    summary_lines: list[tuple[str, str]]   # (label, value): dated rows total, + cushion, = Total Cash Needed


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
    dated_rows = [
        CashNeededScheduleReportRow(
            date_text=_date_text(row["date"]),
            description=str(row["description"]),
            signed_amount_text=_money_text(row["signed_amount_dollars"]),
            is_money_in=Decimal(str(row["signed_amount_dollars"])) > 0,
        )
        for row in schedule["dated_cash_rows"]
    ]
    held_rows = [
        CashThatMustStayInAccountReportRow(
            description=str(held["description"]),
            amount_text=_money_text(held["amount_dollars"]),
            window_text=f"{_date_text(held['reserve_starts_on_date'])} → {_date_text(held['reserve_ends_on_date'])}",
        )
        for held in schedule["cash_that_must_stay_in_account"]
    ]
    summary_lines = [
        ("Dated rows total (net out)", _money_text(schedule["dated_cash_rows_net_outflow_dollars"])),
        ("+ Rehab cushion (must stay in the account)", _money_text(schedule["cash_that_must_stay_in_account_total_dollars"])),
        ("= Total Cash Needed", _money_text(schedule["total_cash_needed_dollars"])),
    ]
    return CashNeededScheduleReport(dated_rows, held_rows, summary_lines)
