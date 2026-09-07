"""`POST /send-offer` hardening: a real e-mail address, single-line header
fields, HTML-escaped body values, and no password material in the logs."""

from __future__ import annotations

import logging
import smtplib

import pytest
from pydantic import ValidationError

from BL.email.common import offer_email
from ReqRes.common.send_offer_schemas import SendOfferReq

VALID = {
    "agent_name": "Dana Levi",
    "agent_email": "dana@example.com",
    "property_address": "12 Ocean Dr, Miami FL",
    "purchase_price": "250000.00",
    "inspection_period_days": 7,
}


class TestSchema:
    def test_valid_payload_is_accepted(self):
        req = SendOfferReq(**VALID)
        assert req.agent_email == "dana@example.com"

    @pytest.mark.parametrize("bad", ["not-an-email", "dana@", "a@b", "dana@example.com\nBcc: x@y.z"])
    def test_agent_email_must_be_an_email(self, bad):
        with pytest.raises(ValidationError):
            SendOfferReq(**{**VALID, "agent_email": bad})

    @pytest.mark.parametrize("field", ["agent_name", "property_address"])
    def test_header_fields_reject_line_breaks(self, field):
        with pytest.raises(ValidationError):
            SendOfferReq(**{**VALID, field: "first line\r\nSubject: injected"})

    def test_lengths_are_bounded(self):
        with pytest.raises(ValidationError):
            SendOfferReq(**{**VALID, "property_address": "x" * 501})
        with pytest.raises(ValidationError):
            SendOfferReq(**{**VALID, "inspection_period_days": 400})

    def test_the_endpoint_returns_422_for_a_bad_address(self, client):
        response = client.post("/send-offer", json={**VALID, "agent_email": "nope"})
        assert response.status_code == 422


class _FakeSMTP:
    sent = []

    def __init__(self, *args, **kwargs):
        pass

    def login(self, *args, **kwargs):
        pass

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)

    def quit(self):
        pass


class TestBody:
    @pytest.fixture(autouse=True)
    def _smtp(self, monkeypatch):
        _FakeSMTP.sent = []
        monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
        monkeypatch.setenv("EMAIL_PASSWORD", "abcdabcdabcdabcd")

    def test_markup_in_the_name_and_address_is_escaped(self):
        req = SendOfferReq(**{**VALID, "agent_name": '<img src=x onerror="alert(1)">', "property_address": "1 <b>Main</b> St"})
        ok, _ = offer_email.send_offer_email(req)
        assert ok and len(_FakeSMTP.sent) == 1
        body = _FakeSMTP.sent[0].get_payload()[0].get_payload(decode=True).decode()
        assert '<img src=x onerror="alert(1)">' not in body
        assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in body
        assert "1 &lt;b&gt;Main&lt;/b&gt; St" in body
        assert _FakeSMTP.sent[0]["To"] == "dana@example.com"

    def test_a_plain_name_and_address_render_unchanged(self):
        ok, _ = offer_email.send_offer_email(SendOfferReq(**VALID))
        assert ok
        body = _FakeSMTP.sent[0].get_payload()[0].get_payload(decode=True).decode()
        assert "Hi Dana Levi," in body
        assert "<strong>12 Ocean Dr, Miami FL</strong>" in body

    def test_the_password_never_reaches_the_logs(self, caplog):
        with caplog.at_level(logging.DEBUG):
            offer_email.send_offer_email(SendOfferReq(**VALID))
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert "abcd" not in text
        assert "password starts with" not in text
        assert "length" not in text.lower()
