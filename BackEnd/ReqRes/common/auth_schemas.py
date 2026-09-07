from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterOptionsReq(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


class RegisterVerifyReq(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    challenge_id: UUID
    credential: dict[str, Any]
    label: Optional[str] = Field(None, max_length=200)


class LoginVerifyReq(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]


class CeremonyOptionsRes(BaseModel):
    challenge_id: str
    options: str  # PublicKeyCredential*Options as JSON (SimpleWebAuthn shape)
    username: Optional[str] = None


class UserRes(BaseModel):
    id: str
    username: str
    display_name: str
    reps_user: Optional[str]
    role: str


class SessionStatusRes(BaseModel):
    status: str  # ok | pending_approval
    user: UserRes
    device_id: str
    device_status: str
    auth_mode: str
    device_policy: str


class EnrollmentTokenRes(BaseModel):
    token: str
    expires_in_minutes: int


class AuthConfigRes(BaseModel):
    auth_mode: str
    device_policy: str
    rp_id: str


class OAuthTxnRes(BaseModel):
    txn: str
    client_name: str
    redirect_uri: Optional[str] = None
    scopes: list[str]


class OAuthApproveReq(BaseModel):
    txn: UUID


class OAuthApproveRes(BaseModel):
    redirect_uri: str
