"""Deposit and Steal through Mercury (tasks/todo/ConstructionAccountPerRehab.md, Step E), against the fake bank of
test_liquidity_construction_account.py and a fake transfer endpoint.

The deal: construction budget $70,000, rehab cost $50,000, cushion $5,000 (so $5,000 to deposit). The owner signs in
with a soft passkey: a transfer needs a web session whose passkey was used in the last minutes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

import mcp_server
from BL.auth.common import settings as auth_settings
from BL.liquidity.common.mercury_client import MercuryApiError
from BL.liquidity.common.mercury_transfers import MercuryTransferAnswer, MercuryTransferNotAnsweredError
from BL.liquidity.constructionAccount import construction_account_transfers as transfers_module
from DAL.data_models.audit.models import AuditLog
from db import SessionLocal
from tests.test_auth_passkeys import ORIGIN, XRW, enroll
from tests.test_devices import _age_sessions
from tests.test_liquidity_construction_account import (  # noqa: F401  (fixtures)
    DEPOSIT, DURING_THE_REHAB, _link, _refresh, _rows, _status, bought_deal, mercury,
)
from tests.webauthn_helpers import SoftPasskey

KEY = "transfer-key-0001"


class FakeMercuryTransfers:
    """Mercury's `POST /transfer`: moves the money on the fake bank and lists it on both accounts, the next day."""

    def __init__(self, fake_bank):
        self.fake_bank = fake_bank
        self.calls: list[dict] = []
        self.answer_with_an_id = True
        self.next_error: Exception | None = None
        self.show_in_the_feed = False

    def send(self, workspace_label, source_account_id, destination_account_id, amount_dollars, idempotency_key, note):
        self.calls.append(dict(workspace_label=workspace_label, source=source_account_id, destination=destination_account_id,
                               amount=amount_dollars, idempotency_key=idempotency_key))
        if self.next_error is not None:
            error, self.next_error = self.next_error, None
            raise error
        transfer_id = f"mercury-transfer-{len(self.calls)}"
        self.fake_bank.balance_by_account_id[source_account_id] -= int(amount_dollars)
        self.fake_bank.balance_by_account_id[destination_account_id] += int(amount_dollars)
        if self.show_in_the_feed:
            self.put_in_the_feed(transfer_id, source_account_id, destination_account_id, int(amount_dollars))
        return MercuryTransferAnswer(transfer_id if self.answer_with_an_id else None, "sent")

    def put_in_the_feed(self, transfer_id, source_account_id, destination_account_id, amount):
        for account_id, signed_amount in ((source_account_id, -amount), (destination_account_id, amount)):
            self.fake_bank.transactions_by_account_id[account_id].append({
                "id": transfer_id, "signed_amount_dollars": Decimal(signed_amount), "kind": "internalTransfer", "status": "sent",
                "counterparty_name": "Internal transfer", "transaction_date": date.today() + timedelta(days=1),
                "is_internal_transfer": True, "is_failed_or_cancelled": False, "is_pending": False})


@pytest.fixture
def transfers(monkeypatch, mercury) -> FakeMercuryTransfers:  # noqa: F811
    fake = FakeMercuryTransfers(mercury)
    monkeypatch.setenv("MERCURY_TRANSFER_API_TOKEN_AJYK", "fake-transfer-token-ajyk")
    monkeypatch.setattr(transfers_module, "send_internal_transfer", fake.send)
    return fake


