"""The MCP connector's principal (SECURITY_PLAN.md §3.6).

The connector is a *device*: a `service` user (`mcp-connector`) with one
device of kind `mcp` and a session of kind `mcp`. In-process tool calls carry
that session's access cookie, so the routers' `require_session` applies to
tools exactly as it does to the browser -- no bypass path. The raw access
token lives only in this process's memory and is re-issued when it expires.
"""

from __future__ import annotations

import threading
from typing import Optional

from db import SessionLocal
from BL.auth import session as sessions
from BL.auth.common import settings
from BL.auth.common.audit import record as audit
from DAL.crud import auth as crud

SERVICE_USERNAME = "mcp-connector"

_lock = threading.Lock()
_access: Optional[str] = None


def ensure_service_principal(db):
    """The service user and its trusted `mcp` device; created on first use."""

    user = crud.get_user_by_username(db, SERVICE_USERNAME)
    if user is None:
        user = crud.add_user(db, username=SERVICE_USERNAME, display_name="MCP connector", reps_user=None, role="service")
    # The connector has exactly one device. A revoked one is never replaced
    # here: revoking it in the dashboard (or `manage.py revoke-device`) must
    # stop every tool until an owner approves it again.
    device = None
    for candidate in crud.list_devices(db):
        if candidate.user_id == user.id and candidate.kind == "mcp":
            device = candidate
            if candidate.status != "revoked":
                break
    if device is None:
        device = crud.add_device(
            db,
            user_id=user.id,
            kind="mcp",
            device_key_hash=crud.sha256(sessions.new_token()),
            label="MCP connector",
            status="trusted",
            approved_by=user.id,
            approved_at=crud.now(),
        )
    return user, device


def service_cookies() -> dict[str, str]:
    """Cookies for an in-process tool call; empty when AUTH_MODE is off."""

    global _access
    if settings.auth_mode() == "off":
        return {}
    with _lock:
        with SessionLocal() as db:
            if _access is not None and sessions.verify_access(db, _access) is not None:
                db.commit()
                return {settings.cookie_name(sessions.ACCESS_COOKIE): _access}
            user, device = ensure_service_principal(db)
            if device.status == "revoked":
                return {}
            session, access, _refresh = sessions.issue_session(db, user=user, device=device, credential_id=None, request=None, kind="mcp")
            audit("mcp_session_issued", None, user_id=user.id, session_id=session.id, device_id=device.id)
            db.commit()
            _access = access
            return {settings.cookie_name(sessions.ACCESS_COOKIE): access}


def forget() -> None:
    global _access
    with _lock:
        _access = None
