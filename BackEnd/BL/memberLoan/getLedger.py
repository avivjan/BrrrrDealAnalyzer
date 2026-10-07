from datetime import date

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot, member_loan_position_as_of
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import ledger_row_res
from ReqRes.common.member_loan_schemas import MemberLoanLedgerRes


def get_member_loan_ledger(db, caller: MemberLoanCaller, through_date: date) -> MemberLoanOutcome:
    snapshot = load_member_loan_ledger_snapshot(db)
    position = member_loan_position_as_of(snapshot, through_date)
    rows = [ledger_row_res(snapshot, row, caller.members) for row in position.ledger_rows]
    return MemberLoanOutcome(MemberLoanLedgerRes(through_date=through_date, rows=rows))
