"""Phase 0 shared-key gate (BL/auth/common/app_key.py, wired in main.py).

Every operation in the committed OpenAPI snapshot -- the same list the MCP
server derives its tools from -- must answer 401 `app_key_required` without
the key under `APP_KEY_MODE=enforce`, and must not answer 401 with it. The
health ping stays public. `off` (the default) and `shadow` never reject.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re

import pytest

from BL.auth.common.app_key import DETAIL, HEADER

GOLDEN_OPENAPI = pathlib.Path(__file__).parent / "_regression_snapshots" / "openapi.json"
KEY = "phase0-test-key-0123456789abcdef"


def operations() -> list[tuple[str, str]]:
    spec = json.loads(GOLDEN_OPENAPI.read_text())
    return [(method.upper(), path) for path, ops in spec["paths"].items() for method in ops]


def concrete(path: str) -> str:
    # A well-formed but absent id: the point is "not 401", and an unparseable
    # id would surface the routes' pre-existing 500 on bad UUIDs instead.
    return re.sub(r"\{[^}]+\}", "00000000-0000-4000-8000-000000000000", path)


OPERATIONS = operations()
PROTECTED = [op for op in OPERATIONS if op[1] != "/helloworld" and not op[1].startswith("/auth")]


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setenv("APP_KEY_MODE", "enforce")
    monkeypatch.setenv("APP_KEY", KEY)


class TestEnforce:
    def test_the_snapshot_covers_every_route(self):
        assert len(OPERATIONS) >= 45

    @pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
    def test_every_data_operation_rejects_a_missing_key(self, client, enforce, method, path):
        response = client.request(method, concrete(path))
        assert response.status_code == 401
        assert response.json() == {"detail": DETAIL}

    @pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
    def test_every_data_operation_accepts_the_key(self, client, enforce, method, path):
        response = client.request(method, concrete(path), headers={HEADER: KEY})
        assert response.status_code != 401

    def test_a_wrong_key_is_rejected(self, client, enforce):
        response = client.get("/active-deals", headers={HEADER: KEY + "x"})
        assert response.status_code == 401

    def test_helloworld_stays_public(self, client, enforce):
        assert client.get("/helloworld").status_code == 200

    def test_enforce_without_a_configured_key_rejects_everything(self, client, monkeypatch):
        monkeypatch.setenv("APP_KEY_MODE", "enforce")
        monkeypatch.delenv("APP_KEY", raising=False)
        assert client.get("/active-deals", headers={HEADER: ""}).status_code == 401


class TestOffAndShadow:
    def test_off_is_the_default_and_checks_nothing(self, client, monkeypatch):
        monkeypatch.delenv("APP_KEY_MODE", raising=False)
        monkeypatch.setenv("APP_KEY", KEY)
        assert client.get("/active-deals").status_code == 200

    def test_shadow_logs_and_lets_the_request_through(self, client, monkeypatch, caplog):
        monkeypatch.setenv("APP_KEY_MODE", "shadow")
        monkeypatch.setenv("APP_KEY", KEY)
        with caplog.at_level(logging.WARNING, logger="BL.auth.common.app_key"):
            assert client.get("/active-deals").status_code == 200
        assert any("would reject GET /active-deals" in r.message for r in caplog.records)

    def test_shadow_is_quiet_when_the_key_is_right(self, client, monkeypatch, caplog):
        monkeypatch.setenv("APP_KEY_MODE", "shadow")
        monkeypatch.setenv("APP_KEY", KEY)
        with caplog.at_level(logging.WARNING, logger="BL.auth.common.app_key"):
            assert client.get("/active-deals", headers={HEADER: KEY}).status_code == 200
        assert not [r for r in caplog.records if "would reject" in r.message]

    def test_an_unknown_mode_falls_back_to_off(self, client, monkeypatch):
        monkeypatch.setenv("APP_KEY_MODE", "yes please")
        assert client.get("/active-deals").status_code == 200
