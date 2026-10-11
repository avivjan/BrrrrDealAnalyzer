from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot, propose_member_loan_event
from BL.memberLoan.common.member_loan_notifications import NOTIFICATION_PROPOSED
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import proposal_res
from ReqRes.common.member_loan_schemas import MemberLoanProposalCreateReq


def propose_event(db, caller: MemberLoanCaller, request: MemberLoanProposalCreateReq) -> MemberLoanOutcome:
    result = propose_member_loan_event(db, caller, request)
    snapshot = load_member_loan_ledger_snapshot(db)
    event = snapshot.events_by_id[result.event_id]
    return MemberLoanOutcome(proposal_res(snapshot, event, caller), [(NOTIFICATION_PROPOSED, event.id)])
