from sqlalchemy.orm import Session
from models_liquidity import LiquiditySettings
from ReqRes.liquidity.liquidityReq import LiquidityUpdate

def get_liquidity_settings(db: Session) -> LiquiditySettings:
    settings = db.query(LiquiditySettings).first()
    if not settings:
        settings = LiquiditySettings(big_whale_amount=0, mini_whale_amount=0)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

def update_liquidity_settings(db: Session, update_data: LiquidityUpdate) -> LiquiditySettings:
    settings = get_liquidity_settings(db)
    settings.big_whale_amount = update_data.big_whale_amount
    settings.mini_whale_amount = update_data.mini_whale_amount
    db.commit()
    db.refresh(settings)
    return settings

