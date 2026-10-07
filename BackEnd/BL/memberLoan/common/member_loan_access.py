"""Who may use the Member Loan module: exactly the two members, on a passkey.

Self-gated like `routers/devices.py`: every route needs a real passkey web
session whatever AUTH_MODE says (decision D2: defense in depth), the session's
user must be one of the two configured members, and every write also needs the
CSRF headers, a recent passkey assertion (step-up) and stays under the hourly
rate limit. MCP connector sessions are refused outright.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from BL.auth import device as devices_bl
from BL.auth import session as sessions_bl
from BL.auth.common.audit import client_ip, count_recent, record as record_security_event
from BL.auth.common.session_dependency import _csrf_problem, resolve_principal
from BL.memberLoan.common.member_loan_settings import MemberLoanMisconfigured, MemberLoanSettings, load_member_loan_settings
from DAL.crud import auth as auth_crud
from db import get_db

MEMBER_ROLE_LENDER = "lender"
MEMBER_ROLE_YARDEN = "yarden"
MEMBER_LOAN_WRITE_SECURITY_EVENT = "member_loan_write"


@dataclass(frozen=True)
class MemberLoanMember:
    user_id: Optional[UUID]
    username: str
    display_name: str
    role: str
    email: Optional[str]


@dataclass(frozen=True)
class MemberLoanMembers:
    lender: MemberLoanMember
    yarden: MemberLoanMember

    def by_username(self, username: str) -> Optional[MemberLoanMember]:
        return next((m for m in (self.lender, self.yarden) if m.username == username), None)

    def other_than(self, member: MemberLoanMember) -> MemberLoanMember:
        return self.yarden if member.username == self.lender.username else self.lender

    def display_name_for(self, username: str) -> str:
        member = self.by_username(username)
        return member.display_name if member else username


@dataclass(frozen=True)
class MemberLoanCaller:
    member: MemberLoanMember
    members: MemberLoanMembers
    settings: MemberLoanSettings
    request_ip: Optional[str]
    user_agent: Optional[str]

    @property
    def other_member(self) -> MemberLoanMember:
        return self.members.other_than(self.member)


def _member(db: DbSession, username: str, role: str, email: Optional[str]) -> MemberLoanMember:
    user = auth_crud.get_user_by_username(db, username)
    fallback_name = username[:1].upper() + username[1:]
    return MemberLoanMember(
        user_id=user.id if user else None,
        username=username,
        display_name=(user.display_name if user and user.display_name else fallback_name),
        role=role,
        email=email,
    )


def load_member_loan_members(db: DbSession, settings: MemberLoanSettings) -> MemberLoanMembers:
    return MemberLoanMembers(
        lender=_member(db, settings.lender_username, MEMBER_ROLE_LENDER, settings.lender_email),
        yarden=_member(db, settings.yarden_username, MEMBER_ROLE_YARDEN, settings.yarden_email),
    )


def _resolve_member_loan_caller(request: Request, db: DbSession) -> tuple[MemberLoanCaller, object]:
    try:
        settings = load_member_loan_settings()
    except MemberLoanMisconfigured:
        raise HTTPException(status_code=503, detail="member_loan_not_configured")
    principal = resolve_principal(request, db)
    if principal is None:
        raise HTTPException(status_code=401, detail="unauthenticated")
    if devices_bl.effective_status(principal.device) != "trusted":
        raise HTTPException(status_code=403, detail="device_pending")
    if principal.session.kind != "web" or principal.user.role != "owner":
        raise HTTPException(status_code=403, detail="web_session_required")
    members = load_member_loan_members(db, settings)
    member = members.by_username(principal.user.username)
    if member is None:
        record_security_event(
            "member_loan_access_denied", request, user_id=principal.user.id, session_id=principal.session.id,
            device_id=principal.device.id, detail={"path": request.url.path},
        )
        raise HTTPException(status_code=403, detail="member_loan_access_denied")
    db.commit()  # the last-seen touches made while resolving the session
    caller = MemberLoanCaller(
        member=member,
        members=members,
        settings=settings,
        request_ip=client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:512] or None),
    )
    return caller, principal


def require_member_loan_reader(request: Request, db: DbSession = Depends(get_db)) -> MemberLoanCaller:
    caller, _ = _resolve_member_loan_caller(request, db)
    return caller


def require_member_loan_writer(request: Request, db: DbSession = Depends(get_db)) -> MemberLoanCaller:
    caller, principal = _resolve_member_loan_caller(request, db)
    problem = _csrf_problem(request)
    if problem is not None:
        raise HTTPException(status_code=403, detail=f"csrf: {problem}")
    if not sessions_bl.is_recently_authenticated(principal.session):
        raise HTTPException(status_code=403, detail="reauth_required")
    if count_recent(MEMBER_LOAN_WRITE_SECURITY_EVENT, 60, user_id=principal.user.id) >= caller.settings.writes_per_hour_per_member:
        raise HTTPException(status_code=429, detail="Too many changes in the last hour. Please try again later.")
    record_security_event(
        MEMBER_LOAN_WRITE_SECURITY_EVENT, request, user_id=principal.user.id, session_id=principal.session.id,
        device_id=principal.device.id, detail={"path": request.url.path},
    )
    return caller
