"""The Mercury transfer client (tasks/todo/ConstructionAccountPerRehab.md, Step E): one pinned URL, the transfer token
only, never retried, and Mercury's answer read defensively."""

from __future__ import annotations

from decimal import Decimal

import pytest
import requests

from BL.liquidity.common import mercury_transfers
from BL.liquidity.common.mercury_client import MercuryApiError, MercurySlowDownError
from BL.liquidity.common.mercury_transfers import (
    TRANSFER_URL, MercuryTransferNotAnsweredError, MercuryTransferTokenMissingError, send_internal_transfer,
)


class FakeResponse:
    def __init__(self, status_code: int, body=None, headers=None):
        self.status_code, self._body, self.headers = status_code, body, headers or {}
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


@pytest.fixture
def posts(monkeypatch):
    calls = []
    answers = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(dict(url=url, json=json, headers=headers))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    for name in [name for name in __import__("os").environ if name.startswith("MERCURY_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MERCURY_API_TOKEN_AJYK", "the-read-token")
    monkeypatch.setenv("MERCURY_TRANSFER_API_TOKEN_AJYK", "the-transfer-token")
    monkeypatch.setattr(mercury_transfers.requests, "post", fake_post)
    return calls, answers


def _send(**changes):
    arguments = dict(mercury_workspace_label="AJYK", source_mercury_account_id="checking", destination_mercury_account_id="construction",
                     amount_dollars=Decimal("5000.004"), idempotency_key="transfer-key-0001", note="Deposit: 12 Oak St")
    return send_internal_transfer(**{**arguments, **changes})


def test_one_pinned_url_the_transfer_token_and_the_body_mercury_documents(posts):
    calls, answers = posts
    answers.append(FakeResponse(200, {"id": "mercury-transfer-1", "status": "sent"}))
    answer = _send()
    assert (answer.mercury_transfer_id, answer.mercury_transfer_status) == ("mercury-transfer-1", "sent")
    assert [call["url"] for call in calls] == [TRANSFER_URL] == ["https://api.mercury.com/api/v1/transfer"]
    assert calls[0]["headers"]["Authorization"] == "Bearer the-transfer-token"
    assert calls[0]["json"] == {"sourceAccountId": "checking", "destinationAccountId": "construction", "amount": 5000.0,
                                "idempotencyKey": "transfer-key-0001", "note": "Deposit: 12 Oak St"}


def test_no_transfer_token_never_falls_back_to_the_read_token(posts, monkeypatch):
    calls, _answers = posts
    monkeypatch.delenv("MERCURY_TRANSFER_API_TOKEN_AJYK")
    with pytest.raises(MercuryTransferTokenMissingError) as error:
        _send()
    assert error.value.transfer_token_environment_variable_name == "MERCURY_TRANSFER_API_TOKEN_AJYK"
    assert "the-read-token" not in str(error.value) and calls == []


def test_a_timeout_or_a_server_error_is_maybe_sent_and_never_retried(posts):
    calls, answers = posts
    answers.append(requests.Timeout("read timed out with headers Authorization: Bearer the-transfer-token"))
    with pytest.raises(MercuryTransferNotAnsweredError) as error:
        _send()
    assert "the-transfer-token" not in str(error.value)
    answers.append(FakeResponse(503))
    with pytest.raises(MercuryTransferNotAnsweredError):
        _send()
    assert len(calls) == 2


def test_a_refusal_is_in_our_own_words(posts):
    _calls, answers = posts
    answers.append(FakeResponse(400, {"errors": {"message": "Insufficient funds in account 123456789"}}))
    with pytest.raises(MercuryApiError) as error:
        _send()
    assert str(error.value) == "HTTP 400"
    answers.append(FakeResponse(429, headers={"Retry-After": "30"}))
    with pytest.raises(MercurySlowDownError):
        _send()


@pytest.mark.parametrize("body, expected", [
    (None, (None, "unknown")),
    ({"status": "weird"}, (None, "unknown")),
    ({"transaction": {"id": "tx-9", "status": "Pending"}}, ("tx-9", "pending")),
    ({"id": "bad id with spaces", "status": "sent"}, (None, "sent")),
])
def test_the_answer_is_read_defensively(posts, body, expected):
    _calls, answers = posts
    answers.append(FakeResponse(200, body))
    answer = _send()
    assert (answer.mercury_transfer_id, answer.mercury_transfer_status) == expected


@pytest.mark.parametrize("changes", [
    dict(source_mercury_account_id="../accounts"), dict(destination_mercury_account_id=""),
    dict(idempotency_key="short"), dict(amount_dollars=Decimal("0")),
])
def test_bad_arguments_are_refused_before_any_call(posts, changes):
    calls, _answers = posts
    with pytest.raises(MercuryApiError):
        _send(**changes)
    assert calls == []
