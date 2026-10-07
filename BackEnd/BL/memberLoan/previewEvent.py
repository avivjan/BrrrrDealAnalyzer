from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import preview_member_loan_proposal
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_views import preview_res
from ReqRes.common.member_loan_schemas import MemberLoanProposalCreateReq


def preview_event(db, caller: MemberLoanCaller, request: MemberLoanProposalCreateReq) -> MemberLoanOutcome:
    return MemberLoanOutcome(preview_res(preview_member_loan_proposal(db, request)))
