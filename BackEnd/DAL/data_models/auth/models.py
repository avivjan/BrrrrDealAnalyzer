"""Passkey users, credentials, devices and sessions (SECURITY_PLAN.md §3.2, §3.4).

All ids are UUIDs. Secrets (session tokens, enrollment tokens, device keys)
are stored as SHA-256 hashes only; the raw values live in the browser.
"""

import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Uuid, func

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    # Legacy REPS tab id (`Aviv2026` / `Yarden2026`) this person logs as by default.
    reps_user = Column(String(32), nullable=True)
    # `owner` may approve devices and issue enrollment links; `service` is the
    # MCP connector's principal (no passkey, no login page).
    role = Column(String(16), nullable=False, default="owner")
    disabled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    credential_id = Column(LargeBinary, nullable=False, unique=True)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    transports = Column(String(200), nullable=True)
    aaguid = Column(String(64), nullable=True)
    backup_eligible = Column(Boolean, nullable=False, default=False)
    backup_state = Column(Boolean, nullable=False, default=False)
    label = Column(String(200), nullable=False, default="Passkey")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class Device(Base):
    """A browser profile (or the MCP connector) that has been seen.

    `status` is the allow-list: `pending` until a trusted user approves it,
    `trusted`, or `revoked`. `device_key_hash` is the hash of the long-lived
    `bw_device` cookie that identifies the profile across logins.
    """

    __tablename__ = "devices"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(16), nullable=False, default="browser")  # browser | mcp
    device_key_hash = Column(String(64), nullable=False, unique=True)
    label = Column(String(200), nullable=False, default="Browser")
    platform = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_ip = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    approved_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class Session(Base):
    """One login on one device: a short-lived access token and a rotating
    refresh token (both hashed). `refresh_family` ties the rotations of one
    login together so a replayed old refresh token revokes the whole family."""

    __tablename__ = "sessions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(Uuid(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    credential_id = Column(Uuid(as_uuid=True), ForeignKey("webauthn_credentials.id"), nullable=True)
    kind = Column(String(16), nullable=False, default="web")  # web | mcp
    # For `mcp` sessions issued through OAuth: the registered client they belong to.
    oauth_client_id = Column(String(128), nullable=True, index=True)
    scopes = Column(String(200), nullable=True)
    access_hash = Column(String(64), nullable=False, unique=True)
    access_expires_at = Column(DateTime(timezone=True), nullable=False)
    refresh_hash = Column(String(64), nullable=True, unique=True)
    # The refresh token this one replaced. Presenting it again means the token
    # was stolen and replayed: the whole family is revoked.
    prev_refresh_hash = Column(String(64), nullable=True, index=True)
    refresh_family = Column(Uuid(as_uuid=True), nullable=False, default=uuid.uuid4, index=True)
    status = Column(String(16), nullable=False, default="trusted")  # pending | trusted | revoked
    auth_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)


class EnrollmentToken(Base):
    __tablename__ = "enrollment_tokens"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    created_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String(16), nullable=False)  # register | login | reauth
    challenge = Column(LargeBinary, nullable=False)
    user_id = Column(Uuid(as_uuid=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OAuthClient(Base):
    """A dynamically registered MCP client (claude.ai, Claude Code)."""

    __tablename__ = "oauth_clients"

    client_id = Column(String(128), primary_key=True)
    client_secret_hash = Column(String(64), nullable=True)
    client_name = Column(String(200), nullable=True)
    redirect_uris = Column(JSON, nullable=False)
    metadata_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    disabled_at = Column(DateTime(timezone=True), nullable=True)


class OAuthAuthorization(Base):
    """One `/authorize` request waiting for (or just given) the owner's consent."""

    __tablename__ = "oauth_authorizations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(String(128), nullable=False, index=True)
    params = Column(JSON, nullable=False)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    device_id = Column(Uuid(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    code_hash = Column(String(64), nullable=True, unique=True)
    code_expires_at = Column(DateTime(timezone=True), nullable=True)
    code_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
