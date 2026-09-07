"""Trusted devices (SECURITY_PLAN.md §3.4): the dashboard endpoints, the
pending → approved state machine, revocation, session and passkey management,
and the step-up on /send-offer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from BL.auth import service as service_bl
from BL.auth import session as sessions
from BL.auth.common import settings
from DAL.crud import auth as crud
from DAL.data_models.audit.models import AuditLog
from DAL.data_models.auth.models import Session
from db import SessionLocal
from tests.mcp_helpers import call as _call, call_json as _call_json
from tests.test_auth_passkeys import ORIGIN, XRW, enroll, login
from tests.webauthn_helpers import SoftPasskey

CSRF = XRW


@pytest.fixture(autouse=True)
def _dev_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "enforce")
    monkeypatch.setenv("DEVICE_POLICY", "enforce")
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    service_bl.forget()


def _second_browser(client: TestClient, pk: SoftPasskey) -> tuple[dict, dict]:
    """Log the same passkey in from a fresh cookie jar; returns (cookies, status)."""
    trusted = dict(client.cookies)
    client.cookies.clear()
    r = login(client, pk)
    assert r.status_code == 200
    pending = dict(client.cookies)
    client.cookies.clear()
    client.cookies.update(trusted)
    return pending, r.json()


def _age_sessions(seconds: int = 3600) -> None:
    """Make every session's last passkey assertion `seconds` old (step-up expired)."""
    from datetime import timedelta

    with SessionLocal() as db:
        for row in db.execute(select(Session)).scalars():
            row.auth_time = crud.now() - timedelta(seconds=seconds)
        db.commit()


def _events(event: str) -> int:
    with SessionLocal() as s:
        return len(list(s.execute(select(AuditLog).where(AuditLog.event == event)).scalars()))


