"""Signing in the Software (Amendment No. 1, Section 1; tasks/todo/MemberLoanSigning.md).

Every change to the loan, and every sent statement, is a document both members
sign. A signature is three calls:

  1. start   `start_change_proposal_signing` / `start_reversal_proposal_signing`
             (the proposer: nothing is stored on the loan yet, only a draft PDF)
             or `start_document_signing` (the other member, or a statement).
             It pins the exact PDF in a signing request.
  2. passkey `begin_signing_passkey`: WebAuthn options whose challenge is
             derived from that PDF's SHA-256 (`member_loan_signing_ceremony.py`).
  3. finish  `complete_signing`: typed legal name, consent, drawn signature and
             the passkey assertion. In one transaction under the Member Loan
             write lock it writes the proposal (for a proposer), the document,
             the signature and the audit row; the other member's signature on
             a Loan Change Record also writes the `approved` decision. When every
             required member has acted, the signed copy is made in the same
             transaction, and delivered after commit.

A record whose printed figures no longer match what approving it would do
cannot be signed (S4); `expire_stale_member_loan_proposals` then expires it.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session as DbSession

from BL.memberLoan.common import member_loan_settings
from BL.memberLoan.common.member_loan_access import MemberLoanCaller, MemberLoanMember, MemberLoanMembers
from BL.memberLoan.common.member_loan_engine import REVERSAL
from BL.memberLoan.common.member_loan_hash_chain import GENESIS_HASH, compute_row_hash
from BL.memberLoan.common.member_loan_ledger_service import (
    PROPOSAL_STATE_PENDING,
    MemberLoanLedgerSnapshot,
    MemberLoanRequestRefused,
    append_member_loan_approval,
    append_member_loan_audit_entry,
    append_proposed_member_loan_event,
    append_proposed_member_loan_reversal,
    live_figures_still_match_the_proposal,
    live_preview_for,
    load_member_loan_ledger_snapshot,
    next_member_loan_proposal_sequence,
    preview_member_loan_proposal,
    preview_member_loan_reversal_proposal,
    statement_month_affected_by,
)
from BL.memberLoan.common.member_loan_signing_ceremony import (
    ELECTRONIC_SIGNATURE_CONSENT_TEXT,
    MemberLoanPasskeySigningOptions,
    begin_passkey_signing,
    decode_drawn_signature_png,
    drop_unused_passkey_challenge,
    finish_passkey_signing,
    refuse_unless_typed_name_matches,
)
from BL.memberLoan.common.member_loan_signing_documents import (
    DOCUMENT_KIND_LOAN_CHANGE,
    DOCUMENT_KIND_MONTHLY_STATEMENT,
    SIGNATURE_MEANING_OBJECTED,
    SIGNATURE_MEANING_SIGNED,
    build_loan_change_document_content,
    build_statement_signing_document_content,
    objection_statement_text,
    plain_change_name_with_legal_names,
    signer_entry,
)
from BL.memberLoan.common.member_loan_signing_pdf import (
    concatenate_pdfs,
    render_loan_change_record_pdf,
    render_signature_certificate_pdf,
    render_statement_signing_pdf,
)
from BL.memberLoan.common.member_loan_statement_document import format_long_date, format_money
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import (
    MemberLoanEvent,
    MemberLoanSignature,
    MemberLoanSignedCopy,
    MemberLoanSigningDocument,
    MemberLoanSigningRequest,
)
from ReqRes.common.member_loan_schemas import MemberLoanProposalCreateReq

SIGNING_PURPOSE_PROPOSE_CHANGE = "propose_change"
SIGNING_PURPOSE_PROPOSE_REVERSAL = "propose_reversal"
SIGNING_PURPOSE_SIGN_DOCUMENT = "sign_document"
SIGNING_REQUEST_LIFETIME = timedelta(minutes=30)
STATEMENT_RESPONSE_DAYS = 30
FIGURES_CHANGED_MESSAGE = (
    "Another change was approved since this record was prepared, so its figures are no longer right. "
    "Please review the new figures and sign again."
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# -- documents ---------------------------------------------------------------------


def _append_signing_document(db: DbSession, *, document_id: Optional[UUID] = None, **fields) -> MemberLoanSigningDocument:
    last = member_loan_crud.get_last_member_loan_signing_document(db)
    row = MemberLoanSigningDocument(
        id=document_id or uuid.uuid4(),
        document_sequence=(last.document_sequence + 1) if last else 1,
        created_at=member_loan_settings.utc_now(),
        previous_document_hash=last.document_hash if last else GENESIS_HASH,
        document_hash="",
        **fields,
    )
    row.document_hash = compute_row_hash(row, "document_hash")
    member_loan_crud.add_member_loan_row(db, row)
    return row


def create_statement_signing_document(
    db: DbSession,
    *,
    statement_document: dict,
    members: MemberLoanMembers,
    sent_line: str,
    signing_pdf: Optional[bytes] = None,
    document_id: Optional[UUID] = None,
) -> MemberLoanSigningDocument:
    """The statement both members are asked to sign. The caller holds the write lock and commits.

    `signing_pdf` is the PDF the statement e-mail attached, when there was one,
    so the document signed is byte for byte the one sent."""

    content = build_statement_signing_document_content(statement_document=statement_document, members=members, sent_line=sent_line)
    pdf = signing_pdf if signing_pdf is not None else render_statement_signing_pdf(content)
    document = _append_signing_document(
        db,
        document_id=document_id,
        document_kind=DOCUMENT_KIND_MONTHLY_STATEMENT,
        event_id=None,
        statement_month=date.fromisoformat(statement_document["statement_month"] + "-01"),
        title=content["title"],
        document_content=content,
        unsigned_pdf=pdf,
        unsigned_pdf_sha256=_sha256(pdf),
        required_signer_usernames=[members.lender.username, members.yarden.username],
    )
    append_member_loan_audit_entry(
        db, actor_user_id=None, actor_username="system", action="statement_signing_document_created",
        detail={"statement_month": statement_document["statement_month"], "document_id": str(document.id),
                "pdf_sha256": document.unsigned_pdf_sha256},
    )
    return document


def statement_signing_pdf_and_content(*, statement_document: dict, members: MemberLoanMembers, sent_line: str) -> tuple[dict, bytes]:
    content = build_statement_signing_document_content(statement_document=statement_document, members=members, sent_line=sent_line)
    return content, render_statement_signing_pdf(content)


@dataclass(frozen=True)
class MemberLoanDocumentSignatureState:
    signatures_by_username: dict[str, MemberLoanSignature]

    def has_acted(self, username: str) -> bool:
        return username in self.signatures_by_username


def signature_state_of(db: DbSession, document: MemberLoanSigningDocument) -> MemberLoanDocumentSignatureState:
    return MemberLoanDocumentSignatureState({s.signer_username: s for s in member_loan_crud.list_member_loan_signatures(db, document.id)})


def statement_response_deadline(db: DbSession, document: MemberLoanSigningDocument) -> Optional[date]:
    """The last day a member may still sign or object in the Software: 30 days after the statement was sent."""

    sends = [s for s in member_loan_crud.list_member_loan_statement_sends(db, document.statement_month) if not s.is_dry_run and s.status == "sent"]
    if not sends or sends[0].sent_at is None:
        return None
    if sends[0].objection_deadline is not None:
        return sends[0].objection_deadline
    sent_on = sends[0].sent_at.astimezone(member_loan_settings.LOAN_TIME_ZONE).date()
    return sent_on + timedelta(days=STATEMENT_RESPONSE_DAYS)


# -- step 1: start -------------------------------------------------------------------


def _new_signing_request(db: DbSession, caller: MemberLoanCaller, **fields) -> MemberLoanSigningRequest:
    now = member_loan_settings.utc_now()
    member_loan_crud.prune_expired_member_loan_signing_requests(db, now)
    row = MemberLoanSigningRequest(
        id=uuid.uuid4(),
        user_id=caller.member.user_id,
        username=caller.member.username,
        created_at=now,
        expires_at=now + SIGNING_REQUEST_LIFETIME,
        **fields,
    )
    member_loan_crud.add_member_loan_row(db, row)
    db.commit()
    return row


def _change_fields(request: MemberLoanProposalCreateReq) -> dict:
    return {
        "event_type": request.event_type,
        "effective_date": request.effective_date.isoformat(),
        "amount": None if request.amount is None else f"{Decimal(request.amount):.2f}",
        "interest_election_choice": request.interest_election_choice,
        "written_agreement_date": request.written_agreement_date.isoformat() if request.written_agreement_date else None,
        "written_agreement_description": " ".join((request.written_agreement_description or "").split()) or None,
        "payment_reference": " ".join((request.payment_reference or "").split()) or None,
        "note": " ".join((request.note or "").split()) or None,
    }


def start_change_proposal_signing(db: DbSession, caller: MemberLoanCaller, request: MemberLoanProposalCreateReq) -> MemberLoanSigningRequest:
    preview = preview_member_loan_proposal(db, request)
    content = build_loan_change_document_content(
        change=_change_fields(request),
        preview=preview.as_plain_dict(),
        record_number=next_member_loan_proposal_sequence(db),
        proposer=caller.member,
        members=caller.members,
        prepared_on=member_loan_settings.new_york_today(),
    )
    pdf = render_loan_change_record_pdf(content)
    proposer_entry = content["signers"][0]
    return _new_signing_request(
        db, caller,
        signing_purpose=SIGNING_PURPOSE_PROPOSE_CHANGE,
        proposal_draft=request.model_dump(mode="json"),
        draft_document_content=content,
        draft_pdf=pdf,
        document_sha256=_sha256(pdf),
        signature_meaning=SIGNATURE_MEANING_SIGNED,
        signer_role=proposer_entry["role"],
        signature_statement_text=proposer_entry["statement_text"],
    )


def start_reversal_proposal_signing(
    db: DbSession, caller: MemberLoanCaller, target_event_id: UUID, reason: str, note: Optional[str]
) -> MemberLoanSigningRequest:
    snapshot = load_member_loan_ledger_snapshot(db)
    target, preview = preview_member_loan_reversal_proposal(snapshot, target_event_id)
    cleaned_reason = " ".join(reason.split())
    change = {
        "event_type": REVERSAL,
        "effective_date": target.effective_date.isoformat(),
        "reverses_event_id": str(target.id),
        "reversed_event_type": target.event_type,
        "reversed_record_number": target.proposal_sequence,
        "reversed_change_summary": _reversed_change_summary(target, caller.members),
        "reversal_reason": cleaned_reason,
        "note": " ".join((note or "").split()) or None,
    }
    content = build_loan_change_document_content(
        change=change,
        preview=preview.as_plain_dict(),
        record_number=next_member_loan_proposal_sequence(db),
        proposer=caller.member,
        members=caller.members,
        prepared_on=member_loan_settings.new_york_today(),
    )
    pdf = render_loan_change_record_pdf(content)
    proposer_entry = content["signers"][0]
    return _new_signing_request(
        db, caller,
        signing_purpose=SIGNING_PURPOSE_PROPOSE_REVERSAL,
        proposal_draft={"reverses_event_id": str(target.id), "reason": cleaned_reason, "note": change["note"]},
        draft_document_content=content,
        draft_pdf=pdf,
        document_sha256=_sha256(pdf),
        signature_meaning=SIGNATURE_MEANING_SIGNED,
        signer_role=proposer_entry["role"],
        signature_statement_text=proposer_entry["statement_text"],
    )


def _reversed_change_summary(target: MemberLoanEvent, members: MemberLoanMembers) -> str:
    amount = f" of {format_money(Decimal(target.amount))}" if target.amount is not None else ""
    return f"{plain_change_name_with_legal_names(target.event_type, members)}{amount} on {format_long_date(target.effective_date)}"


def _refuse_unless_loan_change_can_be_countersigned(
    snapshot: MemberLoanLedgerSnapshot, document: MemberLoanSigningDocument, caller: MemberLoanCaller
) -> MemberLoanEvent:
    event = snapshot.events_by_id.get(document.event_id)
    if event is None:
        raise MemberLoanRequestRefused(404, "That change was not found.")
    state = snapshot.state_of(event)
    if state != PROPOSAL_STATE_PENDING:
        raise MemberLoanRequestRefused(409, f"This change is no longer waiting for a signature: it was {state}.", code="already_decided")
    if event.proposed_by_username == caller.member.username:
        raise MemberLoanRequestRefused(
            403, f"Only {caller.other_member.display_name} can sign to approve a change you proposed.", code="not_the_counterparty"
        )
    target = snapshot.events_by_id.get(event.reverses_event_id) if event.event_type == REVERSAL else None
    if statement_month_affected_by(target or event) in snapshot.locked_statement_months:
        raise MemberLoanRequestRefused(422, "The statement for that month was already sent, so this change can no longer be signed.",
                                       code="month_locked")
    if not live_figures_still_match_the_proposal(snapshot, event):
        raise MemberLoanRequestRefused(409, FIGURES_CHANGED_MESSAGE, code="figures_changed")
    return event


def start_document_signing(
    db: DbSession, caller: MemberLoanCaller, document_id: UUID, signature_meaning: str, objection_reason: Optional[str]
) -> MemberLoanSigningRequest:
    document = member_loan_crud.get_member_loan_signing_document(db, document_id)
    if document is None:
        raise MemberLoanRequestRefused(404, "That document was not found.")
    entry = signer_entry(document.document_content, caller.member.username)
    if entry is None or caller.member.username not in document.required_signer_usernames:
        raise MemberLoanRequestRefused(403, "You are not asked to sign this document.", code="not_a_signer")
    if document.document_kind == DOCUMENT_KIND_LOAN_CHANGE:
        # The proposer signed when proposing; this names the real reason they cannot sign again.
        _refuse_unless_loan_change_can_be_countersigned(load_member_loan_ledger_snapshot(db), document, caller)
    if signature_state_of(db, document).has_acted(caller.member.username):
        raise MemberLoanRequestRefused(409, "You already signed this document.", code="already_signed")
    reason = " ".join((objection_reason or "").split()) or None
    if document.document_kind == DOCUMENT_KIND_LOAN_CHANGE:
        if signature_meaning != SIGNATURE_MEANING_SIGNED:
            raise MemberLoanRequestRefused(422, "A change cannot be objected to: reject it instead.", code="objection_not_allowed")
        statement_text = entry["statement_text"]
    else:
        deadline = statement_response_deadline(db, document)
        if deadline is not None and member_loan_settings.new_york_today() > deadline:
            raise MemberLoanRequestRefused(
                422, "The 30 days to sign or object to this statement have passed; it is binding (Section 8.3).", code="response_period_over"
            )
        if signature_meaning == SIGNATURE_MEANING_OBJECTED:
            if reason is None or len(reason) < 3:
                raise MemberLoanRequestRefused(422, "Please write the reason for your objection.", code="objection_reason_required")
            statement_text = objection_statement_text(caller.member, document.document_content["month_label"], reason)
        else:
            reason = None
            statement_text = entry["statement_text"]
    return _new_signing_request(
        db, caller,
        signing_purpose=SIGNING_PURPOSE_SIGN_DOCUMENT,
        document_id=document.id,
        document_sha256=document.unsigned_pdf_sha256,
        signature_meaning=signature_meaning,
        objection_reason=reason,
        signer_role=entry["role"],
        signature_statement_text=statement_text,
    )


def _caller_signing_request(db: DbSession, caller: MemberLoanCaller, signing_request_id: UUID) -> MemberLoanSigningRequest:
    signing_request = member_loan_crud.get_member_loan_signing_request(db, signing_request_id)
    if signing_request is None or signing_request.username != caller.member.username:
        raise MemberLoanRequestRefused(404, "That signing was not found. Please start again.", code="signing_request_not_found")
    if signing_request.consumed_at is not None:
        raise MemberLoanRequestRefused(409, "This signing was already completed.", code="signing_request_used")
    if signing_request.expires_at < member_loan_settings.utc_now():
        raise MemberLoanRequestRefused(410, "This signing took too long and expired. Please start again.", code="signing_request_expired")
    return signing_request


def signing_request_pdf(db: DbSession, caller: MemberLoanCaller, signing_request_id: UUID) -> tuple[bytes, str]:
    signing_request = _caller_signing_request(db, caller, signing_request_id)
    if signing_request.draft_pdf is not None:
        return bytes(signing_request.draft_pdf), "loan-change-record-draft.pdf"
    document = member_loan_crud.get_member_loan_signing_document(db, signing_request.document_id)
    return bytes(document.unsigned_pdf), document_pdf_filename(document, signed=False)


def signing_request_content(db: DbSession, signing_request: MemberLoanSigningRequest) -> dict:
    if signing_request.draft_document_content is not None:
        return signing_request.draft_document_content
    return member_loan_crud.get_member_loan_signing_document(db, signing_request.document_id).document_content


# -- step 2: passkey -----------------------------------------------------------------


def begin_signing_passkey(db: DbSession, caller: MemberLoanCaller, signing_request_id: UUID) -> MemberLoanPasskeySigningOptions:
    signing_request = _caller_signing_request(db, caller, signing_request_id)
    drop_unused_passkey_challenge(db, signing_request.passkey_challenge_id)
    options = begin_passkey_signing(db, user_id=caller.member.user_id, document_sha256=signing_request.document_sha256)
    signing_request.passkey_challenge_id = options.challenge_id
    signing_request.passkey_challenge_nonce = options.challenge_nonce_hex
    db.commit()
    return options


# -- step 3: finish ------------------------------------------------------------------


@dataclass(frozen=True)
class MemberLoanSigningCompletion:
    document_id: UUID
    event_id: Optional[UUID]
    signed_copy_id: Optional[UUID]
    new_proposal_event_id: Optional[UUID] = None


def _append_signature(
    db: DbSession,
    caller: MemberLoanCaller,
    document: MemberLoanSigningDocument,
    signing_request: MemberLoanSigningRequest,
    *,
    typed_full_legal_name: str,
    drawn_signature_png: bytes,
    evidence,
) -> MemberLoanSignature:
    if document.unsigned_pdf_sha256 != signing_request.document_sha256:  # pragma: no cover -- a document never changes
        raise MemberLoanRequestRefused(409, "The document changed. Please start again.", code="document_changed")
    last = member_loan_crud.get_last_member_loan_signature(db)
    row = MemberLoanSignature(
        id=uuid.uuid4(),
        signature_sequence=(last.signature_sequence + 1) if last else 1,
        document_id=document.id,
        signer_user_id=caller.member.user_id,
        signer_username=caller.member.username,
        signer_role=signing_request.signer_role,
        signature_meaning=signing_request.signature_meaning,
        objection_reason=signing_request.objection_reason,
        typed_full_legal_name=" ".join(typed_full_legal_name.split()),
        signature_statement_text=signing_request.signature_statement_text,
        drawn_signature_png=drawn_signature_png,
        signed_document_sha256=document.unsigned_pdf_sha256,
        webauthn_credential_id=evidence.credential_id,
        webauthn_authenticator_data=evidence.authenticator_data,
        webauthn_client_data_json=evidence.client_data_json,
        webauthn_signature=evidence.signature,
        passkey_challenge_nonce=signing_request.passkey_challenge_nonce,
        request_ip=caller.request_ip,
        user_agent=caller.user_agent,
        device_id=caller.device_id,
        signed_at=member_loan_settings.utc_now(),
        previous_signature_hash=last.signature_hash if last else GENESIS_HASH,
        signature_hash="",
    )
    row.signature_hash = compute_row_hash(row, "signature_hash")
    member_loan_crud.add_member_loan_row(db, row)
    append_member_loan_audit_entry(
        db,
        actor_user_id=caller.member.user_id,
        actor_username=caller.member.username,
        action="document_objected" if row.signature_meaning == SIGNATURE_MEANING_OBJECTED else "document_signed",
        event_id=document.event_id,
        detail={"document_id": str(document.id), "document_kind": document.document_kind, "signature_sequence": row.signature_sequence,
                "signed_document_sha256": row.signed_document_sha256, "objection_reason": row.objection_reason},
        request_ip=caller.request_ip,
        user_agent=caller.user_agent,
    )
    return row


def _append_signed_copy_if_complete(db: DbSession, document: MemberLoanSigningDocument) -> Optional[MemberLoanSignedCopy]:
    signatures = member_loan_crud.list_member_loan_signatures(db, document.id)
    if {s.signer_username for s in signatures} != set(document.required_signer_usernames):
        return None
    completed_at = member_loan_settings.utc_now()
    certificate = render_signature_certificate_pdf(
        content=document.document_content, unsigned_pdf_sha256=document.unsigned_pdf_sha256, signatures=signatures, completed_at=completed_at,
    )
    signed_pdf = concatenate_pdfs([bytes(document.unsigned_pdf), certificate])
    last = member_loan_crud.get_last_member_loan_signed_copy(db)
    row = MemberLoanSignedCopy(
        id=uuid.uuid4(),
        signed_copy_sequence=(last.signed_copy_sequence + 1) if last else 1,
        document_id=document.id,
        signed_pdf=signed_pdf,
        signed_pdf_sha256=_sha256(signed_pdf),
        completed_at=completed_at,
        previous_signed_copy_hash=last.signed_copy_hash if last else GENESIS_HASH,
        signed_copy_hash="",
    )
    row.signed_copy_hash = compute_row_hash(row, "signed_copy_hash")
    member_loan_crud.add_member_loan_row(db, row)
    append_member_loan_audit_entry(
        db, actor_user_id=None, actor_username="system", action="document_fully_signed", event_id=document.event_id,
        detail={"document_id": str(document.id), "signed_pdf_sha256": row.signed_pdf_sha256},
    )
    return row


def complete_signing(
    db: DbSession,
    caller: MemberLoanCaller,
    signing_request_id: UUID,
    *,
    typed_full_legal_name: str,
    electronic_signature_consent_confirmed: bool,
    drawn_signature_png_base64: str,
    passkey_challenge_id: UUID,
    passkey_credential: dict[str, Any],
    http_request: Optional[Request],
) -> MemberLoanSigningCompletion:
    signing_request = _caller_signing_request(db, caller, signing_request_id)
    if not electronic_signature_consent_confirmed:
        raise MemberLoanRequestRefused(422, f"Please tick the box: {ELECTRONIC_SIGNATURE_CONSENT_TEXT}", code="consent_required")
    refuse_unless_typed_name_matches(typed_full_legal_name, caller.member.legal_name)
    drawn_signature_png = decode_drawn_signature_png(drawn_signature_png_base64)
    if signing_request.passkey_challenge_id != passkey_challenge_id or signing_request.passkey_challenge_nonce is None:
        raise MemberLoanRequestRefused(409, "Please confirm with your passkey again.", code="passkey_challenge_mismatch")
    evidence = finish_passkey_signing(
        db, challenge_id=passkey_challenge_id, credential=passkey_credential, request=http_request, signer_user_id=caller.member.user_id,
    )

    member_loan_crud.acquire_member_loan_write_lock(db)
    snapshot = load_member_loan_ledger_snapshot(db)
    new_proposal_event_id: Optional[UUID] = None
    if signing_request.signing_purpose in (SIGNING_PURPOSE_PROPOSE_CHANGE, SIGNING_PURPOSE_PROPOSE_REVERSAL):
        event = _record_signed_proposal(db, caller, snapshot, signing_request)
        new_proposal_event_id = event.id
        draft_pdf = bytes(signing_request.draft_pdf)
        document = _append_signing_document(
            db,
            document_kind=DOCUMENT_KIND_LOAN_CHANGE,
            event_id=event.id,
            statement_month=None,
            title=signing_request.draft_document_content["title"],
            document_content=signing_request.draft_document_content,
            unsigned_pdf=draft_pdf,
            unsigned_pdf_sha256=_sha256(draft_pdf),
            required_signer_usernames=[s["username"] for s in signing_request.draft_document_content["signers"]],
        )
    else:
        document = member_loan_crud.get_member_loan_signing_document(db, signing_request.document_id)
        if signature_state_of(db, document).has_acted(caller.member.username):
            raise MemberLoanRequestRefused(409, "You already signed this document.", code="already_signed")
        event = None
        if document.document_kind == DOCUMENT_KIND_LOAN_CHANGE:
            event = _refuse_unless_loan_change_can_be_countersigned(snapshot, document, caller)

    _append_signature(db, caller, document, signing_request, typed_full_legal_name=typed_full_legal_name,
                      drawn_signature_png=drawn_signature_png, evidence=evidence)
    if signing_request.signing_purpose == SIGNING_PURPOSE_SIGN_DOCUMENT and document.document_kind == DOCUMENT_KIND_LOAN_CHANGE:
        append_member_loan_approval(db, caller, event, live_preview_for(snapshot, event))
    signed_copy = _append_signed_copy_if_complete(db, document)
    signing_request.consumed_at = member_loan_settings.utc_now()
    db.commit()
    return MemberLoanSigningCompletion(
        document_id=document.id,
        event_id=document.event_id,
        signed_copy_id=signed_copy.id if signed_copy else None,
        new_proposal_event_id=new_proposal_event_id,
    )


def _record_signed_proposal(
    db: DbSession, caller: MemberLoanCaller, snapshot: MemberLoanLedgerSnapshot, signing_request: MemberLoanSigningRequest
) -> MemberLoanEvent:
    """Re-check the draft under the write lock: its record number and figures must still be the ones signed."""

    content = signing_request.draft_document_content
    if next_member_loan_proposal_sequence(db) != content["record_number"]:
        raise MemberLoanRequestRefused(409, "Another change was proposed meanwhile. Please review and sign again.", code="document_changed")
    if signing_request.signing_purpose == SIGNING_PURPOSE_PROPOSE_CHANGE:
        request = MemberLoanProposalCreateReq(**signing_request.proposal_draft)
        preview = preview_member_loan_proposal(db, request, snapshot)
        if preview.preview_fingerprint != content["preview_fingerprint"]:
            raise MemberLoanRequestRefused(409, FIGURES_CHANGED_MESSAGE, code="figures_changed")
        return append_proposed_member_loan_event(db, caller, request, snapshot)
    draft = signing_request.proposal_draft
    target, preview = preview_member_loan_reversal_proposal(snapshot, UUID(draft["reverses_event_id"]))
    if preview.preview_fingerprint != content["preview_fingerprint"]:
        raise MemberLoanRequestRefused(409, FIGURES_CHANGED_MESSAGE, code="figures_changed")
    return append_proposed_member_loan_reversal(db, caller, target, preview, draft["reason"], draft["note"])


# -- reading -------------------------------------------------------------------------


def document_pdf_filename(document: MemberLoanSigningDocument, *, signed: bool) -> str:
    suffix = "-signed" if signed else ""
    if document.document_kind == DOCUMENT_KIND_MONTHLY_STATEMENT:
        return f"member-loan-statement-{document.statement_month:%Y-%m}{suffix}.pdf"
    return f"loan-change-record-{document.document_content['record_number']}{suffix}.pdf"


def documents_waiting_for(db: DbSession, snapshot: MemberLoanLedgerSnapshot, member: MemberLoanMember) -> list[MemberLoanSigningDocument]:
    waiting = []
    today = member_loan_settings.new_york_today()
    for document in member_loan_crud.list_member_loan_signing_documents(db):
        if member.username not in document.required_signer_usernames or signature_state_of(db, document).has_acted(member.username):
            continue
        if document.document_kind == DOCUMENT_KIND_LOAN_CHANGE:
            event = snapshot.events_by_id.get(document.event_id)
            if event is None or snapshot.state_of(event) != PROPOSAL_STATE_PENDING:
                continue
        else:
            deadline = statement_response_deadline(db, document)
            if deadline is not None and today > deadline:
                continue
        waiting.append(document)
    return waiting
