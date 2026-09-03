"""Re-exported from ReqRes.common.active_deal_schemas -- the schema is defined there, once, for the whole app."""

from ReqRes.common.active_deal_schemas import BrrrActiveDealCreate  # noqa: F401
from ReqRes.common.active_deal_schemas import FlipActiveDealCreate  # noqa: F401

from typing import Union

AddActiveDealReq = Union[BrrrActiveDealCreate, FlipActiveDealCreate]
