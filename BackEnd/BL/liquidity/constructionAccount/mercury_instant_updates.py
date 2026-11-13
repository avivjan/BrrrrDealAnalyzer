"""Instant updates: Mercury calls us when something moves in an LLC, and we read that LLC at once
(tasks/todo/ConstructionAccountPerRehab.md, Step F).

    turn on   register https://<this app>/webhooks/mercury/<random token> at Mercury (a passkey step-up)
    an event  check its signature and age; then read the whole LLC fresh through the shared pace: every balance (the
              main Liquidity cash balance too) and its linked construction accounts, whose rows move as the bank reports
    turn off  remove the address at Mercury; the old address stops answering

An event's contents are never trusted or stored: a valid one only means "look now". Inside the 10-second floor (or a
back-off) the read waits for the floor's end, once however many events arrive. What the read changed on the timeline
is kept on the workspace row, so an open page can show "Timeline updated from the bank".

Errors are recorded for the settings drawer in our own words, never Mercury's text, and never the secret.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from BL.liquidity.common import mercury_reads
from BL.liquidity.common.mercury_client import MercuryApiError
from BL.liquidity.common.mercury_webhooks import (
    SIGNATURE_DOES_NOT_MATCH, SIGNATURE_IS_TOO_OLD, SIGNATURE_IS_VALID, MercuryWebhookTokenMissingError, check_event_signature,
    delete_webhook, register_webhook,
)
from BL.liquidity.common.mercury_token_names import read_token_environment_variable_name
from BL.liquidity.constructionAccount.construction_accounts import refresh_one_workspace
from DAL.data_models.liquidity.mercury_models import LiquidityMercuryWebhook

RECEIVING_PATH_PREFIX = "/webhooks/mercury/"
SIGNATURE_PROBLEM_MESSAGES = {
    SIGNATURE_DOES_NOT_MATCH: "An event arrived with a wrong signature and was ignored.",
    SIGNATURE_IS_TOO_OLD: "An event arrived more than 5 minutes old (a replay?) and was ignored.",
}
SIGNATURE_IS_MISSING_MESSAGE = "An event arrived without a usable signature and was ignored."


class InstantUpdatesRefusedError(Exception):
    """Turning instant updates on or off could not be done. The message is written for the owner; `was_recorded`
    means it is also on the workspace's webhook row (the router commits it)."""

    def __init__(self, message: str, http_status: int = 409, was_recorded: bool = False):
        super().__init__(message)
        self.http_status = http_status
        self.was_recorded = was_recorded


class UnknownWebhookAddressError(Exception):
    """No workspace has instant updates on at this address."""


class InvalidWebhookEventError(Exception):
    """The event failed its signature or age check (recorded on the webhook row)."""


