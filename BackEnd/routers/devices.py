"""/devices, /sessions, /credentials -- the trusted-device dashboard
(SECURITY_PLAN.md §3.4).

Self-gated: every call needs a real session whatever AUTH_MODE says (there is
nothing to manage without one), mutations need the CSRF headers, and approve /
revoke / passkey deletion need a recent passkey assertion (step-up). Any trusted
owner may approve or revoke any device (a two-person business); sessions and
passkeys are the caller's own. Never MCP tools (mcp_server excludes the prefixes).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DbSession

from BL.auth import device as devices_bl
from BL.auth import service as service_bl
from BL.auth import session as sessions
from BL.auth.common.audit import record as audit
from BL.auth.common.session_dependency import Principal, _csrf_problem, require_recent_auth, resolve_principal
from DAL.crud import auth as crud
from DAL.data_models.auth.models import Device, Session, WebAuthnCredential
from db import get_db
from ReqRes.common.auth_schemas import CredentialRes, DeviceRenameReq, DeviceRes, SessionRes

router = APIRouter()


def _principal(request: Request, db: DbSession, *, allow_pending: bool = False) -> Principal:
    principal = resolve_principal(request, db)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    if not allow_pending and devices_bl.effective_status(principal.device) != "trusted":
        raise HTTPException(status_code=403, detail="device_pending")
    if principal.session.kind != "web":
        raise HTTPException(status_code=403, detail="web_session_required")
    return principal


def _csrf(request: Request) -> None:
    problem = _csrf_problem(request)
    if problem is not None:
        raise HTTPException(status_code=403, detail=f"csrf: {problem}")


def _device_res(db: DbSession, device: Device, principal: Principal) -> DeviceRes:
    owner = crud.get_user(db, device.user_id)
    return DeviceRes(
        id=str(device.id),
        user_id=str(device.user_id),
        user_display_name=owner.display_name if owner else "",
        kind=device.kind,
        label=device.label,
        platform=device.platform,
        status=device.status,
        first_seen_at=device.first_seen_at,
        last_seen_at=device.last_seen_at,
        last_ip=device.last_ip,
        approved_at=device.approved_at,
        is_current=device.id == principal.device.id,
    )


def _device_or_404(db: DbSession, device_id: UUID) -> Device:
    device = crud.get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="unknown_device")
    return device


# --- devices ------------------------------------------------------------------ #

@router.get("/devices/me", response_model=DeviceRes)
def devices_me(request: Request, db: DbSession = Depends(get_db)):
    """The caller's own device; answers a pending one so /pending can poll."""

    principal = _principal(request, db, allow_pending=True)
    db.commit()
    return _device_res(db, principal.device, principal)


@router.get("/devices", response_model=list[DeviceRes])
def devices_list(request: Request, db: DbSession = Depends(get_db)):
    principal = _principal(request, db)
    db.commit()
    rows = [d for d in crud.list_devices(db) if d.status != "revoked" or d.kind == "mcp"]
    rows.sort(key=lambda d: (d.status != "pending", d.first_seen_at))
    return [_device_res(db, d, principal) for d in rows]


@router.patch("/devices/{device_id}", response_model=DeviceRes)
def devices_rename(device_id: UUID, payload: DeviceRenameReq, request: Request, db: DbSession = Depends(get_db)):
    principal = _principal(request, db)
    _csrf(request)
    device = _device_or_404(db, device_id)
    device.label = payload.label.strip() or device.label
    audit("device_renamed", request, user_id=principal.user.id, session_id=principal.session.id, device_id=device.id)
    db.commit()
    return _device_res(db, device, principal)


@router.post("/devices/{device_id}/approve", response_model=DeviceRes)
def devices_approve(device_id: UUID, request: Request, principal: Principal = Depends(require_recent_auth), db: DbSession = Depends(get_db)):
    """Step-up protected: a pending device becomes trusted and its sessions follow."""

    _principal(request, db)
    _csrf(request)
    device = _device_or_404(db, device_id)
    if device.status == "revoked":
        raise HTTPException(status_code=409, detail="device_revoked")
    if device.status == "pending":
        device.status = "trusted"
        device.approved_by = principal.user.id
        device.approved_at = crud.now()
        for s in crud.sessions_for_device(db, device.id):
            if s.status == "pending":
                s.status = "trusted"
        audit("device_approved", request, user_id=principal.user.id, session_id=principal.session.id, device_id=device.id)
    db.commit()
    return _device_res(db, device, principal)


