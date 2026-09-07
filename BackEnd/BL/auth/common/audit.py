"""Write and count security audit events (`audit_log`).

`record()` uses its own short session and never raises: an audit failure is
logged, but must not turn a working request into a 500. `count_recent()` is
the basis of the rate limits (send-offer today, login attempts in Phase 2).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import func, select

from db import SessionLocal
from DAL.data_models.audit.models import AuditLog

logger = logging.getLogger(__name__)


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    # Render terminates TLS in front of uvicorn and sets X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else None)


def record(event: str, request: Optional[Request] = None, *, detail: Optional[dict[str, Any]] = None, **ids: Any) -> None:
    try:
        with SessionLocal() as session:
            session.add(
                AuditLog(
                    event=event,
                    ip=client_ip(request),
                    user_agent=(request.headers.get("user-agent", "")[:512] if request is not None else None),
                    detail=detail,
                    **{k: v for k, v in ids.items() if k in {"user_id", "session_id", "device_id"}},
                )
            )
            session.commit()
    except Exception:  # noqa: BLE001 -- auditing must never break the request
        logger.exception("audit: failed to record %s", event)


def count_recent(event: str, minutes: int, *, ip: Optional[str] = None, user_id: Any = None) -> int:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    stmt = select(func.count()).select_from(AuditLog).where(AuditLog.event == event, AuditLog.at >= since)
    if ip is not None:
        stmt = stmt.where(AuditLog.ip == ip)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    try:
        with SessionLocal() as session:
            return int(session.execute(stmt).scalar_one())
    except Exception:  # noqa: BLE001
        logger.exception("audit: failed to count %s", event)
        return 0
