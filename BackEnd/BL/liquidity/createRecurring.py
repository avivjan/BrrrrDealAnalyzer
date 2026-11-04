from sqlalchemy.orm import Session

from DAL.data_models import LIQUIDITY_RECURRING_FREQUENCIES
from ReqRes.common.liquidity_schemas import LiquidityRecurringTransactionCreate
from DAL.crud.liquidity import insert_recurring
from BL.liquidity.common.mappers import recurring_to_res
from BL.liquidity.dealCashRows.liquidity_deals import today_for_liquidity


def create_recurring(db: Session, data: LiquidityRecurringTransactionCreate):
    """Raises ValueError for an unsupported frequency."""
    if data.frequency not in LIQUIDITY_RECURRING_FREQUENCIES:
        # Should already be guarded by the Literal type, but defense-in-depth
        # so a hand-rolled HTTP client can't poison the DB.
        raise ValueError(f"Unsupported frequency: {data.frequency!r}")
    rule = insert_recurring(db, data)
    # Occurrences before today are history (already in the bank balance), never overdue, unless the caller says
    # from when a missed one counts (a series entered with a payment already missed).
    rule.occurrences_can_be_overdue_from = data.occurrences_can_be_overdue_from or today_for_liquidity(db, None)
    db.commit()
    db.refresh(rule)
    return recurring_to_res(rule)
