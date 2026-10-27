"""Start signing a proposed change: render its Loan Change Record. Nothing is recorded on the loan yet."""

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_service import start_change_proposal_signing
from BL.memberLoan.common.member_loan_views import signing_request_res
from ReqRes.common.member_loan_schemas import MemberLoanProposalCreateReq


def start_change_signing(db, caller: MemberLoanCaller, request: MemberLoanProposalCreateReq) -> MemberLoanOutcome:
    signing_request = start_change_proposal_signing(db, caller, request)
    return MemberLoanOutcome(signing_request_res(db, signing_request, caller))
