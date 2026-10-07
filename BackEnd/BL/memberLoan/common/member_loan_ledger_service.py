"""The Member Loan ledger: proposals, decisions, expiry, the month lock and the audit trail.

Every write runs inside one transaction that first takes the Member Loan
advisory lock, so validation (R6), the hash chains and the "one decision per
proposal" rule never race. The event row or decision row and its audit entry
commit together or not at all. E-mail is never sent here: callers schedule
notifications after the commit (D5).

Lifecycle (D16): a proposal is `pending` until exactly one decision follows it:
`approved` (only the other member, with the preview fingerprint they saw, R7),
`rejected` (only the other member, with a reason), `cancelled` (only the
proposer) or `expired` (the system: 14 days without a decision, or its month's
statement was sent first). Only approved events that no approved reversal
cancels reach the engine (R5).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

from BL.memberLoan.common.member_loan_access import MemberLoanCaller, MemberLoanMembers
from BL.memberLoan.common.member_loan_engine import (
    DEFAULT_MEMBER_LOAN_TERMS,
    EVENT_TYPES_THAT_CARRY_AN_AMOUNT,
    INTEREST_PAYMENT_ELECTION,
    LENDER_ADDITIONAL_ADVANCE,
    REVERSAL,
    YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE,
    EffectiveMemberLoanEvent,
    MemberLoanEventPreview,
    MemberLoanEventRejected,
    MemberLoanTerms,
    calculate_member_loan_position,
    first_day_of_month,
    preview_member_loan_event,
    preview_member_loan_reversal,
)
from BL.memberLoan.common.member_loan_hash_chain import GENESIS_HASH, compute_row_hash
from BL.memberLoan.common import member_loan_settings
from BL.memberLoan.common.member_loan_settings import PENDING_PROPOSAL_LIFETIME_DAYS
from BL.memberLoan.common.member_loan_statement_document import EVENT_TYPE_PLAIN_NAMES, format_money, format_month_label, format_short_date
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanAuditEntry, MemberLoanEvent, MemberLoanEventDecision
from ReqRes.common.member_loan_schemas import MemberLoanProposalCreateReq

PROPOSAL_STATE_PENDING = "pending"
DECISION_APPROVED = "approved"
DECISION_REJECTED = "rejected"
DECISION_CANCELLED = "cancelled"
DECISION_EXPIRED = "expired"
SYSTEM_ACTOR_USERNAME = "system"

AUDIT_ACTION_BY_DECISION = {
    DECISION_APPROVED: "event_approved",
    DECISION_REJECTED: "event_rejected",
    DECISION_CANCELLED: "event_cancelled",
    DECISION_EXPIRED: "event_expired",
}


class MemberLoanRequestRefused(Exception):
    """A request the members must see refused, with a plain-language reason."""

    def __init__(self, status_code: int, plain_language_reason: str, *, code: Optional[str] = None, extra: Optional[dict] = None):
        super().__init__(plain_language_reason)
        self.status_code = status_code
        self.plain_language_reason = plain_language_reason
        self.code = code
        self.extra = extra or {}


def member_loan_terms() -> MemberLoanTerms:
    return DEFAULT_MEMBER_LOAN_TERMS


# -- reading the ledger ------------------------------------------------------------


@dataclass
class MemberLoanLedgerSnapshot:
    events: list[MemberLoanEvent]
    decisions_by_event_id: dict[UUID, MemberLoanEventDecision]
    locked_statement_months: set[date]
    events_by_id: dict[UUID, MemberLoanEvent] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.events_by_id = {e.id: e for e in self.events}

    def state_of(self, event: MemberLoanEvent) -> str:
        decision = self.decisions_by_event_id.get(event.id)
        return decision.decision if decision else PROPOSAL_STATE_PENDING

    def approved_reversal_of(self, event: MemberLoanEvent) -> Optional[MemberLoanEvent]:
        return next(
            (
                e
                for e in self.events
                if e.event_type == REVERSAL and e.reverses_event_id == event.id and self.state_of(e) == DECISION_APPROVED
            ),
            None,
        )

    def pending_reversal_of(self, event: MemberLoanEvent) -> Optional[MemberLoanEvent]:
        return next(
            (
                e
                for e in self.events
                if e.event_type == REVERSAL and e.reverses_event_id == event.id and self.state_of(e) == PROPOSAL_STATE_PENDING
            ),
            None,
        )

    def is_in_effect(self, event: MemberLoanEvent) -> bool:
        return (
            event.event_type != REVERSAL
            and self.state_of(event) == DECISION_APPROVED
            and self.approved_reversal_of(event) is None
        )

    def effective_engine_events(self) -> list[EffectiveMemberLoanEvent]:
        return [
            engine_event_for(event, self.decisions_by_event_id[event.id].decision_sequence)
            for event in self.events
            if self.is_in_effect(event)
        ]

    def pending_events(self) -> list[MemberLoanEvent]:
        return [e for e in self.events if self.state_of(e) == PROPOSAL_STATE_PENDING]

    def ledger_fingerprint(self) -> str:
        last_event_hash = self.events[-1].event_hash if self.events else GENESIS_HASH
        decisions = sorted(self.decisions_by_event_id.values(), key=lambda d: d.decision_sequence)
        last_decision_hash = decisions[-1].decision_hash if decisions else GENESIS_HASH
        return hashlib.sha256(f"{last_event_hash}:{last_decision_hash}".encode()).hexdigest()


def engine_event_for(event: MemberLoanEvent, application_order: int) -> EffectiveMemberLoanEvent:
    return EffectiveMemberLoanEvent(
        event_id=str(event.id),
        event_type=event.event_type,
        effective_date=event.effective_date,
        application_order=application_order,
        amount=None if event.amount is None else Decimal(event.amount),
        interest_election_choice=event.interest_election_choice,
    )


def load_member_loan_ledger_snapshot(db: DbSession) -> MemberLoanLedgerSnapshot:
    return MemberLoanLedgerSnapshot(
        events=member_loan_crud.list_member_loan_events(db),
        decisions_by_event_id={d.event_id: d for d in member_loan_crud.list_member_loan_event_decisions(db)},
        locked_statement_months=member_loan_crud.list_months_with_a_sent_member_loan_statement(db),
    )


def statement_month_affected_by(event: MemberLoanEvent | None, *, event_type: Optional[str] = None, effective_date: Optional[date] = None) -> date:
    """The month whose statement an event changes.

    An interest choice dated on an Interest Date controls the capitalization
    that closes the *previous* month, so it belongs to that month's statement.
    """

    event_type = event.event_type if event is not None else event_type
    effective_date = event.effective_date if event is not None else effective_date
    if event_type == INTEREST_PAYMENT_ELECTION:
        return first_day_of_month(effective_date - timedelta(days=1))
    return first_day_of_month(effective_date)


def _refuse_if_month_locked(snapshot: MemberLoanLedgerSnapshot, month: date) -> None:
    if month in snapshot.locked_statement_months:
        raise MemberLoanRequestRefused(
            422,
            f"The statement for {format_month_label(month)} was already sent, so changes to that month can no longer be made.",
            code="month_locked",
        )


def _refuse_if_too_far_in_the_future(effective_date: date) -> None:
    latest_allowed_date = member_loan_settings.new_york_today() + timedelta(days=1)
    if effective_date > latest_allowed_date:
        raise MemberLoanRequestRefused(
            422,
            "The date cannot be in the future. Changes are recorded on the day the money actually moves.",
            code="date_in_future",
        )


# -- audit trail -------------------------------------------------------------------


def append_member_loan_audit_entry(
    db: DbSession,
    *,
    actor_user_id: Optional[UUID],
    actor_username: str,
    action: str,
    event_id: Optional[UUID] = None,
    state_before: Optional[dict] = None,
    state_after: Optional[dict] = None,
    detail: Optional[dict] = None,
    request_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> MemberLoanAuditEntry:
    """Append one hash-chained audit row. The caller holds the write lock and commits."""

    last = member_loan_crud.get_last_member_loan_audit_entry(db)
    row = MemberLoanAuditEntry(
        id=uuid.uuid4(),
        audit_sequence=(last.audit_sequence + 1) if last else 1,
        recorded_at=member_loan_settings.utc_now(),
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        action=action,
        event_id=event_id,
        state_before=state_before,
        state_after=state_after,
        detail=detail,
        request_ip=request_ip,
        user_agent=user_agent,
        previous_audit_hash=last.audit_hash if last else GENESIS_HASH,
        audit_hash="",
    )
    row.audit_hash = compute_row_hash(row, "audit_hash")
    member_loan_crud.add_member_loan_row(db, row)
    return row


def _append_decision(
    db: DbSession,
    *,
    event: MemberLoanEvent,
    decision: str,
    decided_by_user_id: Optional[UUID],
    decided_by_username: str,
    decision_reason: Optional[str] = None,
    preview: Optional[MemberLoanEventPreview] = None,
) -> MemberLoanEventDecision:
    last = member_loan_crud.get_last_member_loan_event_decision(db)
    row = MemberLoanEventDecision(
        id=uuid.uuid4(),
        decision_sequence=(last.decision_sequence + 1) if last else 1,
        event_id=event.id,
        decision=decision,
        decided_by_user_id=decided_by_user_id,
        decided_by_username=decided_by_username,
        decided_at=member_loan_settings.utc_now(),
        decision_reason=decision_reason,
        preview_fingerprint_confirmed=preview.preview_fingerprint if (preview and decision == DECISION_APPROVED) else None,
        preview_at_decision=preview.as_plain_dict() if preview else None,
        previous_decision_hash=last.decision_hash if last else GENESIS_HASH,
        decision_hash="",
    )
    row.decision_hash = compute_row_hash(row, "decision_hash")
    member_loan_crud.add_member_loan_row(db, row)
    return row


# -- previews ----------------------------------------------------------------------


def live_preview_for(snapshot: MemberLoanLedgerSnapshot, event: MemberLoanEvent) -> MemberLoanEventPreview:
    """What approving `event` would change right now. Raises `MemberLoanEventRejected` (R6)."""

    effective_events = snapshot.effective_engine_events()
    if event.event_type == REVERSAL:
        return preview_member_loan_reversal(member_loan_terms(), effective_events, str(event.reverses_event_id))
    return preview_member_loan_event(member_loan_terms(), effective_events, engine_event_for(event, 0))


# -- expiry ------------------------------------------------------------------------


@dataclass(frozen=True)
class MemberLoanDecisionOutcome:
    event_id: UUID
    decision: str


def expire_stale_member_loan_proposals(db: DbSession, snapshot: MemberLoanLedgerSnapshot) -> list[MemberLoanDecisionOutcome]:
    """Expire pending proposals that waited too long or whose month is now locked.

    The caller holds the write lock; it commits. Returns what expired, for the
    after-commit e-mails.
    """

    expired: list[MemberLoanDecisionOutcome] = []
    now = member_loan_settings.utc_now()
    for event in snapshot.pending_events():
        reason = None
        if now - event.proposed_at >= timedelta(days=PENDING_PROPOSAL_LIFETIME_DAYS):
            reason = f"It waited {PENDING_PROPOSAL_LIFETIME_DAYS} days without a decision."
        else:
            affected_month = statement_month_affected_by(_reversal_target_or_self(snapshot, event))
            if affected_month in snapshot.locked_statement_months:
                reason = f"The statement for {format_month_label(affected_month)} was sent before it was approved."
        if reason is None:
            continue
        decision = _append_decision(
            db, event=event, decision=DECISION_EXPIRED, decided_by_user_id=None,
            decided_by_username=SYSTEM_ACTOR_USERNAME, decision_reason=reason,
        )
        snapshot.decisions_by_event_id[event.id] = decision
        append_member_loan_audit_entry(
            db, actor_user_id=None, actor_username=SYSTEM_ACTOR_USERNAME, action="event_expired",
            event_id=event.id, detail={"reason": reason},
        )
        expired.append(MemberLoanDecisionOutcome(event.id, DECISION_EXPIRED))
    return expired


def _reversal_target_or_self(snapshot: MemberLoanLedgerSnapshot, event: MemberLoanEvent) -> MemberLoanEvent:
    if event.event_type == REVERSAL and event.reverses_event_id in snapshot.events_by_id:
        return snapshot.events_by_id[event.reverses_event_id]
    return event


def expire_stale_proposals_in_own_transaction(db: DbSession) -> list[MemberLoanDecisionOutcome]:
    """For reads and the cron: a short write transaction that only expires."""

    member_loan_crud.acquire_member_loan_write_lock(db)
    snapshot = load_member_loan_ledger_snapshot(db)
    expired = expire_stale_member_loan_proposals(db, snapshot)
    db.commit()
    return expired


# -- proposing ---------------------------------------------------------------------


def _validate_proposal_fields(request: MemberLoanProposalCreateReq) -> Optional[Decimal]:
    event_type = request.event_type
    amount = None if request.amount is None else Decimal(request.amount)
    if event_type in EVENT_TYPES_THAT_CARRY_AN_AMOUNT:
        if amount is None or amount <= 0:
            raise MemberLoanRequestRefused(422, "Please enter an amount above $0.00.", code="amount_required")
        if request.interest_election_choice is not None:
            raise MemberLoanRequestRefused(422, "An interest choice belongs only to the 'Interest choice' change.")
    if event_type == INTEREST_PAYMENT_ELECTION:
        if request.interest_election_choice is None:
            raise MemberLoanRequestRefused(422, "Please choose 'reinvest' or 'cash'.", code="election_choice_required")
        if amount is not None:
            raise MemberLoanRequestRefused(422, "An interest choice has no amount.")
    if event_type in (LENDER_ADDITIONAL_ADVANCE, YARDEN_ADDITIONAL_WITHDRAWAL_INCREASE):
        if request.written_agreement_date is None or not (request.written_agreement_description or "").strip():
            raise MemberLoanRequestRefused(
                422,
                "This change needs the written agreement both members signed: its date and a short description.",
                code="written_agreement_required",
            )
    return amount


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _append_event(db: DbSession, caller: MemberLoanCaller, preview: MemberLoanEventPreview, **fields) -> MemberLoanEvent:
    last = member_loan_crud.get_last_member_loan_event(db)
    row = MemberLoanEvent(
        id=fields.pop("id"),
        proposal_sequence=(last.proposal_sequence + 1) if last else 1,
        proposed_by_user_id=caller.member.user_id,
        proposed_by_username=caller.member.username,
        proposed_at=member_loan_settings.utc_now(),
        request_ip=caller.request_ip,
        preview_at_proposal=preview.as_plain_dict(),
        preview_fingerprint_at_proposal=preview.preview_fingerprint,
        previous_event_hash=last.event_hash if last else GENESIS_HASH,
        event_hash="",
        **fields,
    )
    row.event_hash = compute_row_hash(row, "event_hash")
    member_loan_crud.add_member_loan_row(db, row)
    return row


@dataclass(frozen=True)
class MemberLoanWriteResult:
    """The event written or decided. Expiry runs separately, before every request
    (`expire_stale_proposals_in_own_transaction`), so its e-mails go out even
    when the write itself is refused."""

    event_id: UUID
    decision: Optional[str] = None


def propose_member_loan_event(db: DbSession, caller: MemberLoanCaller, request: MemberLoanProposalCreateReq) -> MemberLoanWriteResult:
    amount = _validate_proposal_fields(request)
    member_loan_crud.acquire_member_loan_write_lock(db)
    snapshot = load_member_loan_ledger_snapshot(db)
    _refuse_if_too_far_in_the_future(request.effective_date)
    _refuse_if_month_locked(
        snapshot, statement_month_affected_by(None, event_type=request.event_type, effective_date=request.effective_date)
    )
    new_event_id = uuid.uuid4()
    candidate = EffectiveMemberLoanEvent(
        event_id=str(new_event_id),
        event_type=request.event_type,
        effective_date=request.effective_date,
        application_order=0,
        amount=amount,
        interest_election_choice=request.interest_election_choice,
    )
    try:
        preview = preview_member_loan_event(member_loan_terms(), snapshot.effective_engine_events(), candidate)
    except MemberLoanEventRejected as rejected:
        raise MemberLoanRequestRefused(422, rejected.plain_language_reason, code="cannot_be_applied")
    event = _append_event(
        db,
        caller,
        preview,
        id=new_event_id,
        event_type=request.event_type,
        effective_date=request.effective_date,
        amount=amount,
        interest_election_choice=request.interest_election_choice,
        written_agreement_date=request.written_agreement_date,
        written_agreement_description=_clean_text(request.written_agreement_description),
        payment_reference=_clean_text(request.payment_reference),
        note=_clean_text(request.note),
    )
    append_member_loan_audit_entry(
        db,
        actor_user_id=caller.member.user_id,
        actor_username=caller.member.username,
        action="event_proposed",
        event_id=event.id,
        state_before=preview.buckets_before.as_plain_dict(),
        state_after=preview.buckets_after.as_plain_dict(),
        detail={"event_type": event.event_type, "effective_date": event.effective_date.isoformat(),
                "amount": None if amount is None else f"{amount:.2f}", "preview_fingerprint": preview.preview_fingerprint},
        request_ip=caller.request_ip,
        user_agent=caller.user_agent,
    )
    db.commit()
    return MemberLoanWriteResult(event_id=event.id)


def propose_member_loan_reversal(
    db: DbSession, caller: MemberLoanCaller, target_event_id: UUID, reason: str, note: Optional[str]
) -> MemberLoanWriteResult:
    member_loan_crud.acquire_member_loan_write_lock(db)
    snapshot = load_member_loan_ledger_snapshot(db)
    target = snapshot.events_by_id.get(target_event_id)
    if target is None:
        raise MemberLoanRequestRefused(404, "That change was not found.")
    if not snapshot.is_in_effect(target):
        raise MemberLoanRequestRefused(409, "Only an approved change that is still in effect can be reversed.")
    if snapshot.pending_reversal_of(target) is not None:
        raise MemberLoanRequestRefused(409, "A reversal of this change is already waiting for approval.")
    _refuse_if_month_locked(snapshot, statement_month_affected_by(target))
    try:
        preview = preview_member_loan_reversal(member_loan_terms(), snapshot.effective_engine_events(), str(target.id))
    except MemberLoanEventRejected as rejected:
        raise MemberLoanRequestRefused(422, f"It cannot be reversed: {rejected.plain_language_reason}", code="cannot_be_applied")
    event = _append_event(
        db,
        caller,
        preview,
        id=uuid.uuid4(),
        event_type=REVERSAL,
        effective_date=target.effective_date,
        reverses_event_id=target.id,
        reversal_reason=_clean_text(reason),
        note=_clean_text(note),
    )
    append_member_loan_audit_entry(
        db,
        actor_user_id=caller.member.user_id,
        actor_username=caller.member.username,
        action="event_proposed",
        event_id=event.id,
        state_before=preview.buckets_before.as_plain_dict(),
        state_after=preview.buckets_after.as_plain_dict(),
        detail={"event_type": REVERSAL, "reverses_event_id": str(target.id), "preview_fingerprint": preview.preview_fingerprint},
        request_ip=caller.request_ip,
        user_agent=caller.user_agent,
    )
    db.commit()
    return MemberLoanWriteResult(event_id=event.id)


# -- deciding ----------------------------------------------------------------------


def decide_member_loan_event(
    db: DbSession,
    caller: MemberLoanCaller,
    event_id: UUID,
    decision: str,
    *,
    preview_fingerprint: Optional[str] = None,
    reason: Optional[str] = None,
) -> MemberLoanWriteResult:
    member_loan_crud.acquire_member_loan_write_lock(db)
    snapshot = load_member_loan_ledger_snapshot(db)
    event = snapshot.events_by_id.get(event_id)
    if event is None:
        raise MemberLoanRequestRefused(404, "That change was not found.")
    state = snapshot.state_of(event)
    if state != PROPOSAL_STATE_PENDING:
        raise MemberLoanRequestRefused(409, f"This change is no longer waiting: it was {state}.", code="already_decided")
    proposer_is_caller = event.proposed_by_username == caller.member.username
    if decision in (DECISION_APPROVED, DECISION_REJECTED) and proposer_is_caller:
        raise MemberLoanRequestRefused(
            403, f"Only {caller.other_member.display_name} can approve or reject a change you proposed.", code="not_the_counterparty"
        )
    if decision == DECISION_CANCELLED and not proposer_is_caller:
        raise MemberLoanRequestRefused(403, "Only the member who proposed a change can cancel it.", code="not_the_proposer")

    preview: Optional[MemberLoanEventPreview] = None
    if decision == DECISION_APPROVED:
        _refuse_if_month_locked(snapshot, statement_month_affected_by(_reversal_target_or_self(snapshot, event)))
        try:
            preview = live_preview_for(snapshot, event)
        except MemberLoanEventRejected as rejected:
            raise MemberLoanRequestRefused(
                422, f"It cannot be approved any more: {rejected.plain_language_reason}", code="cannot_be_applied"
            )
        if preview.preview_fingerprint != preview_fingerprint:
            raise MemberLoanRequestRefused(
                409,
                "The figures changed since you looked: another change was approved in the meantime. Please review the new figures.",
                code="figures_changed",
                extra={"live_preview": preview.as_plain_dict()},
            )
    else:
        try:
            preview = live_preview_for(snapshot, event)
        except MemberLoanEventRejected:
            preview = None

    decision_row = _append_decision(
        db,
        event=event,
        decision=decision,
        decided_by_user_id=caller.member.user_id,
        decided_by_username=caller.member.username,
        decision_reason=_clean_text(reason),
        preview=preview,
    )
    append_member_loan_audit_entry(
        db,
        actor_user_id=caller.member.user_id,
        actor_username=caller.member.username,
        action=AUDIT_ACTION_BY_DECISION[decision],
        event_id=event.id,
        state_before=preview.buckets_before.as_plain_dict() if (preview and decision == DECISION_APPROVED) else None,
        state_after=preview.buckets_after.as_plain_dict() if (preview and decision == DECISION_APPROVED) else None,
        detail={"decision_sequence": decision_row.decision_sequence, "reason": decision_row.decision_reason},
        request_ip=caller.request_ip,
        user_agent=caller.user_agent,
    )
    db.commit()
    return MemberLoanWriteResult(event_id=event.id, decision=decision)


# -- views -------------------------------------------------------------------------


def plain_event_name(event_type: str, members: MemberLoanMembers) -> str:
    return EVENT_TYPE_PLAIN_NAMES[event_type].format(lender=members.lender.display_name, yarden=members.yarden.display_name)


def reversed_event_summary(snapshot: MemberLoanLedgerSnapshot, event: MemberLoanEvent, members: MemberLoanMembers) -> Optional[str]:
    if event.event_type != REVERSAL:
        return None
    target = snapshot.events_by_id.get(event.reverses_event_id)
    if target is None:
        return None
    amount = f" of {format_money(Decimal(target.amount))}" if target.amount is not None else ""
    return f"{plain_event_name(target.event_type, members)}{amount} on {format_short_date(target.effective_date)}"


def proposals_waiting_for(snapshot: MemberLoanLedgerSnapshot, username: str) -> int:
    return sum(1 for e in snapshot.pending_events() if e.proposed_by_username != username)


def proposals_waiting_for_other_member(snapshot: MemberLoanLedgerSnapshot, username: str) -> int:
    return sum(1 for e in snapshot.pending_events() if e.proposed_by_username == username)


def member_loan_position_as_of(snapshot: MemberLoanLedgerSnapshot, as_of_date: date):
    try:
        return calculate_member_loan_position(member_loan_terms(), snapshot.effective_engine_events(), as_of_date)
    except MemberLoanEventRejected as rejected:
        raise MemberLoanRequestRefused(422, rejected.plain_language_reason)

