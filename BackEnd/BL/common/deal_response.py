"""ORM deal row -> `*Res` Pydantic transforms.

Runs the calculator directly on the ORM row (duck-typed, see
`BL.analyze.analyzeBRRR` / `BL.analyze.analyzeFlip`), merges every column with the calc result, and
validates the merged dict into the response model.
"""

from typing import Union

from DAL.data_models import BrrrActiveDeal, FlipActiveDeal, BoughtBrrrDeal, BoughtFlipDeal
from ReqRes.common.active_deal_schemas import BrrrActiveDealRes, FlipActiveDealRes
from ReqRes.common.bought_deal_schemas import BoughtBrrrDealRes, BoughtFlipDealRes
from BL.analyze.analyzeBRRR import calculate_brrr_results
from BL.analyze.analyzeFlip import calculate_flip_results


def create_deal_response(deal: Union[BrrrActiveDeal, FlipActiveDeal]):
    if isinstance(deal, BrrrActiveDeal):
        calc = calculate_brrr_results(deal)
        deal_data = {c.name: getattr(deal, c.name) for c in deal.__table__.columns}
        deal_data.update(calc.model_dump())
        deal_data['deal_type'] = "BRRRR"
        return BrrrActiveDealRes.model_validate(deal_data)
    elif isinstance(deal, FlipActiveDeal):
        calc = calculate_flip_results(deal)
        deal_data = {c.name: getattr(deal, c.name) for c in deal.__table__.columns}
        deal_data.update(calc.model_dump())
        deal_data['deal_type'] = "FLIP"
        return FlipActiveDealRes.model_validate(deal_data)
    return None


def create_bought_deal_response(deal: Union[BoughtBrrrDeal, BoughtFlipDeal]):
    if isinstance(deal, BoughtBrrrDeal):
        calc = calculate_brrr_results(deal)
        deal_data = {c.name: getattr(deal, c.name) for c in deal.__table__.columns}
        deal_data.update(calc.model_dump())
        deal_data['deal_type'] = "BRRRR"
        return BoughtBrrrDealRes.model_validate(deal_data)
    elif isinstance(deal, BoughtFlipDeal):
        calc = calculate_flip_results(deal)
        deal_data = {c.name: getattr(deal, c.name) for c in deal.__table__.columns}
        deal_data.update(calc.model_dump())
        deal_data['deal_type'] = "FLIP"
        return BoughtFlipDealRes.model_validate(deal_data)
    return None