@pytest.fixture
def signed_in(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    enroll(client, SoftPasskey(auth_settings.rp_id(), ORIGIN))
    return client


@pytest.fixture
def linked(client, mercury, bought_deal):  # noqa: F811
    assert _link(client, bought_deal["id"]).status_code == 200
    _refresh(client)
    return bought_deal


def _send(client, deal_id: str, direction: str, amount: float, key: str = KEY, preview_only: bool = False, **extra):
    return client.post(f"/liquidity/construction-accounts/{deal_id}/{direction}", headers=XRW,
                       params={"preview_only": "true"} if preview_only else None,
                       json={"amount_dollars": amount, "idempotency_key": key, **extra})


def _settings(client, **changes):
    assert client.put("/liquidity/settings", json=changes).status_code == 200


class TestDeposit:
    def test_the_preview_asks_mercury_nothing_needs_no_passkey_and_saves_nothing(self, client, transfers, linked):
        response = _send(client, linked["id"], "deposit", 5000, preview_only=True)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["was_preview_only"] is True and body["transfer"] is None
        assert body["status_after"]["remaining_deposit_dollars"] == 0 and body["status_before"]["remaining_deposit_dollars"] == 5000
        assert body["changes_the_liquidity_timeline"] is True and body["row_descriptions_marked_done"]
        assert transfers.calls == []
        assert _status(client, linked["id"])["transfers_made_in_the_app"] == []
        assert _rows(client, linked["id"])[DEPOSIT]["done_at"] is None

    def test_a_deposit_needs_a_signed_in_person(self, client, transfers, linked):
        assert _send(client, linked["id"], "deposit", 5000).status_code == 401
        assert transfers.calls == []

    def test_a_deposit_needs_a_recent_passkey(self, signed_in, transfers, linked):
        _age_sessions()
        response = _send(signed_in, linked["id"], "deposit", 5000)
        assert response.status_code == 403 and response.json() == {"detail": "reauth_required"}
        assert transfers.calls == []

    def test_a_deposit_moves_the_money_between_the_linked_accounts_and_marks_the_deposit_row_done(self, signed_in, transfers, linked):
        response = _send(signed_in, linked["id"], "deposit", 5000)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["transfer"]["transfer_outcome"] == "accepted_by_mercury" and body["transfer"]["amount_dollars"] == 5000
        assert transfers.calls == [dict(workspace_label="AJYK", source="checking", destination="construction",
                                        amount=Decimal("5000.00"), idempotency_key=KEY)]
        assert _rows(signed_in, linked["id"])[DEPOSIT]["done_at"] is not None
        status = _status(signed_in, linked["id"])
        assert status["own_money_transferred_into_the_account_dollars"] == 5000 and status["remaining_deposit_dollars"] == 0
        assert [transfer["is_in_the_bank_feed"] for transfer in status["transfers_made_in_the_app"]] == [False]

    def test_the_same_key_never_makes_a_second_transfer(self, signed_in, transfers, linked):
        first = _send(signed_in, linked["id"], "deposit", 5000).json()
        again = _send(signed_in, linked["id"], "deposit", 5000)
        assert again.status_code == 200 and again.json()["transfer"]["transfer_id"] == first["transfer"]["transfer_id"]
        assert len(transfers.calls) == 1
        other_amount = _send(signed_in, linked["id"], "deposit", 4000)
        assert other_amount.status_code == 409 and "already used" in other_amount.json()["detail"]
        assert len(transfers.calls) == 1

    def test_it_counts_once_before_and_after_the_bank_feed_shows_it(self, signed_in, transfers, linked):
        _send(signed_in, linked["id"], "deposit", 5000)
        transfers.put_in_the_feed("mercury-transfer-1", "checking", "construction", 5000)
        _refresh(signed_in)
        status = _status(signed_in, linked["id"])
        assert status["own_money_transferred_into_the_account_dollars"] == 5000
        assert status["current_balance_dollars"] == 5000
        assert status["transfers_made_in_the_app"][0]["is_in_the_bank_feed"] is True

    def test_an_answer_without_an_id_is_matched_by_amount_and_date(self, signed_in, transfers, linked):
        transfers.answer_with_an_id = False
        _send(signed_in, linked["id"], "deposit", 5000)
        transfers.put_in_the_feed("feed-id-without-a-link", "checking", "construction", 5000)
        _refresh(signed_in)
        status = _status(signed_in, linked["id"])
        assert status["own_money_transferred_into_the_account_dollars"] == 5000
        assert status["transfers_made_in_the_app"][0]["is_in_the_bank_feed"] is True

    def test_the_audit_row_names_the_transfer_but_never_the_amount(self, signed_in, transfers, linked):
        _send(signed_in, linked["id"], "deposit", 5000)
        with SessionLocal() as db:
            rows = list(db.execute(select(AuditLog).where(AuditLog.event == "liquidity_construction_account_transfer")).scalars())
        assert len(rows) == 1
        detail = rows[0].detail
        assert detail["transfer_direction"] == "deposit_into_construction_account" and detail["transfer_outcome"] == "accepted_by_mercury"
        assert "5000" not in str(detail) and "amount" not in str(detail)


class TestMercuryAnswers:
    def test_no_answer_is_kept_as_such_never_retried_and_not_counted(self, signed_in, transfers, linked):
        transfers.next_error = MercuryTransferNotAnsweredError("no answer in time")
        body = _send(signed_in, linked["id"], "deposit", 5000).json()
        assert body["transfer"]["transfer_outcome"] == "mercury_did_not_answer"
        assert _status(signed_in, linked["id"])["own_money_transferred_into_the_account_dollars"] == 0
        again = _send(signed_in, linked["id"], "deposit", 5000).json()
        assert again["transfer"]["transfer_outcome"] == "mercury_did_not_answer"
        assert len(transfers.calls) == 1

    def test_a_refused_transfer_is_not_counted(self, signed_in, transfers, linked):
        transfers.next_error = MercuryApiError("HTTP 400")
        body = _send(signed_in, linked["id"], "deposit", 5000).json()
        assert body["transfer"]["transfer_outcome"] == "refused_by_mercury"
        assert _rows(signed_in, linked["id"])[DEPOSIT]["done_at"] is None


class TestGuards:
    def test_the_kill_switch_in_the_settings(self, signed_in, transfers, linked):
        _settings(signed_in, construction_account_in_app_transfers_enabled=False)
        response = _send(signed_in, linked["id"], "deposit", 5000)
        assert response.status_code == 409 and "turned off" in response.json()["detail"]
        assert transfers.calls == []

    def test_the_maximum_per_transfer_in_the_settings(self, signed_in, transfers, linked):
        _settings(signed_in, construction_account_maximum_single_transfer_dollars=1000)
        response = _send(signed_in, linked["id"], "deposit", 5000)
        assert response.status_code == 409 and "per-transfer maximum" in response.json()["detail"]

    def test_the_hourly_limit_in_the_settings(self, signed_in, transfers, linked):
        _settings(signed_in, construction_account_transfers_per_hour_limit=1)
        assert _send(signed_in, linked["id"], "deposit", 1000, key="transfer-key-0001").status_code == 200
        response = _send(signed_in, linked["id"], "deposit", 1000, key="transfer-key-0002")
        assert response.status_code == 429 and len(transfers.calls) == 1
        assert _status(signed_in, linked["id"])["transfers_left_this_hour"] == 0

    def test_no_more_than_the_source_account_has_available(self, signed_in, transfers, linked):
        response = _send(signed_in, linked["id"], "deposit", 90000)
        assert response.status_code == 409 and "Only $80,000.00 is available" in response.json()["detail"]

    def test_no_transfer_token_names_the_setting_to_add(self, signed_in, transfers, linked, monkeypatch):
        monkeypatch.delenv("MERCURY_TRANSFER_API_TOKEN_AJYK")
        response = _send(signed_in, linked["id"], "deposit", 5000)
        assert response.status_code == 409 and "MERCURY_TRANSFER_API_TOKEN_AJYK" in response.json()["detail"]
        status = _status(signed_in, linked["id"])
        assert status["has_a_transfer_token"] is False and status["transfer_token_environment_variable_name"] == "MERCURY_TRANSFER_API_TOKEN_AJYK"

    def test_no_transfer_on_a_closed_out_account(self, signed_in, transfers, linked):
        assert signed_in.post(f"/liquidity/construction-accounts/{linked['id']}/mark-closed-out").status_code == 200
        response = _send(signed_in, linked["id"], "deposit", 5000)
        assert response.status_code == 409 and "closed out" in response.json()["detail"]

    def test_the_request_cannot_choose_the_accounts(self, signed_in, transfers, linked):
        response = _send(signed_in, linked["id"], "deposit", 1000, source_mercury_account_id="tax", destination_mercury_account_id="other-checking")
        assert response.status_code == 200
        assert (transfers.calls[0]["source"], transfers.calls[0]["destination"]) == ("checking", "construction")

    def test_an_unlinked_deal_cannot_transfer(self, signed_in, transfers, mercury, bought_deal):  # noqa: F811
        assert _send(signed_in, bought_deal["id"], "deposit", 1000).status_code == 404


class TestSteal:
    def test_above_safe_to_steal_needs_a_confirmation_naming_the_top_up(self, signed_in, transfers, linked, mercury):  # noqa: F811
        mercury.move("construction", "draw-1", 35000, counterparty_name="Lender")   # 35,000 + (70,000 - 35,000) - 50,000 = 20,000 back
        _refresh(signed_in, DURING_THE_REHAB)
        assert _status(signed_in, linked["id"])["safe_to_steal_now_dollars"] == 20000
        refused = _send(signed_in, linked["id"], "steal", 25000)
        assert refused.status_code == 409 and "$5,000.00 above safe to steal now" in refused.json()["detail"]
        assert transfers.calls == []
        confirmed = _send(signed_in, linked["id"], "steal", 25000, confirm_amount_exceeds_safe_to_steal=True)
        assert confirmed.status_code == 200, confirmed.text
        assert (transfers.calls[0]["source"], transfers.calls[0]["destination"]) == ("construction", "checking")
        status = _status(signed_in, linked["id"])
        assert status["own_money_transferred_out_of_the_account_dollars"] == 25000
        # $5,000 short at rehab end, which the $5,000 deposit still to come covers: no top-up yet.
        assert (status["projected_return_at_rehab_end_dollars"], status["top_up_needed_dollars"]) == (-5000, 0)


class TestNeverAnMcpTool:
    def test_deposit_and_steal_are_not_tools(self):
        assert {"deposit_into_liquidity_construction_account", "steal_from_liquidity_construction_account"} <= mcp_server.EXCLUDED_TOOL_NAMES
        assert not [name for name in mcp_server.tools() if "deposit_into" in name or "steal_from" in name]


class TestTheSameKeyAtOnce:
    def test_a_second_request_racing_the_first_is_refused_and_asks_mercury_nothing(self, signed_in, transfers, linked, monkeypatch):
        """Both pass the 'already asked?' check; the stored key lets only one through."""
        monkeypatch.setattr(transfers_module, "get_transfer_by_idempotency_key", lambda db, key: None)
        assert _send(signed_in, linked["id"], "deposit", 5000).status_code == 200
        racing = _send(signed_in, linked["id"], "deposit", 5000)
        assert racing.status_code == 409 and "already being sent" in racing.json()["detail"]
        assert len(transfers.calls) == 1
