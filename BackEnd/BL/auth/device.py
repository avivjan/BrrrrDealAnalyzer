"""Devices: the browser profile (or MCP connector) a session belongs to.

`DEVICE_POLICY` (SECURITY_PLAN.md §3.4):
    off      (default) every device is trusted on first sight -- today's behaviour
    log      new devices are recorded as pending but treated as trusted (log only)
    enforce  new devices are pending until a trusted user approves them
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session as DbSession

from BL.auth.common.audit import client_ip
from DAL.crud import auth as crud
from DAL.data_models.auth.models import Device, User

_POLICIES = {"off", "log", "enforce"}


def device_policy() -> str:
    raw = (os.getenv("DEVICE_POLICY") or "off").strip().lower()
    return raw if raw in _POLICIES else "off"


def new_device_key() -> str:
    return secrets.token_urlsafe(32)


def platform_from(user_agent: str) -> str:
    ua = user_agent.lower()
    for needle, name in (("iphone", "iOS"), ("ipad", "iPadOS"), ("android", "Android"), ("mac os", "macOS"), ("windows", "Windows"), ("linux", "Linux")):
        if needle in ua:
            return name
    return "Unknown"


def resolve_device(
    db: DbSession,
    *,
    user: User,
    request: Optional[Request],
    device_key: Optional[str],
    trusted_on_creation: bool = False,
    kind: str = "browser",
) -> tuple[Device, str]:
    """The device behind `device_key` (the `bw_device` cookie), created if new.

    Returns the device and the key the cookie must carry (a new key when the
    device was just created). `trusted_on_creation` is used by enrollment: a
    person holding an enrollment link was approved by whoever issued it.
    """

    user_agent = (request.headers.get("user-agent", "") if request is not None else "")[:512]
    ip = client_ip(request)
    if device_key:
        device = crud.get_device_by_key_hash(db, crud.sha256(device_key))
        if device is not None and device.user_id == user.id and device.status != "revoked":
            device.last_seen_at = crud.now()
            device.last_ip = ip
            if user_agent:
                device.user_agent = user_agent
            return device, device_key

    key = new_device_key()
    status = "trusted" if (trusted_on_creation or device_policy() == "off") else "pending"
    device = crud.add_device(
        db,
        user_id=user.id,
        kind=kind,
        device_key_hash=crud.sha256(key),
        label=f"{platform_from(user_agent)} browser" if kind == "browser" else "MCP connector",
        platform=platform_from(user_agent) if user_agent else None,
        user_agent=user_agent or None,
        last_ip=ip,
        status=status,
        approved_by=user.id if status == "trusted" else None,
        approved_at=crud.now() if status == "trusted" else None,
    )
    return device, key


def effective_status(device: Device) -> str:
    """What the request pipeline treats the device as: under `log` a pending
    device behaves as trusted (and is logged), under `enforce` it is blocked."""

    if device.status == "pending" and device_policy() != "enforce":
        return "trusted"
    return device.status
