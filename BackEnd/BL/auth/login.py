"""Passkey login and step-up (re-authentication)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session as DbSession
from webauthn import generate_authentication_options, options_to_json, verify_authentication_response
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.exceptions import InvalidAuthenticationResponse
from webauthn.helpers.structs import UserVerificationRequirement

from BL.auth.common import settings
from BL.auth.common.audit import client_ip, count_recent, record as audit
from BL.auth import device as devices
from BL.auth import session as sessions
from BL.auth.register import AuthError, CHALLENGE_MINUTES
from DAL.crud import auth as crud
from DAL.data_models.auth.models import Session, User, WebAuthnCredential

LOGIN_FAILURES_PER_WINDOW = 10
LOGIN_WINDOW_MINUTES = 15


def begin_login(db: DbSession, *, kind: str = "login", user_id: Optional[UUID] = None) -> dict[str, Any]:
    options = generate_authentication_options(
        rp_id=settings.rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = crud.add_challenge(
        db,
        kind=kind,
        challenge=options.challenge,
        user_id=user_id,
        expires_at=crud.now() + timedelta(minutes=CHALLENGE_MINUTES),
    )
    crud.prune_challenges(db)
    return {"challenge_id": str(challenge.id), "options": options_to_json(options)}


def _too_many_failures(request: Optional[Request]) -> bool:
    ip = client_ip(request)
    return count_recent("login_failed", LOGIN_WINDOW_MINUTES, ip=ip) >= LOGIN_FAILURES_PER_WINDOW


def _verify_assertion(
    db: DbSession,
    *,
    kind: str,
    challenge_id: UUID,
    credential: dict[str, Any] | str,
    request: Optional[Request],
    expected_user_id: Optional[UUID] = None,
) -> tuple[User, WebAuthnCredential]:
    if _too_many_failures(request):
        raise AuthError("too many failed attempts; try again later", 429)
    challenge = crud.pop_challenge(db, challenge_id, kind)
    if challenge is None:
        raise AuthError("login challenge is invalid or has expired", 400)
    raw_id = credential.get("rawId") or credential.get("id") if isinstance(credential, dict) else None
    cred = crud.get_credential_by_id(db, base64url_to_bytes(raw_id)) if raw_id else None
    if cred is None or (expected_user_id is not None and cred.user_id != expected_user_id):
        audit("login_failed", request, detail={"reason": "unknown_credential"})
        raise AuthError("passkey could not be verified")
    user = crud.get_user(db, cred.user_id)
    if user is None or user.disabled_at is not None:
        audit("login_failed", request, detail={"reason": "user_disabled"})
        raise AuthError("passkey could not be verified")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=bytes(challenge.challenge),
            expected_rp_id=settings.rp_id(),
            expected_origin=settings.allowed_origins(),
            credential_public_key=bytes(cred.public_key),
            credential_current_sign_count=cred.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        audit("login_failed", request, user_id=user.id, detail={"reason": type(exc).__name__})
        raise AuthError("passkey could not be verified") from exc
    cred.sign_count = verified.new_sign_count
    cred.backup_state = bool(verified.credential_backed_up)
    cred.last_used_at = crud.now()
    return user, cred


def finish_login(
    db: DbSession,
    *,
    challenge_id: UUID,
    credential: dict[str, Any] | str,
    request: Optional[Request],
    device_key: Optional[str],
) -> tuple[User, Session, str, str, str]:
    user, cred = _verify_assertion(db, kind="login", challenge_id=challenge_id, credential=credential, request=request)
    device, key = devices.resolve_device(db, user=user, request=request, device_key=device_key)
    session, access, refresh = sessions.issue_session(db, user=user, device=device, credential_id=cred.id, request=request)
    audit(
        "login_ok" if session.status == "trusted" else "device_pending",
        request,
        user_id=user.id,
        session_id=session.id,
        device_id=device.id,
        detail={"device_status": device.status},
    )
    return user, session, access, refresh, key


def finish_reauth(
    db: DbSession,
    *,
    session: Session,
    challenge_id: UUID,
    credential: dict[str, Any] | str,
    request: Optional[Request],
) -> None:
    """A fresh assertion by the session's own user refreshes `auth_time`."""

    user, _ = _verify_assertion(
        db, kind="reauth", challenge_id=challenge_id, credential=credential, request=request, expected_user_id=session.user_id
    )
    session.auth_time = crud.now()
    audit("reauth_ok", request, user_id=user.id, session_id=session.id, device_id=session.device_id)
