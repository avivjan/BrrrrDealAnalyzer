"""Member Loan tables (tasks/todo/MemberLoan.md, Data model).

Every table is append-only: a Postgres trigger refuses UPDATE and DELETE
(`migrations/steps/member_loan_append_only_triggers.py`). The one exception
is a statement send, whose `status` may move once out of `sending`.

A proposal never changes: its state comes from the single decision row that
may follow it (unique `event_id`). Proposals, decisions and audit entries each
carry a SHA-256 hash chain (`previous_*_hash` -> `*_hash`) so an edit made
directly in the database is detectable (`GET /member-loan/integrity`).
"""

import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    and_,
    false,
    literal,
)

from db import Base

MEMBER_LOAN_APPEND_ONLY_TABLE_NAMES = (
    "member_loan_events",
    "member_loan_event_decisions",
    "member_loan_audit_entries",
    "member_loan_statement_sends",
)


class MemberLoanEvent(Base):
    """One proposed change to the loan. Pending until a decision row exists."""

    __tablename__ = "member_loan_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_sequence = Column(BigInteger, nullable=False, unique=True)
    event_type = Column(String(64), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=True)
    interest_election_choice = Column(String(16), nullable=True)
    written_agreement_date = Column(Date, nullable=True)
    written_agreement_description = Column(String(500), nullable=True)
    payment_reference = Column(String(200), nullable=True)
    note = Column(String(1000), nullable=True)
    reverses_event_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_events.id"), nullable=True, index=True)
    reversal_reason = Column(String(500), nullable=True)
    proposed_by_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    proposed_by_username = Column(String(64), nullable=False)
    proposed_at = Column(DateTime(timezone=True), nullable=False)
    request_ip = Column(String(64), nullable=True)
    preview_at_proposal = Column(JSON, nullable=False)
    preview_fingerprint_at_proposal = Column(String(64), nullable=False)
    previous_event_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False, unique=True)


class MemberLoanEventDecision(Base):
    """approved | rejected | cancelled | expired -- at most one per proposal."""

    __tablename__ = "member_loan_event_decisions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_sequence = Column(BigInteger, nullable=False, unique=True)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_events.id"), nullable=False, unique=True)
    decision = Column(String(16), nullable=False)
    # NULL for the system (expiry); `decided_by_username` is then "system".
    decided_by_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    decided_by_username = Column(String(64), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=False)
    decision_reason = Column(String(500), nullable=True)
    preview_fingerprint_confirmed = Column(String(64), nullable=True)
    preview_at_decision = Column(JSON, nullable=True)
    previous_decision_hash = Column(String(64), nullable=False)
    decision_hash = Column(String(64), nullable=False, unique=True)


class MemberLoanAuditEntry(Base):
    __tablename__ = "member_loan_audit_entries"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_sequence = Column(BigInteger, nullable=False, unique=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    actor_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_username = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False, index=True)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_events.id"), nullable=True, index=True)
    state_before = Column(JSON, nullable=True)
    state_after = Column(JSON, nullable=True)
    detail = Column(JSON, nullable=True)
    request_ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    previous_audit_hash = Column(String(64), nullable=False)
    audit_hash = Column(String(64), nullable=False, unique=True)


class MemberLoanStatementSend(Base):
    """One attempt to e-mail a month's statement, or a dry run.

    The partial unique index allows one live real send (`sending` or `sent`)
    per month. A `failed` row does not block `--retry-failed`; dry runs never
    count.
    """

    __tablename__ = "member_loan_statement_sends"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_month = Column(Date, nullable=False, index=True)
    is_dry_run = Column(Boolean, nullable=False)
    status = Column(String(16), nullable=False)  # sending | sent | failed
    recipients = Column(JSON, nullable=False)
    sender_address = Column(String(320), nullable=False)
    statement_snapshot = Column(JSON, nullable=False)
    engine_version = Column(String(16), nullable=False)
    pdf_sha256 = Column(String(64), nullable=False)
    proposals_left_out_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    objection_deadline = Column(Date, nullable=True)
    error_text = Column(String(500), nullable=True)

    __table_args__ = (
        Index(
            "uq_member_loan_statement_sends_one_live_real_send_per_month",
            "statement_month",
            unique=True,
            postgresql_where=and_(is_dry_run == false(), status != literal("failed")),
        ),
    )
