"""Every signing document (changes and statements), newest first, optionally only those waiting for the caller."""

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_service import documents_waiting_for
from BL.memberLoan.common.member_loan_views import signing_document_res
from DAL.crud import member_loan as member_loan_crud


def list_documents(db, caller: MemberLoanCaller, waiting_for_me: bool) -> MemberLoanOutcome:
    snapshot = load_member_loan_ledger_snapshot(db)
    documents = (
        documents_waiting_for(db, snapshot, caller.member) if waiting_for_me else member_loan_crud.list_member_loan_signing_documents(db)
    )
    ordered = sorted(documents, key=lambda d: d.document_sequence, reverse=True)
    return MemberLoanOutcome([signing_document_res(db, snapshot, d, caller) for d in ordered])
