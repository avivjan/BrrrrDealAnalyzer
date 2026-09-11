"""Row-level access for the auth tables. No commits here (the BL commits)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from DAL.data_models.auth.models import (
    AuthChallenge,
    Device,
    EnrollmentToken,
    Session,
    User,
    WebAuthnCredential,
)


def sha256(value: str | bytes) -> str:
    raw = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- users ----------------------------------------------------------------- #

def get_user(db: DbSession, user_id: UUID) -> Optional[User]:
    return db.get(User, user_id)


def get_user_by_username(db: DbSession, username: str) -> Optional[User]:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def count_users(db: DbSession) -> int:
    return len(db.execute(select(User.id)).all())


def add_user(db: DbSession, *, username: str, display_name: str, reps_user: Optional[str], role: str = "owner") -> User:
    user = User(username=username, display_name=display_name, reps_user=reps_user, role=role)
    db.add(user)
    db.flush()
    return user


# --- credentials ----------------------------------------------------------- #

def credentials_for_user(db: DbSession, user_id: UUID) -> list[WebAuthnCredential]:
    return list(db.execute(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id)).scalars())


def get_credential_by_id(db: DbSession, credential_id: bytes) -> Optional[WebAuthnCredential]:
    return db.execute(select(WebAuthnCredential).where(WebAuthnCredential.credential_id == credential_id)).scalar_one_or_none()


def add_credential(db: DbSession, **fields) -> WebAuthnCredential:
    cred = WebAuthnCredential(**fields)
    db.add(cred)
    db.flush()
    return cred


# --- enrollment tokens ----------------------------------------------------- #

def add_enrollment_token(db: DbSession, *, user_id: UUID, token_hash: str, expires_at: datetime, created_by: Optional[UUID]) -> EnrollmentToken:
    row = EnrollmentToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at, created_by=created_by)
    db.add(row)
    db.flush()
    return row


def get_enrollment_token(db: DbSession, token_hash: str) -> Optional[EnrollmentToken]:
    return db.execute(select(EnrollmentToken).where(EnrollmentToken.token_hash == token_hash)).scalar_one_or_none()


# --- challenges ------------------------------------------------------------ #

def add_challenge(db: DbSession, *, kind: str, challenge: bytes, user_id: Optional[UUID], expires_at: datetime) -> AuthChallenge:
    row = AuthChallenge(kind=kind, challenge=challenge, user_id=user_id, expires_at=expires_at)
    db.add(row)
    db.flush()
    return row


def pop_challenge(db: DbSession, challenge_id: UUID, kind: str) -> Optional[AuthChallenge]:
    """Return and delete a live challenge (single use)."""
    row = db.get(AuthChallenge, challenge_id)
    if row is None or row.kind != kind:
        return None
    db.delete(row)
    if row.expires_at < now():
        return None
    return row


def prune_challenges(db: DbSession) -> None:
    for row in db.execute(select(AuthChallenge).where(AuthChallenge.expires_at < now())).scalars():
        db.delete(row)


# --- devices --------------------------------------------------------------- #

def get_device(db: DbSession, device_id: UUID) -> Optional[Device]:
    return db.get(Device, device_id)


def get_device_by_key_hash(db: DbSession, key_hash: str) -> Optional[Device]:
    return db.execute(select(Device).where(Device.device_key_hash == key_hash)).scalar_one_or_none()


def add_device(db: DbSession, **fields) -> Device:
    device = Device(**fields)
    db.add(device)
    db.flush()
    return device


def list_devices(db: DbSession) -> list[Device]:
    return list(db.execute(select(Device).order_by(Device.first_seen_at)).scalars())


# --- sessions -------------------------------------------------------------- #

def add_session(db: DbSession, **fields) -> Session:
    session = Session(**fields)
    db.add(session)
    db.flush()
    return session


def get_session_by_access_hash(db: DbSession, access_hash: str) -> Optional[Session]:
    return db.execute(select(Session).where(Session.access_hash == access_hash)).scalar_one_or_none()


def get_session_by_refresh_hash(db: DbSession, refresh_hash: str) -> Optional[Session]:
    return db.execute(select(Session).where(Session.refresh_hash == refresh_hash)).scalar_one_or_none()


def sessions_for_family(db: DbSession, family: UUID) -> list[Session]:
    return list(db.execute(select(Session).where(Session.refresh_family == family)).scalars())


def sessions_for_device(db: DbSession, device_id: UUID) -> list[Session]:
    return list(db.execute(select(Session).where(Session.device_id == device_id)).scalars())


def sessions_for_user(db: DbSession, user_id: UUID) -> list[Session]:
    return list(db.execute(select(Session).where(Session.user_id == user_id).order_by(Session.created_at)).scalars())
