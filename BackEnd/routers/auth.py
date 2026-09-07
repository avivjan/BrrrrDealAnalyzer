"""/auth/* -- passkey enrollment, login, refresh, step-up, logout.

Public router: none of these require a session (except step-up, logout and
enrollment-token issuance, which check it themselves). Never exposed as MCP
tools (mcp_server excludes the prefix).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DbSession

from BL.auth import device as devices
from BL.auth import login as login_bl
from BL.auth import oauth
from BL.auth import register as register_bl
from BL.auth import session as sessions
from BL.auth.common import settings
from BL.auth.common.audit import record as audit
from BL.auth.common.session_dependency import Principal, _csrf_problem, require_recent_auth, resolve_principal
from BL.auth.register import AuthError
from DAL.crud import auth as crud
from db import get_db
from ReqRes.common.auth_schemas import (
    AuthConfigRes,
    CeremonyOptionsRes,
    EnrollmentTokenRes,
    LoginVerifyReq,
    OAuthApproveReq,
    OAuthApproveRes,
    OAuthTxnRes,
    RegisterOptionsReq,
    RegisterVerifyReq,
    SessionStatusRes,
    UserRes,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _status(user, session, device) -> SessionStatusRes:
    effective = devices.effective_status(device)
    return SessionStatusRes(
        status="ok" if effective == "trusted" else "pending_approval",
        user=UserRes(id=str(user.id), username=user.username, display_name=user.display_name, reps_user=user.reps_user, role=user.role),
        device_id=str(device.id),
        device_status=device.status,
        auth_mode=settings.auth_mode(),
        device_policy=devices.device_policy(),
    )


def _csrf(request: Request) -> None:
    problem = _csrf_problem(request)
    if problem is not None:
        raise HTTPException(status_code=403, detail=f"csrf: {problem}")


def _principal_or_401(request: Request, db: DbSession) -> Principal:
    principal = resolve_principal(request, db)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    if principal.session.kind != "web":
        # OAuth connector tokens are sessions too, but only the in-process
        # tool path may use them; presented as a browser cookie they are refused.
        raise HTTPException(status_code=403, detail="web_session_required")
    return principal


@router.get("/auth/config", response_model=AuthConfigRes)
def auth_config():
    """Public: tells the SPA whether a session is required (AUTH_MODE) so an
    `off` deployment keeps working exactly as before, with no login screen."""

    return AuthConfigRes(auth_mode=settings.auth_mode(), device_policy=devices.device_policy(), rp_id=settings.rp_id())


@router.post("/auth/register/options", response_model=CeremonyOptionsRes)
def auth_register_options(payload: RegisterOptionsReq, db: DbSession = Depends(get_db)):
    try:
        result = register_bl.begin_registration(db, token=payload.token)
        db.commit()
        return result
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)


@router.post("/auth/register/verify", response_model=SessionStatusRes, status_code=201)
def auth_register_verify(payload: RegisterVerifyReq, request: Request, response: Response, db: DbSession = Depends(get_db)):
    try:
        user, session, access, refresh, device_key = register_bl.finish_registration(
            db,
            token=payload.token,
            challenge_id=payload.challenge_id,
            credential=payload.credential,
            label=payload.label,
            request=request,
            device_key=sessions.read_cookie(request, sessions.DEVICE_COOKIE),
        )
        db.commit()
    except AuthError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    sessions.set_session_cookies(response, access, refresh)
    sessions.set_device_cookie(response, device_key)
    return _status(user, session, crud.get_device(db, session.device_id))


@router.post("/auth/login/options", response_model=CeremonyOptionsRes)
def auth_login_options(db: DbSession = Depends(get_db)):
    result = login_bl.begin_login(db)
    db.commit()
    return result


@router.post("/auth/login/verify", response_model=SessionStatusRes)
def auth_login_verify(payload: LoginVerifyReq, request: Request, response: Response, db: DbSession = Depends(get_db)):
    try:
        user, session, access, refresh, device_key = login_bl.finish_login(
            db,
            challenge_id=payload.challenge_id,
            credential=payload.credential,
            request=request,
            device_key=sessions.read_cookie(request, sessions.DEVICE_COOKIE),
        )
        db.commit()
    except AuthError as exc:
        db.commit()  # the audit row and the consumed challenge stay
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    sessions.set_session_cookies(response, access, refresh)
    sessions.set_device_cookie(response, device_key)
    return _status(user, session, crud.get_device(db, session.device_id))


@router.post("/auth/refresh", response_model=SessionStatusRes)
def auth_refresh(request: Request, response: Response, db: DbSession = Depends(get_db)):
    _csrf(request)
    rotated = sessions.refresh_session(db, sessions.read_cookie(request, sessions.REFRESH_COOKIE))
    db.commit()
    if rotated is None:
        sessions.clear_session_cookies(response)
        raise HTTPException(status_code=401, detail="unauthenticated")
    session, access, refresh = rotated
    user = crud.get_user(db, session.user_id)
    device = crud.get_device(db, session.device_id)
    if user is None or user.disabled_at is not None or device is None or device.status == "revoked":
        sessions.revoke(session)
        db.commit()
        sessions.clear_session_cookies(response)
        raise HTTPException(status_code=401, detail="unauthenticated")
    sessions.set_session_cookies(response, access, refresh)
    return _status(user, session, device)


@router.get("/auth/me", response_model=SessionStatusRes)
def auth_me(request: Request, db: DbSession = Depends(get_db)):
    principal = _principal_or_401(request, db)
    db.commit()
    return _status(principal.user, principal.session, principal.device)


@router.delete("/auth/session", status_code=204)
def auth_logout(request: Request, response: Response, db: DbSession = Depends(get_db)):
    _csrf(request)
    principal = resolve_principal(request, db)
    if principal is not None:
        sessions.revoke(principal.session)
        audit("logout", request, user_id=principal.user.id, session_id=principal.session.id, device_id=principal.device.id)
        db.commit()
    sessions.clear_session_cookies(response)
    return Response(status_code=204)


@router.post("/auth/reauth/options", response_model=CeremonyOptionsRes)
def auth_reauth_options(request: Request, db: DbSession = Depends(get_db)):
    _csrf(request)
    principal = _principal_or_401(request, db)
    result = login_bl.begin_login(db, kind="reauth", user_id=principal.user.id)
    db.commit()
    return result


@router.post("/auth/reauth/verify", response_model=SessionStatusRes)
def auth_reauth_verify(payload: LoginVerifyReq, request: Request, db: DbSession = Depends(get_db)):
    _csrf(request)
    principal = _principal_or_401(request, db)
    try:
        login_bl.finish_reauth(db, session=principal.session, challenge_id=payload.challenge_id, credential=payload.credential, request=request)
        db.commit()
    except AuthError as exc:
        db.commit()
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    return _status(principal.user, principal.session, principal.device)


@router.post("/auth/enrollment-tokens", response_model=EnrollmentTokenRes, status_code=201)
def auth_enrollment_token(request: Request, principal: Principal = Depends(require_recent_auth), db: DbSession = Depends(get_db)):
    """A link to add a passkey on another device, for the same person."""

    if devices.effective_status(principal.device) != "trusted":
        raise HTTPException(status_code=403, detail="device_pending")
    token = register_bl.issue_enrollment_token(db, user=principal.user, created_by=principal.user.id)
    audit("enrollment_token_issued", request, user_id=principal.user.id, session_id=principal.session.id, device_id=principal.device.id)
    db.commit()
    return EnrollmentTokenRes(token=token, expires_in_minutes=settings.enroll_minutes())


# --- MCP connector consent (MCP_AUTH_MODE=oauth, SECURITY_PLAN.md §3.6) ------- #

@router.get("/auth/oauth/txn/{txn}", response_model=OAuthTxnRes)
def auth_oauth_txn(txn: UUID, request: Request, db: DbSession = Depends(get_db)):
    """What the SPA's /connect page shows before the owner approves a connector."""

    principal = _principal_or_401(request, db)
    if devices.effective_status(principal.device) != "trusted":
        raise HTTPException(status_code=403, detail="device_pending")
    info = oauth.describe_authorization(db, txn)
    if info is None:
        raise HTTPException(status_code=404, detail="unknown_authorization")
    return OAuthTxnRes(**info)


@router.post("/auth/oauth/approve", response_model=OAuthApproveRes)
def auth_oauth_approve(payload: OAuthApproveReq, request: Request, principal: Principal = Depends(require_recent_auth), db: DbSession = Depends(get_db)):
    """Step-up protected: creates the connector's `mcp` device and the code."""

    if devices.effective_status(principal.device) != "trusted":
        raise HTTPException(status_code=403, detail="device_pending")
    try:
        redirect = oauth.approve_authorization(db, txn_id=payload.txn, user=principal.user, request=request)
    except oauth.AuthorizeError:
        raise HTTPException(status_code=400, detail="authorization_invalid")
    db.commit()
    return OAuthApproveRes(redirect_uri=redirect)
