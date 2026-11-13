"""Rows of a rehab's construction account: the link, the manual adjustments and the transaction overrides
(tasks/todo/ConstructionAccountPerRehab.md). No commits here: the business layer commits."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from DAL.data_models.liquidity.construction_account_models import (
    LiquidityConstructionAccount, LiquidityConstructionAccountManualAdjustment, LiquidityConstructionAccountTransactionOverride,
    LiquidityConstructionAccountTransfer,
)


def get_construction_account_of_deal(db: Session, bought_brrr_deal_id) -> Optional[LiquidityConstructionAccount]:
    return (db.query(LiquidityConstructionAccount)
            .filter(LiquidityConstructionAccount.bought_brrr_deal_id == bought_brrr_deal_id).first())


def get_all_construction_accounts(db: Session) -> list[LiquidityConstructionAccount]:
    return db.query(LiquidityConstructionAccount).all()


def get_construction_account_by_mercury_account_id(db: Session, construction_mercury_account_id: str) -> Optional[LiquidityConstructionAccount]:
    return (db.query(LiquidityConstructionAccount)
            .filter(LiquidityConstructionAccount.construction_mercury_account_id == construction_mercury_account_id).first())


def get_manual_adjustments_of_deal(db: Session, bought_brrr_deal_id) -> list[LiquidityConstructionAccountManualAdjustment]:
    return (db.query(LiquidityConstructionAccountManualAdjustment)
            .filter(LiquidityConstructionAccountManualAdjustment.bought_brrr_deal_id == bought_brrr_deal_id)
            .order_by(LiquidityConstructionAccountManualAdjustment.date, LiquidityConstructionAccountManualAdjustment.created_at).all())


def get_manual_adjustment(db: Session, bought_brrr_deal_id, adjustment_id: str) -> Optional[LiquidityConstructionAccountManualAdjustment]:
    try:
        adjustment_uuid = uuid.UUID(str(adjustment_id))
    except ValueError:
        return None
    return (db.query(LiquidityConstructionAccountManualAdjustment)
            .filter(LiquidityConstructionAccountManualAdjustment.id == adjustment_uuid,
                    LiquidityConstructionAccountManualAdjustment.bought_brrr_deal_id == bought_brrr_deal_id).first())


def get_transaction_overrides_of_deal(db: Session, bought_brrr_deal_id) -> list[LiquidityConstructionAccountTransactionOverride]:
    return (db.query(LiquidityConstructionAccountTransactionOverride)
            .filter(LiquidityConstructionAccountTransactionOverride.bought_brrr_deal_id == bought_brrr_deal_id).all())


def get_transaction_override(db: Session, bought_brrr_deal_id, mercury_transaction_id: str) -> Optional[LiquidityConstructionAccountTransactionOverride]:
    return (db.query(LiquidityConstructionAccountTransactionOverride)
            .filter(LiquidityConstructionAccountTransactionOverride.mercury_transaction_id == mercury_transaction_id,
                    LiquidityConstructionAccountTransactionOverride.bought_brrr_deal_id == bought_brrr_deal_id).first())


def delete_everything_of_deal(db: Session, bought_brrr_deal_id) -> None:
    """The link, the manual adjustments and the overrides of one deal (an unlink, or the deal's deletion)."""
    for model in (LiquidityConstructionAccountManualAdjustment, LiquidityConstructionAccountTransactionOverride, LiquidityConstructionAccount):
        db.query(model).filter(model.bought_brrr_deal_id == bought_brrr_deal_id).delete(synchronize_session=False)


def get_transfers_of_construction_account(db: Session, bought_brrr_deal_id, construction_mercury_account_id: str) -> list[LiquidityConstructionAccountTransfer]:
    """The deal's in-app transfers of one construction account (an old account's transfers stay with that account)."""
    return (db.query(LiquidityConstructionAccountTransfer)
            .filter(LiquidityConstructionAccountTransfer.bought_brrr_deal_id == bought_brrr_deal_id,
                    LiquidityConstructionAccountTransfer.construction_mercury_account_id == construction_mercury_account_id)
            .order_by(LiquidityConstructionAccountTransfer.requested_at.desc()).all())


def get_transfer_by_idempotency_key(db: Session, idempotency_key: str) -> Optional[LiquidityConstructionAccountTransfer]:
    return db.query(LiquidityConstructionAccountTransfer).filter(LiquidityConstructionAccountTransfer.idempotency_key == idempotency_key).first()


def count_transfers_requested_since(db: Session, since) -> int:
    """Every transfer asked of Mercury since `since`, refused ones included (the hourly limit counts attempts)."""
    return db.query(LiquidityConstructionAccountTransfer).filter(LiquidityConstructionAccountTransfer.requested_at >= since).count()
