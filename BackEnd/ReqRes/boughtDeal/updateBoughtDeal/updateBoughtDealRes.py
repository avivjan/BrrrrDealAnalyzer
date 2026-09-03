"""Re-exported from ReqRes.common.bought_deal_schemas -- the schema is defined there, once, for the whole app."""

from ReqRes.common.bought_deal_schemas import BoughtBrrrDealRes  # noqa: F401
from ReqRes.common.bought_deal_schemas import BoughtFlipDealRes  # noqa: F401

from typing import Union

UpdateBoughtDealRes = Union[BoughtBrrrDealRes, BoughtFlipDealRes]
