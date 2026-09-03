from sqlalchemy.orm import Session

from DAL.data_models import LIQUIDITY_RECURRING_FREQUENCIES
from ReqRes.common.liquidity_schemas import LiquidityRecurringTransactionUpdate
from DAL.crud.liquidity import get_recurring
from BL.liquidity.common.mappers import recurring_to_res


def update_recurring(db: Session, rule_id: str, data: LiquidityRecurringTransactionUpdate):
    """Apply a partial update; raises ValueError if the merged row is invalid,
    returns `None` if no matching row was found.

    The `end_date >= start_date` invariant lives here (not in the schema)
    because either field may be omitted from the patch payload.
    """
    rule = get_recurring(db, rule_id)
    if not rule:
        return None

    if data.description is not None:
        rule.description = data.description
    if data.amount_k is not None:
        if data.amount_k == 0:
            raise ValueError("amount_k must be non-zero.")
        rule.amount_k = data.amount_k
    if data.start_date is not None:
        rule.start_date = data.start_date
    # `end_date` is intentionally allowed to be set back to NULL via PATCH,
    # but the Update schema can't distinguish "unset" from "explicit null"
    # without a sentinel. Update endpoints treat `None` as "leave as-is" to
    # match the rest of this codebase.
    if data.end_date is not None:
        rule.end_date = data.end_date
    if data.occurrences is not None:
        rule.occurrences = data.occurrences
    if data.frequency is not None:
        if data.frequency not in LIQUIDITY_RECURRING_FREQUENCIES:
            raise ValueError(f"Unsupported frequency: {data.frequency!r}")
        rule.frequency = data.frequency
    if data.interval is not None:
        rule.interval = data.interval

    if rule.end_date is not None and rule.end_date < rule.start_date:
        raise ValueError("end_date must be on or after start_date.")

    db.commit()
    db.refresh(rule)
    return recurring_to_res(rule)
