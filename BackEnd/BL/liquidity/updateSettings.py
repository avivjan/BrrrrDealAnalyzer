from datetime import date
from sqlalchemy.orm import Session

from ReqRes.common.liquidity_schemas import LiquiditySettingsUpdate
from DAL.crud.liquidity import get_settings as _get_settings, insert_settings
from BL.liquidity.common.mappers import settings_to_res

# The soft-warning threshold of a fresh install: $5,000.
DEFAULT_RESERVE_DOLLARS = 5000


def update_settings(db: Session, data: LiquiditySettingsUpdate):
    settings = _get_settings(db)
    if not settings:
        settings = insert_settings(
            db,
            opening_balance_dollars=data.opening_balance_dollars if data.opening_balance_dollars is not None else 0,
            opening_balance_date=data.opening_balance_date if data.opening_balance_date is not None else date.today(),
            reserve_dollars=data.reserve_dollars if data.reserve_dollars is not None else DEFAULT_RESERVE_DOLLARS,
        )
    else:
        if data.opening_balance_dollars is not None:
            settings.opening_balance_dollars = data.opening_balance_dollars
        if data.opening_balance_date is not None:
            settings.opening_balance_date = data.opening_balance_date
        if data.reserve_dollars is not None:
            settings.reserve_dollars = data.reserve_dollars
    # Sent explicitly (a list, or null for "every active account"): stored as sent.
    if "mercury_account_ids_counted_as_cash" in data.model_fields_set:
        settings.mercury_account_ids_counted_as_cash = data.mercury_account_ids_counted_as_cash
    if data.timezone_name is not None:
        settings.timezone_name = data.timezone_name
    db.commit()
    db.refresh(settings)
    return settings_to_res(settings)
