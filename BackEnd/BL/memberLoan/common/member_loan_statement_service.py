"""Assemble one month's statement from the ledger (figures + plain-language document)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from BL.memberLoan.common.member_loan_access import MemberLoanMembers
from BL.memberLoan.common.member_loan_engine import (
    INTEREST_PAYMENT_ELECTION,
    REVERSAL,
    build_member_loan_monthly_statement_figures,
)
from BL.memberLoan.common.member_loan_ledger_service import (
    DECISION_APPROVED,
    MemberLoanLedgerSnapshot,
    member_loan_terms,
    statement_month_affected_by,
)
from BL.memberLoan.common.member_loan_settings import LOAN_TIME_ZONE
from BL.memberLoan.common.member_loan_statement_document import (
    MemberLoanEventDescription,
    MemberLoanStatementDocument,
    build_member_loan_statement_document,
)
from DAL.data_models.memberLoan.models import MemberLoanEvent


def _description(snapshot: MemberLoanLedgerSnapshot, event: MemberLoanEvent, members: MemberLoanMembers) -> MemberLoanEventDescription:
    decision = snapshot.decisions_by_event_id.get(event.id)
    target = snapshot.events_by_id.get(event.reverses_event_id) if event.event_type == REVERSAL else None
    return MemberLoanEventDescription(
        event_id=str(event.id),
        event_type=event.event_type,
        proposed_by_display_name=members.display_name_for(event.proposed_by_username),
        proposed_on=event.proposed_at.astimezone(LOAN_TIME_ZONE).date(),
        approved_by_display_name=members.display_name_for(decision.decided_by_username) if decision else "",
        approved_on=decision.decided_at.astimezone(LOAN_TIME_ZONE).date() if decision else event.effective_date,
        effective_date=event.effective_date,
        amount=None if event.amount is None else Decimal(event.amount),
        written_agreement_date=event.written_agreement_date,
        written_agreement_description=event.written_agreement_description,
        payment_reference=event.payment_reference,
        note=event.note,
        reversal_reason=event.reversal_reason,
        reversed_event_description=_description(snapshot, target, members) if target is not None else None,
    )


def count_proposals_waiting_for_month(snapshot: MemberLoanLedgerSnapshot, month: date) -> int:
    count = 0
    for event in snapshot.pending_events():
        target = snapshot.events_by_id.get(event.reverses_event_id) if event.event_type == REVERSAL else None
        if statement_month_affected_by(target or event) == month:
            count += 1
    return count


def build_member_loan_statement_for_month(
    snapshot: MemberLoanLedgerSnapshot, members: MemberLoanMembers, month: date
) -> MemberLoanStatementDocument:
    terms = member_loan_terms()
    figures = build_member_loan_monthly_statement_figures(terms, snapshot.effective_engine_events(), month)

    descriptions = {
        str(event.id): _description(snapshot, event, members)
        for event in snapshot.events
        if snapshot.is_in_effect(event) and event.event_type != INTEREST_PAYMENT_ELECTION
    }
    election: Optional[MemberLoanEvent] = None
    for event in snapshot.events:
        if (
            event.event_type == INTEREST_PAYMENT_ELECTION
            and snapshot.is_in_effect(event)
            and event.effective_date == figures.statement_date
        ):
            if election is None or (
                snapshot.decisions_by_event_id[event.id].decision_sequence
                > snapshot.decisions_by_event_id[election.id].decision_sequence
            ):
                election = event
    reversals = [
        _description(snapshot, event, members)
        for event in snapshot.events
        if event.event_type == REVERSAL
        and snapshot.state_of(event) == DECISION_APPROVED
        and event.reverses_event_id in snapshot.events_by_id
        and statement_month_affected_by(snapshot.events_by_id[event.reverses_event_id]) == month
    ]
    return build_member_loan_statement_document(
        figures,
        terms,
        lender_display_name=members.lender.display_name,
        yarden_display_name=members.yarden.display_name,
        event_descriptions=descriptions,
        interest_election_description=_description(snapshot, election, members) if election else None,
        reversals_approved_in_month=reversals,
        proposals_left_out_count=count_proposals_waiting_for_month(snapshot, month),
        ledger_fingerprint=snapshot.ledger_fingerprint(),
    )
