"""The ledger as CSV. Cells that a spreadsheet would run as a formula are neutralised."""

import csv
import io
from datetime import date

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot, member_loan_position_as_of
from BL.memberLoan.common.member_loan_views import ledger_row_res

CSV_COLUMNS = (
    "date", "what happened", "amount", "proposed by", "approved by", "principal", "capitalized interest",
    "total balance", "accrued interest", "interest payable in cash", "amount owed", "credited to lender capital",
)
FORMULA_TRIGGER_CHARACTERS = ("=", "+", "-", "@", "\t", "\r")


def neutralise_spreadsheet_formula(cell: str) -> str:
    """A text cell starting like a formula gets a leading apostrophe (CSV injection).
    Numbers are written as plain digits, so a negative amount stays a number."""
    return f"'{cell}" if cell.startswith(FORMULA_TRIGGER_CHARACTERS) else cell


def export_ledger_csv(db, caller: MemberLoanCaller, through_date: date) -> tuple[str, str]:
    snapshot = load_member_loan_ledger_snapshot(db)
    position = member_loan_position_as_of(snapshot, through_date)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for row in position.ledger_rows:
        res = ledger_row_res(snapshot, row, caller.members)
        buckets = res.buckets_after
        writer.writerow([
            res.row_date.isoformat(),
            neutralise_spreadsheet_formula(res.plain_description),
            res.amount or "",
            neutralise_spreadsheet_formula(res.proposed_by_display_name or ""),
            neutralise_spreadsheet_formula(res.approved_by_display_name or ""),
            buckets.original_principal,
            buckets.capitalized_interest,
            buckets.total_balance,
            buckets.accrued_interest,
            buckets.interest_payable,
            buckets.amount_owed,
            buckets.lender_capital_credited,
        ])
    return output.getvalue(), f"member-loan-ledger-through-{through_date.isoformat()}.csv"
