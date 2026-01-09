from pydantic import BaseModel
from decimal import Decimal

class SendOfferReq(BaseModel):
    agent_name: str
    agent_email: str
    property_address: str
    purchase_price: Decimal
    inspection_period_days: int

