"""Sessions: issue, verify, refresh (with rotation and reuse detection),
revoke, and the cookies that carry them (SECURITY_PLAN.md §3.2).

Raw tokens are 256-bit random strings that exist only in the client's cookie
jar; the database holds SHA-256 hashes.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy.orm import Session as DbSession

from BL.auth.common import settings
from BL.auth.common.audit import client_ip
from DAL.crud import auth as crud
from DAL.data_models.auth.models import Device, Session, User

ACCESS_COOKIE = "bw_at"
REFRESH_COOKIE = "bw_rt"
DEVICE_COOKIE = "bw_device"
DEVICE_COOKIE_DAYS = 400
LAST_SEEN_THROTTLE = timedelta(minutes=5)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def issue_session(
    db: DbSession,
    *,
    user: User,
    device: Device,
    credential_id: Optional[UUID],
    request: Optional[Request],
    kind: str = "web",
) -> tuple[Session, str, str]:
    """Create a session for `user` on `device`; returns (row, access, refresh)."""

    access, refresh = new_token(), new_token()
    now = crud.now()
    session = crud.add_session(
        db,
        user_id=user.id,
        device_id=device.id,
        credential_id=credential_id,
        kind=kind,
        access_hash=crud.sha256(access),
        access_expires_at=now + timedelta(minutes=settings.access_minutes()),
        refresh_hash=crud.sha256(refresh),
        status="trusted" if device.status == "trusted" else "pending",
        auth_time=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=settings.refresh_days()),
        ip=client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:512] if request is not None else None),
    )
    return session, access, refresh


def verify_access(db: DbSession, access: Optional[str]) -> Optional[Session]:
    """The live session behind an access token, or None."""

    if not access:
        return None
    session = crud.get_session_by_access_hash(db, crud.sha256(access))
    if session is None or session.status == "revoked":
        return None
    now = crud.now()
    if session.access_expires_at < now or session.expires_at < now:
        return None
    if now - session.last_seen_at > LAST_SEEN_THROTTLE:
        session.last_seen_at = now
    return session


def refresh_session(db: DbSession, refresh: Optional[str], *, kind: str = "web") -> Optional[tuple[Session, str, str]]:
    """Rotate: a valid refresh token yields a new access + refresh pair.

    A refresh token that was already rotated away is a replay: every session
    in its family is revoked and None is returned. `kind` pins the caller: the
    cookie endpoint only rotates browser sessions and the OAuth token endpoint
    only connector sessions, so a token from one path is inert on the other
    (and is left untouched, not rotated away from its rightful holder).
    """

    if not refresh:
        return None
    presented = crud.sha256(refresh)
    session = crud.get_session_by_refresh_hash(db, presented)
    if session is None:
        replayed = db.query(Session).filter(Session.prev_refresh_hash == presented).first()
        if replayed is not None:
            for member in crud.sessions_for_family(db, replayed.refresh_family):
                revoke(member)
        return None
    now = crud.now()
    if session.status == "revoked" or session.expires_at < now or session.kind != kind:
        return None
    access, new_refresh = new_token(), new_token()
    session.prev_refresh_hash = session.refresh_hash
    session.refresh_hash = crud.sha256(new_refresh)
    session.access_hash = crud.sha256(access)
    session.access_expires_at = now + timedelta(minutes=settings.access_minutes())
    session.last_seen_at = now
    return session, access, new_refresh


def revoke(session: Session) -> None:
    if session.status != "revoked":
        session.status = "revoked"
        session.revoked_at = crud.now()


def revoke_device_sessions(db: DbSession, device_id: UUID) -> int:
    count = 0
    for session in crud.sessions_for_device(db, device_id):
        if session.status != "revoked":
            revoke(session)
            count += 1
    return count


def is_recently_authenticated(session: Session) -> bool:
    return (crud.now() - session.auth_time).total_seconds() <= settings.reauth_seconds()


# --- cookies ----------------------------------------------------------------- #

def _set(response: Response, base: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=settings.cookie_name(base),
        value=value,
        max_age=max_age,
        path="/",
        secure=settings.cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def set_session_cookies(response: Response, access: str, refresh: str) -> None:
    _set(response, ACCESS_COOKIE, access, settings.access_minutes() * 60)
    _set(response, REFRESH_COOKIE, refresh, settings.refresh_days() * 86400)


def set_device_cookie(response: Response, device_key: str) -> None:
    _set(response, DEVICE_COOKIE, device_key, DEVICE_COOKIE_DAYS * 86400)


def clear_session_cookies(response: Response) -> None:
    # A `__Host-` cookie is only deleted by a Set-Cookie that carries the same
    # Secure/Path attributes; a bare delete_cookie() is ignored by browsers.
    for base in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(key=settings.cookie_name(base), path="/", secure=settings.cookie_secure(), httponly=True, samesite="lax")


def read_cookie(request: Request, base: str) -> Optional[str]:
    """Over https only the `__Host-` name counts: that prefix is what proves
    the cookie was set by this host; the bare name is for plain-http dev."""
    name = settings.cookie_name(base)
    if name == base:
        return request.cookies.get(base)
    return request.cookies.get(name)
