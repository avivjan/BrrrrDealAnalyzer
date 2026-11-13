"""Mercury internal transfers: the one write this app makes at Mercury (tasks/todo/ConstructionAccountPerRehab.md,
Step E). Deposit (an LLC's checking -> a rehab's construction account) and Steal (the construction account -> the
same LLC's checking).

The transfer token is separate from the read token and write-capable: `MERCURY_TRANSFER_API_TOKEN_<LABEL>`, read
only here, only at the moment of the call, and only into the Authorization header. No read path imports this module,
and this module never uses a read token. The URL is pinned to the one transfer endpoint, and the call is never
retried: Mercury's own idempotency key and our stored transfer row make a repeat safe, but a silent retry could not
tell "not sent" from "sent, answer lost".

Mercury's answer is checked defensively: its transfer response is not fully documented, so a missing id or an
unknown status is kept as such, never guessed.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import requests

from BL.common.secret import Secret
from BL.liquidity.common.mercury_client import MERCURY_API_BASE, MERCURY_TIMEOUT_SECONDS, MercuryApiError, _raise_for_an_error_status
from BL.liquidity.common.mercury_token_names import transfer_token_environment_variable_name

logger = logging.getLogger(__name__)

# The approval-gated internal transfer (the token's "Transfer Money with Approval" scope): Mercury sends it once the
# organization's approval rules are met (an approval in the Mercury app). Same body as POST /transfer.
TRANSFER_URL = f"{MERCURY_API_BASE}/request-transfer"
_MERCURY_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,80}")
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"[A-Za-z0-9-]{8,80}")
# Mercury's transaction statuses; anything else is stored as "unknown".
# A transfer's statuses, and an approval request's (stored in snake case: pendingApproval -> pending_approval).
KNOWN_MERCURY_TRANSFER_STATUSES = {"pending", "sent", "cancelled", "failed", "pending_approval", "approved", "rejected"}
_APPROVAL_REQUEST_STATUS_NAMES = {"pendingapproval": "pending_approval", "approved": "approved", "rejected": "rejected", "cancelled": "cancelled"}
UNKNOWN_MERCURY_TRANSFER_STATUS = "unknown"
TRANSFER_NOTE_MAXIMUM_LENGTH = 120


class MercuryTransferTokenMissingError(RuntimeError):
    """The LLC has no transfer token. Carries the setting's name (never a value) for the message."""

    def __init__(self, transfer_token_environment_variable_name: str):
        super().__init__(f"No transfer token: add {transfer_token_environment_variable_name} to the hosting secrets")
        self.transfer_token_environment_variable_name = transfer_token_environment_variable_name


class MercuryTransferRefusedError(MercuryApiError):
    """Mercury answered the transfer with an error status (4xx): nothing was sent. Carries the status code only, never
    Mercury's text, so the owner can see why (a token's permissions or allowed IPs, the request, a slow-down)."""

    def __init__(self, http_status: int):
        super().__init__(f"HTTP {http_status}")
        self.http_status = http_status


class MercuryTransferNotAnsweredError(MercuryApiError):
    """The request left, but no usable answer came back: the transfer may or may not have been made."""


@dataclass(frozen=True)
class MercuryTransferAnswer:
    mercury_transfer_id: Optional[str]
    mercury_transfer_status: str


def _transfer_token_of_workspace(mercury_workspace_label: str) -> Secret:
    name = transfer_token_environment_variable_name(mercury_workspace_label)
    token = (os.environ.get(name) or "").strip()
    if not token:
        raise MercuryTransferTokenMissingError(name)
    return Secret(token)


def _answer_of(body: object) -> MercuryTransferAnswer:
    """The transfer's id and status, from whichever of the shapes Mercury may answer with."""
    if not isinstance(body, dict):
        return MercuryTransferAnswer(None, UNKNOWN_MERCURY_TRANSFER_STATUS)
    candidates = [body] + [body[key] for key in ("transaction", "transfer") if isinstance(body.get(key), dict)]
    transfer_id, status = None, UNKNOWN_MERCURY_TRANSFER_STATUS
    for candidate in candidates:
        raw_id = candidate.get("id") or candidate.get("requestId")
        if transfer_id is None and isinstance(raw_id, str) and _MERCURY_ID_PATTERN.fullmatch(raw_id):
            transfer_id = raw_id
        raw_status = candidate.get("status")
        if status == UNKNOWN_MERCURY_TRANSFER_STATUS and isinstance(raw_status, str):
            named = _APPROVAL_REQUEST_STATUS_NAMES.get(raw_status.lower(), raw_status.lower())
            if named in KNOWN_MERCURY_TRANSFER_STATUSES:
                status = named
    return MercuryTransferAnswer(transfer_id, status)


def send_internal_transfer(mercury_workspace_label: str, source_mercury_account_id: str, destination_mercury_account_id: str,
                           amount_dollars: Decimal, idempotency_key: str, note: str) -> MercuryTransferAnswer:
    """`POST /request-transfer` between two accounts of one LLC (it waits for an approval in Mercury). Raises `MercuryTransferTokenMissingError`, `MercuryApiError`
    (refused: nothing was sent), `MercurySlowDownError`, or `MercuryTransferNotAnsweredError` (maybe sent)."""
    for account_id in (source_mercury_account_id, destination_mercury_account_id):
        if not _MERCURY_ID_PATTERN.fullmatch(account_id or ""):
            raise MercuryApiError("not a Mercury account id")
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key or ""):
        raise MercuryApiError("not an idempotency key")
    if amount_dollars <= 0:
        raise MercuryApiError("the amount must be above zero")
    token = _transfer_token_of_workspace(mercury_workspace_label)
    payload = {
        "sourceAccountId": source_mercury_account_id,
        "destinationAccountId": destination_mercury_account_id,
        "amount": float(amount_dollars.quantize(Decimal("0.01"))),
        "idempotencyKey": idempotency_key,
        "note": note[:TRANSFER_NOTE_MAXIMUM_LENGTH],
    }
    headers = {"Authorization": f"Bearer {token.reveal()}", "Accept": "application/json", "Content-Type": "application/json"}
    try:
        response = requests.post(TRANSFER_URL, json=payload, headers=headers, timeout=MERCURY_TIMEOUT_SECONDS)
    except requests.Timeout as error:
        logger.warning("Mercury transfer: no answer in time (%s)", type(error).__name__)
        raise MercuryTransferNotAnsweredError("no answer in time") from error
    except requests.ConnectionError as error:
        # A connection that failed before the request was sent and one cut after it look alike: maybe sent.
        logger.warning("Mercury transfer: connection failed (%s)", type(error).__name__)
        raise MercuryTransferNotAnsweredError("connection failed") from error
    except requests.RequestException as error:
        logger.warning("Mercury transfer: request failed (%s)", type(error).__name__)
        raise MercuryTransferNotAnsweredError("request failed") from error
    finally:
        token.wipe()
    if response.status_code >= 500:
        raise MercuryTransferNotAnsweredError(f"HTTP {response.status_code}")
    if response.status_code == 429:
        _raise_for_an_error_status(response)   # Mercury's slow-down, with its Retry-After
    if not response.ok:
        logger.warning("Mercury refused a transfer: HTTP %s", response.status_code)
        raise MercuryTransferRefusedError(response.status_code)
    try:
        body = response.json()
    except ValueError:
        body = None
    return _answer_of(body)
