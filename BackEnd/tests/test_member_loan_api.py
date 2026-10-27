"""Member Loan API: the two-member gate, two-party approval by signing, the month lock,
append-only storage, the audit trail and the e-mails (tasks/todo/MemberLoan.md and
tasks/todo/MemberLoanSigning.md, Tests > Integration). Signing itself is covered in
`test_member_loan_signing.py`."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from BL.memberLoan.common.member_loan_engine import MEMBER_LOAN_ENGINE_VERSION
from DAL.data_models.memberLoan.models import MemberLoanAuditEntry, MemberLoanEvent, MemberLoanStatementSend
from db import SessionLocal, engine
from tests.member_loan_helpers import (
    COMPANY_EMAIL,
    LENDER_EMAIL,
    WRITE_HEADERS,
    YARDEN_EMAIL,
    approve,
    configure_member_loan_environment,
    start_change_signing,
    enrolled_member_client,
    member_loan_clock,  # noqa: F401  (fixture)
    member_loan_google_drive,  # noqa: F401  (fixture)
    member_loan_mailbox,  # noqa: F401  (fixture)
    propose,
    propose_reversal,
    summary,
)

WITHDRAWAL_ON_DECEMBER_15 = {"event_type": "lender_withdrawal", "effective_date": "2026-12-15", "amount": "1000.00"}


@pytest.fixture(autouse=True)
def _member_loan_environment(monkeypatch, member_loan_clock, member_loan_mailbox, member_loan_google_drive):
    configure_member_loan_environment(monkeypatch)


@pytest.fixture
def aviv() -> TestClient:
    return enrolled_member_client("aviv")


@pytest.fixture
def yarden() -> TestClient:
    return enrolled_member_client("yarden")


def _audit_actions() -> list[str]:
    with SessionLocal() as db:
        return [row.action for row in db.execute(select(MemberLoanAuditEntry).order_by(MemberLoanAuditEntry.audit_sequence)).scalars()]


def _mark_statement_sent(month: date) -> None:
    from datetime import datetime, timezone

    with SessionLocal() as db:
        db.add(MemberLoanStatementSend(
            id=uuid.uuid4(), statement_month=month, is_dry_run=False, status="sent", recipients=[LENDER_EMAIL, YARDEN_EMAIL],
            sender_address="bigwhalesllc@gmail.com", statement_snapshot={}, engine_version=MEMBER_LOAN_ENGINE_VERSION,
            pdf_sha256="0" * 64, proposals_left_out_count=0, started_at=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc), objection_deadline=date(2027, 1, 31),
        ))
        db.commit()


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class TestGate:
    ROUTES = [
        ("GET", "/member-loan/access"),
        ("GET", "/member-loan/summary?as_of_date=2026-12-15"),
        ("GET", "/member-loan/ledger?through_date=2026-12-15"),
        ("GET", "/member-loan/ledger.csv?through_date=2026-12-15"),
        ("GET", "/member-loan/events"),
        ("GET", "/member-loan/statements/2026-11"),
        ("GET", "/member-loan/statements/2026-11/pdf"),
        ("GET", "/member-loan/audit"),
        ("GET", "/member-loan/integrity"),
        ("GET", "/member-loan/explanation"),
        ("POST", "/member-loan/events"),
        ("POST", "/member-loan/event-previews"),
        ("POST", "/member-loan/change-documents"),
        ("POST", f"/member-loan/events/{uuid.uuid4()}/reversal-documents"),
        ("GET", "/member-loan/documents"),
        ("GET", f"/member-loan/documents/{uuid.uuid4()}"),
        ("GET", f"/member-loan/documents/{uuid.uuid4()}/pdf"),
        ("GET", f"/member-loan/documents/{uuid.uuid4()}/signed-pdf"),
        ("POST", f"/member-loan/documents/{uuid.uuid4()}/signing-requests"),
        ("GET", f"/member-loan/signing-requests/{uuid.uuid4()}/pdf"),
        ("POST", f"/member-loan/signing-requests/{uuid.uuid4()}/passkey-options"),
        ("POST", f"/member-loan/signing-requests/{uuid.uuid4()}/signature"),
        ("POST", f"/member-loan/events/{uuid.uuid4()}/approval"),
        ("POST", f"/member-loan/events/{uuid.uuid4()}/rejection"),
        ("POST", f"/member-loan/events/{uuid.uuid4()}/cancellation"),
        ("POST", f"/member-loan/events/{uuid.uuid4()}/reversal"),
    ]

    @pytest.mark.parametrize("auth_mode", ["off", "shadow", "enforce"])
    def test_every_route_needs_a_session_whatever_auth_mode_says(self, client, monkeypatch, auth_mode):
        monkeypatch.setenv("AUTH_MODE", auth_mode)
        for method, path in self.ROUTES:
            assert client.request(method, path, headers=WRITE_HEADERS).status_code == 401, path

    def test_a_third_owner_is_refused_and_audited(self, aviv, yarden):
        outsider = enrolled_member_client("someone_else")
        response = outsider.get("/member-loan/access")
        assert response.status_code == 403 and response.json()["detail"] == "member_loan_access_denied"
        from DAL.data_models.audit.models import AuditLog

        with SessionLocal() as db:
            assert db.execute(select(AuditLog).where(AuditLog.event == "member_loan_access_denied")).scalars().first() is not None

    def test_the_two_members_are_allowed_with_their_roles(self, aviv, yarden):
        assert aviv.get("/member-loan/access").json()["role"] == "lender"
        body = yarden.get("/member-loan/access").json()
        assert body["role"] == "yarden" and body["other_member_display_name"] == "Aviv"

    def test_a_bad_configuration_fails_closed(self, aviv, monkeypatch):
        monkeypatch.setenv("MEMBER_LOAN_ALLOWED_USERNAMES", "aviv,yarden,mallory")
        assert aviv.get("/member-loan/access").status_code == 503

    def test_writes_need_the_csrf_headers(self, aviv, yarden):
        response = aviv.post("/member-loan/change-documents", json=WITHDRAWAL_ON_DECEMBER_15)
        assert response.status_code == 403 and response.json()["detail"].startswith("csrf")
        cross_site = aviv.post("/member-loan/change-documents", json=WITHDRAWAL_ON_DECEMBER_15,
                               headers={**WRITE_HEADERS, "Origin": "https://evil.example"})
        assert cross_site.status_code == 403

    def test_reject_and_cancel_need_a_recent_passkey_prompt_while_signing_carries_its_own(self, aviv, yarden):
        from tests.test_devices import _age_sessions

        first = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        _age_sessions()
        rejection = yarden.post(f"/member-loan/events/{first}/rejection", json={"reason": "no"}, headers=WRITE_HEADERS)
        assert rejection.status_code == 403 and rejection.json()["detail"] == "reauth_required"
        assert aviv.post(f"/member-loan/events/{first}/cancellation", headers=WRITE_HEADERS).json()["detail"] == "reauth_required"
        assert approve(yarden, first).status_code == 200  # the signature's own passkey assertion is the fresh prompt

    def test_writes_are_rate_limited(self, aviv, yarden, monkeypatch):
        monkeypatch.setenv("MEMBER_LOAN_WRITES_PER_HOUR", "6")  # a signed proposal is three writes
        assert propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).status_code == 201
        assert propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).status_code == 201
        assert propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).status_code == 429

    def test_the_old_unsigned_routes_are_gone(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        for path, body in (("/member-loan/events", WITHDRAWAL_ON_DECEMBER_15),
                           (f"/member-loan/events/{event_id}/approval", {"preview_fingerprint": "0" * 64}),
                           (f"/member-loan/events/{event_id}/reversal", {"reason": "old route"})):
            response = yarden.post(path, json=body, headers=WRITE_HEADERS)
            assert response.status_code == 410 and response.json()["detail"]["code"] == "signing_required", path
        assert yarden.get(f"/member-loan/events/{event_id}").json()["state"] == "pending"

    def test_the_mcp_connector_has_no_member_loan_tool(self):
        import mcp_server

        assert not any("member" in name or "loan" in name for name in mcp_server.tools())


# ---------------------------------------------------------------------------
# Two-party approval
# ---------------------------------------------------------------------------


class TestApproval:
    def test_a_proposal_changes_nothing_until_the_other_member_approves(self, aviv, yarden):
        proposal = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15)
        assert proposal.status_code == 201, proposal.text
        body = proposal.json()
        assert body["state"] == "pending" and body["caller_may_cancel"] and not body["caller_may_sign_or_reject"]
        assert body["preview_at_proposal"]["buckets_after"]["amount_owed"] == "30166.01"
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "31166.01"

        approved = approve(yarden, body["id"])
        assert approved.status_code == 200, approved.text
        assert approved.json()["state"] == "approved"
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "30166.01"
        assert summary(aviv, "2027-01-01")["buckets"]["total_balance"] == "30326.90"

    def test_the_proposer_cannot_approve_or_reject_their_own_change(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        response = approve(aviv, event_id)
        assert response.status_code == 403 and response.json()["detail"]["code"] == "not_the_counterparty"
        response = aviv.post(f"/member-loan/events/{event_id}/rejection", json={"reason": "no"}, headers=WRITE_HEADERS)
        assert response.status_code == 403

    def test_only_the_proposer_can_cancel(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        assert yarden.post(f"/member-loan/events/{event_id}/cancellation", headers=WRITE_HEADERS).status_code == 403
        cancelled = aviv.post(f"/member-loan/events/{event_id}/cancellation", headers=WRITE_HEADERS)
        assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
        again = aviv.post(f"/member-loan/events/{event_id}/cancellation", headers=WRITE_HEADERS)
        assert again.status_code == 409 and again.json()["detail"]["code"] == "already_decided"

    def test_rejection_needs_a_reason_and_changes_nothing(self, aviv, yarden):
        event_id = propose(yarden, event_type="lender_additional_advance", effective_date="2026-12-10", amount="5000.00",
                           written_agreement_date="2026-12-09", written_agreement_description="Both agreed by e-mail").json()["id"]
        assert aviv.post(f"/member-loan/events/{event_id}/rejection", json={"reason": ""}, headers=WRITE_HEADERS).status_code == 422
        rejected = aviv.post(f"/member-loan/events/{event_id}/rejection", json={"reason": "Not agreed"}, headers=WRITE_HEADERS)
        assert rejected.status_code == 200 and rejected.json()["state"] == "rejected"
        assert rejected.json()["decision_reason"] == "Not agreed"
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "31166.01"

    def test_a_second_decision_is_refused(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        assert approve(yarden, event_id).status_code == 200
        second = yarden.post(f"/member-loan/events/{event_id}/rejection", json={"reason": "late"}, headers=WRITE_HEADERS)
        assert second.status_code == 409

    def test_the_one_decision_rule_holds_in_the_database_too(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO member_loan_event_decisions (id, decision_sequence, event_id, decision, decided_by_username, "
                    "decided_at, previous_decision_hash, decision_hash) VALUES (:id, 99, :event_id, 'rejected', 'x', now(), 'a', 'b')"
                ), {"id": uuid.uuid4(), "event_id": uuid.UUID(event_id)})

    def test_a_record_whose_figures_changed_expires_and_cannot_be_signed(self, aviv, yarden, member_loan_mailbox):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        earlier = propose(yarden, event_type="lender_additional_advance", effective_date="2026-12-02", amount="100.00",
                          written_agreement_date="2026-12-01", written_agreement_description="Signed note").json()["id"]
        assert approve(aviv, earlier).status_code == 200
        stale = yarden.get(f"/member-loan/events/{event_id}").json()
        assert stale["state"] == "expired" and "figures on its Loan Change Record changed" in stale["decision_reason"]
        assert approve(yarden, event_id).status_code == 409
        assert any("expired" in m["subject"] for m in member_loan_mailbox.to(LENDER_EMAIL))
        assert propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).status_code == 201  # proposed again on the new figures

    def test_a_change_that_would_break_a_later_approved_change_expires(self, aviv, yarden):
        later = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-18", amount="31000.00").json()["id"]
        earlier = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-10", amount="1000.00").json()["id"]
        assert approve(yarden, later).status_code == 200
        assert yarden.get(f"/member-loan/events/{earlier}").json()["state"] == "expired"
        assert approve(yarden, earlier).status_code == 409

    def test_a_proposal_that_cannot_be_applied_now_is_refused(self, aviv, yarden):
        response = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-15", amount="40000.00")
        assert response.status_code == 422 and "more than" in response.json()["detail"]["message"]

    def test_reversal_needs_approval_and_the_original_stays_until_then(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        reversal = propose_reversal(yarden, event_id, reason="Entered twice")
        assert reversal.status_code == 201, reversal.text
        assert reversal.json()["reversed_event_summary"].startswith("Withdrawal by Aviv of $1,000.00")
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "30166.01"
        assert propose_reversal(aviv, event_id, reason="again").status_code == 409
        assert approve(aviv, reversal.json()["id"]).status_code == 200
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "31166.01"
        assert propose_reversal(aviv, event_id, reason="third").status_code == 409

    def test_pending_proposals_expire_after_14_days(self, aviv, yarden, member_loan_clock, member_loan_mailbox):
        member_loan_clock.set(2026, 12, 2)
        event_id = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-02", amount="10.00").json()["id"]
        member_loan_clock.advance_days(14)
        body = yarden.get(f"/member-loan/events/{event_id}").json()
        assert body["state"] == "expired" and body["decided_by_display_name"] == "the system"
        assert approve_after_expiry_is_refused(yarden, event_id)
        assert "event_expired" in _audit_actions()
        assert any("expired" in m["subject"] for m in member_loan_mailbox.to(LENDER_EMAIL))

    def test_required_fields_by_event_type(self, aviv, yarden):
        assert propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-15").status_code == 422
        no_agreement = propose(aviv, event_type="yarden_additional_withdrawal_increase", effective_date="2026-12-15", amount="10.00")
        assert no_agreement.status_code == 422 and no_agreement.json()["detail"]["code"] == "written_agreement_required"
        assert propose(aviv, event_type="interest_payment_election", effective_date="2027-01-01").status_code == 422
        assert propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-15", amount="10.001").status_code == 422
        assert propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-15", amount=1000).status_code == 422
        assert propose(aviv, event_type="interest_payment_election", effective_date="2027-01-05", interest_election_choice="cash").status_code == 422

    def test_an_advance_may_fall_on_any_day(self, aviv, yarden):
        event_id = propose(aviv, event_type="lender_additional_advance", effective_date="2026-12-10", amount="5000.00",
                           written_agreement_date="2026-12-09", written_agreement_description="Signed note").json()["id"]
        assert approve(yarden, event_id).status_code == 200
        assert summary(aviv, "2026-12-10")["buckets"]["original_principal"] == "35410.00"


def approve_after_expiry_is_refused(member_client, event_id) -> bool:
    return approve(member_client, event_id).status_code == 409


# ---------------------------------------------------------------------------
# The month lock and the future-date limit
# ---------------------------------------------------------------------------


class TestDatesAndLock:
    def test_a_month_stays_open_until_its_statement_is_sent(self, aviv, yarden, member_loan_clock):
        member_loan_clock.set(2027, 1, 1, hour=12)  # Jan 1 in New York, statement not sent yet
        event_id = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-31", amount="10.00").json()["id"]
        assert approve(yarden, event_id).status_code == 200

    def test_after_the_send_the_month_is_locked_and_its_proposals_expire(self, aviv, yarden, member_loan_clock):
        member_loan_clock.set(2027, 1, 1, hour=12)
        approved_id = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-31", amount="10.00").json()["id"]
        approve(yarden, approved_id)
        pending_id = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-30", amount="10.00").json()["id"]
        _mark_statement_sent(date(2026, 12, 1))

        locked = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-31", amount="10.00")
        assert locked.status_code == 422 and locked.json()["detail"]["code"] == "month_locked"
        assert yarden.get(f"/member-loan/events/{pending_id}").json()["state"] == "expired"
        assert propose_reversal(yarden, approved_id, reason="wrong").status_code == 422
        assert propose(aviv, event_type="lender_withdrawal", effective_date="2027-01-01", amount="10.00").status_code == 201

    def test_the_interest_choice_for_jan_1_belongs_to_december(self, aviv, yarden, member_loan_clock):
        member_loan_clock.set(2027, 1, 1, hour=12)
        _mark_statement_sent(date(2026, 12, 1))
        response = propose(aviv, event_type="interest_payment_election", effective_date="2027-01-01", interest_election_choice="cash")
        assert response.status_code == 422 and response.json()["detail"]["code"] == "month_locked"

    def test_a_dry_run_does_not_lock(self, aviv, yarden, member_loan_clock):
        member_loan_clock.set(2027, 1, 1, hour=12)
        from datetime import datetime, timezone

        with SessionLocal() as db:
            db.add(MemberLoanStatementSend(
                id=uuid.uuid4(), statement_month=date(2026, 12, 1), is_dry_run=True, status="sent", recipients=[],
                sender_address="x", statement_snapshot={}, engine_version="1", pdf_sha256="0" * 64,
                started_at=datetime.now(timezone.utc),
            ))
            db.commit()
        assert propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-31", amount="10.00").status_code == 201

    def test_dates_after_tomorrow_in_new_york_are_refused(self, aviv, yarden, member_loan_clock):
        member_loan_clock.set(2026, 12, 20, hour=15)
        assert propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-21", amount="10.00").status_code == 201
        future = propose(aviv, event_type="lender_withdrawal", effective_date="2026-12-22", amount="10.00")
        assert future.status_code == 422 and future.json()["detail"]["code"] == "date_in_future"


# ---------------------------------------------------------------------------
# Append-only storage, hash chains and the audit trail
# ---------------------------------------------------------------------------


class TestHistoryCannotBeRewritten:
    @pytest.mark.parametrize("statement", [
        "UPDATE member_loan_events SET amount = 1",
        "DELETE FROM member_loan_events",
        "UPDATE member_loan_event_decisions SET decision = 'rejected'",
        "DELETE FROM member_loan_audit_entries",
    ])
    def test_the_database_refuses_edits_and_deletes(self, aviv, yarden, statement):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as connection:
                connection.execute(text(statement))

    def test_a_statement_send_may_only_move_out_of_sending(self):
        from datetime import datetime, timezone
        from sqlalchemy.exc import DBAPIError

        send_id = uuid.uuid4()
        with SessionLocal() as db:
            db.add(MemberLoanStatementSend(
                id=send_id, statement_month=date(2026, 10, 1), is_dry_run=False, status="sending", recipients=["a"],
                sender_address="x", statement_snapshot={}, engine_version="1", pdf_sha256="0" * 64, started_at=datetime.now(timezone.utc),
            ))
            db.commit()
        with engine.begin() as connection:
            connection.execute(text("UPDATE member_loan_statement_sends SET status = 'sent', sent_at = now() WHERE id = :id"), {"id": send_id})
        for statement in ("UPDATE member_loan_statement_sends SET status = 'failed'", "DELETE FROM member_loan_statement_sends",
                          "UPDATE member_loan_statement_sends SET pdf_sha256 = 'x'"):
            with pytest.raises(DBAPIError):
                with engine.begin() as connection:
                    connection.execute(text(statement))

    def test_integrity_check_finds_a_row_changed_behind_the_app(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        assert aviv.get("/member-loan/integrity").json()["intact"] is True
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE member_loan_events DISABLE TRIGGER member_loan_events_append_only"))
            connection.execute(text("UPDATE member_loan_events SET amount = 1.00"))
            connection.execute(text("ALTER TABLE member_loan_events ENABLE TRIGGER member_loan_events_append_only"))
        result = aviv.get("/member-loan/integrity").json()
        assert result["intact"] is False and any("changed after it was written" in p for p in result["problems"])

    def test_every_write_has_one_audit_entry_with_the_state_before_and_after(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        with SessionLocal() as db:
            rows = list(db.execute(select(MemberLoanAuditEntry).order_by(MemberLoanAuditEntry.audit_sequence)).scalars())
        proposal_rows = [r for r in rows if r.action == "event_proposed"]
        approval_rows = [r for r in rows if r.action == "event_approved"]
        assert len(proposal_rows) == 1 and len(approval_rows) == 1
        assert approval_rows[0].actor_username == "yarden"
        assert approval_rows[0].state_before["amount_owed"] == "31166.01"
        assert approval_rows[0].state_after["amount_owed"] == "30166.01"
        audit = aviv.get("/member-loan/audit").json()
        assert {"event_proposed", "document_signed", "event_approved", "document_fully_signed", "proposal_notification_sent",
                "signed_copy_emailed", "signed_copy_saved_to_drive"} <= {e["action"] for e in audit}


# ---------------------------------------------------------------------------
# E-mails
# ---------------------------------------------------------------------------


class TestNotifications:
    def test_a_proposal_asks_only_the_other_member_to_sign_with_a_link_and_no_token(self, aviv, yarden, member_loan_mailbox):
        proposal = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        assert member_loan_mailbox.to(LENDER_EMAIL) == []
        [message] = member_loan_mailbox.to(YARDEN_EMAIL)
        assert message["recipients"] == (YARDEN_EMAIL,) and message["subject"] == "whales loan update – please sign"
        assert f"https://bigwhales.example/member-loan/sign/{proposal['signing_document_id']}" in message["text_body"]
        assert "token" not in message["text_body"].lower()
        assert "$31,166.01" in message["text_body"] and "$30,166.01" in message["text_body"]
        assert "does not sign anything by itself" in message["text_body"]
        [attachment] = message["attachments"]
        assert attachment.filename == "loan-change-record-1.pdf" and attachment.content.startswith(b"%PDF")

    def test_the_signed_copy_goes_to_all_three_addresses_and_to_drive(self, aviv, yarden, member_loan_mailbox, member_loan_google_drive):
        event_id = propose(yarden, event_type="yarden_additional_withdrawal_increase", effective_date="2026-12-15", amount="2000.00",
                           written_agreement_date="2026-12-14", written_agreement_description="Side letter signed by both").json()["id"]
        approve(aviv, event_id)
        [signed] = [m for m in member_loan_mailbox.sent if m["subject"] == "whales loan update"]
        assert signed["recipients"] == [LENDER_EMAIL, YARDEN_EMAIL, COMPANY_EMAIL]
        for expected in ("Loan Change Record No. 1 – Additional withdrawal by Yarden Kelly", "Signed by Yarden Kelly", "Signed by Aviv Jan"):
            assert expected in signed["text_body"], expected
        [attachment] = signed["attachments"]
        assert attachment.filename.endswith("whales loan update #1 – Additional withdrawal by Yarden Kelly $2,000.00 – signed.pdf")
        assert [name for name, _ in member_loan_google_drive.saved] == [attachment.filename]
        assert member_loan_google_drive.saved[0][1] == attachment.content
        assert not [m for m in member_loan_mailbox.sent if "approved" in m["subject"]]  # the signed copy replaces it

    @pytest.mark.parametrize("decision", ["rejection", "cancellation"])
    def test_rejection_and_cancellation_mail_both(self, aviv, yarden, member_loan_mailbox, decision):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        actor = yarden if decision == "rejection" else aviv
        actor.post(f"/member-loan/events/{event_id}/{decision}", json={"reason": "No"} if decision == "rejection" else None, headers=WRITE_HEADERS)
        decided = [m for m in member_loan_mailbox.sent if ("rejected" in m["subject"] or "cancelled" in m["subject"])]
        assert len(decided) == 1 and set(decided[0]["recipients"]) == {LENDER_EMAIL, YARDEN_EMAIL}
        assert "Nothing changed" in decided[0]["text_body"]

    def test_a_failed_e_mail_keeps_the_change_and_is_audited(self, aviv, yarden, member_loan_mailbox):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        member_loan_mailbox.fail_next = 1
        assert approve(yarden, event_id).status_code == 200
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "30166.01"
        assert "signed_copy_email_failed" in _audit_actions() and "signed_copy_saved_to_drive" in _audit_actions()

    def test_a_reversal_proposal_and_its_approval_are_mailed(self, aviv, yarden, member_loan_mailbox):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        reversal_id = propose_reversal(yarden, event_id, reason="Entered twice").json()["id"]
        assert any("It reverses: Withdrawal by Aviv" in m["text_body"] for m in member_loan_mailbox.to(LENDER_EMAIL))
        approve(aviv, reversal_id)
        signed = [m for m in member_loan_mailbox.sent if m["subject"] == "whales loan update"]
        assert len(signed) == 2 and "Loan Change Record No. 2 – Reversal of an earlier change" in signed[-1]["text_body"]


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


class TestReads:
    def test_a_preview_shows_the_figures_and_writes_nothing(self, aviv, yarden):
        response = aviv.post("/member-loan/event-previews", json=WITHDRAWAL_ON_DECEMBER_15, headers=WRITE_HEADERS)
        assert response.status_code == 200, response.text
        assert response.json()["buckets_after"]["amount_owed"] == "30166.01"
        assert response.json()["allocation"]["from_capitalized_interest"] == "611.24"
        assert aviv.get("/member-loan/events").json() == []
        assert _audit_actions() == []
        refused = aviv.post("/member-loan/event-previews", json={**WITHDRAWAL_ON_DECEMBER_15, "amount": "99999.00"}, headers=WRITE_HEADERS)
        assert refused.status_code == 422 and "more than" in refused.json()["detail"]["message"]

    def test_summary_needs_an_explicit_date(self, aviv, yarden):
        assert aviv.get("/member-loan/summary").status_code == 422
        assert summary(aviv, "2026-12-15")["buckets"]["accrued_interest"] == "144.77"

    def test_ledger_rows_show_who_proposed_and_approved(self, aviv, yarden):
        event_id = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"]
        approve(yarden, event_id)
        rows = aviv.get("/member-loan/ledger", params={"through_date": "2027-01-01"}).json()["rows"]
        assert [r["row_kind"] for r in rows] == ["loan_start", "interest_date", "interest_date", "lender_withdrawal", "interest_date"]
        withdrawal = rows[3]
        assert withdrawal["proposed_by_display_name"] == "Aviv" and withdrawal["approved_by_display_name"] == "Yarden"
        assert rows[-1]["buckets_after"]["total_balance"] == "30326.90"

    def test_csv_export_neutralises_formulas(self, aviv, yarden):
        response = aviv.get("/member-loan/ledger.csv", params={"through_date": "2026-12-15"})
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
        lines = response.text.splitlines()
        assert lines[0].startswith("date,what happened,amount")
        assert lines[-1].startswith("2026-12-01,Interest for November added to the debt ($307.14)")
        from BL.memberLoan.exportLedgerCsv import neutralise_spreadsheet_formula

        assert neutralise_spreadsheet_formula("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
        assert neutralise_spreadsheet_formula("aviv") == "aviv"

    def test_statement_json_and_pdf(self, aviv, yarden):
        statement = aviv.get("/member-loan/statements/2026-11").json()
        assert statement["is_final"] is False
        assert statement["document"]["summary_rows"][-1] == ["Amount Owed on Dec 1", "$31,021.24"]
        pdf = aviv.get("/member-loan/statements/2026-11/pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert aviv.get("/member-loan/statements/2026-09").status_code == 422
        assert aviv.get("/member-loan/statements/2027-06").status_code == 422

    def test_explanation_lists_the_formulas(self, aviv, yarden):
        lines = aviv.get("/member-loan/explanation").json()["lines"]
        assert any("12% a year" in line for line in lines) and any("Feb 28 counts 3 days" in line for line in lines)

    def test_waiting_counts(self, aviv, yarden):
        propose(aviv, **WITHDRAWAL_ON_DECEMBER_15)
        assert yarden.get("/member-loan/access").json()["proposals_waiting_for_you"] == 1
        assert yarden.get("/member-loan/access").json()["documents_waiting_for_your_signature"] == 1
        assert aviv.get("/member-loan/access").json()["proposals_waiting_for_you"] == 0
        assert aviv.get("/member-loan/access").json()["documents_waiting_for_your_signature"] == 0
        assert summary(aviv, "2026-12-15")["proposals_waiting_for_other_member"] == 1
        assert [e["state"] for e in yarden.get("/member-loan/events", params={"state": "pending"}).json()] == ["pending"]
