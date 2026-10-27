"""Check every Member Loan hash chain, and that every signature still covers its document.

Beyond the chains: each document's PDF still hashes to the SHA-256 its
signatures covered, each signature's passkey assertion names the challenge
derived from that SHA-256 (`passkey_assertion_is_bound_to_document`), and each
signed copy's PDF still hashes to its recorded SHA-256."""

import hashlib

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_hash_chain import verify_hash_chain
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signing_ceremony import passkey_assertion_is_bound_to_document
from DAL.crud import member_loan as member_loan_crud
from ReqRes.common.member_loan_schemas import MemberLoanIntegrityRes


def _signing_problems(documents, signatures, signed_copies) -> list[str]:
    problems = []
    documents_by_id = {d.id: d for d in documents}
    for document in documents:
        if hashlib.sha256(bytes(document.unsigned_pdf)).hexdigest() != document.unsigned_pdf_sha256:
            problems.append(f"Signing document {document.document_sequence}: its PDF no longer matches the one signed.")
    for signature in signatures:
        document = documents_by_id.get(signature.document_id)
        if document is None or signature.signed_document_sha256 != document.unsigned_pdf_sha256:
            problems.append(f"Signature {signature.signature_sequence} does not cover its document's PDF.")
        elif not passkey_assertion_is_bound_to_document(
            client_data_json_base64url=signature.webauthn_client_data_json,
            document_sha256=signature.signed_document_sha256,
            nonce_hex=signature.passkey_challenge_nonce,
        ):
            problems.append(f"Signature {signature.signature_sequence}: its passkey assertion is not bound to the document.")
    for signed_copy in signed_copies:
        if hashlib.sha256(bytes(signed_copy.signed_pdf)).hexdigest() != signed_copy.signed_pdf_sha256:
            problems.append(f"Signed copy {signed_copy.signed_copy_sequence}: its PDF was changed.")
    return problems


def check_integrity(db, caller: MemberLoanCaller) -> MemberLoanOutcome:
    events = member_loan_crud.list_member_loan_events(db)
    decisions = member_loan_crud.list_member_loan_event_decisions(db)
    audit_entries = member_loan_crud.list_member_loan_audit_entries(db)
    documents = member_loan_crud.list_member_loan_signing_documents(db)
    signatures = member_loan_crud.list_member_loan_signatures(db)
    signed_copies = member_loan_crud.list_member_loan_signed_copies(db)
    problems = (
        verify_hash_chain(events, hash_column_name="event_hash", previous_hash_column_name="previous_event_hash", table_label="Proposal")
        + verify_hash_chain(decisions, hash_column_name="decision_hash", previous_hash_column_name="previous_decision_hash", table_label="Decision")
        + verify_hash_chain(audit_entries, hash_column_name="audit_hash", previous_hash_column_name="previous_audit_hash", table_label="Audit")
        + verify_hash_chain(documents, hash_column_name="document_hash", previous_hash_column_name="previous_document_hash",
                            table_label="Signing document")
        + verify_hash_chain(signatures, hash_column_name="signature_hash", previous_hash_column_name="previous_signature_hash",
                            table_label="Signature")
        + verify_hash_chain(signed_copies, hash_column_name="signed_copy_hash", previous_hash_column_name="previous_signed_copy_hash",
                            table_label="Signed copy")
        + _signing_problems(documents, signatures, signed_copies)
    )
    return MemberLoanOutcome(
        MemberLoanIntegrityRes(
            intact=not problems,
            problems=problems,
            proposals_checked=len(events),
            decisions_checked=len(decisions),
            audit_entries_checked=len(audit_entries),
            signing_documents_checked=len(documents),
            signatures_checked=len(signatures),
            signed_copies_checked=len(signed_copies),
        )
    )
