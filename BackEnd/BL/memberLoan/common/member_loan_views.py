"""Turn the ledger into the API's response models, in plain words."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from BL.memberLoan.common.member_loan_access import MemberLoanCaller, MemberLoanMembers
from BL.memberLoan.common.member_loan_engine import (
    INTEREST_ELECTION_CASH,
    LEDGER_ROW_KIND_INTEREST_DATE,
    LEDGER_ROW_KIND_LOAN_START,
    REVERSAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
    MemberLoanBuckets,
    MemberLoanEventPreview,
    MemberLoanEventRejected,
    MemberLoanLedgerRow,
    first_day_of_previous_month,
)
from BL.memberLoan.common.member_loan_ledger_service import (
    PROPOSAL_STATE_PENDING,
    MemberLoanLedgerSnapshot,
    live_preview_for,
    plain_event_name,
    reversed_event_summary,
    statement_month_affected_by,
)
from BL.memberLoan.common import member_loan_settings
from BL.memberLoan.common.member_loan_signing_ceremony import ELECTRONIC_SIGNATURE_CONSENT_TEXT
from BL.memberLoan.common.member_loan_signing_documents import DOCUMENT_KIND_MONTHLY_STATEMENT
from BL.memberLoan.common.member_loan_signing_service import signature_state_of, signing_request_content, statement_response_deadline
from BL.memberLoan.common.member_loan_statement_document import format_money
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanEvent, MemberLoanSigningDocument, MemberLoanSigningRequest
from ReqRes.common.member_loan_schemas import (
    MemberLoanAllocationRes,
    MemberLoanBucketsRes,
    MemberLoanDocumentSignerRes,
    MemberLoanLedgerRowRes,
    MemberLoanPreviewRes,
    MemberLoanProposalRes,
    MemberLoanSignedCopyDeliveryRes,
    MemberLoanSigningDocumentRes,
    MemberLoanSigningRequestRes,
)


def buckets_res(buckets: MemberLoanBuckets | dict) -> MemberLoanBucketsRes:
    plain = buckets if isinstance(buckets, dict) else buckets.as_plain_dict()
    return MemberLoanBucketsRes(**plain)


def preview_res(preview: MemberLoanEventPreview | dict) -> MemberLoanPreviewRes:
    plain = preview if isinstance(preview, dict) else preview.as_plain_dict()
    allocation = plain.get("allocation")
    return MemberLoanPreviewRes(
        effective_date=plain["effective_date"],
        buckets_before=MemberLoanBucketsRes(**plain["buckets_before"]),
        buckets_after=MemberLoanBucketsRes(**plain["buckets_after"]),
        allocation=MemberLoanAllocationRes(**allocation) if allocation else None,
        preview_fingerprint=plain["preview_fingerprint"],
    )


def proposal_res(snapshot: MemberLoanLedgerSnapshot, event: MemberLoanEvent, caller: MemberLoanCaller) -> MemberLoanProposalRes:
    members = caller.members
    signing_document_id = snapshot.signing_document_id_by_event_id.get(event.id)
    state = snapshot.state_of(event)
    decision = snapshot.decisions_by_event_id.get(event.id)
    live_preview: Optional[MemberLoanPreviewRes] = None
    live_preview_problem: Optional[str] = None
    figures_changed = False
    if state == PROPOSAL_STATE_PENDING:
        try:
            live = live_preview_for(snapshot, event)
            live_preview = preview_res(live)
            figures_changed = live.preview_fingerprint != event.preview_fingerprint_at_proposal
        except MemberLoanEventRejected as rejected:
            live_preview_problem = f"It cannot be approved as things stand: {rejected.plain_language_reason}"
            figures_changed = True
    proposed_by_caller = event.proposed_by_username == caller.member.username
    target = snapshot.events_by_id.get(event.reverses_event_id) if event.event_type == REVERSAL else None
    month = statement_month_affected_by(target or event)
    may_reverse = (
        event.event_type != REVERSAL
        and snapshot.is_in_effect(event)
        and snapshot.pending_reversal_of(event) is None
        and month not in snapshot.locked_statement_months
    )
    return MemberLoanProposalRes(
        id=str(event.id),
        proposal_sequence=event.proposal_sequence,
        event_type=event.event_type,
        plain_event_name=plain_event_name(event.event_type, members),
        effective_date=event.effective_date,
        amount=None if event.amount is None else f"{Decimal(event.amount):.2f}",
        interest_election_choice=event.interest_election_choice,
        written_agreement_date=event.written_agreement_date,
        written_agreement_description=event.written_agreement_description,
        payment_reference=event.payment_reference,
        note=event.note,
        reverses_event_id=str(event.reverses_event_id) if event.reverses_event_id else None,
        reversed_event_summary=reversed_event_summary(snapshot, event, members),
        reversal_reason=event.reversal_reason,
        state=state,
        proposed_by_display_name=members.display_name_for(event.proposed_by_username),
        proposed_at=event.proposed_at,
        decided_by_display_name=(
            None if decision is None else ("the system" if decision.decided_by_user_id is None else members.display_name_for(decision.decided_by_username))
        ),
        decided_at=None if decision is None else decision.decided_at,
        decision_reason=None if decision is None else decision.decision_reason,
        preview_at_proposal=preview_res(event.preview_at_proposal),
        live_preview=live_preview,
        live_preview_problem=live_preview_problem,
        figures_changed_since_proposal=figures_changed,
        signing_document_id=str(signing_document_id) if signing_document_id else None,
        caller_may_sign_or_reject=(state == PROPOSAL_STATE_PENDING and not proposed_by_caller),
        caller_may_cancel=(state == PROPOSAL_STATE_PENDING and proposed_by_caller),
        caller_may_propose_reversal=may_reverse,
        includes_yarden_increase_warning=(
            event.event_type == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE
            or (target is not None and target.event_type == YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE)
        ),
    )


def _ledger_row_description(row: MemberLoanLedgerRow, members: MemberLoanMembers) -> str:
    if row.row_kind == LEDGER_ROW_KIND_LOAN_START:
        return f"Loan started with {format_money(row.amount)}"
    if row.row_kind == LEDGER_ROW_KIND_INTEREST_DATE:
        month_name = f"{first_day_of_previous_month(row.row_date):%B}"
        if row.interest_election_choice == INTEREST_ELECTION_CASH:
            return f"Interest for {month_name} ({format_money(row.interest_moved_to_interest_payable)}) to be paid to {members.lender.display_name} in cash"
        return f"Interest for {month_name} added to the debt ({format_money(row.interest_added_to_debt)})"
    name = plain_event_name(row.row_kind, members)
    if row.amount is None:
        choice = "paid in cash" if row.interest_election_choice == INTEREST_ELECTION_CASH else "added to the debt"
        return f"{name}: interest for {first_day_of_previous_month(row.row_date):%B} to be {choice}"
    return f"{name} of {format_money(row.amount)}"


def ledger_row_res(snapshot: MemberLoanLedgerSnapshot, row: MemberLoanLedgerRow, members: MemberLoanMembers) -> MemberLoanLedgerRowRes:
    proposed_by = approved_by = None
    if row.event_id is not None:
        event = snapshot.events_by_id.get(UUID(row.event_id))
        decision = snapshot.decisions_by_event_id.get(event.id) if event else None
        if event is not None:
            proposed_by = members.display_name_for(event.proposed_by_username)
        if decision is not None:
            approved_by = members.display_name_for(decision.decided_by_username)
    is_interest_date = row.row_kind == LEDGER_ROW_KIND_INTEREST_DATE
    return MemberLoanLedgerRowRes(
        row_date=row.row_date,
        row_kind=row.row_kind,
        plain_description=_ledger_row_description(row, members),
        event_id=row.event_id,
        amount=None if row.amount is None else f"{row.amount:.2f}",
        allocation=MemberLoanAllocationRes(**row.allocation.as_plain_dict()) if row.allocation else None,
        interest_added_to_debt=f"{row.interest_added_to_debt:.2f}" if is_interest_date else None,
        interest_moved_to_interest_payable=f"{row.interest_moved_to_interest_payable:.2f}" if is_interest_date else None,
        buckets_after=buckets_res(row.buckets_after),
        proposed_by_display_name=proposed_by,
        approved_by_display_name=approved_by,
    )


def statement_month_is_viewable(month: date, loan_start_month: date, current_month: date) -> bool:
    return loan_start_month <= month <= current_month


def signing_document_res(
    db, snapshot: MemberLoanLedgerSnapshot, document: MemberLoanSigningDocument, caller: MemberLoanCaller
) -> MemberLoanSigningDocumentRes:
    members = caller.members
    state = signature_state_of(db, document)
    signers = []
    for entry in document.document_content["signers"]:
        signature = state.signatures_by_username.get(entry["username"])
        signers.append(MemberLoanDocumentSignerRes(
            username=entry["username"],
            display_name=members.display_name_for(entry["username"]),
            legal_name=entry["legal_name"],
            role_label=entry["role_label"],
            status="waiting" if signature is None else signature.signature_meaning,
            signed_at=None if signature is None else signature.signed_at,
            objection_reason=None if signature is None else signature.objection_reason,
        ))
    proposal_state = None
    response_deadline = None
    is_statement = document.document_kind == DOCUMENT_KIND_MONTHLY_STATEMENT
    if is_statement:
        response_deadline = statement_response_deadline(db, document)
        still_open = response_deadline is None or member_loan_settings.new_york_today() <= response_deadline
    else:
        event = snapshot.events_by_id.get(document.event_id)
        proposal_state = snapshot.state_of(event) if event is not None else None
        still_open = proposal_state == PROPOSAL_STATE_PENDING
    caller_must_act = (
        still_open and caller.member.username in document.required_signer_usernames and not state.has_acted(caller.member.username)
    )
    signed_copy = member_loan_crud.get_member_loan_signed_copy_for_document(db, document.id)
    deliveries = member_loan_crud.list_member_loan_signed_copy_deliveries(db, signed_copy.id) if signed_copy else []
    return MemberLoanSigningDocumentRes(
        id=str(document.id),
        document_kind=document.document_kind,
        title=document.title,
        event_id=str(document.event_id) if document.event_id else None,
        statement_month=document.statement_month.strftime("%Y-%m") if document.statement_month else None,
        record_number=document.document_content.get("record_number"),
        created_at=document.created_at,
        document_sha256=document.unsigned_pdf_sha256,
        content=document.document_content,
        signers=signers,
        caller_must_act=caller_must_act,
        caller_may_object=caller_must_act and is_statement,
        proposal_state=proposal_state,
        response_deadline=response_deadline,
        is_complete=signed_copy is not None,
        completed_at=signed_copy.completed_at if signed_copy else None,
        signed_copy_sha256=signed_copy.signed_pdf_sha256 if signed_copy else None,
        deliveries=[
            MemberLoanSignedCopyDeliveryRes(delivery_channel=d.delivery_channel, delivery_status=d.delivery_status, attempted_at=d.attempted_at)
            for d in deliveries
        ],
    )


def signing_request_res(db, signing_request: MemberLoanSigningRequest, caller: MemberLoanCaller) -> MemberLoanSigningRequestRes:
    return MemberLoanSigningRequestRes(
        signing_request_id=str(signing_request.id),
        signing_purpose=signing_request.signing_purpose,
        document_id=str(signing_request.document_id) if signing_request.document_id else None,
        document_sha256=signing_request.document_sha256,
        document_content=signing_request_content(db, signing_request),
        signature_meaning=signing_request.signature_meaning,
        objection_reason=signing_request.objection_reason,
        signature_statement_text=signing_request.signature_statement_text,
        full_legal_name_to_type=caller.member.legal_name,
        electronic_signature_consent_text=ELECTRONIC_SIGNATURE_CONSENT_TEXT,
        expires_at=signing_request.expires_at,
    )
