"""Turn the ledger into the API's response models, in plain words."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

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
from BL.memberLoan.common.member_loan_statement_document import format_money
from DAL.data_models.memberLoan.models import MemberLoanEvent
from ReqRes.common.member_loan_schemas import (
    MemberLoanAllocationRes,
    MemberLoanBucketsRes,
    MemberLoanLedgerRowRes,
    MemberLoanPreviewRes,
    MemberLoanProposalRes,
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
        caller_may_approve_or_reject=(state == PROPOSAL_STATE_PENDING and not proposed_by_caller),
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
        from uuid import UUID

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
