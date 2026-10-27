"""Shared set-up for the Member Loan API tests: two enrolled members, a clock, a mailbox,
a fake Google Drive, and the signing steps (`propose` and `approve` sign with each
member's software passkey, the way the app does)."""

from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from BL.auth import service as service_bl
from BL.auth.common import settings as auth_settings
from BL.memberLoan.common import member_loan_google_drive as google_drive_upload_module
from BL.memberLoan.common import member_loan_mail_transport, member_loan_settings
from tests.test_auth_passkeys import ORIGIN, XRW, enroll
from tests.webauthn_helpers import SoftPasskey

WRITE_HEADERS = XRW
LENDER_EMAIL = "lender@example.test"
YARDEN_EMAIL = "yarden@example.test"
COMPANY_EMAIL = "company@example.test"
LEGAL_NAME_BY_USERNAME = {"aviv": "Aviv Jan", "yarden": "Yarden Kelly"}


def drawn_signature_png(width: int = 300, height: int = 100) -> bytes:
    """A real PNG of the size a signature pad exports (transparent pixels are enough)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\x00" + b"\x00\x00\x00\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


DRAWN_SIGNATURE_PNG_BASE64 = "data:image/png;base64," + base64.b64encode(drawn_signature_png()).decode("ascii")


@dataclass
class CapturedMailbox:
    sent: list[dict] = field(default_factory=list)
    fail_next: int = 0

    def deliver(self, **message) -> None:
        if self.fail_next:
            self.fail_next -= 1
            raise member_loan_mail_transport.MemberLoanEmailNotSent("SMTPServerDisconnected")
        self.sent.append(message)

    def to(self, address: str) -> list[dict]:
        return [m for m in self.sent if address in m["recipients"]]


@dataclass
class ControllableClock:
    now: datetime

    def set(self, year: int, month: int, day: int, hour: int = 15) -> None:
        self.now = datetime(year, month, day, hour, 0, tzinfo=timezone.utc)

    def advance_days(self, days: int) -> None:
        from datetime import timedelta

        self.now = self.now + timedelta(days=days)


@dataclass
class FakeGoogleDrive:
    saved: list[tuple[str, bytes]] = field(default_factory=list)
    fail_next: int = 0

    def save(self, file_name: str, pdf: bytes) -> str:
        if self.fail_next:
            self.fail_next -= 1
            raise google_drive_upload_module.MemberLoanDriveUploadFailed("URLError")
        self.saved.append((file_name, pdf))
        return f"drive-file-{len(self.saved)}"


def configure_member_loan_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "off")  # the module gates itself whatever AUTH_MODE says
    monkeypatch.delenv("DEVICE_POLICY", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("MEMBER_LOAN_LENDER_USERNAME", "aviv")
    monkeypatch.setenv("MEMBER_LOAN_YARDEN_USERNAME", "yarden")
    monkeypatch.setenv("MEMBER_LOAN_ALLOWED_USERNAMES", "aviv,yarden")
    monkeypatch.setenv("MEMBER_LOAN_LENDER_EMAIL", LENDER_EMAIL)
    monkeypatch.setenv("MEMBER_LOAN_YARDEN_EMAIL", YARDEN_EMAIL)
    monkeypatch.setenv("MEMBER_LOAN_COMPANY_EMAIL", COMPANY_EMAIL)
    monkeypatch.setenv("MEMBER_LOAN_APP_ORIGIN", "https://bigwhales.example")
    monkeypatch.delenv("MEMBER_LOAN_WRITES_PER_HOUR", raising=False)
    service_bl.forget()


@pytest.fixture
def member_loan_clock(monkeypatch) -> ControllableClock:
    clock = ControllableClock(datetime(2026, 12, 20, 15, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(member_loan_settings, "utc_now", lambda: clock.now)
    return clock


@pytest.fixture
def member_loan_mailbox(monkeypatch) -> CapturedMailbox:
    mailbox = CapturedMailbox()
    monkeypatch.setattr(member_loan_mail_transport, "deliver_member_loan_email", mailbox.deliver)
    return mailbox


@pytest.fixture
def member_loan_google_drive(monkeypatch) -> FakeGoogleDrive:
    drive = FakeGoogleDrive()
    monkeypatch.setattr(google_drive_upload_module, "save_pdf_to_loan_agreements_folder", drive.save)
    return drive


def enrolled_member_client(username: str) -> TestClient:
    from main import app  # the app conftest already imported and wired to the test database

    member_client = TestClient(app)
    passkey = SoftPasskey(auth_settings.rp_id(), ORIGIN)
    enroll(member_client, passkey, username=username)
    member_client.member_loan_passkey = passkey
    member_client.member_loan_legal_name = LEGAL_NAME_BY_USERNAME.get(username, username)
    return member_client


@dataclass
class SigningStepResponse:
    """What `propose` and `approve` return: the failing step's response, or the signed result."""

    status_code: int
    payload: Any
    text: str = ""

    def json(self) -> Any:
        return self.payload


