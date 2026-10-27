"""One signing document: its details, its PDF as signed, and its signed copy once complete."""

from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import MemberLoanRequestRefused, load_member_loan_ledger_snapshot
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_service import document_pdf_filename
from BL.memberLoan.common.member_loan_views import signing_document_res
from DAL.crud import member_loan as member_loan_crud


def _document_or_refuse(db, document_id: UUID):
    document = member_loan_crud.get_member_loan_signing_document(db, document_id)
    if document is None:
        raise MemberLoanRequestRefused(404, "That document was not found.")
    return document


def get_document(db, caller: MemberLoanCaller, document_id: UUID) -> MemberLoanOutcome:
    document = _document_or_refuse(db, document_id)
    return MemberLoanOutcome(signing_document_res(db, load_member_loan_ledger_snapshot(db), document, caller))


def get_document_pdf(db, caller: MemberLoanCaller, document_id: UUID) -> tuple[bytes, str]:
    document = _document_or_refuse(db, document_id)
    return bytes(document.unsigned_pdf), document_pdf_filename(document, signed=False)


def get_signed_copy_pdf(db, caller: MemberLoanCaller, document_id: UUID) -> tuple[bytes, str]:
    document = _document_or_refuse(db, document_id)
    signed_copy = member_loan_crud.get_member_loan_signed_copy_for_document(db, document.id)
    if signed_copy is None:
        raise MemberLoanRequestRefused(404, "This document is not signed by everyone yet.", code="not_signed_yet")
    return bytes(signed_copy.signed_pdf), document_pdf_filename(document, signed=True)
