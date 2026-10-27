"""Member Loan queries. No business logic and no commits (BL owns the transaction)."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from DAL.data_models.memberLoan.models import (
    MemberLoanAuditEntry,
    MemberLoanEvent,
    MemberLoanEventDecision,
    MemberLoanSignature,
    MemberLoanSignedCopy,
    MemberLoanSignedCopyDelivery,
    MemberLoanSigningDocument,
    MemberLoanSigningRequest,
    MemberLoanStatementSend,
    MemberLoanStatementSignatureReminder,
)

# Arbitrary but fixed: serialises every Member Loan write (proposal, decision,
# audit entry, statement send) so validation and the hash chains never race.
MEMBER_LOAN_WRITE_LOCK_KEY = 6_032_026_101


def acquire_member_loan_write_lock(db: Session) -> None:
    """Held until the surrounding transaction commits or rolls back. Postgres only."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MEMBER_LOAN_WRITE_LOCK_KEY})


def list_member_loan_events(db: Session) -> list[MemberLoanEvent]:
    return list(db.execute(select(MemberLoanEvent).order_by(MemberLoanEvent.proposal_sequence)).scalars())


def get_member_loan_event(db: Session, event_id: UUID) -> Optional[MemberLoanEvent]:
    return db.get(MemberLoanEvent, event_id)


def get_last_member_loan_event(db: Session) -> Optional[MemberLoanEvent]:
    return db.execute(select(MemberLoanEvent).order_by(MemberLoanEvent.proposal_sequence.desc()).limit(1)).scalar_one_or_none()


def list_member_loan_event_decisions(db: Session) -> list[MemberLoanEventDecision]:
    return list(db.execute(select(MemberLoanEventDecision).order_by(MemberLoanEventDecision.decision_sequence)).scalars())


def get_last_member_loan_event_decision(db: Session) -> Optional[MemberLoanEventDecision]:
    return db.execute(
        select(MemberLoanEventDecision).order_by(MemberLoanEventDecision.decision_sequence.desc()).limit(1)
    ).scalar_one_or_none()


def list_member_loan_audit_entries(db: Session, *, newest_first: bool = False, limit: Optional[int] = None) -> list[MemberLoanAuditEntry]:
    order = MemberLoanAuditEntry.audit_sequence.desc() if newest_first else MemberLoanAuditEntry.audit_sequence
    statement = select(MemberLoanAuditEntry).order_by(order)
    if limit is not None:
        statement = statement.limit(limit)
    return list(db.execute(statement).scalars())


def get_last_member_loan_audit_entry(db: Session) -> Optional[MemberLoanAuditEntry]:
    return db.execute(
        select(MemberLoanAuditEntry).order_by(MemberLoanAuditEntry.audit_sequence.desc()).limit(1)
    ).scalar_one_or_none()


def list_member_loan_statement_sends(db: Session, statement_month: Optional[date] = None) -> list[MemberLoanStatementSend]:
    statement = select(MemberLoanStatementSend).order_by(MemberLoanStatementSend.started_at)
    if statement_month is not None:
        statement = statement.where(MemberLoanStatementSend.statement_month == statement_month)
    return list(db.execute(statement).scalars())


def list_months_with_a_sent_member_loan_statement(db: Session) -> set[date]:
    rows = db.execute(
        select(MemberLoanStatementSend.statement_month).where(
            MemberLoanStatementSend.is_dry_run.is_(False), MemberLoanStatementSend.status == "sent"
        )
    ).scalars()
    return set(rows)


def count_member_loan_events(db: Session) -> int:
    return int(db.execute(select(func.count()).select_from(MemberLoanEvent)).scalar_one())


def add_member_loan_row(db: Session, row) -> None:
    db.add(row)
    db.flush()


# -- e-signing -------------------------------------------------------------------


def list_member_loan_signing_documents(db: Session) -> list[MemberLoanSigningDocument]:
    return list(db.execute(select(MemberLoanSigningDocument).order_by(MemberLoanSigningDocument.document_sequence)).scalars())


