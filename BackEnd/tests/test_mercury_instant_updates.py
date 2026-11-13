"""Instant updates (tasks/todo/ConstructionAccountPerRehab.md, Step F): turning them on and off at Mercury, and the
public address Mercury calls, against the fake bank of test_liquidity_construction_account.py.

A signed event reads the LLC once, fresh: every balance (the main Liquidity cash balance too), its linked construction
accounts and their rows. A wrongly signed, old or unknown event reads nothing.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import time

import pytest

import mcp_server
from BL.auth.common import settings as auth_settings
from BL.liquidity.common import mercury_reads
from BL.liquidity.common.mercury_client import MercuryApiError
from BL.liquidity.common.mercury_webhooks import (
    SIGNATURE_DOES_NOT_MATCH, SIGNATURE_IS_MISSING_OR_MALFORMED, SIGNATURE_IS_TOO_OLD, SIGNATURE_IS_VALID, MercuryWebhookRegistration,
    check_event_signature,
)
from BL.liquidity.constructionAccount import mercury_instant_updates as instant_updates_module
from tests.test_auth_passkeys import ORIGIN, XRW, enroll
from tests.test_liquidity_construction_account import (  # noqa: F401  (fixtures)
    RETURN, _amounts, _link, _refresh, bought_deal, mercury,
)
from tests.webauthn_helpers import SoftPasskey

SECRET = "whsec-test-signing-secret"
HTTPS = {**XRW, "X-Forwarded-Proto": "https"}
# `routers/__init__.py` re-exports each router object under its module's name: the module itself, for its knobs.
receiver_module = importlib.import_module("routers.mercury_webhooks")


def _signature(body: bytes, secret: str = SECRET, at: int | None = None) -> str:
    timestamp = int(time.time()) if at is None else at
    return f"t={timestamp},v1=" + hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


class FakeMercuryWebhooks:
    def __init__(self):
        self.registered: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.refuse_registration = False

    def register(self, workspace_label, receiving_url):
        if self.refuse_registration:
            raise MercuryApiError("auth failed (403)")
        self.registered.append((workspace_label, receiving_url))
        return MercuryWebhookRegistration(f"endpoint-{len(self.registered)}", SECRET)

    def delete(self, workspace_label, endpoint_id):
        self.deleted.append((workspace_label, endpoint_id))


@pytest.fixture
def webhooks(monkeypatch, mercury):  # noqa: F811
    fake = FakeMercuryWebhooks()
    monkeypatch.setattr(instant_updates_module, "register_webhook", fake.register)
    monkeypatch.setattr(instant_updates_module, "delete_webhook", fake.delete)
    receiver_module.reset_mercury_webhook_rate_limits()
    return fake


@pytest.fixture
def deferred_reads(monkeypatch):
    """The read an event inside the floor waits for, recorded instead of slept for."""
    scheduled = []
    monkeypatch.setattr(receiver_module, "read_the_workspace_once_the_floor_ends", lambda label, at: scheduled.append(label))
    return scheduled


@pytest.fixture
def signed_in(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    enroll(client, SoftPasskey(auth_settings.rp_id(), ORIGIN))
    return client


def _turn_on(client, label: str = "AJYK"):
    return client.post(f"/liquidity/mercury-webhooks/{label}/turn-on", headers=HTTPS)


def _workspace(client, label: str = "AJYK") -> dict:
    return next(workspace for workspace in client.get("/liquidity/mercury-connection-status").json()["workspaces"]
                if workspace["mercury_workspace_label"] == label)


def _address(webhooks: FakeMercuryWebhooks) -> str:
    return webhooks.registered[-1][1].removeprefix("https://testserver")


def _send_event(client, address: str, body: bytes = b'{"type":"transaction.created"}', signature: str | None = None):
    return client.post(address, content=body, headers={"Content-Type": "application/json",
                                                       "Mercury-Signature": signature if signature is not None else _signature(body)})


class TestTurningOnAndOff:
    def test_turning_on_needs_a_recent_passkey(self, client, webhooks):
        assert _turn_on(client).status_code == 401
        assert webhooks.registered == []

    def test_turning_on_registers_this_apps_https_address_and_waits_for_the_first_event(self, signed_in, webhooks):
        response = _turn_on(signed_in)
        assert response.status_code == 200, response.text
        label, url = webhooks.registered[0]
        assert label == "AJYK" and url.startswith("https://testserver/webhooks/mercury/") and len(url.rsplit("/", 1)[1]) >= 32
        workspace = _workspace(signed_in)
        assert workspace["instant_updates_are_on"] is True and workspace["last_valid_event_received_at"] is None
        assert SECRET not in response.text and SECRET not in json.dumps(signed_in.get("/liquidity/mercury-connection-status").json())

    def test_an_http_address_is_refused(self, signed_in, webhooks):
        response = signed_in.post("/liquidity/mercury-webhooks/AJYK/turn-on", headers=XRW)
        assert response.status_code == 409 and "https" in response.json()["detail"]
        assert webhooks.registered == []

    def test_an_llc_without_a_read_token_is_refused_naming_the_setting(self, signed_in, webhooks):
        response = _turn_on(signed_in, "NOPE")
        assert response.status_code == 409 and "MERCURY_API_TOKEN_NOPE" in response.json()["detail"]

    def test_a_refused_registration_is_recorded_in_our_own_words(self, signed_in, webhooks):
        webhooks.refuse_registration = True
        response = _turn_on(signed_in)
        assert response.status_code == 502
        workspace = _workspace(signed_in)
        assert workspace["instant_updates_are_on"] is False
        assert "Mercury refused to turn on instant updates (auth failed (403))" in workspace["last_webhook_error_message"]

    def test_turning_off_removes_it_at_mercury_and_the_old_address_stops_answering(self, signed_in, webhooks):
        _turn_on(signed_in)
        address = _address(webhooks)
        response = signed_in.post("/liquidity/mercury-webhooks/AJYK/turn-off", headers=HTTPS)
        assert response.status_code == 200
        assert webhooks.deleted == [("AJYK", "endpoint-1")]
        assert _workspace(signed_in)["instant_updates_are_on"] is False
        assert _send_event(signed_in, address).status_code == 404


class TestEvents:
    def test_a_signed_event_reads_the_whole_llc_once_and_the_main_cash_balance_follows(self, signed_in, webhooks, mercury, bought_deal,  # noqa: F811
                                                                                       monkeypatch):
        monkeypatch.setenv("MERCURY_CACHE_SECONDS", "60")   # as deployed: the balance page then answers from the stored read
        _link(signed_in, bought_deal["id"])
        _refresh(signed_in)
        _turn_on(signed_in)
        last_change_before = signed_in.get("/liquidity/construction-accounts/last-change").json()
        mercury.balance_by_account_id["checking"] += 12000   # money lands in a checking account, not a construction one
        calls_before = mercury.accounts_call_count_by_workspace.get("AJYK", 0)
        assert _send_event(signed_in, _address(webhooks)).status_code == 200
        assert mercury.accounts_call_count_by_workspace["AJYK"] == calls_before + 1
        assert signed_in.get("/liquidity/mercury-balance").json()["counted_as_cash_balance_dollars"] == 80000 + 12000 + 9000
        assert mercury.accounts_call_count_by_workspace["AJYK"] == calls_before + 1
        last_change = signed_in.get("/liquidity/construction-accounts/last-change").json()
        assert last_change["cash_balance_last_changed_at"] != last_change_before["cash_balance_last_changed_at"]
        assert _workspace(signed_in)["last_valid_event_received_at"] is not None

    def test_an_event_refreshes_the_construction_account_rows_and_keeps_them_for_the_open_pages(self, signed_in, webhooks, mercury, bought_deal):  # noqa: F811
        _link(signed_in, bought_deal["id"])
        _refresh(signed_in)
        _turn_on(signed_in)
        # A draw, then a steal made in Mercury itself: only own money moves the projection (draws and payments cancel out).
        mercury.move("construction", "draw-1", 30000, counterparty_name="Lender")
        mercury.move("construction", "steal-in-mercury", -10000, internal=True)
        assert _send_event(signed_in, _address(webhooks)).status_code == 200
        last_change = signed_in.get("/liquidity/construction-accounts/last-change").json()
        assert last_change["last_instant_update_at"] is not None
        assert [changes["deal_id"] for changes in last_change["bank_reported_row_changes_of_last_instant_update"]] == [bought_deal["id"]]
        # balance 20,000 + (70,000 - 30,000 still to draw) - 50,000 unpaid + the 5,000 deposit still to come
        assert _amounts(signed_in, bought_deal["id"])[RETURN] == 20000 + 40000 - 50000 + 5000

    def test_events_inside_the_floor_wait_for_one_read(self, signed_in, webhooks, mercury, deferred_reads, monkeypatch):  # noqa: F811
        _turn_on(signed_in)
        monkeypatch.setattr(mercury_reads, "MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE", 10)
        assert _send_event(signed_in, _address(webhooks)).status_code == 200
        calls_after_the_first = mercury.accounts_call_count_by_workspace["AJYK"]
        assert _send_event(signed_in, _address(webhooks)).status_code == 200
        assert mercury.accounts_call_count_by_workspace["AJYK"] == calls_after_the_first
        assert deferred_reads == ["AJYK"]

    @pytest.mark.parametrize("signature, recorded", [
        (_signature(b'{"type":"transaction.created"}', secret="not-the-secret"), "wrong signature"),
        (_signature(b'{"type":"transaction.created"}', at=int(time.time()) - 3600), "more than 5 minutes old"),
        ("", "without a usable signature"),
    ])
    def test_a_bad_event_reads_nothing_and_is_recorded(self, signed_in, webhooks, mercury, signature, recorded):  # noqa: F811
        _turn_on(signed_in)
        calls_before = mercury.accounts_call_count_by_workspace.get("AJYK", 0)
        assert _send_event(signed_in, _address(webhooks), signature=signature).status_code == 401
        assert mercury.accounts_call_count_by_workspace.get("AJYK", 0) == calls_before
        workspace = _workspace(signed_in)
        assert recorded in workspace["last_webhook_error_message"] and workspace["last_valid_event_received_at"] is None

    def test_an_altered_body_fails_its_signature(self, signed_in, webhooks):
        _turn_on(signed_in)
        signature = _signature(b'{"type":"transaction.created"}')
        assert _send_event(signed_in, _address(webhooks), body=b'{"type":"something.else"}', signature=signature).status_code == 401

    def test_an_unknown_address_is_not_found_and_records_nothing(self, client, webhooks):
        assert _send_event(client, "/webhooks/mercury/" + "x" * 43).status_code == 404

    def test_a_body_too_large_is_refused(self, signed_in, webhooks):
        _turn_on(signed_in)
        body = b"x" * (receiver_module.MAXIMUM_EVENT_BODY_BYTES + 1)
        assert _send_event(signed_in, _address(webhooks), body=body).status_code in (413, 422)

    def test_each_sender_is_rate_limited_whatever_address_it_calls(self, signed_in, webhooks, monkeypatch):
        _turn_on(signed_in)
        monkeypatch.setattr(receiver_module, "EVENTS_PER_MINUTE_PER_ADDRESS", 3)
        address = _address(webhooks)
        unknown = "/webhooks/mercury/" + "y" * 43
        assert [_send_event(signed_in, path).status_code for path in (address, unknown, address, address)] == [200, 404, 200, 429]


class TestSignature:
    BODY = b'{"id":"evt-1"}'

    def test_valid(self):
        assert check_event_signature(SECRET, _signature(self.BODY), self.BODY) == SIGNATURE_IS_VALID

    def test_wrong_secret_old_timestamp_and_malformed(self):
        assert check_event_signature(SECRET, _signature(self.BODY, secret="other"), self.BODY) == SIGNATURE_DOES_NOT_MATCH
        assert check_event_signature(SECRET, _signature(self.BODY, at=int(time.time()) - 301), self.BODY) == SIGNATURE_IS_TOO_OLD
        assert check_event_signature(SECRET, "v1=abc", self.BODY) == SIGNATURE_IS_MISSING_OR_MALFORMED
        assert check_event_signature(SECRET, None, self.BODY) == SIGNATURE_IS_MISSING_OR_MALFORMED

    def test_one_of_several_signatures_may_match(self):
        good = _signature(self.BODY)
        timestamp, good_signature = good.split(",")
        assert check_event_signature(SECRET, f"{timestamp},v1={'0' * 64},{good_signature}", self.BODY) == SIGNATURE_IS_VALID


class TestNeverAnMcpTool:
    def test_no_webhook_tool(self):
        assert not [name for name in mcp_server.tools() if "webhook" in name or "instant_updates" in name]
