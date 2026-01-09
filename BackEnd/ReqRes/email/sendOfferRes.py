from pydantic import BaseModel

class SendOfferRes(BaseModel):
    message: str
    success: bool

