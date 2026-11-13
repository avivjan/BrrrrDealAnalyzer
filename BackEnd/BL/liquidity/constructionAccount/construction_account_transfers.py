"""Deposit and Steal: the app moves money between a rehab's construction account and the same LLC's checking
(tasks/todo/ConstructionAccountPerRehab.md, Step E).

    Deposit: primary checking -> construction account (the cushion, plus any rehab beyond the budget)
    Steal:   construction account -> primary checking (the spread, or the cushion back)

The guards, in order: the settings' kill switch; a linked, open account; the LLC's transfer token; the per-transfer
maximum and the hourly limit (both from the settings); the source account's available balance, read from Mercury
through the shared pace; and for a Steal above "safe to steal now", an explicit confirmation of the top-up it will
need. The two accounts always come from the stored link: the request carries only an amount and a key.

**Exactly once.** The idempotency key is stored on the transfer row, committed before Mercury is asked. The same key
again answers that row and asks Mercury nothing; Mercury gets the same key too. A request is never retried here: an
answer that never came is stored as "Mercury did not answer", for the owner to check in Mercury.

This is the one place in this package that commits on its own (the row before the call, so a crash mid-call still
leaves the key); the router commits the rest. A preview (`preview_only`) asks Mercury nothing: it answers the rows
before -> after as if Mercury accepted the transfer, and is rolled back.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from BL.liquidity.common import mercury_reads
from BL.liquidity.common.mercury_client import MercuryApiError, MercurySlowDownError
from BL.liquidity.common.mercury_token_names import transfer_token_environment_variable_name, workspace_has_a_transfer_token
from BL.liquidity.common.mercury_transfers import (
    UNKNOWN_MERCURY_TRANSFER_STATUS, MercuryTransferNotAnsweredError, MercuryTransferRefusedError, MercuryTransferTokenMissingError,
    send_internal_transfer,
)
from BL.liquidity.constructionAccount import construction_accounts as construction_accounts_bl
from BL.liquidity.constructionAccount.construction_account_rows import projection_of_linked_deal
from BL.liquidity.constructionAccount.construction_account_transfer_settings import transfer_limits, transfer_res, transfers_left_this_hour
from DAL.crud.liquidity_construction_account import get_transfer_by_idempotency_key
from DAL.data_models.liquidity.construction_account_models import (
    TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT, TRANSFER_DIRECTION_STEAL_TO_PRIMARY_CHECKING, TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY,
    TRANSFER_OUTCOME_BEING_SENT, TRANSFER_OUTCOME_FAILED_OR_CANCELLED_AT_MERCURY, TRANSFER_OUTCOME_MERCURY_DID_NOT_ANSWER,
    TRANSFER_OUTCOME_REFUSED_BY_MERCURY, LiquidityConstructionAccountTransfer,
)
from ReqRes.common.liquidity_construction_account_schemas import ConstructionAccountTransferReq, ConstructionAccountTransferWriteRes
from ReqRes.common.liquidity_deal_schemas import UseDealValueForField

ONE_CENT = Decimal("0.01")
MERCURY_STATUSES_THAT_MEAN_NOTHING_MOVED = {"failed", "cancelled"}


class ConstructionAccountTransferRefusedError(Exception):
    """A guard said no; nothing was asked of Mercury. `http_status`: 409 (a conflict with the account or the
    settings), 429 (the hourly limit). The message is written for the owner."""

    def __init__(self, message: str, http_status: int = 409):
        super().__init__(message)
        self.http_status = http_status


def _money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _source_and_destination(link, transfer_direction: str) -> tuple[str, str]:
    if transfer_direction == TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT:
        return link.primary_checking_mercury_account_id, link.construction_mercury_account_id
    return link.construction_mercury_account_id, link.primary_checking_mercury_account_id


def _refuse_unless_the_transfer_may_be_made(db: Session, deal, link, transfer_direction: str, amount_dollars: Decimal,
                                            confirm_amount_exceeds_safe_to_steal: bool, now: datetime, preview_only: bool) -> None:
    limits = transfer_limits(db)
    if not limits.in_app_transfers_are_enabled:
        raise ConstructionAccountTransferRefusedError("In-app transfers are turned off in the construction account settings.")
    if link.closed_out_at is not None:
        raise ConstructionAccountTransferRefusedError("This construction account is closed out: reopen it first.")
    if not workspace_has_a_transfer_token(link.mercury_workspace_label):
        raise ConstructionAccountTransferRefusedError(
            f"No transfer token for this LLC: add {transfer_token_environment_variable_name(link.mercury_workspace_label)} to the hosting secrets.")
    if amount_dollars > limits.maximum_single_transfer_dollars:
        raise ConstructionAccountTransferRefusedError(
            f"Above the {_money(limits.maximum_single_transfer_dollars)} per-transfer maximum in the construction account settings.")
    if not preview_only and transfers_left_this_hour(db, limits, now) <= 0:
        raise ConstructionAccountTransferRefusedError(
            f"{limits.transfers_per_hour_limit} transfers in the last hour, the limit in the construction account settings. Try again later.",
            http_status=429)
    source_account_id, _destination = _source_and_destination(link, transfer_direction)
    source_account = construction_accounts_bl._required_accounts_by_id(db, want_fresh=True).get(source_account_id)
    if source_account is None:
        raise ConstructionAccountTransferRefusedError("The source account is no longer in Mercury.")
    available = Decimal(str(source_account["available_balance_dollars"])).quantize(ONE_CENT)
    if amount_dollars > available:
        raise ConstructionAccountTransferRefusedError(f"Only {_money(available)} is available in {source_account['name']}.")
    if transfer_direction == TRANSFER_DIRECTION_STEAL_TO_PRIMARY_CHECKING and not preview_only:
        safe_to_steal = projection_of_linked_deal(db, deal, link).safe_to_steal_now_dollars
        if amount_dollars > safe_to_steal and not confirm_amount_exceeds_safe_to_steal:
            raise ConstructionAccountTransferRefusedError(
                f"This is {_money(amount_dollars - safe_to_steal)} above safe to steal now ({_money(safe_to_steal)}): "
                f"you will need to top up the account by about that much before the rehab ends. Confirm to go ahead.")


def _new_transfer_row(deal, link, transfer_direction: str, data: ConstructionAccountTransferReq, amount_dollars: Decimal,
                      transfer_outcome: str, now: datetime, requested_by_user_id) -> LiquidityConstructionAccountTransfer:
    source_account_id, destination_account_id = _source_and_destination(link, transfer_direction)
    return LiquidityConstructionAccountTransfer(
        id=uuid.uuid4(), bought_brrr_deal_id=deal.id, construction_mercury_account_id=link.construction_mercury_account_id,
        source_mercury_account_id=source_account_id, destination_mercury_account_id=destination_account_id,
        mercury_workspace_label=link.mercury_workspace_label, transfer_direction=transfer_direction, amount_dollars=amount_dollars,
        idempotency_key=data.idempotency_key, transfer_outcome=transfer_outcome, requested_at=now, requested_by_user_id=requested_by_user_id,
    )


def _ask_mercury(transfer: LiquidityConstructionAccountTransfer, deal_address: str) -> None:
    """Send the stored transfer once and keep what came back on the row. Never retried."""
    direction_word = "Deposit" if transfer.transfer_direction == TRANSFER_DIRECTION_DEPOSIT_INTO_CONSTRUCTION_ACCOUNT else "Steal"
    try:
        answer = send_internal_transfer(
            transfer.mercury_workspace_label, transfer.source_mercury_account_id, transfer.destination_mercury_account_id,
            Decimal(transfer.amount_dollars), transfer.idempotency_key, f"{direction_word}: {deal_address}")
    except MercuryTransferNotAnsweredError:
        transfer.transfer_outcome = TRANSFER_OUTCOME_MERCURY_DID_NOT_ANSWER
        transfer.mercury_transfer_status = UNKNOWN_MERCURY_TRANSFER_STATUS
        return
    except MercuryTransferRefusedError as refusal:
        transfer.transfer_outcome = TRANSFER_OUTCOME_REFUSED_BY_MERCURY
        transfer.mercury_refusal_http_status = refusal.http_status
        return
    except MercurySlowDownError:
        transfer.transfer_outcome = TRANSFER_OUTCOME_REFUSED_BY_MERCURY
        transfer.mercury_refusal_http_status = 429
        return
    except (MercuryTransferTokenMissingError, MercuryApiError):
        transfer.transfer_outcome = TRANSFER_OUTCOME_REFUSED_BY_MERCURY
        return
    transfer.mercury_transfer_id = answer.mercury_transfer_id
    transfer.mercury_transfer_status = answer.mercury_transfer_status
    transfer.transfer_outcome = (TRANSFER_OUTCOME_FAILED_OR_CANCELLED_AT_MERCURY if answer.mercury_transfer_status in MERCURY_STATUSES_THAT_MEAN_NOTHING_MOVED
                                 else TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY)


def make_construction_account_transfer(db: Session, bought_deal_id: str, transfer_direction: str, data: ConstructionAccountTransferReq,
                                       today: Optional[date], use_deal_value_for: list[UseDealValueForField], preview_only: bool,
                                       requested_by_user_id=None) -> ConstructionAccountTransferWriteRes:
    deal, link = construction_accounts_bl._find_linked(db, bought_deal_id)
    amount_dollars = Decimal(str(data.amount_dollars)).quantize(ONE_CENT)
    now = _utc_now()

    already_asked = get_transfer_by_idempotency_key(db, data.idempotency_key)
    if already_asked is not None:
        if (str(already_asked.bought_brrr_deal_id) != str(deal.id) or already_asked.transfer_direction != transfer_direction
                or Decimal(already_asked.amount_dollars) != amount_dollars):
            raise ConstructionAccountTransferRefusedError("This transfer key was already used for another transfer.")
        # The same transfer asked again (the passkey step-up retries the same request): its stored answer, nothing sent.
        answer = construction_accounts_bl._write(db, deal, today, use_deal_value_for, preview_only, lambda: None)
        return ConstructionAccountTransferWriteRes(**answer.model_dump(), transfer=transfer_res(already_asked))

    _refuse_unless_the_transfer_may_be_made(db, deal, link, transfer_direction, amount_dollars,
                                            data.confirm_amount_exceeds_safe_to_steal, now, preview_only)

    if preview_only:
        def as_if_mercury_accepted_it() -> None:
            db.add(_new_transfer_row(deal, link, transfer_direction, data, amount_dollars, TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY, now, requested_by_user_id))
        answer = construction_accounts_bl._write(db, deal, today, use_deal_value_for, True, as_if_mercury_accepted_it)
        return ConstructionAccountTransferWriteRes(**answer.model_dump(), transfer=None)

    resolved_today = construction_accounts_bl.today_for_liquidity(db, today)
    status_before = construction_accounts_bl.status_of_deal(db, deal, resolved_today)
    transfer = _new_transfer_row(deal, link, transfer_direction, data, amount_dollars, TRANSFER_OUTCOME_BEING_SENT, now, requested_by_user_id)
    db.add(transfer)
    try:
        db.commit()   # the key is stored before Mercury is asked (see the module docstring)
    except IntegrityError:
        # The same key, sent twice at once (a double tap): the first one is being sent; this one asks nothing.
        db.rollback()
        raise ConstructionAccountTransferRefusedError("This transfer is already being sent. Check the account in a moment.")

    _ask_mercury(transfer, deal.address or "")
    db.flush()
    if transfer.transfer_outcome == TRANSFER_OUTCOME_ACCEPTED_BY_MERCURY:
        # The balances moved: the next allowed read of this LLC goes to Mercury, and the open pages reload.
        mercury_reads.ask_for_a_fresh_read_of_workspace(db, link.mercury_workspace_label)
        mercury_reads.mark_construction_accounts_changed(db, link.mercury_workspace_label, now)
    answer = construction_accounts_bl._write(db, deal, resolved_today, use_deal_value_for, False, lambda: None, status_before=status_before)
    return ConstructionAccountTransferWriteRes(**answer.model_dump(), transfer=transfer_res(transfer))