def get_member_loan_signing_document(db: Session, document_id: UUID) -> Optional[MemberLoanSigningDocument]:
    return db.get(MemberLoanSigningDocument, document_id)


def get_member_loan_signing_document_for_event(db: Session, event_id: UUID) -> Optional[MemberLoanSigningDocument]:
    return db.execute(select(MemberLoanSigningDocument).where(MemberLoanSigningDocument.event_id == event_id)).scalar_one_or_none()


def get_member_loan_signing_document_for_statement_month(db: Session, statement_month: date) -> Optional[MemberLoanSigningDocument]:
    return db.execute(
        select(MemberLoanSigningDocument).where(MemberLoanSigningDocument.statement_month == statement_month)
    ).scalar_one_or_none()


def get_last_member_loan_signing_document(db: Session) -> Optional[MemberLoanSigningDocument]:
    return db.execute(
        select(MemberLoanSigningDocument).order_by(MemberLoanSigningDocument.document_sequence.desc()).limit(1)
    ).scalar_one_or_none()


def list_member_loan_signatures(db: Session, document_id: Optional[UUID] = None) -> list[MemberLoanSignature]:
    statement = select(MemberLoanSignature).order_by(MemberLoanSignature.signature_sequence)
    if document_id is not None:
        statement = statement.where(MemberLoanSignature.document_id == document_id)
    return list(db.execute(statement).scalars())


def get_last_member_loan_signature(db: Session) -> Optional[MemberLoanSignature]:
    return db.execute(select(MemberLoanSignature).order_by(MemberLoanSignature.signature_sequence.desc()).limit(1)).scalar_one_or_none()


def list_member_loan_signed_copies(db: Session) -> list[MemberLoanSignedCopy]:
    return list(db.execute(select(MemberLoanSignedCopy).order_by(MemberLoanSignedCopy.signed_copy_sequence)).scalars())


def get_member_loan_signed_copy_for_document(db: Session, document_id: UUID) -> Optional[MemberLoanSignedCopy]:
    return db.execute(select(MemberLoanSignedCopy).where(MemberLoanSignedCopy.document_id == document_id)).scalar_one_or_none()


def get_member_loan_signed_copy(db: Session, signed_copy_id: UUID) -> Optional[MemberLoanSignedCopy]:
    return db.get(MemberLoanSignedCopy, signed_copy_id)


def get_last_member_loan_signed_copy(db: Session) -> Optional[MemberLoanSignedCopy]:
    return db.execute(
        select(MemberLoanSignedCopy).order_by(MemberLoanSignedCopy.signed_copy_sequence.desc()).limit(1)
    ).scalar_one_or_none()


def list_member_loan_signed_copy_deliveries(db: Session, signed_copy_id: Optional[UUID] = None) -> list[MemberLoanSignedCopyDelivery]:
    statement = select(MemberLoanSignedCopyDelivery).order_by(MemberLoanSignedCopyDelivery.attempted_at)
    if signed_copy_id is not None:
        statement = statement.where(MemberLoanSignedCopyDelivery.signed_copy_id == signed_copy_id)
    return list(db.execute(statement).scalars())


def list_member_loan_statement_signature_reminders(db: Session, statement_month: date) -> list[MemberLoanStatementSignatureReminder]:
    return list(
        db.execute(
            select(MemberLoanStatementSignatureReminder).where(MemberLoanStatementSignatureReminder.statement_month == statement_month)
        ).scalars()
    )


def get_member_loan_signing_request(db: Session, signing_request_id: UUID) -> Optional[MemberLoanSigningRequest]:
    return db.get(MemberLoanSigningRequest, signing_request_id)


def prune_expired_member_loan_signing_requests(db: Session, now) -> None:
    for row in db.execute(select(MemberLoanSigningRequest).where(MemberLoanSigningRequest.expires_at < now)).scalars():
        db.delete(row)
