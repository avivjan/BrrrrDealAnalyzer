from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import MemberLoanRequestRefused, load_member_loan_ledger_snapshot
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import proposal_res


def get_event(db, caller: MemberLoanCaller, event_id: UUID) -> MemberLoanOutcome:
    snapshot = load_member_loan_ledger_snapshot(db)
    event = snapshot.events_by_id.get(event_id)
    if event is None:
        raise MemberLoanRequestRefused(404, "That change was not found.")
    return MemberLoanOutcome(proposal_res(snapshot, event, caller))
