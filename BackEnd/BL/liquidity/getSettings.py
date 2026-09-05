from datetime import date as date_type
from sqlalchemy.orm import Session

from ReqRes.common.liquidity_schemas import LiquiditySettingsUpdate
from DAL.crud.liquidity import get_settings as _get_settings
from BL.liquidity.common.mappers import settings_to_res
from BL.liquidity.updateSettings import update_settings


def get_settings(db: Session):
    settings = _get_settings(db)
    if not settings:
        default_data = LiquiditySettingsUpdate(
            opening_balance_k=0,
            opening_balance_date=date_type.today(),
            reserve_k=5,
        )
        # `update_settings` already returns the built Res; the initial-create
        # path below matches the original inline `upsert_settings` + response
        # construction that used to live in the route.
        return update_settings(db, default_data)
    return settings_to_res(settings)
