"""A software passkey for the tests: a P-256 key that answers registration
and authentication ceremonies the way a platform authenticator would."""

from __future__ import annotations

import hashlib
import json
import os
import struct
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

FLAG_UP, FLAG_UV, FLAG_BE, FLAG_BS, FLAG_AT = 0x01, 0x04, 0x08, 0x10, 0x40


class SoftPasskey:
    def __init__(self, rp_id: str, origin: str, *, synced: bool = True, credential_id: bytes | None = None):
        self.rp_id = rp_id
        self.origin = origin
        self.synced = synced
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = credential_id or os.urandom(32)
        self.sign_count = 0

    # --- helpers --------------------------------------------------------- #

    def _client_data(self, kind: str, challenge: bytes) -> bytes:
        return json.dumps({"type": kind, "challenge": bytes_to_base64url(challenge), "origin": self.origin, "crossOrigin": False}).encode()

    def _flags(self, with_cred: bool) -> int:
        flags = FLAG_UP | FLAG_UV
        if self.synced:
            flags |= FLAG_BE | FLAG_BS
        if with_cred:
            flags |= FLAG_AT
        return flags

    def _cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})

    def _auth_data(self, with_cred: bool) -> bytes:
        data = hashlib.sha256(self.rp_id.encode()).digest() + bytes([self._flags(with_cred)]) + struct.pack(">I", self.sign_count)
        if with_cred:
            data += b"\x00" * 16 + struct.pack(">H", len(self.credential_id)) + self.credential_id + self._cose_key()
        return data

    # --- ceremonies ------------------------------------------------------ #

    def register(self, options_json: str) -> dict[str, Any]:
        options = json.loads(options_json)
        challenge = base64url_to_bytes(options["challenge"])
        client_data = self._client_data("webauthn.create", challenge)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": self._auth_data(True)})
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal", "hybrid"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def authenticate(self, options_json: str, *, bump_counter: bool = False) -> dict[str, Any]:
        options = json.loads(options_json)
        challenge = base64url_to_bytes(options["challenge"])
        if bump_counter:
            self.sign_count += 1
        client_data = self._client_data("webauthn.get", challenge)
        auth_data = self._auth_data(False)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": None,
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def public_pem(self) -> bytes:
        return self.key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
