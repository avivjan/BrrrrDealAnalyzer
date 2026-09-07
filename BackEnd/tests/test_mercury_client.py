"""Mercury client hygiene (F-05, F-21): only `/accounts` is ever requested,
the token is never in a string except the Authorization header, upstream
error bodies are not relayed, and a fresh summary is cached."""

from __future__ import annotations

import pytest
import requests

from BL.liquidity.common import mercury_client as mc


class _Resp:
    def __init__(self, status: int, body=None, text: str = ""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.fixture(autouse=True)
def _tokens(monkeypatch):
    for k in [k for k in list(__import__("os").environ) if k.startswith("MERCURY_API_TOKEN")]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MERCURY_API_TOKEN_AJYK", "sekrit-token-ajyk-0001")
    monkeypatch.delenv("MERCURY_CACHE_SECONDS", raising=False)
    mc.clear_cache()
    yield
    mc.clear_cache()


def _ok_accounts():
    return _Resp(200, {"accounts": [{"id": "a1", "name": "Ops", "type": "checking", "status": "active", "currentBalance": 12000, "availableBalance": 11000}]})


def test_tokens_are_secrets_and_only_accounts_is_called(monkeypatch):
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return _ok_accounts()

    monkeypatch.setattr(requests, "get", fake_get)
    tokens = mc.discover_tokens()
    assert "sekrit" not in repr(tokens) and "sekrit" not in str(tokens)
    summary = mc.summarize_balance()
    assert [c[0] for c in calls] == [mc.ACCOUNTS_URL]
    assert calls[0][1]["Authorization"] == "Bearer sekrit-token-ajyk-0001"
    assert calls[0][2] == mc.MERCURY_TIMEOUT_SECONDS
    assert summary["total_balance_k"] == 12.0 and summary["workspace_count"] == 1
    assert "sekrit" not in repr(summary)


def test_a_fresh_summary_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "get", lambda *a, **k: (calls.append(1), _ok_accounts())[1])
    first = mc.summarize_balance()
    second = mc.summarize_balance()
    assert first is second and len(calls) == 1
    mc.clear_cache()
    mc.summarize_balance()
    assert len(calls) == 2


def test_cache_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MERCURY_CACHE_SECONDS", "0")
    calls = []
    monkeypatch.setattr(requests, "get", lambda *a, **k: (calls.append(1), _ok_accounts())[1])
    mc.summarize_balance()
    mc.summarize_balance()
    assert len(calls) == 2


def test_upstream_error_bodies_are_not_relayed(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(500, text="internal id 42 for token sekrit"))
    with pytest.raises(mc.MercuryApiError) as excinfo:
        mc.summarize_balance()
    assert str(excinfo.value) == "AJYK: HTTP 500"


def test_request_exceptions_are_generic(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("https://api.mercury.com/api/v1/accounts?Authorization=Bearer sekrit")

    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(mc.MercuryApiError) as excinfo:
        mc.summarize_balance()
    assert "sekrit" not in str(excinfo.value)
    assert str(excinfo.value) == "AJYK: request failed"


def test_errors_are_never_cached(monkeypatch):
    responses = iter([_Resp(503, text="down"), _ok_accounts()])
    monkeypatch.setattr(requests, "get", lambda *a, **k: next(responses))
    with pytest.raises(mc.MercuryApiError):
        mc.summarize_balance()
    assert mc.summarize_balance()["workspace_count"] == 1