@router.post("/devices/{device_id}/revoke", response_model=DeviceRes)
def devices_revoke(device_id: UUID, request: Request, principal: Principal = Depends(require_recent_auth), db: DbSession = Depends(get_db)):
    """Step-up protected: the device and every session it holds stop at once."""

    _principal(request, db)
    _csrf(request)
    device = _device_or_404(db, device_id)
    if device.status != "revoked":
        device.status = "revoked"
        device.revoked_at = crud.now()
        sessions.revoke_device_sessions(db, device.id)
        if device.kind == "mcp":
            service_bl.forget()
        audit("device_revoked", request, user_id=principal.user.id, session_id=principal.session.id, device_id=device.id)
    db.commit()
    return _device_res(db, device, principal)


# --- sessions ----------------------------------------------------------------- #

def _live(s: Session) -> bool:
    return s.status != "revoked" and s.expires_at > crud.now()


def _session_res(db: DbSession, s: Session, principal: Principal) -> SessionRes:
    device = crud.get_device(db, s.device_id)
    return SessionRes(
        id=str(s.id),
        device_id=str(s.device_id),
        device_label=device.label if device else "",
        kind=s.kind,
        created_at=s.created_at,
        last_seen_at=s.last_seen_at,
        ip=s.ip,
        is_current=s.id == principal.session.id,
    )


@router.get("/sessions", response_model=list[SessionRes])
def sessions_list(request: Request, db: DbSession = Depends(get_db)):
    principal = _principal(request, db)
    db.commit()
    return [_session_res(db, s, principal) for s in crud.sessions_for_user(db, principal.user.id) if _live(s)]


@router.delete("/sessions/{session_id}", status_code=204)
def sessions_end(session_id: UUID, request: Request, db: DbSession = Depends(get_db)):
    """End one of the caller's sessions (the current one included: that is a logout)."""

    principal = _principal(request, db)
    _csrf(request)
    target = db.get(Session, session_id)
    if target is None or target.user_id != principal.user.id:
        raise HTTPException(status_code=404, detail="unknown_session")
    sessions.revoke(target)
    audit("session_ended", request, user_id=principal.user.id, session_id=principal.session.id, device_id=principal.device.id, detail={"ended": str(target.id)})
    db.commit()
    return Response(status_code=204)


@router.post("/sessions/end-others", status_code=204)
def sessions_end_others(request: Request, db: DbSession = Depends(get_db)):
    """End every other session of the caller (a lost phone, a shared computer)."""

    principal = _principal(request, db)
    _csrf(request)
    ended = 0
    for s in crud.sessions_for_user(db, principal.user.id):
        if s.id != principal.session.id and s.status != "revoked":
            sessions.revoke(s)
            ended += 1
    audit("sessions_ended_others", request, user_id=principal.user.id, session_id=principal.session.id, device_id=principal.device.id, detail={"count": ended})
    db.commit()
    return Response(status_code=204)


# --- passkeys ------------------------------------------------------------------ #

def _credential_res(c: WebAuthnCredential) -> CredentialRes:
    return CredentialRes(id=str(c.id), label=c.label, created_at=c.created_at, last_used_at=c.last_used_at, backup_state=c.backup_state, transports=c.transports)


@router.get("/credentials", response_model=list[CredentialRes])
def credentials_list(request: Request, db: DbSession = Depends(get_db)):
    principal = _principal(request, db)
    db.commit()
    return [_credential_res(c) for c in crud.credentials_for_user(db, principal.user.id)]


@router.delete("/credentials/{credential_id}", status_code=204)
def credentials_delete(credential_id: UUID, request: Request, principal: Principal = Depends(require_recent_auth), db: DbSession = Depends(get_db)):
    """Step-up protected; the last passkey can never be removed (lock-out)."""

    _principal(request, db)
    _csrf(request)
    mine = crud.credentials_for_user(db, principal.user.id)
    target = next((c for c in mine if c.id == credential_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="unknown_credential")
    if len(mine) == 1:
        raise HTTPException(status_code=409, detail="last_credential")
    for s in crud.sessions_for_user(db, principal.user.id):
        if s.credential_id == target.id:
            s.credential_id = None
    db.delete(target)
    audit("credential_deleted", request, user_id=principal.user.id, session_id=principal.session.id, device_id=principal.device.id, detail={"credential": str(target.id)})
    db.commit()
    return Response(status_code=204)
