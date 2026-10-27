"""The signing ceremony of Amendment No. 1, Section 1.2: view the record, type the
full legal name, tick the consent box, draw a signature, confirm with the passkey.

The passkey step is what makes the signature strong. Its WebAuthn challenge is
not random: it is SHA-256 of the document's SHA-256 and a random nonce, so the
authenticator's cryptographic signature covers this exact PDF. Anyone holding
the PDF, the nonce and the stored assertion can check the binding again
(`passkey_challenge_for_document`), independently of this application.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import struct
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session as DbSession

from BL.auth import login as login_bl
from BL.auth.register import AuthError, CHALLENGE_MINUTES
from BL.memberLoan.common.member_loan_ledger_service import MemberLoanRequestRefused
from DAL.crud import auth as auth_crud

MEMBER_LOAN_SIGNATURE_CHALLENGE_KIND = "loan_signature"  # auth_challenges.kind holds 16 characters
LARGEST_DRAWN_SIGNATURE_BYTES = 60 * 1024
PNG_FILE_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SMALLEST_DRAWN_SIGNATURE_SIDE_PIXELS = 40
LARGEST_DRAWN_SIGNATURE_SIDE_PIXELS = 2000  # the pad exports 600 × 200; a bigger PNG would only cost memory to decode
ELECTRONIC_SIGNATURE_CONSENT_TEXT = (
    "I agree this is my electronic signature and that it has the same effect as my handwritten signature "
    "(Amendment No. 1 to the Loan Agreement, Section 1)."
)


def passkey_challenge_for_document(document_sha256: str, nonce_hex: str) -> bytes:
    return hashlib.sha256(f"{document_sha256}:{nonce_hex}".encode("ascii")).digest()


def passkey_assertion_is_bound_to_document(*, client_data_json_base64url: str, document_sha256: str, nonce_hex: str) -> bool:
    """Whether a stored assertion's signed client data names the challenge derived from this document."""

    try:
        padded = client_data_json_base64url + "=" * (-len(client_data_json_base64url) % 4)
        client_data = json.loads(base64.urlsafe_b64decode(padded))
        signed_challenge = base64.urlsafe_b64decode(client_data["challenge"] + "=" * (-len(client_data["challenge"]) % 4))
    except (ValueError, KeyError, TypeError):
        return False
    return client_data.get("type") == "webauthn.get" and signed_challenge == passkey_challenge_for_document(document_sha256, nonce_hex)


@dataclass(frozen=True)
class MemberLoanPasskeySigningOptions:
    challenge_id: UUID
    challenge_nonce_hex: str
    options_json: str


def begin_passkey_signing(db: DbSession, *, user_id: UUID, document_sha256: str) -> MemberLoanPasskeySigningOptions:
    nonce_hex = os.urandom(32).hex()
    ceremony = login_bl.begin_login(
        db,
        kind=MEMBER_LOAN_SIGNATURE_CHALLENGE_KIND,
        user_id=user_id,
        challenge=passkey_challenge_for_document(document_sha256, nonce_hex),
    )
    return MemberLoanPasskeySigningOptions(UUID(ceremony["challenge_id"]), nonce_hex, ceremony["options"])


@dataclass(frozen=True)
class MemberLoanPasskeySignatureEvidence:
    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str


def finish_passkey_signing(
    db: DbSession, *, challenge_id: UUID, credential: dict[str, Any], request: Optional[Request], signer_user_id: UUID
) -> MemberLoanPasskeySignatureEvidence:
    """Verify the assertion (the signer's own passkey, user verification required)."""

    try:
        login_bl.verify_signature_assertion(
            db,
            kind=MEMBER_LOAN_SIGNATURE_CHALLENGE_KIND,
            challenge_id=challenge_id,
            credential=credential,
            request=request,
            expected_user_id=signer_user_id,
        )
    except AuthError as error:
        raise MemberLoanRequestRefused(
            429 if error.status == 429 else 403,
            "Your passkey could not confirm this signature. Please try signing again.",
            code="passkey_not_verified",
        ) from error
    response = credential.get("response") or {}
    return MemberLoanPasskeySignatureEvidence(
        credential_id=str(credential.get("rawId") or credential.get("id")),
        authenticator_data=str(response.get("authenticatorData", "")),
        client_data_json=str(response.get("clientDataJSON", "")),
        signature=str(response.get("signature", "")),
    )


def passkey_challenge_lifetime() -> timedelta:
    return timedelta(minutes=CHALLENGE_MINUTES)


def drop_unused_passkey_challenge(db: DbSession, challenge_id: Optional[UUID]) -> None:
    if challenge_id is not None:
        auth_crud.pop_challenge(db, challenge_id, MEMBER_LOAN_SIGNATURE_CHALLENGE_KIND)


def normalized_legal_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def refuse_unless_typed_name_matches(typed_full_legal_name: str, expected_legal_name: str) -> None:
    if normalized_legal_name(typed_full_legal_name) != normalized_legal_name(expected_legal_name):
        raise MemberLoanRequestRefused(
            422,
            f"Please type your full legal name exactly as in the Agreement: {expected_legal_name}.",
            code="legal_name_mismatch",
        )


def decode_drawn_signature_png(drawn_signature_png_base64: str) -> bytes:
    """The drawn signature as PNG bytes, refused unless it really is a small PNG image."""

    text = drawn_signature_png_base64.strip()
    if text.startswith("data:image/png;base64,"):
        text = text[len("data:image/png;base64,"):]
    try:
        png = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        png = b""
    refusal = MemberLoanRequestRefused(422, "Please draw your signature again.", code="drawn_signature_invalid")
    if not png.startswith(PNG_FILE_SIGNATURE) or len(png) > LARGEST_DRAWN_SIGNATURE_BYTES or len(png) < 33:
        raise refusal
    # The first chunk of every PNG is IHDR: width and height, 4 bytes each.
    if png[12:16] != b"IHDR":
        raise refusal
    width, height = struct.unpack(">II", png[16:24])
    if not all(SMALLEST_DRAWN_SIGNATURE_SIDE_PIXELS <= side <= LARGEST_DRAWN_SIGNATURE_SIDE_PIXELS for side in (width, height)):
        raise refusal
    return png
