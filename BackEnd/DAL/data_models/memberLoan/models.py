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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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
    "member_loan_signing_documents",
    "member_loan_signatures",
    "member_loan_signed_copies",
    "member_loan_signed_copy_deliveries",
    "member_loan_statement_signature_reminders",
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


# -- e-signing (tasks/todo/MemberLoanSigning.md) --------------------------------


class MemberLoanSigningDocument(Base):
    """A document the members sign: one Loan Change Record per proposal, or one
    statement per sent month. The PDF never changes once written; its SHA-256 is
    what every passkey signature on it covers."""

    __tablename__ = "member_loan_signing_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_sequence = Column(BigInteger, nullable=False, unique=True)
    document_kind = Column(String(32), nullable=False)  # loan_change | monthly_statement
    event_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_events.id"), nullable=True, unique=True)
    statement_month = Column(Date, nullable=True, unique=True)
    title = Column(String(300), nullable=False)
    document_content = Column(JSON, nullable=False)
    unsigned_pdf = Column(LargeBinary, nullable=False)
    unsigned_pdf_sha256 = Column(String(64), nullable=False)
    required_signer_usernames = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    previous_document_hash = Column(String(64), nullable=False)
    document_hash = Column(String(64), nullable=False, unique=True)


class MemberLoanSignature(Base):
    """One member's signature (or signed objection) on one document, with the
    passkey assertion over the document's SHA-256 kept as evidence."""

    __tablename__ = "member_loan_signatures"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signature_sequence = Column(BigInteger, nullable=False, unique=True)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_signing_documents.id"), nullable=False, index=True)
    signer_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    signer_username = Column(String(64), nullable=False)
    signer_role = Column(String(64), nullable=False)
    signature_meaning = Column(String(16), nullable=False)  # signed | objected
    objection_reason = Column(String(1000), nullable=True)
    typed_full_legal_name = Column(String(200), nullable=False)
    signature_statement_text = Column(Text, nullable=False)
    drawn_signature_png = Column(LargeBinary, nullable=False)
    signed_document_sha256 = Column(String(64), nullable=False)
    webauthn_credential_id = Column(String(512), nullable=False)
    webauthn_authenticator_data = Column(Text, nullable=False)
    webauthn_client_data_json = Column(Text, nullable=False)
    webauthn_signature = Column(Text, nullable=False)
    # The challenge the passkey signed was SHA-256("<signed_document_sha256>:<nonce>").
    passkey_challenge_nonce = Column(String(64), nullable=False)
    request_ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    device_id = Column(Uuid(as_uuid=True), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=False)
    previous_signature_hash = Column(String(64), nullable=False)
    signature_hash = Column(String(64), nullable=False, unique=True)

    __table_args__ = (UniqueConstraint("document_id", "signer_username", name="uq_member_loan_signatures_one_per_signer"),)


class MemberLoanSignedCopy(Base):
    """The finished copy once every required member has acted: the unsigned
    pages plus a signature certificate page."""

    __tablename__ = "member_loan_signed_copies"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signed_copy_sequence = Column(BigInteger, nullable=False, unique=True)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_signing_documents.id"), nullable=False, unique=True)
    signed_pdf = Column(LargeBinary, nullable=False)
    signed_pdf_sha256 = Column(String(64), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    previous_signed_copy_hash = Column(String(64), nullable=False)
    signed_copy_hash = Column(String(64), nullable=False, unique=True)


class MemberLoanSignedCopyDelivery(Base):
    """One attempt to e-mail a signed copy or save it to Google Drive. A retry
    is a new row; the newest row per channel is the current state."""

    __tablename__ = "member_loan_signed_copy_deliveries"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signed_copy_id = Column(Uuid(as_uuid=True), ForeignKey("member_loan_signed_copies.id"), nullable=False, index=True)
    delivery_channel = Column(String(16), nullable=False)  # email | google_drive
    delivery_status = Column(String(16), nullable=False)  # sent | failed
    external_file_id = Column(String(200), nullable=True)
    error_text = Column(String(500), nullable=True)
    attempted_at = Column(DateTime(timezone=True), nullable=False)


class MemberLoanStatementSignatureReminder(Base):
    """One day's request to sign a statement, claimed before the e-mail goes out;
    the unique key keeps it to one a day (a failed send is in the audit trail)."""

    __tablename__ = "member_loan_statement_signature_reminders"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_month = Column(Date, nullable=False)
    recipient_username = Column(String(64), nullable=False)
    reminder_date = Column(Date, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("statement_month", "recipient_username", "reminder_date", name="uq_member_loan_statement_reminder_once_a_day"),
    )


class MemberLoanSigningRequest(Base):
    """A member's signing in progress (mutable, short-lived, single use).

    It pins the exact PDF being signed: a draft Loan Change Record (no event
    exists yet) or an existing document. The passkey challenge is derived from
    `document_sha256`, so the assertion proves which document was signed."""

    __tablename__ = "member_loan_signing_requests"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    username = Column(String(64), nullable=False)
    signing_purpose = Column(String(32), nullable=False)  # propose_change | propose_reversal | sign_document
    # No foreign key: the test harness TRUNCATEs the append-only tables, which
    # a reference from this ordinary table would block.
    document_id = Column(Uuid(as_uuid=True), nullable=True)
    proposal_draft = Column(JSON, nullable=True)
    draft_document_content = Column(JSON, nullable=True)
    draft_pdf = Column(LargeBinary, nullable=True)
    document_sha256 = Column(String(64), nullable=False)
    signature_meaning = Column(String(16), nullable=False)
    objection_reason = Column(String(1000), nullable=True)
    signer_role = Column(String(64), nullable=False)
    signature_statement_text = Column(Text, nullable=False)
    passkey_challenge_id = Column(Uuid(as_uuid=True), nullable=True)
    passkey_challenge_nonce = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
