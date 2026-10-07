from typing import Optional

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import proposal_res


def list_events(db, caller: MemberLoanCaller, state: Optional[str]) -> MemberLoanOutcome:
    snapshot = load_member_loan_ledger_snapshot(db)
    events = [e for e in reversed(snapshot.events) if state is None or snapshot.state_of(e) == state]
    return MemberLoanOutcome([proposal_res(snapshot, e, caller) for e in events])
