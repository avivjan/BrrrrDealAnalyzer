"""The audit table, the send-offer rate limit built on it, and the
secret-value log filter."""

from __future__ import annotations

import logging

from sqlalchemy import select

from BL.auth.common import audit
from BL.common.logging_redact import SecretRedactFilter, redact_secrets
from DAL.data_models.audit.models import AuditLog
from db import SessionLocal

OFFER = {
    "agent_name": "Dana Levi",
    "agent_email": "dana@example.com",
    "property_address": "12 Ocean Dr, Miami FL",
    "purchase_price": "250000.00",
    "inspection_period_days": 7,
}


def _rows(event: str):
    with SessionLocal() as s:
        return s.execute(select(AuditLog).where(AuditLog.event == event).order_by(AuditLog.id)).scalars().all()


class TestRecordAndCount:
    def test_record_writes_a_row_and_count_recent_sees_it(self):
        audit.record("unit_event", None, detail={"k": "v"})
        assert _rows("unit_event")[0].detail == {"k": "v"}
        assert audit.count_recent("unit_event", 5) == 1
        assert audit.count_recent("unit_event", 5, ip="9.9.9.9") == 0


class TestSendOfferRateLimit:
    def test_the_limit_returns_429_and_is_audited(self, client, monkeypatch):
        monkeypatch.setenv("SEND_OFFER_PER_HOUR", "2")
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        # The mailer is unconfigured, so each attempt is a 500 -- still an attempt.
        assert client.post("/send-offer", json=OFFER).status_code == 500
        assert client.post("/send-offer", json=OFFER).status_code == 500
        third = client.post("/send-offer", json=OFFER)
        assert third.status_code == 429
        assert "Too many offers" in third.json()["detail"]
        rows = _rows("send_offer")
        assert [r.detail for r in rows] == [{"ok": False}, {"ok": False}, {"ok": False, "reason": "rate_limited"}]
        assert all("dana" not in str(r.detail) for r in rows)

    def test_the_default_limit_is_generous(self, client, monkeypatch):
        monkeypatch.delenv("SEND_OFFER_PER_HOUR", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        for _ in range(5):
            assert client.post("/send-offer", json=OFFER).status_code == 500


class TestSecretRedaction:
    def test_configured_values_and_bearer_tokens_are_replaced(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PASSWORD", "abcdabcdabcdabcd")
        monkeypatch.setenv("MERCURY_API_TOKEN_AJYK", "sekrit-token-ajyk-0001")
        text = redact_secrets("pw=abcdabcdabcdabcd hdr=Bearer sekrit-token-ajyk-0001 tok=sekrit-token-ajyk-0001")
        assert "abcdabcdabcdabcd" not in text and "sekrit" not in text
        assert text.count("[REDACTED]") == 3

    def test_the_filter_rewrites_records(self, monkeypatch):
        monkeypatch.setenv("APP_KEY", "phase0-test-key-0123456789abcdef")
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "key is %s", ("phase0-test-key-0123456789abcdef",), None)
        assert SecretRedactFilter().filter(record) is True
        assert "phase0-test-key" not in record.getMessage()

    def test_the_root_logger_has_the_filter(self):
        root = logging.getLogger()
        assert any(isinstance(f, SecretRedactFilter) for f in root.filters)
