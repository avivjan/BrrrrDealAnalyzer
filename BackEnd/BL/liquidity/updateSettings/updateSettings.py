from datetime import date
from sqlalchemy.orm import Session

from ReqRes.common.liquidity_schemas import LiquiditySettingsUpdate
from DAL.crud.liquidity import get_settings as _get_settings, insert_settings
from BL.liquidity.common.mappers import settings_to_res


def update_settings(db: Session, data: LiquiditySettingsUpdate):
    settings = _get_settings(db)
    if not settings:
        settings = insert_settings(
            db,
            opening_balance_k=data.opening_balance_k if data.opening_balance_k is not None else 0,
            opening_balance_date=data.opening_balance_date if data.opening_balance_date is not None else date.today(),
            reserve_k=data.reserve_k if data.reserve_k is not None else 5,
        )
    else:
        if data.opening_balance_k is not None:
            settings.opening_balance_k = data.opening_balance_k
        if data.opening_balance_date is not None:
            settings.opening_balance_date = data.opening_balance_date
        if data.reserve_k is not None:
            settings.reserve_k = data.reserve_k
    db.commit()
    db.refresh(settings)
    return settings_to_res(settings)
