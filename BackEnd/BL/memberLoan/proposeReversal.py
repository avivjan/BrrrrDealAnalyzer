from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot, propose_member_loan_reversal
from BL.memberLoan.common.member_loan_notifications import NOTIFICATION_PROPOSED
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import proposal_res
from ReqRes.common.member_loan_schemas import MemberLoanReversalProposalReq


def propose_reversal(db, caller: MemberLoanCaller, target_event_id: UUID, request: MemberLoanReversalProposalReq) -> MemberLoanOutcome:
    result = propose_member_loan_reversal(db, caller, target_event_id, request.reason, request.note)
    snapshot = load_member_loan_ledger_snapshot(db)
    event = snapshot.events_by_id[result.event_id]
    return MemberLoanOutcome(proposal_res(snapshot, event, caller), [(NOTIFICATION_PROPOSED, event.id)])
