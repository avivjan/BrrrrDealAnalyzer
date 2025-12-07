from sqlalchemy import Column, Integer, Numeric
from db import Base

class LiquiditySettings(Base):
    __tablename__ = "liquidity_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    big_whale_amount = Column(Numeric(12, 2), nullable=False, default=0.0)
    mini_whale_amount = Column(Numeric(12, 2), nullable=False, default=0.0)

