"""MCP_AUTH_MODE=oauth (SECURITY_PLAN.md §3.6): a connector registers, the
owner approves it on the SPA's /connect page with a passkey session, and the
bearer token it receives is a revocable `mcp` device session that goes through
the same `require_session` gate as the website."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

import main as app_main
import mcp_server
from BL.auth import service as service_bl
from BL.auth.common import settings
from DAL.crud import auth as crud
from DAL.data_models.audit.models import AuditLog
from DAL.data_models.auth.models import Device, Session
from db import SessionLocal
from tests.test_auth_passkeys import ORIGIN, XRW, enroll
from tests.webauthn_helpers import SoftPasskey

ISSUER = "http://localhost:8000"
REDIRECT = "http://localhost:9999/callback"
RPC = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
LIST_TOOLS = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


def _call(name, arguments=None):
    return {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}


@pytest.fixture
def oauth_app(monkeypatch):
    """A second app wired like main.py but mounted in OAuth mode."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("MCP_AUTH_MODE", "oauth")
    monkeypatch.setenv("MCP_ISSUER_URL", ISSUER)
    monkeypatch.delenv("MCP_PATH_SECRET", raising=False)
    monkeypatch.delenv("DEVICE_POLICY", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    service_bl.forget()
    saved = (mcp_server._app, mcp_server._tools)
    app = FastAPI(lifespan=mcp_server.lifespan)
    app_main.install_routers(app)
    assert mcp_server.mount(app) == "/mcp"
    try:
        with TestClient(app) as client:
            yield client
    finally:
        mcp_server._app, mcp_server._tools = saved


def _pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def register(client: TestClient) -> str:
    r = client.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "Claude", "token_endpoint_auth_method": "none"})
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


def connect(client: TestClient, *, approve_headers=XRW) -> tuple[str, str, str]:
    """DCR -> /authorize -> owner approves on /connect -> /token. Returns (client_id, access, refresh)."""
    client_id = register(client)
    verifier, challenge = _pkce()
    r = client.get(
        "/authorize",
        params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "code_challenge": challenge, "code_challenge_method": "S256", "state": "xyz", "scope": "tools"},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    location = r.headers["location"]
    assert location.startswith(f"{ORIGIN}/connect?txn="), location
    txn = parse_qs(urlparse(location).query)["txn"][0]

    shown = client.get(f"/auth/oauth/txn/{txn}")
    assert shown.status_code == 200, shown.text
    assert shown.json()["client_name"] == "Claude" and shown.json()["scopes"] == ["tools"]

    approved = client.post("/auth/oauth/approve", json={"txn": txn}, headers=approve_headers)
    assert approved.status_code == 200, approved.text
    back = urlparse(approved.json()["redirect_uri"])
    assert back.scheme + "://" + back.netloc + back.path == REDIRECT
    query = parse_qs(back.query)
    assert query["state"] == ["xyz"]

    token = client.post("/token", data={"grant_type": "authorization_code", "code": query["code"][0], "redirect_uri": REDIRECT, "client_id": client_id, "code_verifier": verifier})
    assert token.status_code == 200, token.text
    body = token.json()
    assert body["token_type"].lower() == "bearer" and body["refresh_token"]
    return client_id, body["access_token"], body["refresh_token"]


def _rpc(client: TestClient, access: str | None, payload: dict):
    headers = dict(RPC)
    if access:
        headers["Authorization"] = f"Bearer {access}"
    return client.post("/mcp", json=payload, headers=headers)


