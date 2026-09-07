"""Append-only security audit log (SECURITY_PLAN.md §3.2).

One row per security-relevant event: a Mercury balance fetch, an offer e-mail,
an MCP tool call, and -- from Phase 2 -- every login, refresh, device approval
and revocation. `detail` never carries a token or a secret. The table also
backs the lightweight rate limits (count recent rows for an ip/event).
"""

from sqlalchemy import Column, BigInteger, String, DateTime, JSON, Uuid, func

from db import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    event = Column(String(64), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), nullable=True)
    session_id = Column(Uuid(as_uuid=True), nullable=True)
    device_id = Column(Uuid(as_uuid=True), nullable=True)
    ip = Column(String(64), nullable=True, index=True)
    user_agent = Column(String(512), nullable=True)
    detail = Column(JSON, nullable=True)
