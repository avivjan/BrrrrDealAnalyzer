"""Signing in the Software (tasks/todo/MemberLoanSigning.md, Tests): the Loan Change
Record and statement wording, the passkey bound to the document, proposing and
approving by signature, statements signed or objected to, the daily reminders,
the signed copy's e-mail and Google Drive delivery, and the changeover."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select, text

from BL.memberLoan.common import member_loan_google_drive as google_drive_upload_module
from BL.memberLoan.common import member_loan_settings
from BL.memberLoan.common.member_loan_access import MemberLoanMember, MemberLoanMembers
from BL.memberLoan.common.member_loan_engine import DEFAULT_MEMBER_LOAN_TERMS, EffectiveMemberLoanEvent, preview_member_loan_event
from BL.memberLoan.common.member_loan_ledger_service import (
    EXPIRY_REASON_SIGNING_REPLACED_APPROVAL,
    append_proposed_member_loan_event,
    load_member_loan_ledger_snapshot,
)
from BL.memberLoan.common.member_loan_signed_copy_delivery import (
    AUTOMATIC_DELIVERY_ATTEMPTS,
    retry_failed_signed_copy_deliveries,
    signed_copy_file_name,
)
from BL.memberLoan.common.member_loan_signing_ceremony import (
    decode_drawn_signature_png,
    normalized_legal_name,
    passkey_assertion_is_bound_to_document,
)
from BL.memberLoan.common.member_loan_signing_documents import (
    build_loan_change_document_content,
    build_statement_signing_document_content,
)
from BL.memberLoan.common.member_loan_signing_pdf import render_loan_change_record_pdf
from BL.memberLoan.common.member_loan_statement_sender import send_member_loan_statement
from BL.memberLoan.common.member_loan_statement_signing import send_due_statement_signature_reminders
from BL.memberLoan.common.member_loan_ledger_service import MemberLoanRequestRefused
from DAL.crud import member_loan as member_loan_crud
from DAL.data_models.memberLoan.models import MemberLoanSignature, MemberLoanSignedCopyDelivery
from db import SessionLocal, engine
from ReqRes.common.member_loan_schemas import MemberLoanProposalCreateReq
from tests.member_loan_helpers import (
    COMPANY_EMAIL,
    DRAWN_SIGNATURE_PNG_BASE64,
    LENDER_EMAIL,
    YARDEN_EMAIL,
    approve,
    configure_member_loan_environment,
    drawn_signature_png,
    enrolled_member_client,
    member_loan_clock,  # noqa: F401  (fixture)
    member_loan_google_drive,  # noqa: F401  (fixture)
    member_loan_mailbox,  # noqa: F401  (fixture)
    propose,
    sign_document,
    sign_signing_request,
    start_change_signing,
    start_document_signing,
    summary,
)

REAL_SAVE_PDF_TO_LOAN_AGREEMENTS_FOLDER = google_drive_upload_module.save_pdf_to_loan_agreements_folder  # before the fake replaces it
WITHDRAWAL_ON_DECEMBER_15 = {"event_type": "lender_withdrawal", "effective_date": "2026-12-15", "amount": "1000.00"}
MEMBERS = MemberLoanMembers(
    lender=MemberLoanMember(None, "aviv", "Aviv", "lender", LENDER_EMAIL, "Aviv Jan"),
    yarden=MemberLoanMember(None, "yarden", "Yarden", "yarden", YARDEN_EMAIL, "Yarden Kelly"),
)


@pytest.fixture(autouse=True)
def _environment(monkeypatch, member_loan_clock, member_loan_mailbox, member_loan_google_drive):
    configure_member_loan_environment(monkeypatch)


@pytest.fixture
def aviv() -> TestClient:
    return enrolled_member_client("aviv")


@pytest.fixture
def yarden() -> TestClient:
    return enrolled_member_client("yarden")


def _audit_actions() -> list[str]:
    from DAL.data_models.memberLoan.models import MemberLoanAuditEntry

    with SessionLocal() as db:
        return [row.action for row in db.execute(select(MemberLoanAuditEntry).order_by(MemberLoanAuditEntry.audit_sequence)).scalars()]


def _change_content(change: dict, *, proposer: MemberLoanMember = MEMBERS.lender) -> dict:
    candidate = EffectiveMemberLoanEvent(
        event_id="x", event_type=change["event_type"], effective_date=date.fromisoformat(change["effective_date"]), application_order=0,
        amount=Decimal(change["amount"]) if change.get("amount") else None, interest_election_choice=change.get("interest_election_choice"),
    )
    preview = preview_member_loan_event(DEFAULT_MEMBER_LOAN_TERMS, [], candidate).as_plain_dict()
    return build_loan_change_document_content(
        change=change, preview=preview, record_number=3, proposer=proposer, members=MEMBERS, prepared_on=date(2026, 12, 15)
    )


# ---------------------------------------------------------------------------
# Unit: what is signed
# ---------------------------------------------------------------------------


class TestLoanChangeRecordWording:
    @pytest.mark.parametrize("change, section, counterparty_confirms_only", [
        (WITHDRAWAL_ON_DECEMBER_15, "Section 6.1 of the Agreement", True),
        ({"event_type": "lender_additional_advance", "effective_date": "2026-12-10", "amount": "5000.00",
          "written_agreement_date": "2026-12-09", "written_agreement_description": "Signed note"}, "Section 2.2 of the Agreement", False),
        ({"event_type": "yarden_capital_contribution_reduction", "effective_date": "2026-12-15", "amount": "5000.00"},
         "Section 7 of the Agreement", False),
        ({"event_type": "yarden_additional_withdrawal_increase", "effective_date": "2026-12-15", "amount": "2000.00",
          "written_agreement_date": "2026-12-14", "written_agreement_description": "Side letter"}, "Section 7A", False),
        ({"event_type": "interest_payment_election", "effective_date": "2026-12-01", "interest_election_choice": "cash"},
         "Section 4.4 of the Agreement", True),
    ])
    def test_each_change_cites_its_section_and_the_right_countersignature(self, change, section, counterparty_confirms_only):
        content = _change_content(change)
        assert any(section in line for line in content["contract_basis_lines"])
        proposer_text, counterparty_text = (s["statement_text"] for s in content["signers"])
        assert proposer_text.startswith("I, Aviv Jan, propose this change")
        if counterparty_confirms_only:
            assert "confirmation of fact, not consent" in counterparty_text and "Section 2.3" in counterparty_text
        else:
            assert "agree to this change" in counterparty_text and "Section 1.3" in counterparty_text
        assert content["signers"][1]["legal_name"] == "Yarden Kelly"

    def test_the_withdrawal_confirmation_names_the_amount_and_date(self):
        counterparty_text = _change_content(WITHDRAWAL_ON_DECEMBER_15)["signers"][1]["statement_text"]
        assert "$1,000.00 was paid to Aviv Jan on Dec 15, 2026" in counterparty_text

    def test_the_pdf_prints_the_engine_figures(self):
        content = _change_content(WITHDRAWAL_ON_DECEMBER_15)
        pdf_text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(render_loan_change_record_pdf(content))).pages)
        for label, before, after in content["figures_rows"]:
            assert before in pdf_text and after in pdf_text, label
        assert ["Amount Owed", "$31,166.01", "$30,166.01"] in content["figures_rows"]
        for needle in ("Loan Change Record", "No. 3", "Section 6.1", "Every other term of the Agreement stays unchanged",
                       "I, Yarden Kelly, signing as Member, for Big Whales AY LLC"):
            assert needle in pdf_text, needle

    def test_a_yarden_withdrawal_record_says_section_7a_covers_it(self):
        content = _change_content({"event_type": "yarden_additional_withdrawal_increase", "effective_date": "2026-12-15", "amount": "2000.00",
                                   "written_agreement_date": "2026-12-14", "written_agreement_description": "Side letter"})
        assert content["warnings"] and "Section 7A" in content["warnings"][0]


class TestStatementAcknowledgmentWording:
    def _content(self) -> dict:
        statement = {"statement_month": "2026-12", "statement_date": "2027-01-01", "summary_rows": [["Amount Owed on Jan 1", "$31,331.45"]]}
        return build_statement_signing_document_content(statement_document=statement, members=MEMBERS, sent_line="Sent on Jan 1, 2027.")

    def test_the_lender_only_confirms_the_figures(self):
        lender_text = self._content()["signers"][0]["statement_text"]
        assert lender_text.startswith("I, Aviv Jan, Lender, have reviewed this statement for December 2026")
        assert "promise" not in lender_text and "owes" not in lender_text

    def test_yarden_acknowledges_the_debt_for_the_borrower_and_as_guarantor(self):
        yarden_text = self._content()["signers"][1]["statement_text"]
        assert "sign for Big Whales AY LLC as its Member and personally as Guarantor" in yarden_text
        for number, needle in enumerate((
            "figures in this statement are correct",
            "owes the Lender the Amount Owed of $31,331.45 as of Jan 1, 2027",
            "without any defense, offset or counterclaim",
            "promises to pay it",
            "personal guarantee in Section 10",
            "written acknowledgment of the debt",
        ), start=1):
            assert f"{number}. " in yarden_text and needle in yarden_text, needle


class TestCeremonyChecks:
    def test_legal_names_ignore_case_and_spacing(self):
        assert normalized_legal_name("  aviv   JAN ") == normalized_legal_name("Aviv Jan")
        assert normalized_legal_name("Aviv J.") != normalized_legal_name("Aviv Jan")

    def test_a_drawn_signature_must_be_a_small_png(self):
        assert decode_drawn_signature_png(DRAWN_SIGNATURE_PNG_BASE64).startswith(b"\x89PNG")
        for bad in ("not base64!", base64.b64encode(b"GIF89a....").decode(),
                    base64.b64encode(drawn_signature_png(10, 10)).decode(),
                    base64.b64encode(drawn_signature_png(300, 100) + b"\x00" * 70_000).decode()):
            with pytest.raises(MemberLoanRequestRefused):
                decode_drawn_signature_png(bad)

    def test_the_drive_upload_is_signed_over_the_name_and_the_pdf(self):
        body = google_drive_upload_module.build_upload_request_body(file_name="a.pdf", pdf=b"%PDF-1", secret="s3cret", timestamp=1_800_000_000)
        assert body["folder_name"] == "loan agreements" and body["pdf_sha256"] == hashlib.sha256(b"%PDF-1").hexdigest()
        assert body["signature"] == google_drive_upload_module.upload_signature("s3cret", 1_800_000_000, "a.pdf", body["pdf_sha256"])
        assert body["signature"] != google_drive_upload_module.upload_signature("other", 1_800_000_000, "a.pdf", body["pdf_sha256"])

    def test_the_drive_upload_refuses_a_missing_or_foreign_url(self, monkeypatch):
        monkeypatch.delenv("MEMBER_LOAN_DRIVE_UPLOAD_URL", raising=False)
        with pytest.raises(google_drive_upload_module.MemberLoanDriveUploadFailed):
            REAL_SAVE_PDF_TO_LOAN_AGREEMENTS_FOLDER("a.pdf", b"%PDF")
        monkeypatch.setenv("MEMBER_LOAN_DRIVE_UPLOAD_URL", "https://evil.example/exec")
        monkeypatch.setenv("MEMBER_LOAN_DRIVE_UPLOAD_SECRET", "x")
        with pytest.raises(google_drive_upload_module.MemberLoanDriveUploadFailed):
            REAL_SAVE_PDF_TO_LOAN_AGREEMENTS_FOLDER("a.pdf", b"%PDF")


# ---------------------------------------------------------------------------
# Integration: proposing and approving by signature
# ---------------------------------------------------------------------------


class TestProposingBySignature:
    def test_a_draft_changes_and_stores_nothing_until_it_is_signed(self, aviv, yarden, member_loan_mailbox):
        started = start_change_signing(aviv, **WITHDRAWAL_ON_DECEMBER_15)
        assert started.status_code == 201, started.text
        draft = started.json()
        assert draft["signing_purpose"] == "propose_change" and draft["full_legal_name_to_type"] == "Aviv Jan"
        assert draft["document_content"]["title"] == "Loan Change Record No. 1 – Withdrawal by Aviv Jan"
        pdf = aviv.get(f"/member-loan/signing-requests/{draft['signing_request_id']}/pdf")
        assert pdf.status_code == 200 and hashlib.sha256(pdf.content).hexdigest() == draft["document_sha256"]
        assert yarden.get(f"/member-loan/signing-requests/{draft['signing_request_id']}/pdf").status_code == 404
        assert aviv.get("/member-loan/events").json() == [] and aviv.get("/member-loan/documents").json() == []
        assert member_loan_mailbox.sent == []

        signed = sign_signing_request(aviv, draft)
        assert signed.status_code == 200, signed.text
        document = signed.json()["document"]
        assert document["document_sha256"] == draft["document_sha256"]
        assert [s["status"] for s in document["signers"]] == ["signed", "waiting"]
        assert signed.json()["proposal"]["state"] == "pending"
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "31166.01"

    def test_the_passkey_signs_a_challenge_bound_to_the_document(self, aviv, yarden):
        propose(aviv, **WITHDRAWAL_ON_DECEMBER_15)
        with SessionLocal() as db:
            [signature] = db.execute(select(MemberLoanSignature)).scalars().all()
            [document] = member_loan_crud.list_member_loan_signing_documents(db)
        assert signature.signed_document_sha256 == document.unsigned_pdf_sha256
        assert passkey_assertion_is_bound_to_document(client_data_json_base64url=signature.webauthn_client_data_json,
                                                      document_sha256=document.unsigned_pdf_sha256, nonce_hex=signature.passkey_challenge_nonce)
        assert not passkey_assertion_is_bound_to_document(client_data_json_base64url=signature.webauthn_client_data_json,
                                                          document_sha256="0" * 64, nonce_hex=signature.passkey_challenge_nonce)
        assert signature.typed_full_legal_name == "Aviv Jan" and bytes(signature.drawn_signature_png).startswith(b"\x89PNG")

    @pytest.mark.parametrize("problem, expected_code", [
        ({"typed_full_legal_name": "Aviv"}, "legal_name_mismatch"),
        ({"consent": False}, "consent_required"),
        ({"drawn_signature_png_base64": "aGVsbG8="}, "drawn_signature_invalid"),
    ])
    def test_each_ceremony_step_is_required(self, aviv, yarden, problem, expected_code):
        draft = start_change_signing(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        response = sign_signing_request(aviv, draft, **problem)
        assert response.status_code == 422 and response.json()["detail"]["code"] == expected_code
        assert aviv.get("/member-loan/events").json() == []

    def test_another_members_passkey_cannot_sign(self, aviv, yarden):
        draft = start_change_signing(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        response = sign_signing_request(aviv, draft, passkey=yarden.member_loan_passkey)
        assert response.status_code == 403 and response.json()["detail"]["code"] == "passkey_not_verified"

    def test_a_signing_request_is_single_use_and_expires(self, aviv, yarden, member_loan_clock):
        draft = start_change_signing(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        assert sign_signing_request(aviv, draft).status_code == 200
        replay = sign_signing_request(aviv, draft)
        assert replay.status_code == 409 and replay.json()["detail"]["code"] == "signing_request_used"
        late = start_change_signing(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        member_loan_clock.now += timedelta(minutes=31)
        expired = sign_signing_request(aviv, late)
        assert expired.status_code == 410 and expired.json()["detail"]["code"] == "signing_request_expired"
        assert len(aviv.get("/member-loan/events").json()) == 1

    def test_a_draft_whose_record_number_was_taken_must_be_signed_again(self, aviv, yarden):
        first = start_change_signing(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        assert propose(yarden, event_type="lender_additional_advance", effective_date="2026-12-10", amount="10.00",
                       written_agreement_date="2026-12-09", written_agreement_description="note").status_code == 201
        stale = sign_signing_request(aviv, first)
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "document_changed"


class TestApprovingBySignature:
    def test_the_countersignature_approves_and_completes_the_signed_copy(self, aviv, yarden, member_loan_mailbox, member_loan_google_drive):
        proposal = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        document_id = proposal["signing_document_id"]
        waiting = yarden.get("/member-loan/documents", params={"waiting_for_me": True}).json()
        assert [d["id"] for d in waiting] == [document_id] and waiting[0]["caller_must_act"]
        assert aviv.get("/member-loan/documents", params={"waiting_for_me": True}).json() == []

        started = start_document_signing(yarden, document_id).json()
        assert "confirmation of fact, not consent" in started["signature_statement_text"]
        signed = sign_signing_request(yarden, started)
        assert signed.status_code == 200, signed.text
        assert signed.json()["proposal"]["state"] == "approved" and signed.json()["document"]["is_complete"]
        assert summary(aviv, "2026-12-15")["buckets"]["amount_owed"] == "30166.01"

        unsigned = aviv.get(f"/member-loan/documents/{document_id}/pdf").content
        signed_copy = aviv.get(f"/member-loan/documents/{document_id}/signed-pdf")
        assert signed_copy.status_code == 200 and signed_copy.headers["x-content-type-options"] == "nosniff"
        signed_pages = list(PdfReader(io.BytesIO(signed_copy.content)).pages)
        unsigned_pages = list(PdfReader(io.BytesIO(unsigned)).pages)
        assert len(signed_pages) > len(unsigned_pages)
        assert [p.extract_text() for p in signed_pages[:len(unsigned_pages)]] == [p.extract_text() for p in unsigned_pages]
        certificate = "".join(p.extract_text() for p in signed_pages[len(unsigned_pages):])
        for needle in ("Signature Certificate", "Aviv Jan (aviv)", "Yarden Kelly (yarden)", hashlib.sha256(unsigned).hexdigest(),
                       "New York", "UTC"):
            assert needle in certificate, needle

        document = aviv.get(f"/member-loan/documents/{document_id}").json()
        assert {(d["delivery_channel"], d["delivery_status"]) for d in document["deliveries"]} == {("email", "sent"), ("google_drive", "sent")}
        assert aviv.get("/member-loan/integrity").json()["intact"] is True

    def test_the_proposer_cannot_countersign_and_nobody_signs_twice(self, aviv, yarden):
        proposal = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        own = start_document_signing(aviv, proposal["signing_document_id"])
        assert own.status_code == 403 and own.json()["detail"]["code"] == "not_the_counterparty"
        assert approve(yarden, proposal["id"]).status_code == 200
        again = start_document_signing(yarden, proposal["signing_document_id"])
        assert again.status_code == 409

    def test_a_change_cannot_be_objected_to(self, aviv, yarden):
        proposal = propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()
        objection = start_document_signing(yarden, proposal["signing_document_id"], signature_meaning="objected", objection_reason="No")
        assert objection.status_code == 422 and objection.json()["detail"]["code"] == "objection_not_allowed"

    def test_pending_proposals_from_before_signing_expire_with_the_reason(self, aviv, yarden):
        from BL.memberLoan.common.member_loan_access import MemberLoanCaller, load_member_loan_members

        with SessionLocal() as db:
            members = load_member_loan_members(db, member_loan_settings.load_member_loan_settings())
            caller = MemberLoanCaller(member=members.lender, members=members, settings=member_loan_settings.load_member_loan_settings(),
                                      request_ip=None, user_agent=None)
            member_loan_crud.acquire_member_loan_write_lock(db)
            legacy = append_proposed_member_loan_event(db, caller, MemberLoanProposalCreateReq(**WITHDRAWAL_ON_DECEMBER_15),
                                                       load_member_loan_ledger_snapshot(db))
            db.commit()
            legacy_id = str(legacy.id)
        body = yarden.get(f"/member-loan/events/{legacy_id}").json()
        assert body["state"] == "expired" and body["decision_reason"] == EXPIRY_REASON_SIGNING_REPLACED_APPROVAL

    def test_the_signing_tables_refuse_edits_and_deletes(self, aviv, yarden):
        approve(yarden, propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"])
        from sqlalchemy.exc import DBAPIError

        for statement in ("UPDATE member_loan_signatures SET typed_full_legal_name = 'x'", "DELETE FROM member_loan_signatures",
                          "UPDATE member_loan_signing_documents SET title = 'x'", "DELETE FROM member_loan_signed_copies",
                          "DELETE FROM member_loan_signed_copy_deliveries"):
            with pytest.raises(DBAPIError, match="append-only"):
                with engine.begin() as connection:
                    connection.execute(text(statement))

    def test_a_changed_signature_or_pdf_breaks_the_integrity_check(self, aviv, yarden):
        approve(yarden, propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"])
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE member_loan_signing_documents DISABLE TRIGGER member_loan_signing_documents_append_only"))
            connection.execute(text("UPDATE member_loan_signing_documents SET unsigned_pdf = 'x'::bytea"))
            connection.execute(text("ALTER TABLE member_loan_signing_documents ENABLE TRIGGER member_loan_signing_documents_append_only"))
        problems = aviv.get("/member-loan/integrity").json()["problems"]
        assert any("Signing document row 1 was changed after it was written" in p for p in problems)
        assert any("its PDF no longer matches the one signed" in p for p in problems)


# ---------------------------------------------------------------------------
# Integration: delivery of the signed copy
# ---------------------------------------------------------------------------


class TestSignedCopyDelivery:
    def test_a_failed_drive_upload_is_retried_by_the_scheduler(self, aviv, yarden, member_loan_google_drive, member_loan_clock):
        member_loan_google_drive.fail_next = 1
        approve(yarden, propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"])
        assert "signed_copy_drive_save_failed" in _audit_actions() and member_loan_google_drive.saved == []
        assert retry_failed_signed_copy_deliveries() == 0  # its own delivery just ran: left alone for a few minutes
        member_loan_clock.now += timedelta(minutes=11)
        assert retry_failed_signed_copy_deliveries() == 1
        assert len(member_loan_google_drive.saved) == 1
        assert retry_failed_signed_copy_deliveries() == 0

    def test_retries_stop_after_the_attempt_limit(self, aviv, yarden, member_loan_google_drive, member_loan_clock):
        member_loan_google_drive.fail_next = 99
        approve(yarden, propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"])
        member_loan_clock.now += timedelta(minutes=11)
        for _ in range(AUTOMATIC_DELIVERY_ATTEMPTS + 2):
            retry_failed_signed_copy_deliveries()
        with SessionLocal() as db:
            drive_attempts = [d for d in db.execute(select(MemberLoanSignedCopyDelivery)).scalars() if d.delivery_channel == "google_drive"]
        assert len(drive_attempts) == AUTOMATIC_DELIVERY_ATTEMPTS

    def test_a_missing_company_address_fails_the_email_and_is_recorded(self, aviv, yarden, monkeypatch, member_loan_mailbox):
        monkeypatch.delenv("MEMBER_LOAN_COMPANY_EMAIL")
        approve(yarden, propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"])
        assert not [m for m in member_loan_mailbox.sent if m["subject"] == "whales loan update"]
        assert "signed_copy_email_failed" in _audit_actions()

    def test_file_names_say_what_was_signed(self, aviv, yarden):
        approve(yarden, propose(aviv, **WITHDRAWAL_ON_DECEMBER_15).json()["id"])
        with SessionLocal() as db:
            [document] = member_loan_crud.list_member_loan_signing_documents(db)
            signed_copy = member_loan_crud.get_member_loan_signed_copy_for_document(db, document.id)
            assert signed_copy_file_name(document, signed_copy) == "2026-12-20 whales loan update #1 – Withdrawal by Aviv Jan $1,000.00 – signed.pdf"


# ---------------------------------------------------------------------------
# Integration: statements signed or objected to, and the daily reminders
# ---------------------------------------------------------------------------


@pytest.fixture
def sent_december_statement(monkeypatch, member_loan_clock):
    monkeypatch.setenv("MEMBER_LOAN_EMAIL_DRY_RUN", "false")
    member_loan_clock.set(2027, 1, 1, hour=12)  # 7am on Jan 1 in New York
    with SessionLocal() as db:
        assert send_member_loan_statement(db).outcome == "sent"
        return str(member_loan_crud.get_member_loan_signing_document_for_statement_month(db, date(2026, 12, 1)).id)


class TestStatementSigning:
    def test_both_members_respond_and_the_signed_statement_goes_to_all_three(self, aviv, yarden, sent_december_statement,
                                                                              member_loan_mailbox, member_loan_google_drive):
        document_id = sent_december_statement
        statement = aviv.get("/member-loan/statements/2026-12").json()
        assert statement["signing_document_id"] == document_id
        assert sign_document(aviv, document_id).status_code == 200
        no_reason = start_document_signing(yarden, document_id, signature_meaning="objected")
        assert no_reason.status_code == 422 and no_reason.json()["detail"]["code"] == "objection_reason_required"
        objected = sign_document(yarden, document_id, signature_meaning="objected", objection_reason="The December interest looks high")
        assert objected.status_code == 200, objected.text
        signers = objected.json()["document"]["signers"]
        assert [(s["username"], s["status"]) for s in signers] == [("aviv", "signed"), ("yarden", "objected")]
        assert signers[1]["objection_reason"] == "The December interest looks high"

        [signed] = [m for m in member_loan_mailbox.sent if m["subject"] == "whales loan statement"]
        assert signed["recipients"] == [LENDER_EMAIL, YARDEN_EMAIL, COMPANY_EMAIL]
        assert "Objected by Yarden Kelly" in signed["text_body"] and "Signed by Aviv Jan" in signed["text_body"]
        assert member_loan_google_drive.saved[0][0] == "2027-01-01 whales loan statement – December 2026 – signed.pdf"

    def test_signing_closes_after_the_30_days(self, aviv, yarden, sent_december_statement, member_loan_clock):
        member_loan_clock.set(2027, 2, 1, hour=15)
        late = start_document_signing(aviv, sent_december_statement)
        assert late.status_code == 422 and late.json()["detail"]["code"] == "response_period_over"
        assert aviv.get(f"/member-loan/documents/{sent_december_statement}").json()["caller_must_act"] is False

    def test_reminders_go_daily_from_9am_to_who_has_not_acted_until_day_30(self, aviv, yarden, sent_december_statement,
                                                                           member_loan_mailbox, member_loan_clock):
        def reminders_sent_at(year, month, day, hour_utc):
            before = len(member_loan_mailbox.sent)
            member_loan_clock.set(year, month, day, hour=hour_utc)
            send_due_statement_signature_reminders()
            return [m["recipients"] for m in member_loan_mailbox.sent[before:]]

        assert reminders_sent_at(2027, 1, 1, 18) == []  # the statement e-mail was Jan 1's request
        assert reminders_sent_at(2027, 1, 2, 13) == []  # 8am in New York
        assert sorted(r[0] for r in reminders_sent_at(2027, 1, 2, 14)) == [LENDER_EMAIL, YARDEN_EMAIL]
        assert reminders_sent_at(2027, 1, 2, 20) == []  # once a day
        assert sign_document(aviv, sent_december_statement).status_code == 200
        assert reminders_sent_at(2027, 1, 3, 15) == [[YARDEN_EMAIL]]
        assert reminders_sent_at(2027, 1, 31, 15) == [[YARDEN_EMAIL]]
        assert reminders_sent_at(2027, 2, 1, 15) == []  # day 31: binding anyway
        reminder = next(m for m in member_loan_mailbox.sent if m["subject"] == "whales loan statement – please sign" and "until" in m["text_body"])
        assert f"/member-loan/sign/{sent_december_statement}" in reminder["text_body"] and "Jan 31, 2027" in reminder["text_body"]


def test_signed_assertions_are_plain_json_evidence(aviv, yarden):
    propose(aviv, **WITHDRAWAL_ON_DECEMBER_15)
    with SessionLocal() as db:
        [signature] = db.execute(select(MemberLoanSignature)).scalars().all()
    client_data = json.loads(base64.urlsafe_b64decode(signature.webauthn_client_data_json + "=" * (-len(signature.webauthn_client_data_json) % 4)))
    assert client_data["type"] == "webauthn.get" and client_data["origin"]
    assert signature.webauthn_signature and signature.webauthn_authenticator_data and signature.webauthn_credential_id
    assert signature.signed_at.tzinfo is not None and signature.device_id is not None