class TestGate:
    def test_everything_needs_a_session(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "off")  # even with sessions off there is nothing to manage anonymously
        for method, path in [("GET", "/devices"), ("GET", "/devices/me"), ("GET", "/sessions"), ("GET", "/credentials")]:
            assert client.request(method, path).status_code == 401, path
        assert client.post("/devices/00000000-0000-4000-8000-000000000000/approve", headers=CSRF).status_code == 401

    def test_mutations_need_the_csrf_headers(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        me = client.get("/devices/me").json()
        r = client.patch(f"/devices/{me['id']}", json={"label": "x"})
        assert r.status_code == 403 and r.json()["detail"].startswith("csrf")
        assert client.patch(f"/devices/{me['id']}", json={"label": "My laptop"}, headers=CSRF).json()["label"] == "My laptop"

    def test_devices_are_not_mcp_tools(self):
        import mcp_server

        assert not any(n.startswith(("devices", "sessions", "credentials")) for n in mcp_server.tools())


class TestApproval:
    def test_pending_device_is_listed_first_and_can_poll_itself(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        pending_cookies, status = _second_browser(client, pk)
        assert status["status"] == "pending_approval"

        listed = client.get("/devices").json()
        assert [d["status"] for d in listed] == ["pending", "trusted"]
        assert listed[1]["is_current"] and listed[0]["kind"] == "browser"

        # the pending browser may ask about itself and nothing else
        client.cookies.clear()
        client.cookies.update(pending_cookies)
        assert client.get("/devices/me").json()["status"] == "pending"
        assert client.get("/devices").status_code == 403
        assert client.get("/active-deals").status_code == 403

    def test_approve_promotes_the_device_and_its_sessions(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        pending_cookies, _ = _second_browser(client, pk)
        pending_id = next(d["id"] for d in client.get("/devices").json() if d["status"] == "pending")

        r = client.post(f"/devices/{pending_id}/approve", headers=CSRF)
        assert r.status_code == 200 and r.json()["status"] == "trusted" and r.json()["approved_at"]
        assert _events("device_approved") == 1

        client.cookies.clear()
        client.cookies.update(pending_cookies)
        assert client.get("/auth/me").json()["status"] == "ok"
        assert client.get("/active-deals").status_code == 200
        with SessionLocal() as db:
            assert all(s.status == "trusted" for s in crud.sessions_for_device(db, __import__("uuid").UUID(pending_id)))

    def test_approve_needs_a_recent_passkey_prompt(self, client, monkeypatch):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        _second_browser(client, pk)
        pending_id = next(d["id"] for d in client.get("/devices").json() if d["status"] == "pending")
        _age_sessions()
        r = client.post(f"/devices/{pending_id}/approve", headers=CSRF)
        assert r.status_code == 403 and r.json() == {"detail": "reauth_required"}
        opts = client.post("/auth/reauth/options", headers=CSRF).json()
        assert client.post("/auth/reauth/verify", json={"challenge_id": opts["challenge_id"], "credential": pk.authenticate(opts["options"])}, headers=CSRF).status_code == 200
        assert client.post(f"/devices/{pending_id}/approve", headers=CSRF).status_code == 200


class TestRevocation:
    def test_revoke_kills_the_device_and_all_its_sessions(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        other_cookies, _ = _second_browser(client, pk)
        other_id = next(d["id"] for d in client.get("/devices").json() if not d["is_current"])
        client.post(f"/devices/{other_id}/approve", headers=CSRF)

        r = client.post(f"/devices/{other_id}/revoke", headers=CSRF)
        assert r.status_code == 200 and r.json()["status"] == "revoked"
        assert all(d["id"] != other_id for d in client.get("/devices").json())  # revoked browsers drop out of the list
        client.cookies.clear()
        client.cookies.update(other_cookies)
        assert client.get("/active-deals").status_code == 401
        assert client.post("/auth/refresh", headers=CSRF).status_code == 401
        assert client.post("/devices/%s/approve" % other_id, headers=CSRF).status_code == 401

    def test_revoking_the_mcp_connector_stops_every_tool(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        assert _call_json("helloworld")["message"]  # creates the connector device
        mcp = next(d for d in client.get("/devices").json() if d["kind"] == "mcp")
        assert mcp["label"] == "MCP connector"
        assert client.post(f"/devices/{mcp['id']}/revoke", headers=CSRF).json()["status"] == "revoked"
        with pytest.raises(RuntimeError, match="HTTP 401"):
            _call("get_active_deals")
        # it stays visible (revoked) so the owner can see what happened
        assert any(d["id"] == mcp["id"] and d["status"] == "revoked" for d in client.get("/devices").json())


class TestSessions:
    def test_list_end_one_and_end_others(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        other_cookies, _ = _second_browser(client, pk)
        other_id = next(d["id"] for d in client.get("/devices").json() if not d["is_current"])
        client.post(f"/devices/{other_id}/approve", headers=CSRF)

        listed = client.get("/sessions").json()
        assert len(listed) == 2 and sum(s["is_current"] for s in listed) == 1
        other = next(s for s in listed if not s["is_current"])
        assert client.delete(f"/sessions/{other['id']}", headers=CSRF).status_code == 204
        assert len(client.get("/sessions").json()) == 1

        client.cookies.clear()
        client.cookies.update(other_cookies)
        assert client.get("/active-deals").status_code == 401

    def test_end_others_keeps_the_current_one(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        _second_browser(client, pk)
        assert client.post("/sessions/end-others", headers=CSRF).status_code == 204
        assert [s["is_current"] for s in client.get("/sessions").json()] == [True]
        assert client.get("/active-deals").status_code == 200

    def test_only_my_own_sessions(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        with SessionLocal() as db:
            other = crud.add_user(db, username="yarden", display_name="Yarden", reps_user="Yarden2026")
            device = crud.add_device(db, user_id=other.id, kind="browser", device_key_hash=crud.sha256("k"), status="trusted")
            row, _, _ = sessions.issue_session(db, user=other, device=device, credential_id=None, request=None)
            db.commit()
            foreign = str(row.id)
        assert all(s["id"] != foreign for s in client.get("/sessions").json())
        assert client.delete(f"/sessions/{foreign}", headers=CSRF).status_code == 404


class TestCredentials:
    def test_list_and_the_last_passkey_is_undeletable(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk, label="Phone")
        creds = client.get("/credentials").json()
        assert [c["label"] for c in creds] == ["Phone"]
        r = client.delete(f"/credentials/{creds[0]['id']}", headers=CSRF)
        assert r.status_code == 409 and r.json() == {"detail": "last_credential"}

    def test_a_second_passkey_can_be_removed(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk, label="Phone")
        token = client.post("/auth/enrollment-tokens", headers=CSRF).json()["token"]
        key = SoftPasskey(settings.rp_id(), ORIGIN)
        opts = client.post("/auth/register/options", json={"token": token}, headers=CSRF).json()
        # a second passkey for the same person, enrolled on this device
        r = client.post("/auth/register/verify", json={"token": token, "challenge_id": opts["challenge_id"], "credential": key.register(opts["options"]), "label": "Key"}, headers=CSRF)
        assert r.status_code == 201, r.text
        creds = client.get("/credentials").json()
        assert sorted(c["label"] for c in creds) == ["Key", "Phone"]
        gone = next(c for c in creds if c["label"] == "Key")
        assert client.delete(f"/credentials/{gone['id']}", headers=CSRF).status_code == 204
        assert [c["label"] for c in client.get("/credentials").json()] == ["Phone"]
        assert client.get("/active-deals").status_code == 200  # the session survives
        assert _events("credential_deleted") == 1


class TestStepUp:
    OFFER = {"agent_name": "Agent", "agent_email": "agent@example.com", "property_address": "1 Main St", "purchase_price": 100000, "inspection_period_days": 7}

    def _send(self, client):
        return client.post("/send-offer", json=self.OFFER, headers=CSRF)

    def test_send_offer_needs_a_fresh_prompt_only_when_enforced(self, client, monkeypatch):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        _age_sessions()
        r = self._send(client)
        assert r.status_code == 403 and r.json() == {"detail": "reauth_required"}
        # a fresh prompt unlocks it (no mail password is configured, so the send itself fails as today)
        opts = client.post("/auth/reauth/options", headers=CSRF).json()
        client.post("/auth/reauth/verify", json={"challenge_id": opts["challenge_id"], "credential": pk.authenticate(opts["options"])}, headers=CSRF)
        assert self._send(client).status_code == 500
        # shadow and off: today's behaviour, no step-up
        _age_sessions()
        for mode in ("shadow", "off"):
            monkeypatch.setenv("AUTH_MODE", mode)
            assert self._send(client).status_code == 500

    def test_mcp_sessions_are_exempt(self, client, monkeypatch):
        monkeypatch.setenv("DEVICE_POLICY", "off")
        _call_json("helloworld")
        _age_sessions()
        with pytest.raises(RuntimeError) as err:
            _call("send_offer", body=self.OFFER)
        assert "HTTP 500" in str(err.value) and "reauth_required" not in str(err.value)
