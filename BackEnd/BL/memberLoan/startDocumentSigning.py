"""Start signing (or, for a statement, objecting to) an existing document."""

from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_service import start_document_signing
from BL.memberLoan.common.member_loan_views import signing_request_res
from ReqRes.common.member_loan_schemas import MemberLoanDocumentSigningStartReq


def start_signing_document(db, caller: MemberLoanCaller, document_id: UUID, request: MemberLoanDocumentSigningStartReq) -> MemberLoanOutcome:
    signing_request = start_document_signing(db, caller, document_id, request.signature_meaning, request.objection_reason)
    return MemberLoanOutcome(signing_request_res(db, signing_request, caller))
