"""The limits on in-app transfers, from the liquidity settings the owner edits on the Construction Accounts page
(tasks/todo/ConstructionAccountPerRehab.md, Requirement 3), and the transfer figures each deal's status shows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from BL.liquidity.common.mercury_token_names import transfer_token_environment_variable_name, workspace_has_a_transfer_token
from DAL.crud.liquidity import get_settings
from DAL.crud.liquidity_construction_account import count_transfers_requested_since, get_transfers_of_construction_account
from DAL.data_models.liquidity.construction_account_models import LiquidityConstructionAccount
from ReqRes.common.liquidity_construction_account_schemas import ConstructionAccountTransferRes

DEFAULT_IN_APP_TRANSFERS_ARE_ENABLED = True
DEFAULT_TRANSFERS_PER_HOUR_LIMIT = 5
DEFAULT_MAXIMUM_SINGLE_TRANSFER_DOLLARS = Decimal("100000")
TRANSFER_LIMIT_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class ConstructionAccountTransferLimits:
    in_app_transfers_are_enabled: bool
    transfers_per_hour_limit: int
    maximum_single_transfer_dollars: Decimal


def transfer_limits(db: Session) -> ConstructionAccountTransferLimits:
    settings = get_settings(db)
    if settings is None:
        return ConstructionAccountTransferLimits(DEFAULT_IN_APP_TRANSFERS_ARE_ENABLED, DEFAULT_TRANSFERS_PER_HOUR_LIMIT,
                                                 DEFAULT_MAXIMUM_SINGLE_TRANSFER_DOLLARS)
    return ConstructionAccountTransferLimits(
        in_app_transfers_are_enabled=bool(settings.construction_account_in_app_transfers_enabled),
        transfers_per_hour_limit=int(settings.construction_account_transfers_per_hour_limit),
        maximum_single_transfer_dollars=Decimal(settings.construction_account_maximum_single_transfer_dollars),
    )


def transfers_left_this_hour(db: Session, limits: ConstructionAccountTransferLimits, now: datetime) -> int:
    return max(0, limits.transfers_per_hour_limit - count_transfers_requested_since(db, now - TRANSFER_LIMIT_WINDOW))


def transfer_res(transfer) -> ConstructionAccountTransferRes:
    return ConstructionAccountTransferRes(
        transfer_id=str(transfer.id), transfer_direction=transfer.transfer_direction, amount_dollars=float(transfer.amount_dollars),
        transfer_outcome=transfer.transfer_outcome, mercury_transfer_status=transfer.mercury_transfer_status,
        requested_at=transfer.requested_at, is_in_the_bank_feed=transfer.seen_in_the_bank_feed_at is not None,
    )


def transfer_figures_of_link(db: Session, link: LiquidityConstructionAccount) -> dict:
    """The status fields of the "Transfers made in the app" group: names and presence of the token, never its value."""
    limits = transfer_limits(db)
    return dict(
        transfers_made_in_the_app=[transfer_res(transfer) for transfer in
                                   get_transfers_of_construction_account(db, link.bought_brrr_deal_id, link.construction_mercury_account_id)],
        in_app_transfers_are_enabled=limits.in_app_transfers_are_enabled,
        has_a_transfer_token=workspace_has_a_transfer_token(link.mercury_workspace_label),
        transfer_token_environment_variable_name=transfer_token_environment_variable_name(link.mercury_workspace_label),
        transfers_left_this_hour=transfers_left_this_hour(db, limits, datetime.now(timezone.utc)),
        maximum_single_transfer_dollars=float(limits.maximum_single_transfer_dollars),
    )
