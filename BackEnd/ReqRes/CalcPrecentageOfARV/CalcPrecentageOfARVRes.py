from pydantic import BaseModel


class CalcPrecentageOfARVRes(BaseModel):
    total_purchase_costs: float
    alllInPrecentFromARV: float = 0.0
    passes_70_rule: bool
    max_allowed_purchase_price_to_meet_70_rule: float = 0.0
    difference_in_purchase_price_to_meet_70_rule: float = -1.0