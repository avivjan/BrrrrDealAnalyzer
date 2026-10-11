"""The monthly statement e-mail command: idempotent, dry-run by default, logged, and it locks the month."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from BL.memberLoan.common.member_loan_statement_sender import send_member_loan_statement
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanAuditEntry, MemberLoanStatementSend
from db import SessionLocal
from tests.member_loan_helpers import (
    LENDER_EMAIL,
    YARDEN_EMAIL,
    approve,
    configure_member_loan_environment,
    enrolled_member_client,
    member_loan_clock,  # noqa: F401  (fixture)
    member_loan_mailbox,  # noqa: F401  (fixture)
    propose,
)


@pytest.fixture(autouse=True)
def _environment(monkeypatch, member_loan_clock, member_loan_mailbox, tmp_path):
    configure_member_loan_environment(monkeypatch)
    monkeypatch.setenv("MEMBER_LOAN_DRY_RUN_DIRECTORY", str(tmp_path / "dry-runs"))
    monkeypatch.delenv("MEMBER_LOAN_EMAIL_DRY_RUN", raising=False)
    member_loan_clock.set(2027, 1, 1, hour=12)  # 7am on Jan 1 in New York: December just ended


@pytest.fixture
def real_sends_enabled(monkeypatch):
    monkeypatch.setenv("MEMBER_LOAN_EMAIL_DRY_RUN", "false")


def _run(**kwargs):
    with SessionLocal() as db:
        return send_member_loan_statement(db, **kwargs)


def _statement_mails(mailbox):
    return [m for m in mailbox.sent if m["subject"].startswith("Member Loan statement")]


def _sends():
    with SessionLocal() as db:
        return list(db.execute(select(MemberLoanStatementSend).order_by(MemberLoanStatementSend.started_at)).scalars())


def _audit_actions():
    with SessionLocal() as db:
        return [r.action for r in db.execute(select(MemberLoanAuditEntry).order_by(MemberLoanAuditEntry.audit_sequence)).scalars()]


def test_dry_run_is_the_default_writes_files_and_sends_nothing(member_loan_mailbox, tmp_path):
    result = _run()
    assert result.outcome == "dry_run" and result.statement_month == date(2026, 12, 1)
    assert _statement_mails(member_loan_mailbox) == []
    assert sorted(p.rsplit(".", 1)[1] for p in result.written_files) == ["html", "pdf", "txt"]
    text = (tmp_path / "dry-runs" / "member-loan-statement-2026-12.txt").read_text()
    assert "Subject: Member Loan statement – December 2026: Amount Owed $31,331.45" in text
    assert "This statement is binding unless either party objects in writing within 30 days" in text
    [send] = _sends()
    assert send.is_dry_run and send.status == "dry_run"
    assert "statement_dry_run" in _audit_actions()
    with SessionLocal() as db:
        assert member_loan_crud.list_months_with_a_sent_member_loan_statement(db) == set()


def test_a_real_send_goes_once_to_both_with_the_pdf(real_sends_enabled, member_loan_mailbox):
    result = _run()
    assert result.outcome == "sent", result.message
    [mail] = _statement_mails(member_loan_mailbox)
    assert list(mail["recipients"]) == [LENDER_EMAIL, YARDEN_EMAIL]
    [attachment] = mail["attachments"]
    assert attachment.filename == "member-loan-statement-2026-12.pdf" and attachment.content.startswith(b"%PDF")
    assert "Objections must be made in writing by Jan 31, 2027" in mail["text_body"]
    [send] = _sends()
    assert send.status == "sent" and send.objection_deadline == date(2027, 1, 31) and len(send.pdf_sha256) == 64
    assert send.statement_snapshot["summary_rows"][-1] == ["Amount Owed on Jan 1", "$31,331.45"]

    again = _run()
    assert again.outcome == "skipped" and "already sent" in again.message
    assert len(_statement_mails(member_loan_mailbox)) == 1
    assert "statement_sent" in _audit_actions()


def test_a_run_that_loses_the_race_sends_nothing(real_sends_enabled, member_loan_mailbox, monkeypatch):
    with SessionLocal() as db:
        from datetime import datetime, timezone
        import uuid

        db.add(MemberLoanStatementSend(
            id=uuid.uuid4(), statement_month=date(2026, 12, 1), is_dry_run=False, status="sending", recipients=[LENDER_EMAIL],
            sender_address="x", statement_snapshot={}, engine_version="1", pdf_sha256="0" * 64, started_at=datetime.now(timezone.utc),
        ))
        db.commit()
    monkeypatch.setattr(member_loan_crud, "list_member_loan_statement_sends", lambda db, month=None: [])  # as if both checked at once
    result = _run()
    assert result.outcome == "skipped" and "Another run" in result.message
    assert _statement_mails(member_loan_mailbox) == []


def test_an_interrupted_send_is_never_repeated_automatically(real_sends_enabled, member_loan_mailbox):
    with SessionLocal() as db:
        from datetime import datetime, timezone
        import uuid

        db.add(MemberLoanStatementSend(
            id=uuid.uuid4(), statement_month=date(2026, 12, 1), is_dry_run=False, status="sending", recipients=[LENDER_EMAIL],
            sender_address="x", statement_snapshot={}, engine_version="1", pdf_sha256="0" * 64, started_at=datetime.now(timezone.utc),
        ))
        db.commit()
    result = _run(retry_failed=True)
    assert result.outcome == "skipped" and "interrupted" in result.message
    assert _statement_mails(member_loan_mailbox) == []


def test_a_failed_send_is_logged_and_only_retried_on_request(real_sends_enabled, member_loan_mailbox):
    member_loan_mailbox.fail_next = 1
    failed = _run()
    assert failed.outcome == "failed"
    assert [s.status for s in _sends()] == ["failed"]
    assert "statement_send_failed" in _audit_actions()
    assert _run().outcome == "skipped"
    retried = _run(retry_failed=True)
    assert retried.outcome == "sent"
    assert len(_statement_mails(member_loan_mailbox)) == 1
    assert _run(retry_failed=True).outcome == "skipped"


def test_a_month_that_is_not_over_is_refused(real_sends_enabled, member_loan_mailbox):
    assert _run(statement_month=date(2027, 1, 1)).outcome == "refused"
    assert _run(statement_month=date(2026, 9, 1)).outcome == "refused"


def test_the_send_locks_the_month_and_expires_its_pending_proposals(real_sends_enabled, member_loan_mailbox):
    aviv, yarden = enrolled_member_client("aviv"), enrolled_member_client("yarden")
    approved = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-15", amount="1000.00").json()["id"]
    approve(yarden, approved)
    pending = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-20", amount="10.00").json()["id"]

    result = _run()
    assert result.outcome == "sent"
    [mail] = _statement_mails(member_loan_mailbox)
    assert "1 proposed change was still waiting for approval" in mail["text_body"]
    assert yarden.get(f"/member-loan/events/{pending}").json()["state"] == "expired"
    assert any("expired" in m["subject"] for m in member_loan_mailbox.sent)

    statement = aviv.get("/member-loan/statements/2026-12").json()
    assert statement["is_final"] is True and statement["objection_deadline"] == "2027-01-31"
    assert statement["sent_to"] == [LENDER_EMAIL, YARDEN_EMAIL]
    locked = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-31", amount="10.00")
    assert locked.status_code == 422 and locked.json()["detail"]["code"] == "month_locked"


def test_the_command_line(tmp_path, member_loan_mailbox):
    import manage

    assert manage.main(["send-member-loan-statement", "--month", "2026-11", "--dry-run", "--output-dir", str(tmp_path / "cli")]) == 0
    assert (tmp_path / "cli" / "member-loan-statement-2026-11.pdf").exists()
    assert _statement_mails(member_loan_mailbox) == []