class TestConnectorFlow:
    def test_metadata_documents_are_served(self, oauth_app):
        meta = oauth_app.get("/.well-known/oauth-authorization-server")
        assert meta.status_code == 200 and meta.json()["issuer"].rstrip("/") == ISSUER
        assert meta.json()["code_challenge_methods_supported"] == ["S256"]
        resource = oauth_app.get("/.well-known/oauth-protected-resource/mcp")
        assert resource.status_code == 200 and resource.json()["authorization_servers"][0].rstrip("/") == ISSUER

    def test_no_bearer_is_401_with_a_www_authenticate_hint(self, oauth_app):
        r = _rpc(oauth_app, None, LIST_TOOLS)
        assert r.status_code == 401
        assert "oauth-protected-resource" in r.headers["www-authenticate"]
        assert _rpc(oauth_app, "not-a-token", LIST_TOOLS).status_code == 401

    def test_consent_needs_a_trusted_session(self, oauth_app):
        client_id = register(oauth_app)
        _, challenge = _pkce()
        r = oauth_app.get("/authorize", params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "code_challenge": challenge, "code_challenge_method": "S256"}, follow_redirects=False)
        txn = parse_qs(urlparse(r.headers["location"]).query)["txn"][0]
        assert oauth_app.get(f"/auth/oauth/txn/{txn}").status_code == 401
        assert oauth_app.post("/auth/oauth/approve", json={"txn": txn}, headers=XRW).status_code == 401
        # nothing was minted for an anonymous approve
        with SessionLocal() as db:
            assert db.execute(select(Device).where(Device.kind == "mcp")).first() is None

    def test_approve_then_tools_work_as_the_owner(self, oauth_app, monkeypatch):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(oauth_app, pk)
        client_id, access, refresh = connect(oauth_app)

        with SessionLocal() as db:
            device = db.execute(select(Device).where(Device.kind == "mcp")).scalar_one()
            assert device.status == "trusted" and device.label == "MCP: Claude"
            row = db.execute(select(Session).where(Session.kind == "mcp")).scalar_one()
            assert row.oauth_client_id == client_id and row.device_id == device.id and row.scopes == "tools"

        listed = _rpc(oauth_app, access, LIST_TOOLS)
        assert listed.status_code == 200, listed.text
        names = {t["name"] for t in listed.json()["result"]["tools"]}
        assert "get_active_deals" in names and not any(n.startswith("auth") for n in names)

        # Tools run as the connector's own session, even with sessions enforced.
        monkeypatch.setenv("AUTH_MODE", "enforce")
        hello = _rpc(oauth_app, access, _call("helloworld"))
        assert hello.status_code == 200 and not hello.json()["result"].get("isError"), hello.text
        deals = _rpc(oauth_app, access, _call("get_active_deals"))
        assert deals.status_code == 200 and not deals.json()["result"].get("isError"), deals.text
        with SessionLocal() as db:
            audit = db.execute(select(AuditLog).where(AuditLog.event == "mcp_tool_call").order_by(AuditLog.id.desc())).scalars().first()
            user = crud.get_user_by_username(db, "aviv")
            assert audit.detail["tool"] == "get_active_deals" and audit.user_id == user.id

    def test_refresh_rotates_and_revocation_kills_the_token(self, oauth_app):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(oauth_app, pk)
        client_id, access, refresh = connect(oauth_app)

        rotated = oauth_app.post("/token", data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id})
        assert rotated.status_code == 200, rotated.text
        new_access, new_refresh = rotated.json()["access_token"], rotated.json()["refresh_token"]
        assert new_access != access and new_refresh != refresh
        assert _rpc(oauth_app, new_access, LIST_TOOLS).status_code == 200
        # a replayed refresh token is refused
        assert oauth_app.post("/token", data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id}).status_code == 400

        # the SDK's RevocationRequest declares client_secret without a default, so a public client sends it empty
        revoked = oauth_app.post("/revoke", data={"token": new_access, "client_id": client_id, "client_secret": ""})
        assert revoked.status_code == 200, revoked.text
        assert _rpc(oauth_app, new_access, LIST_TOOLS).status_code == 401

    def test_revoking_the_device_ends_every_token(self, oauth_app):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(oauth_app, pk)
        client_id, access, refresh = connect(oauth_app)
        assert _rpc(oauth_app, access, LIST_TOOLS).status_code == 200
        with SessionLocal() as db:
            device = db.execute(select(Device).where(Device.kind == "mcp")).scalar_one()
            device.status = "revoked"
            db.commit()
        assert _rpc(oauth_app, access, LIST_TOOLS).status_code == 401
        assert oauth_app.post("/token", data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id}).status_code == 400

    def test_a_code_is_single_use_and_bound_to_its_verifier(self, oauth_app):
        pk = SoftPasskey(settings.rp_id(), ORIGIN)
        enroll(oauth_app, pk)
        client_id = register(oauth_app)
        verifier, challenge = _pkce()
        r = oauth_app.get("/authorize", params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "code_challenge": challenge, "code_challenge_method": "S256"}, follow_redirects=False)
        txn = parse_qs(urlparse(r.headers["location"]).query)["txn"][0]
        code = parse_qs(urlparse(oauth_app.post("/auth/oauth/approve", json={"txn": txn}, headers=XRW).json()["redirect_uri"]).query)["code"][0]
        wrong = oauth_app.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "client_id": client_id, "code_verifier": "wrong-" + verifier})
        assert wrong.status_code == 400
        ok = oauth_app.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "client_id": client_id, "code_verifier": verifier})
        assert ok.status_code == 200
        again = oauth_app.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "client_id": client_id, "code_verifier": verifier})
        assert again.status_code == 400
        # approving the same transaction twice is refused
        assert oauth_app.post("/auth/oauth/approve", json={"txn": txn}, headers=XRW).status_code == 400


class TestPathModeUnchanged:
    def test_the_default_app_has_no_oauth_routes(self, client):
        assert client.post("/register", json={"redirect_uris": [REDIRECT]}).status_code == 404
        assert client.get("/.well-known/oauth-authorization-server").status_code == 404
        assert client.get("/auth/oauth/txn/00000000-0000-4000-8000-000000000000").status_code == 401
