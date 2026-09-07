"""`require_session`: the one gate every data route goes through in Phase 2.

    AUTH_MODE=off      nothing is checked (default -- today's behaviour)
    AUTH_MODE=shadow   a request that would be rejected is logged and let through
    AUTH_MODE=enforce  401 `unauthenticated` / 403 `device_pending`

The dependency reads the cookies from the raw request (no declared parameter),
so the OpenAPI document of the existing operations does not change. On unsafe
methods it also applies the CSRF checks: an `Origin` (or `Sec-Fetch-Site`)
that is not ours is refused, and the `X-Requested-With` header is required.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from BL.auth import device as devices
from BL.auth import session as sessions
from BL.auth.common import settings
from BL.auth.common.audit import record as audit
from DAL.crud import auth as crud
from db import get_db

logger = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
REQUESTED_WITH = "x-requested-with"


class Principal:
    __slots__ = ("user", "session", "device")

    def __init__(self, user, session, device):
        self.user = user
        self.session = session
        self.device = device


def _csrf_problem(request: Request) -> Optional[str]:
    if request.method in SAFE_METHODS:
        return None
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.allowed_origins():
        return "origin not allowed"
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None and fetch_site not in {"same-origin", "same-site", "none"}:
        return "cross-site request"
    if request.headers.get(REQUESTED_WITH) is None:
        return "missing X-Requested-With"
    return None


def _reject(request: Request, status: int, detail: str) -> None:
    mode = settings.auth_mode()
    if mode == "enforce":
        raise HTTPException(status_code=status, detail=detail)
    logger.warning("auth shadow: would reject %s %s (%s)", request.method, request.url.path, detail)
    audit("auth_denied", request, detail={"path": request.url.path, "reason": detail, "shadow": True})


def resolve_principal(request: Request, db: DbSession) -> Optional[Principal]:
    """The principal behind the request's access cookie, or None."""

    session = sessions.verify_access(db, sessions.read_cookie(request, sessions.ACCESS_COOKIE))
    if session is None:
        return None
    user = crud.get_user(db, session.user_id)
    device = crud.get_device(db, session.device_id)
    if user is None or user.disabled_at is not None or device is None or device.status == "revoked":
        return None
    principal = Principal(user, session, device)
    request.state.principal = principal
    return principal


def require_session(allow_pending: bool = False):
    async def dependency(request: Request, db: DbSession = Depends(get_db)) -> Optional[Principal]:
        if settings.auth_mode() == "off":
            return None
        principal = resolve_principal(request, db)
        if principal is None:
            _reject(request, 401, "unauthenticated")
            return None
        if not allow_pending and devices.effective_status(principal.device) != "trusted":
            _reject(request, 403, "device_pending")
            return None
        problem = _csrf_problem(request)
        if problem is not None:
            _reject(request, 403, f"csrf: {problem}")
            return None
        db.commit()  # last_seen touches
        return principal

    return dependency


def current_principal(request: Request) -> Optional[Principal]:
    return getattr(request.state, "principal", None)


def require_recent_auth(request: Request, db: DbSession = Depends(get_db)) -> Principal:
    """Step-up: a trusted session whose last passkey assertion is recent."""

    principal = current_principal(request) or resolve_principal(request, db)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    if principal.session.kind != "web" or principal.user.role != "owner":
        # An MCP connector's token is a session row too; it never counts as a
        # person at the keyboard (no passkey behind it).
        raise HTTPException(status_code=403, detail="web_session_required")
    problem = _csrf_problem(request)
    if problem is not None:
        raise HTTPException(status_code=403, detail=f"csrf: {problem}")
    if not sessions.is_recently_authenticated(principal.session):
        raise HTTPException(status_code=403, detail="reauth_required")
    return principal


async def require_step_up(request: Request, db: DbSession = Depends(get_db)) -> Optional[Principal]:
    """Step-up on a deliberate action (send an offer), only once sessions are
    enforced -- `off` and `shadow` change nothing. MCP sessions are exempt:
    approving the connector device was the human in the loop."""

    if settings.auth_mode() != "enforce":
        return None
    principal = current_principal(request) or resolve_principal(request, db)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    if principal.session.kind != "mcp" and not sessions.is_recently_authenticated(principal.session):
        raise HTTPException(status_code=403, detail="reauth_required")
    return principal
