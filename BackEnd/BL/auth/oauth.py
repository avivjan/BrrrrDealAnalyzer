"""OAuth 2.1 + PKCE for the MCP connector (SECURITY_PLAN.md §3.6).

The MCP Python SDK supplies the endpoints (`/authorize`, `/token`, `/register`,
`/revoke`, the metadata documents) and the bearer middleware; this module is
the provider behind them. Design:

- A registered client (claude.ai, Claude Code) starts `/authorize`; the
  request is parked as an `OAuthAuthorization` row and the browser is sent to
  the SPA's `/connect?txn=…`, which requires a trusted passkey session.
- The owner approves on that page; the API mints an authorization code bound
  to the PKCE challenge, the user and a new *device* of kind `mcp` (one per
  connector, visible and revocable like a browser).
- `/token` exchanges the code (verifier checked by the SDK) for an access
  token + refresh token: these ARE a `sessions` row of kind `mcp`, so the same
  `require_session` gate and the same revocation apply to tool calls.

Tokens are stored as SHA-256 hashes; the raw values go to the client only.
"""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import select

from BL.auth import session as sessions
from BL.auth.common import settings
from BL.auth.common.audit import record as audit
from DAL.crud import auth as crud
from DAL.data_models.auth.models import Device, OAuthAuthorization, OAuthClient, User
from db import SessionLocal

SCOPE = "tools"
CODE_MINUTES = 5
AUTHORIZATION_MINUTES = 15
DEFAULT_MCP_ACCESS_MINUTES = 60


def mcp_auth_mode() -> str:
    raw = (os.getenv("MCP_AUTH_MODE") or "path").strip().lower()
    return raw if raw in {"path", "oauth"} else "path"


def issuer_url() -> str:
    raw = (os.getenv("MCP_ISSUER_URL") or "").strip().rstrip("/")
    if raw:
        return raw
    return "https://brrrrdealanalyzer.onrender.com" if settings.is_production() else "http://localhost:8000"


def mcp_access_minutes() -> int:
    try:
        return max(1, int((os.getenv("AUTH_MCP_ACCESS_MINUTES") or DEFAULT_MCP_ACCESS_MINUTES)))
    except ValueError:
        return DEFAULT_MCP_ACCESS_MINUTES


def connect_url(txn_id: UUID) -> str:
    return f"{settings.allowed_origins()[0]}/connect?txn={txn_id}"


class BigWhalesOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    # --- clients (dynamic registration) --------------------------------------- #

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with SessionLocal() as db:
            row = db.get(OAuthClient, client_id)
            if row is None or row.disabled_at is not None:
                return None
            return OAuthClientInformationFull.model_validate(row.metadata_json)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        data = client_info.model_dump(mode="json")
        with SessionLocal() as db:
            db.add(
                OAuthClient(
                    client_id=client_info.client_id,
                    client_secret_hash=crud.sha256(client_info.client_secret) if client_info.client_secret else None,
                    client_name=(client_info.client_name or "")[:200] or None,
                    redirect_uris=[str(u) for u in (client_info.redirect_uris or [])],
                    metadata_json=data,
                )
            )
            audit("oauth_client_registered", None, detail={"client_id": client_info.client_id, "name": client_info.client_name})
            db.commit()

    # --- authorization ---------------------------------------------------------- #

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        with SessionLocal() as db:
            row = OAuthAuthorization(
                client_id=client.client_id,
                params=params.model_dump(mode="json"),
                expires_at=crud.now() + timedelta(minutes=AUTHORIZATION_MINUTES),
            )
            db.add(row)
            db.commit()
            return connect_url(row.id)

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> AuthorizationCode | None:
        with SessionLocal() as db:
            row = db.execute(select(OAuthAuthorization).where(OAuthAuthorization.code_hash == crud.sha256(authorization_code))).scalar_one_or_none()
            if row is None or row.client_id != client.client_id or row.code_used_at is not None or row.code_expires_at is None or row.code_expires_at < crud.now():
                return None
            params = row.params
            return AuthorizationCode(
                code=authorization_code,
                scopes=params.get("scopes") or [SCOPE],
                expires_at=row.code_expires_at.timestamp(),
                client_id=row.client_id,
                code_challenge=params["code_challenge"],
                redirect_uri=params["redirect_uri"],
                redirect_uri_provided_explicitly=bool(params.get("redirect_uri_provided_explicitly")),
                resource=params.get("resource"),
                subject=str(row.user_id) if row.user_id else None,
            )

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        with SessionLocal() as db:
            row = db.execute(select(OAuthAuthorization).where(OAuthAuthorization.code_hash == crud.sha256(authorization_code.code))).scalar_one_or_none()
            if row is None or row.code_used_at is not None or row.user_id is None or row.device_id is None:
                raise TokenError("invalid_grant", "authorization code is invalid")
            row.code_used_at = crud.now()
            user = crud.get_user(db, row.user_id)
            device = crud.get_device(db, row.device_id)
            if user is None or device is None or device.status == "revoked":
                raise TokenError("invalid_grant", "authorization is no longer valid")
            token = _issue(db, user=user, device=device, client_id=client.client_id, scopes=authorization_code.scopes)
            audit("oauth_token_issued", None, user_id=user.id, device_id=device.id, detail={"client_id": client.client_id, "grant": "authorization_code"})
            db.commit()
            return token

    # --- refresh ---------------------------------------------------------------- #

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        with SessionLocal() as db:
            row = crud.get_session_by_refresh_hash(db, crud.sha256(refresh_token))
            if row is None or row.kind != "mcp" or row.oauth_client_id != client.client_id or row.status == "revoked" or row.expires_at < crud.now():
                return None
            return RefreshToken(
                token=refresh_token,
                client_id=client.client_id,
                scopes=(row.scopes or SCOPE).split(","),
                expires_at=int(row.expires_at.timestamp()),
                subject=str(row.user_id),
            )

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        with SessionLocal() as db:
            rotated = sessions.refresh_session(db, refresh_token.token)
            if rotated is None:
                db.commit()
                raise TokenError("invalid_grant", "refresh token is invalid")
            row, access, new_refresh = rotated
            row.access_expires_at = crud.now() + timedelta(minutes=mcp_access_minutes())
            device = crud.get_device(db, row.device_id)
            if device is None or device.status == "revoked":
                sessions.revoke(row)
                db.commit()
                raise TokenError("invalid_grant", "device revoked")
            db.commit()
            return OAuthToken(
                access_token=access,
                token_type="Bearer",
                expires_in=mcp_access_minutes() * 60,
                scope=" ".join(scopes or refresh_token.scopes),
                refresh_token=new_refresh,
            )

    # --- access tokens (also the TokenVerifier) --------------------------------- #

    async def load_access_token(self, token: str) -> AccessToken | None:
        with SessionLocal() as db:
            row = sessions.verify_access(db, token)
            if row is None or row.kind != "mcp" or row.oauth_client_id is None:
                return None
            device = crud.get_device(db, row.device_id)
            if device is None or device.status != "trusted":
                return None
            db.commit()
            return AccessToken(
                token=token,
                client_id=row.oauth_client_id,
                scopes=(row.scopes or SCOPE).split(","),
                expires_at=int(row.access_expires_at.timestamp()),
                subject=str(row.user_id),
            )

    async def verify_token(self, token: str) -> AccessToken | None:  # TokenVerifier protocol
        return await self.load_access_token(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        with SessionLocal() as db:
            row = crud.get_session_by_access_hash(db, crud.sha256(token.token)) or crud.get_session_by_refresh_hash(db, crud.sha256(token.token))
            if row is not None:
                sessions.revoke(row)
                audit("oauth_token_revoked", None, user_id=row.user_id, session_id=row.id, device_id=row.device_id)
                db.commit()


def _issue(db, *, user: User, device: Device, client_id: str, scopes: list[str]) -> OAuthToken:
    session, access, refresh = sessions.issue_session(db, user=user, device=device, credential_id=None, request=None, kind="mcp")
    session.oauth_client_id = client_id
    session.scopes = ",".join(scopes or [SCOPE])
    session.access_expires_at = crud.now() + timedelta(minutes=mcp_access_minutes())
    return OAuthToken(
        access_token=access,
        token_type="Bearer",
        expires_in=mcp_access_minutes() * 60,
        scope=" ".join(scopes or [SCOPE]),
        refresh_token=refresh,
    )


# --- the consent step, called by the SPA ----------------------------------------- #

def describe_authorization(db, txn_id: UUID) -> Optional[dict[str, Any]]:
    row = db.get(OAuthAuthorization, txn_id)
    if row is None or row.expires_at < crud.now() or row.code_hash is not None:
        return None
    client = db.get(OAuthClient, row.client_id)
    return {
        "txn": str(row.id),
        "client_name": (client.client_name if client else None) or row.client_id,
        "redirect_uri": row.params.get("redirect_uri"),
        "scopes": row.params.get("scopes") or [SCOPE],
    }


def approve_authorization(db, *, txn_id: UUID, user: User, request) -> str:
    """The owner said yes: bind a new `mcp` device to them and mint the code.

    Returns the redirect URI (with `code` and `state`) the browser must follow.
    """

    row = db.get(OAuthAuthorization, txn_id)
    if row is None or row.expires_at < crud.now() or row.code_hash is not None:
        raise AuthorizeError("invalid_request", "authorization request is invalid or has expired")
    client = db.get(OAuthClient, row.client_id)
    device = crud.add_device(
        db,
        user_id=user.id,
        kind="mcp",
        device_key_hash=crud.sha256(secrets.token_urlsafe(32)),
        label=f"MCP: {(client.client_name if client else None) or row.client_id}"[:200],
        status="trusted",
        approved_by=user.id,
        approved_at=crud.now(),
        last_ip=None,
    )
    code = secrets.token_urlsafe(32)
    row.user_id = user.id
    row.device_id = device.id
    row.code_hash = crud.sha256(code)
    row.code_expires_at = crud.now() + timedelta(minutes=CODE_MINUTES)
    audit("oauth_approved", request, user_id=user.id, device_id=device.id, detail={"client_id": row.client_id})
    from mcp.server.auth.provider import construct_redirect_uri

    return construct_redirect_uri(row.params["redirect_uri"], code=code, state=row.params.get("state"))
