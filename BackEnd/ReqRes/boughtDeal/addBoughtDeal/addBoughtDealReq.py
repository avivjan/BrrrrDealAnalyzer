"""Re-exported from ReqRes.common.bought_deal_schemas -- the schema is defined there, once, for the whole app."""

from ReqRes.common.bought_deal_schemas import BoughtBrrrDealCreate  # noqa: F401
from ReqRes.common.bought_deal_schemas import BoughtFlipDealCreate  # noqa: F401

from typing import Union

AddBoughtDealReq = Union[BoughtBrrrDealCreate, BoughtFlipDealCreate]
