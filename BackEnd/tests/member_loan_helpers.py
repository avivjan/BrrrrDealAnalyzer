"""Shared set-up for the Member Loan API tests: two enrolled members, a clock, a mailbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from BL.auth import service as service_bl
from BL.auth.common import settings as auth_settings
from BL.memberLoan.common import member_loan_mail_transport, member_loan_settings
from tests.test_auth_passkeys import ORIGIN, XRW, enroll
from tests.webauthn_helpers import SoftPasskey

WRITE_HEADERS = XRW
LENDER_EMAIL = "lender@example.test"
YARDEN_EMAIL = "yarden@example.test"


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


def enrolled_member_client(username: str) -> TestClient:
    from main import app  # the app conftest already imported and wired to the test database

    member_client = TestClient(app)
    enroll(member_client, SoftPasskey(auth_settings.rp_id(), ORIGIN), username=username)
    return member_client


def propose(member_client: TestClient, **body):
    return member_client.post("/member-loan/events", json=body, headers=WRITE_HEADERS)


def approve(member_client: TestClient, event_id: str):
    live = member_client.get(f"/member-loan/events/{event_id}").json()
    return member_client.post(
        f"/member-loan/events/{event_id}/approval",
        json={"preview_fingerprint": live["live_preview"]["preview_fingerprint"]},
        headers=WRITE_HEADERS,
    )


def summary(member_client: TestClient, as_of_date: str) -> dict:
    response = member_client.get("/member-loan/summary", params={"as_of_date": as_of_date})
    assert response.status_code == 200, response.text
    return response.json()
