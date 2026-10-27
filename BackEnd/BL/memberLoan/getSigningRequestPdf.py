"""The PDF a signing in progress will sign (a draft Loan Change Record, or the document), for the signer only."""

from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_signing_service import signing_request_pdf


def get_signing_request_pdf(db, caller: MemberLoanCaller, signing_request_id: UUID) -> tuple[bytes, str]:
    return signing_request_pdf(db, caller, signing_request_id)
