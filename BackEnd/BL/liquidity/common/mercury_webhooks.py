"""Mercury webhooks: register our address with an LLC's Mercury workspace, remove it, and check an event's signature
(tasks/todo/ConstructionAccountPerRehab.md, Step F, "instant updates").

An event only ever means "something moved in this LLC: look now". Its contents are never trusted or stored, so the
signature guards nothing but the trigger of a re-read; it is checked all the same, with a 5-minute replay window.

**Unverified against the real Mercury** (only third-party guides were available): the registration body and answer
(`POST /webhooks` with a `url`, answering an `id` and a `secret`), which token Mercury accepts for it (the transfer
token is tried first, then the read token), and the `Mercury-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of
"<t>.<raw body>">` header. A registration Mercury refuses is recorded for the drawer in our own words.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from BL.common.secret import Secret
from BL.liquidity.common.mercury_client import MERCURY_API_BASE, MERCURY_TIMEOUT_SECONDS, MercuryApiError, _raise_for_an_error_status
from BL.liquidity.common.mercury_token_names import read_token_environment_variable_name, transfer_token_environment_variable_name

logger = logging.getLogger(__name__)

WEBHOOKS_URL = f"{MERCURY_API_BASE}/webhooks"
SIGNATURE_HEADER = "Mercury-Signature"
MAXIMUM_EVENT_AGE_SECONDS = 300
_ENDPOINT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,120}")
_HEX_SIGNATURE_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
MAXIMUM_SIGNING_SECRET_LENGTH = 400


class MercuryWebhookTokenMissingError(RuntimeError):
    """The LLC has neither a transfer nor a read token to register with."""


@dataclass(frozen=True)
class MercuryWebhookRegistration:
    mercury_webhook_endpoint_id: str
    signing_secret: str


def _tokens_to_register_with(mercury_workspace_label: str) -> list[Secret]:
    """The transfer token first (more likely to be allowed to manage webhooks), then the read token."""
    tokens = []
    for name in (transfer_token_environment_variable_name(mercury_workspace_label), read_token_environment_variable_name(mercury_workspace_label)):
        value = (os.environ.get(name) or "").strip()
        if value:
            tokens.append(Secret(value))
    if not tokens:
        raise MercuryWebhookTokenMissingError(mercury_workspace_label)
    return tokens


def _headers(token: Secret) -> dict:
    return {"Authorization": f"Bearer {token.reveal()}", "Accept": "application/json", "Content-Type": "application/json"}


def register_webhook(mercury_workspace_label: str, receiving_url: str) -> MercuryWebhookRegistration:
    """Ask Mercury to call `receiving_url` on every event of the LLC. Raises `MercuryApiError` (our own words) when
    every token is refused or the answer has no usable id and secret."""
    last_error: Optional[MercuryApiError] = None
    for token in _tokens_to_register_with(mercury_workspace_label):
        try:
            response = requests.post(WEBHOOKS_URL, json={"url": receiving_url}, headers=_headers(token), timeout=MERCURY_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            logger.warning("Mercury webhook registration failed: %s", type(error).__name__)
            last_error = MercuryApiError("request failed")
            continue
        finally:
            token.wipe()
        try:
            _raise_for_an_error_status(response)
        except MercuryApiError as error:
            last_error = error
            continue
        try:
            body = response.json()
        except ValueError:
            body = None
        endpoint_id = body.get("id") if isinstance(body, dict) else None
        secret = body.get("secret") if isinstance(body, dict) else None
        if (isinstance(endpoint_id, str) and _ENDPOINT_ID_PATTERN.fullmatch(endpoint_id)
                and isinstance(secret, str) and 0 < len(secret) <= MAXIMUM_SIGNING_SECRET_LENGTH):
            return MercuryWebhookRegistration(endpoint_id, secret)
        last_error = MercuryApiError("the answer had no webhook id and secret")
    raise last_error or MercuryApiError("request failed")


def delete_webhook(mercury_workspace_label: str, mercury_webhook_endpoint_id: str) -> None:
    """Remove our address at Mercury. Raises `MercuryApiError` when every token is refused (404 counts as removed)."""
    if not _ENDPOINT_ID_PATTERN.fullmatch(mercury_webhook_endpoint_id or ""):
        raise MercuryApiError("not a webhook id")
    last_error: Optional[MercuryApiError] = None
    for token in _tokens_to_register_with(mercury_workspace_label):
        try:
            response = requests.delete(f"{WEBHOOKS_URL}/{mercury_webhook_endpoint_id}", headers=_headers(token), timeout=MERCURY_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            logger.warning("Mercury webhook removal failed: %s", type(error).__name__)
            last_error = MercuryApiError("request failed")
            continue
        finally:
            token.wipe()
        if response.status_code == 404:
            return
        try:
            _raise_for_an_error_status(response)
            return
        except MercuryApiError as error:
            last_error = error
    raise last_error or MercuryApiError("request failed")


SIGNATURE_IS_VALID = "valid"
SIGNATURE_IS_MISSING_OR_MALFORMED = "missing_or_malformed"
SIGNATURE_DOES_NOT_MATCH = "does_not_match"
SIGNATURE_IS_TOO_OLD = "too_old"


def check_event_signature(signing_secret: str, signature_header: Optional[str], raw_body: bytes,
                          now: Optional[datetime] = None) -> str:
    """One of the SIGNATURE_* answers. HMAC-SHA256 over "<timestamp>.<raw body>", compared in constant time; an event
    signed more than 5 minutes from now is refused (a replay)."""
    if not signature_header or len(signature_header) > 1000:
        return SIGNATURE_IS_MISSING_OR_MALFORMED
    timestamp, signatures = None, []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            timestamp = int(value)
        elif key == "v1" and _HEX_SIGNATURE_PATTERN.fullmatch(value):
            signatures.append(value.lower())
    if timestamp is None or not signatures:
        return SIGNATURE_IS_MISSING_OR_MALFORMED
    expected = hmac.new(signing_secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        return SIGNATURE_DOES_NOT_MATCH
    now_seconds = (now or datetime.now(timezone.utc)).timestamp()
    if abs(now_seconds - timestamp) > MAXIMUM_EVENT_AGE_SECONDS:
        return SIGNATURE_IS_TOO_OLD
    return SIGNATURE_IS_VALID
