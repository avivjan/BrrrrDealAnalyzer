from fastapi import FastAPI
from ReqRes.CalcPrecentageOfARV.CalcPrecentageOfARVReq import CalcPrecentageOfARVReq
from ReqRes.CalcPrecentageOfARV.CalcPrecentageOfARVRes import CalcPrecentageOfARVRes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
) 

@app.get("/helloworld")
def helloworld() -> dict:
    """
    Simple endpoint that returns a Hello World message.
    """
    return {"message": "Hello, World!"}

@app.post("/CalcPrecentageOfARVRes", response_model=CalcPrecentageOfARVRes)
def getAlllInPrecentFromARV(payload: CalcPrecentageOfARVReq) -> CalcPrecentageOfARVRes:
    arv = payload.arv
    purchase_price = payload.purchase_price

    # Origination points are a percentage of purchase price
    origination_points_cost = (payload.origination_points_percent / 100.0) * purchase_price # default is 3% of purchase price
    is_transfer_taxes = payload.is_transfer_taxes # default is False
    transfer_taxes_cost = purchase_price * 0.007 if is_transfer_taxes else 0 # default is 0.7%, aka Doc Stamps

    total_non_purchase_costs = (
        + payload.title_fees # default is 1200
        + payload.title_insurance # default is 1200
        + payload.recording_fees # default is 150
        + transfer_taxes_cost
        + payload.lender_underwriting_fees # default is 600
        + payload.inspection_costs # default is 400
        + origination_points_cost 
        + payload.hml_appraisal_fee # default is 500
        + payload.draw_setup_fee # default is 350
        + payload.rehab_cost 
        + payload.rehab_utilities_cost # default is 1000
    )

    total_purchase_costs = total_non_purchase_costs + purchase_price
    alllInPrecentFromARV = (total_purchase_costs / arv) * 100.0 # convert to percentage
    passes_70_rule = alllInPrecentFromARV <= 70
    max_allowed_purchase_price_to_meet_70_rule = arv * 0.7 - total_non_purchase_costs

    if not passes_70_rule:
        difference_in_purchase_price_to_meet_70_rule = purchase_price - max_allowed_purchase_price_to_meet_70_rule
    else:
        difference_in_purchase_price_to_meet_70_rule = -1

    return CalcPrecentageOfARVRes(
        total_purchase_costs=total_purchase_costs,
        alllInPrecentFromARV=alllInPrecentFromARV,
        passes_70_rule=passes_70_rule,
        max_allowed_purchase_price_to_meet_70_rule=max_allowed_purchase_price_to_meet_70_rule,
        difference_in_purchase_price_to_meet_70_rule=difference_in_purchase_price_to_meet_70_rule,
    )
