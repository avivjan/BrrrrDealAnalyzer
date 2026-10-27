"""Start signing a reversal of an approved change: render its Loan Change Record."""

from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_service import start_reversal_proposal_signing
from BL.memberLoan.common.member_loan_views import signing_request_res
from ReqRes.common.member_loan_schemas import MemberLoanReversalProposalReq


def start_reversal_signing(db, caller: MemberLoanCaller, target_event_id: UUID, request: MemberLoanReversalProposalReq) -> MemberLoanOutcome:
    signing_request = start_reversal_proposal_signing(db, caller, target_event_id, request.reason, request.note)
    return MemberLoanOutcome(signing_request_res(db, signing_request, caller))