@dataclass(frozen=True)
class MercuryEventOutcome:
    mercury_workspace_label: str
    was_read_now: bool
    # Inside the floor or a back-off: when the one deferred read may run.
    deferred_read_not_before: Optional[datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _webhook_of_workspace(db: Session, mercury_workspace_label: str) -> Optional[LiquidityMercuryWebhook]:
    return db.query(LiquidityMercuryWebhook).filter(LiquidityMercuryWebhook.mercury_workspace_label == mercury_workspace_label).first()


def _record_the_error(webhook: LiquidityMercuryWebhook, message: str, now: datetime) -> None:
    webhook.last_webhook_error_message = message[:300]
    webhook.last_webhook_error_at = now


def turn_on_instant_updates(db: Session, mercury_workspace_label: str, public_base_url: str) -> None:
    """Register this app's address for the LLC at Mercury. `public_base_url` is the app's own https origin."""
    if mercury_workspace_label not in mercury_reads.workspace_labels_with_a_read_token():
        raise InstantUpdatesRefusedError(
            f"Add {read_token_environment_variable_name(mercury_workspace_label)} to the hosting secrets first.")
    if not public_base_url.startswith("https://"):
        raise InstantUpdatesRefusedError("Instant updates need the app's public https address: turn them on from the deployed app.")
    now = _utc_now()
    webhook = _webhook_of_workspace(db, mercury_workspace_label)
    if webhook is None:
        webhook = LiquidityMercuryWebhook(mercury_workspace_label=mercury_workspace_label, receiving_path_token=secrets.token_urlsafe(32))
        db.add(webhook)
    if webhook.turned_on_at and webhook.mercury_webhook_endpoint_id:
        return
    receiving_url = f"{public_base_url.rstrip('/')}{RECEIVING_PATH_PREFIX}{webhook.receiving_path_token}"
    try:
        registration = register_webhook(mercury_workspace_label, receiving_url)
    except MercuryWebhookTokenMissingError:
        raise InstantUpdatesRefusedError(f"Add {read_token_environment_variable_name(mercury_workspace_label)} to the hosting secrets first.")
    except MercuryApiError as error:
        message = f"Mercury refused to turn on instant updates ({error}). The token may not be allowed to manage webhooks."
        _record_the_error(webhook, message, now)
        db.flush()
        raise InstantUpdatesRefusedError(message, http_status=502, was_recorded=True)
    webhook.mercury_webhook_endpoint_id = registration.mercury_webhook_endpoint_id
    webhook.signing_secret = registration.signing_secret
    webhook.turned_on_at = now
    db.flush()


def turn_off_instant_updates(db: Session, mercury_workspace_label: str) -> None:
    """Remove the address at Mercury. The receiving address is replaced, so an event still on its way is refused."""
    webhook = _webhook_of_workspace(db, mercury_workspace_label)
    if webhook is None or not webhook.turned_on_at:
        return
    if webhook.mercury_webhook_endpoint_id:
        try:
            delete_webhook(mercury_workspace_label, webhook.mercury_webhook_endpoint_id)
        except (MercuryApiError, MercuryWebhookTokenMissingError) as error:
            _record_the_error(webhook, f"Mercury did not remove the webhook ({error}); it is off here. Remove it in Mercury if events keep coming.", _utc_now())
    webhook.mercury_webhook_endpoint_id = None
    webhook.signing_secret = None
    webhook.turned_on_at = None
    webhook.receiving_path_token = secrets.token_urlsafe(32)
    db.flush()


def apply_an_instant_update(db: Session, mercury_workspace_label: str, today: date) -> None:
    """Read the LLC fresh (inside the pace), store every balance, refresh its construction accounts and their rows, and
    keep what the timeline changed for the open pages. No commit."""
    workspace_read = mercury_reads.read_workspace(db, mercury_workspace_label, want_fresh=True)
    _refreshed, _changed_rows, _accounts_changed, bank_reported_row_changes, _failed = refresh_one_workspace(
        db, mercury_workspace_label, workspace_read, today)
    if bank_reported_row_changes:
        row = mercury_reads.workspace_read_row(db, mercury_workspace_label)
        row.last_instant_update_at = _utc_now()
        row.bank_reported_row_changes_of_last_instant_update = [changes.model_dump(mode="json") for changes in bank_reported_row_changes]
    db.flush()


def receive_mercury_event(db: Session, receiving_path_token: str, raw_body: bytes, signature_header: Optional[str],
                          today: date, now: Optional[datetime] = None) -> MercuryEventOutcome:
    """One event from Mercury. Raises `UnknownWebhookAddressError` (nothing recorded) or `InvalidWebhookEventError`
    (recorded on the webhook row; the router commits it). No commit."""
    now = now or _utc_now()
    webhook = db.query(LiquidityMercuryWebhook).filter(LiquidityMercuryWebhook.receiving_path_token == receiving_path_token).first()
    if webhook is None or not webhook.turned_on_at or not webhook.signing_secret:
        raise UnknownWebhookAddressError()
    verdict = check_event_signature(webhook.signing_secret, signature_header, raw_body, now)
    if verdict != SIGNATURE_IS_VALID:
        _record_the_error(webhook, SIGNATURE_PROBLEM_MESSAGES.get(verdict, SIGNATURE_IS_MISSING_MESSAGE), now)
        db.flush()
        raise InvalidWebhookEventError()
    webhook.last_valid_event_received_at = now
    label = webhook.mercury_workspace_label
    mercury_reads.ask_for_a_fresh_read_of_workspace(db, label, now)
    read_row = mercury_reads.workspace_read_row(db, label, lock_it=True)
    if not mercury_reads.mercury_may_be_read_now(read_row, now):
        db.flush()
        return MercuryEventOutcome(label, was_read_now=False, deferred_read_not_before=mercury_reads.next_read_time_of(read_row))
    apply_an_instant_update(db, label, today)
    return MercuryEventOutcome(label, was_read_now=True, deferred_read_not_before=None)
