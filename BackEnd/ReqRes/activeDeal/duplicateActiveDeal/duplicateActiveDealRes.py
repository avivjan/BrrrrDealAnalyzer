"""Re-exported from ReqRes.common.active_deal_schemas -- the schema is defined there, once, for the whole app."""

from ReqRes.common.active_deal_schemas import BrrrActiveDealRes  # noqa: F401
from ReqRes.common.active_deal_schemas import FlipActiveDealRes  # noqa: F401

from typing import Union

DuplicateActiveDealRes = Union[BrrrActiveDealRes, FlipActiveDealRes]