def _step(response) -> SigningStepResponse:
    return SigningStepResponse(response.status_code, response.json() if response.content else None, response.text)


def sign_signing_request(member_client: TestClient, signing_request: dict, *, typed_full_legal_name: Optional[str] = None,
                         consent: bool = True, drawn_signature_png_base64: str = DRAWN_SIGNATURE_PNG_BASE64, passkey=None):
    """Steps 2 and 3 of a signing: passkey options bound to the document, then the signature."""

    signing_request_id = signing_request["signing_request_id"]
    options = member_client.post(f"/member-loan/signing-requests/{signing_request_id}/passkey-options", headers=WRITE_HEADERS)
    if options.status_code != 200:
        return options
    credential = (passkey or member_client.member_loan_passkey).authenticate(options.json()["options"])
    return member_client.post(
        f"/member-loan/signing-requests/{signing_request_id}/signature",
        json={
            "typed_full_legal_name": typed_full_legal_name or member_client.member_loan_legal_name,
            "electronic_signature_consent_confirmed": consent,
            "drawn_signature_png_base64": drawn_signature_png_base64,
            "passkey_challenge_id": options.json()["passkey_challenge_id"],
            "passkey_credential": credential,
        },
        headers=WRITE_HEADERS,
    )


def start_change_signing(member_client: TestClient, **body):
    return member_client.post("/member-loan/change-documents", json=body, headers=WRITE_HEADERS)


def propose(member_client: TestClient, **body) -> SigningStepResponse:
    """Propose a change by signing its Loan Change Record. On success: 201 and the proposal."""

    started = start_change_signing(member_client, **body)
    if started.status_code != 201:
        return _step(started)
    signed = sign_signing_request(member_client, started.json())
    if signed.status_code != 200:
        return _step(signed)
    return SigningStepResponse(201, signed.json()["proposal"])


def propose_reversal(member_client: TestClient, event_id: str, **body) -> SigningStepResponse:
    started = member_client.post(f"/member-loan/events/{event_id}/reversal-documents", json=body, headers=WRITE_HEADERS)
    if started.status_code != 201:
        return _step(started)
    signed = sign_signing_request(member_client, started.json())
    if signed.status_code != 200:
        return _step(signed)
    return SigningStepResponse(201, signed.json()["proposal"])


def start_document_signing(member_client: TestClient, document_id: str, **body):
    return member_client.post(f"/member-loan/documents/{document_id}/signing-requests", json=body, headers=WRITE_HEADERS)


def sign_document(member_client: TestClient, document_id: str, **body) -> SigningStepResponse:
    """Sign (or object to) a document. On success: 200 and the signing completion."""

    started = start_document_signing(member_client, document_id, **body)
    if started.status_code != 201:
        return _step(started)
    return _step(sign_signing_request(member_client, started.json()))


def approve(member_client: TestClient, event_id: str) -> SigningStepResponse:
    """Approve a change by countersigning its Loan Change Record. On success: 200 and the proposal."""

    event = member_client.get(f"/member-loan/events/{event_id}").json()
    signed = sign_document(member_client, event["signing_document_id"])
    if signed.status_code != 200:
        return signed
    return SigningStepResponse(200, signed.json()["proposal"])


def summary(member_client: TestClient, as_of_date: str) -> dict:
    response = member_client.get("/member-loan/summary", params={"as_of_date": as_of_date})
    assert response.status_code == 200, response.text
    return response.json()
