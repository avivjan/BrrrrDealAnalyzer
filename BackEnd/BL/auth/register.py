"""Enrollment: an enrollment link (issued by the CLI or a trusted user) lets a
person register a passkey, which also creates their first trusted device."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session as DbSession
from webauthn import generate_registration_options, options_to_json, verify_registration_response
from webauthn.helpers.exceptions import InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from BL.auth.common import settings
from BL.auth.common.audit import record as audit
from BL.auth import device as devices
from BL.auth import session as sessions
from DAL.crud import auth as crud
from DAL.data_models.auth.models import EnrollmentToken, User

CHALLENGE_MINUTES = 5


class AuthError(ValueError):
    """A client-facing authentication failure; the router maps it to 401/400."""

    def __init__(self, detail: str, status: int = 401):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def issue_enrollment_token(db: DbSession, *, user: User, created_by: Optional[UUID]) -> str:
    raw = secrets.token_urlsafe(32)
    crud.add_enrollment_token(
        db,
        user_id=user.id,
        token_hash=crud.sha256(raw),
        expires_at=crud.now() + timedelta(minutes=settings.enroll_minutes()),
        created_by=created_by,
    )
    return raw


def _live_token(db: DbSession, raw: str) -> tuple[EnrollmentToken, User]:
    row = crud.get_enrollment_token(db, crud.sha256(raw or ""))
    if row is None or row.used_at is not None or row.expires_at < crud.now():
        raise AuthError("enrollment link is invalid or has expired", 400)
    user = crud.get_user(db, row.user_id)
    if user is None or user.disabled_at is not None:
        raise AuthError("enrollment link is invalid or has expired", 400)
    return row, user


def begin_registration(db: DbSession, *, token: str) -> dict[str, Any]:
    _, user = _live_token(db, token)
    existing = crud.credentials_for_user(db, user.id)
    options = generate_registration_options(
        rp_id=settings.rp_id(),
        rp_name=settings.rp_name(),
        user_id=user.id.bytes,
        user_name=user.username,
        user_display_name=user.display_name,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=c.credential_id) for c in existing],
    )
    challenge = crud.add_challenge(
        db,
        kind="register",
        challenge=options.challenge,
        user_id=user.id,
        expires_at=crud.now() + timedelta(minutes=CHALLENGE_MINUTES),
    )
    crud.prune_challenges(db)
    return {"challenge_id": str(challenge.id), "options": options_to_json(options), "username": user.username}


def finish_registration(
    db: DbSession,
    *,
    token: str,
    challenge_id: UUID,
    credential: dict[str, Any] | str,
    label: Optional[str],
    request: Optional[Request],
    device_key: Optional[str],
) -> tuple[User, Any, str, str, str]:
    """Verify the attestation; returns (user, session, access, refresh, device_key)."""

    token_row, user = _live_token(db, token)
    challenge = crud.pop_challenge(db, challenge_id, "register")
    if challenge is None or challenge.user_id != user.id:
        raise AuthError("registration challenge is invalid or has expired", 400)
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=bytes(challenge.challenge),
            expected_rp_id=settings.rp_id(),
            expected_origin=settings.allowed_origins(),
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        audit("enroll_failed", request, user_id=user.id, detail={"reason": type(exc).__name__})
        raise AuthError("passkey registration could not be verified", 400) from exc

    cred = crud.add_credential(
        db,
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=",".join(t.value if hasattr(t, "value") else str(t) for t in (credential.get("response", {}).get("transports") or [])) if isinstance(credential, dict) else None,
        aaguid=verified.aaguid,
        backup_eligible=bool(verified.credential_backed_up or getattr(verified, "credential_backup_eligible", False)),
        backup_state=bool(verified.credential_backed_up),
        label=(label or "Passkey")[:200],
        last_used_at=crud.now(),
    )
    token_row.used_at = crud.now()

    device, key = devices.resolve_device(db, user=user, request=request, device_key=device_key, trusted_on_creation=True)
    session, access, refresh = sessions.issue_session(db, user=user, device=device, credential_id=cred.id, request=request)
    audit("enroll_ok", request, user_id=user.id, session_id=session.id, device_id=device.id, detail={"credential": str(cred.id)})
    return user, session, access, refresh, key
