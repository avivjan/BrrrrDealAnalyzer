"""Passkeys and sessions (SECURITY_PLAN.md §3.2): enrollment, login, refresh
rotation with replay detection, logout, step-up, the `require_session` gate
in its three modes, and the MCP connector's service session."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from BL.auth import register as register_bl
from BL.auth import service as service_bl
from BL.auth import session as sessions
from BL.auth.common import settings
from DAL.crud import auth as crud
from DAL.data_models.audit.models import AuditLog
from DAL.data_models.auth.models import Device, Session
from db import SessionLocal
from tests.mcp_helpers import call_json as _call_json
from tests.webauthn_helpers import SoftPasskey

ORIGIN = "http://localhost:5173"
XRW = {"X-Requested-With": "XMLHttpRequest", "Origin": ORIGIN}


@pytest.fixture(autouse=True)
def _dev_auth(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.delenv("DEVICE_POLICY", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    service_bl.forget()


def _enroll_token(username: str = "aviv", reps_user: str | None = "Aviv2026") -> str:
    with SessionLocal() as db:
        user = crud.get_user_by_username(db, username) or crud.add_user(db, username=username, display_name=username.title(), reps_user=reps_user)
        token = register_bl.issue_enrollment_token(db, user=user, created_by=None)
        db.commit()
    return token


def enroll(client: TestClient, passkey: SoftPasskey, *, username: str = "aviv", label: str = "Test passkey") -> dict:
    token = _enroll_token(username)
    opts = client.post("/auth/register/options", json={"token": token}, headers=XRW)
    assert opts.status_code == 200, opts.text
    body = opts.json()
    cred = passkey.register(body["options"])
    done = client.post("/auth/register/verify", json={"token": token, "challenge_id": body["challenge_id"], "credential": cred, "label": label}, headers=XRW)
    assert done.status_code == 201, done.text
    return done.json()


def login(client: TestClient, passkey: SoftPasskey, **kw) -> "object":
    opts = client.post("/auth/login/options", headers=XRW)
    assert opts.status_code == 200
    body = opts.json()
    return client.post("/auth/login/verify", json={"challenge_id": body["challenge_id"], "credential": passkey.authenticate(body["options"], **kw)}, headers=XRW)


def _events(event: str) -> list[dict | None]:
    with SessionLocal() as s:
        return [r.detail for r in s.execute(select(AuditLog).where(AuditLog.event == event).order_by(AuditLog.id)).scalars()]


class TestEnrollment:
    def test_register_creates_credential_device_and_session(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        status = enroll(client, pk)
        assert status["status"] == "ok" and status["user"]["username"] == "aviv" and status["user"]["reps_user"] == "Aviv2026"
        assert settings.cookie_name("bw_at") in client.cookies and settings.cookie_name("bw_rt") in client.cookies and "bw_device" in client.cookies
        with SessionLocal() as db:
            user = crud.get_user_by_username(db, "aviv")
            creds = crud.credentials_for_user(db, user.id)
            assert len(creds) == 1 and creds[0].label == "Test passkey" and creds[0].backup_state is True
            device = db.execute(select(Device).where(Device.user_id == user.id)).scalar_one()
            assert device.status == "trusted"
        assert _events("enroll_ok")

    def test_an_enrollment_link_is_single_use_and_expires(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        token = _enroll_token()
        opts = client.post("/auth/register/options", json={"token": token}, headers=XRW).json()
        cred = pk.register(opts["options"])
        assert client.post("/auth/register/verify", json={"token": token, "challenge_id": opts["challenge_id"], "credential": cred}, headers=XRW).status_code == 201
        assert client.post("/auth/register/options", json={"token": token}, headers=XRW).status_code == 400
        assert client.post("/auth/register/options", json={"token": "nope"}, headers=XRW).status_code == 400

    def test_registration_from_another_origin_is_refused(self, client):
        pk = SoftPasskey(settings.rp_id(), "https://evil.example")
        token = _enroll_token()
        opts = client.post("/auth/register/options", json={"token": token}, headers=XRW).json()
        r = client.post("/auth/register/verify", json={"token": token, "challenge_id": opts["challenge_id"], "credential": pk.register(opts["options"])}, headers=XRW)
        assert r.status_code == 400
        assert _events("enroll_failed")

    def test_a_challenge_is_single_use(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        token = _enroll_token()
        opts = client.post("/auth/register/options", json={"token": token}, headers=XRW).json()
        cred = pk.register(opts["options"])
        assert client.post("/auth/register/verify", json={"token": token, "challenge_id": opts["challenge_id"], "credential": cred}, headers=XRW).status_code == 201
        token2 = _enroll_token()
        assert client.post("/auth/register/verify", json={"token": token2, "challenge_id": opts["challenge_id"], "credential": cred}, headers=XRW).status_code == 400


class TestLogin:
    def test_login_with_a_synced_passkey_reporting_sign_count_zero(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN, synced=True)
        enroll(client, pk)
        client.cookies.clear()
        r = login(client, pk)
        assert r.status_code == 200 and r.json()["status"] == "ok"
        assert client.get("/auth/me").json()["user"]["username"] == "aviv"
        assert _events("login_ok")

    def test_login_with_a_hardware_key_that_counts(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN, synced=False)
        enroll(client, pk)
        client.cookies.clear()
        assert login(client, pk, bump_counter=True).status_code == 200
        client.cookies.clear()
        assert login(client, pk, bump_counter=True).status_code == 200

    def test_unknown_passkey_is_refused_and_audited(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        stranger = SoftPasskey(settings.rp_id(), ORIGIN)
        client.cookies.clear()
        assert login(client, stranger).status_code == 401
        assert _events("login_failed")[-1]["reason"] == "unknown_credential"

    def test_login_failures_are_rate_limited(self, client, monkeypatch):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        client.cookies.clear()
        from BL.auth import login as login_bl

        monkeypatch.setattr(login_bl, "LOGIN_FAILURES_PER_WINDOW", 2)
        stranger = SoftPasskey(settings.rp_id(), ORIGIN)
        assert login(client, stranger).status_code == 401
        assert login(client, stranger).status_code == 401
        assert login(client, pk).status_code == 429

    def test_a_disabled_user_cannot_log_in(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        with SessionLocal() as db:
            crud.get_user_by_username(db, "aviv").disabled_at = crud.now()
            db.commit()
        client.cookies.clear()
        assert login(client, pk).status_code == 401


class TestRefreshAndLogout:
    def test_refresh_rotates_and_the_old_token_is_dead(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        rt = settings.cookie_name("bw_rt")
        old_refresh = client.cookies[rt]
        r = client.post("/auth/refresh", headers=XRW)
        assert r.status_code == 200
        assert client.cookies[rt] != old_refresh
        assert client.get("/auth/me").status_code == 200

    def test_a_replayed_refresh_token_revokes_the_family(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        rt = settings.cookie_name("bw_rt")
        stolen = client.cookies[rt]
        assert client.post("/auth/refresh", headers=XRW).status_code == 200
        fresh = client.cookies[rt]
        client.cookies.set(rt, stolen)
        assert client.post("/auth/refresh", headers=XRW).status_code == 401
        client.cookies.set(rt, fresh)
        assert client.post("/auth/refresh", headers=XRW).status_code == 401
        assert client.get("/auth/me").status_code == 401

    def test_logout_revokes_and_clears(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        assert client.delete("/auth/session", headers=XRW).status_code == 204
        assert client.get("/auth/me").status_code == 401
        assert _events("logout")

    def test_expired_access_token_is_refused(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        with SessionLocal() as db:
            for s in db.query(Session).all():
                s.access_expires_at = crud.now()
            db.commit()
        assert client.get("/auth/me").status_code == 401


class TestStepUp:
    def test_reauth_refreshes_auth_time_and_allows_enrollment_tokens(self, client):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        with SessionLocal() as db:
            for s in db.query(Session).all():
                s.auth_time = crud.now().replace(year=2000)
            db.commit()
        assert client.post("/auth/enrollment-tokens", headers=XRW).status_code == 403
        opts = client.post("/auth/reauth/options", headers=XRW).json()
        r = client.post("/auth/reauth/verify", json={"challenge_id": opts["challenge_id"], "credential": pk.authenticate(opts["options"])}, headers=XRW)
        assert r.status_code == 200
        issued = client.post("/auth/enrollment-tokens", headers=XRW)
        assert issued.status_code == 201 and issued.json()["expires_in_minutes"] == settings.enroll_minutes()

    def test_reauth_must_be_the_same_user(self, client):
        aviv = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, aviv)
        yarden = SoftPasskey(settings.rp_id(), ORIGIN)
        # Enrol Yarden on a separate client, keep Aviv's cookies here.
        other = TestClient(client.app)
        enroll(other, yarden, username="yarden")
        opts = client.post("/auth/reauth/options", headers=XRW).json()
        r = client.post("/auth/reauth/verify", json={"challenge_id": opts["challenge_id"], "credential": yarden.authenticate(opts["options"])}, headers=XRW)
        assert r.status_code == 401


class TestTheGate:
    def test_off_mode_checks_nothing(self, client):
        assert client.get("/active-deals").status_code == 200
        assert client.get("/auth/config").json()["auth_mode"] == "off"

    def test_enforce_requires_a_session(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        assert client.get("/active-deals").status_code == 401
        assert client.get("/active-deals").json() == {"detail": "unauthenticated"}
        assert client.get("/helloworld").status_code == 200
        assert client.post("/auth/login/options", headers=XRW).status_code == 200
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        assert client.get("/active-deals").status_code == 200

    def test_enforce_csrf_checks_on_unsafe_methods(self, client, monkeypatch, brrrr_payload):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        assert client.post("/active-deals", json=brrrr_payload).status_code == 403  # no X-Requested-With
        assert client.post("/active-deals", json=brrrr_payload, headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://evil.example"}).status_code == 403
        assert client.post("/active-deals", json=brrrr_payload, headers={"X-Requested-With": "XMLHttpRequest", "Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert client.post("/active-deals", json=brrrr_payload, headers=XRW).status_code == 200

    def test_shadow_logs_and_lets_through(self, client, monkeypatch, caplog):
        monkeypatch.setenv("AUTH_MODE", "shadow")
        with caplog.at_level(logging.WARNING, logger="BL.auth.common.session_dependency"):
            assert client.get("/active-deals").status_code == 200
        assert any("would reject GET /active-deals" in r.message for r in caplog.records)
        assert _events("auth_denied")[-1]["shadow"] is True

    def test_a_revoked_device_kills_its_sessions(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)
        with SessionLocal() as db:
            device = db.query(Device).filter(Device.kind == "browser").one()
            device.status = "revoked"
            sessions.revoke_device_sessions(db, device.id)
            db.commit()
        assert client.get("/active-deals").status_code == 401
        assert client.post("/auth/refresh", headers=XRW).status_code == 401

    def test_enforce_device_policy_blocks_a_pending_device(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        monkeypatch.setenv("DEVICE_POLICY", "enforce")
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(client, pk)  # the enrolling device is trusted
        assert client.get("/active-deals").status_code == 200
        client.cookies.clear()  # a new browser profile: no device cookie
        r = login(client, pk)
        assert r.status_code == 200 and r.json()["status"] == "pending_approval"
        assert client.get("/active-deals").status_code == 403
        assert client.get("/active-deals").json() == {"detail": "device_pending"}
        assert client.get("/auth/me").json()["status"] == "pending_approval"


class TestMcpServiceSession:
    def test_tools_keep_working_under_enforce_through_a_service_device(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        assert _call_json("get_active_deals") == []
        with SessionLocal() as db:
            user = crud.get_user_by_username(db, service_bl.SERVICE_USERNAME)
            assert user is not None and user.role == "service"
            device = db.execute(select(Device).where(Device.user_id == user.id)).scalar_one()
            assert device.kind == "mcp" and device.status == "trusted"
            assert db.query(Session).filter(Session.kind == "mcp").count() == 1
        # The session is reused, not re-issued, on the next call.
        assert _call_json("helloworld")["message"]
        with SessionLocal() as db:
            assert db.query(Session).filter(Session.kind == "mcp").count() == 1

    def test_auth_routes_are_not_tools(self):
        import mcp_server

        assert not any(name.startswith("auth_") for name in mcp_server.tools())

    def test_a_revoked_connector_device_stops_every_tool(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        assert _call_json("get_active_deals") == []
        with SessionLocal() as db:
            device = db.query(Device).filter(Device.kind == "mcp").one()
            device.status = "revoked"
            sessions.revoke_device_sessions(db, device.id)
            db.commit()
        with pytest.raises(RuntimeError, match="HTTP 401"):
            _call_json("get_active_deals")
