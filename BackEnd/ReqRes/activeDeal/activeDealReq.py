"""Backwards-compatible shim -- moved to ReqRes/common/{comps,base_deal,active_deal_schemas}.py."""

from ReqRes.common.comps import SoldComp, RentComp  # noqa: F401
from ReqRes.common.base_deal import BaseDealReq  # noqa: F401
from ReqRes.common.active_deal_schemas import (  # noqa: F401
    BrrrActiveDealCreate,
    FlipActiveDealCreate,
    BrrrActiveDealRes,
    FlipActiveDealRes,
)
