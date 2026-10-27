"""Finish a signing: name, consent, drawn signature and passkey. Records the signature (and, as the
case may be, the proposal or its approval); e-mails and the signed copy's delivery follow the commit."""

from uuid import UUID

from fastapi import Request

from BL.memberLoan.common.member_loan_access import MemberLoanCaller
from BL.memberLoan.common.member_loan_ledger_service import load_member_loan_ledger_snapshot
from BL.memberLoan.common.member_loan_notifications import NOTIFICATION_PROPOSED
from BL.memberLoan.common.member_loan_outcome import MemberLoanOutcome
from BL.memberLoan.common.member_loan_signed_copy_delivery import deliver_signed_copy_after_commit
from BL.memberLoan.common.member_loan_signing_service import complete_signing
from BL.memberLoan.common.member_loan_views import proposal_res, signing_document_res
from DAL.crud import member_loan as member_loan_crud
from ReqRes.common.member_loan_schemas import MemberLoanSignatureSubmitReq, MemberLoanSigningCompletionRes


def complete_document_signing(
    db, caller: MemberLoanCaller, signing_request_id: UUID, request: MemberLoanSignatureSubmitReq, http_request: Request
) -> MemberLoanOutcome:
    completion = complete_signing(
        db,
        caller,
        signing_request_id,
        typed_full_legal_name=request.typed_full_legal_name,
        electronic_signature_consent_confirmed=request.electronic_signature_consent_confirmed,
        drawn_signature_png_base64=request.drawn_signature_png_base64,
        passkey_challenge_id=request.passkey_challenge_id,
        passkey_credential=request.passkey_credential,
        http_request=http_request,
    )
    snapshot = load_member_loan_ledger_snapshot(db)
    document = member_loan_crud.get_member_loan_signing_document(db, completion.document_id)
    event = snapshot.events_by_id.get(completion.event_id) if completion.event_id else None
    # An approval needs no e-mail of its own: the signed copy goes to all three addresses.
    notifications = [(NOTIFICATION_PROPOSED, completion.new_proposal_event_id)] if completion.new_proposal_event_id else []
    jobs = [(deliver_signed_copy_after_commit, completion.signed_copy_id)] if completion.signed_copy_id else []
    return MemberLoanOutcome(
        MemberLoanSigningCompletionRes(
            document=signing_document_res(db, snapshot, document, caller),
            proposal=proposal_res(snapshot, event, caller) if event is not None else None,
        ),
        notifications,
        jobs,
    )
