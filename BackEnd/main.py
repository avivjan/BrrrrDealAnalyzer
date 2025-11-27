from fastapi import FastAPI
from ReqRes.CalcPrecentageOfARV.CalcPrecentageOfARVReq import CalcPrecentageOfARVReq
from ReqRes.CalcPrecentageOfARV.CalcPrecentageOfARVRes import CalcPrecentageOfARVRes
from ReqRes.CalcCashFlow.CalcCashFlowReq import CalcCashFlowReq
from ReqRes.CalcCashFlow.CalcCashFlowRes import CalcCashFlowRes

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


@app.post("/calcCashFlow", response_model=CalcCashFlowRes)
def calcCashFlow(payload: CalcCashFlowReq) -> CalcCashFlowRes:
    arv = payload.arv
    rent = payload.rent
    ltv = payload.ltv/100
    loan_amount = arv * ltv
    loan_term_years = payload.loan_term_years
    
    purchase_price = payload.purchase_price
    rehab_cost = payload.rehab_cost
    down_payment_precent = payload.down_payment
    closing_costs_buy = payload.closing_costs_buy
    hml_principal = (1 - down_payment_precent/100.0) * purchase_price
    HML_points = payload.HML_points/100.0 * hml_principal
    HML_interest_in_cash = payload.HML_interest_in_cash
    closing_cost_refi = payload.closing_cost_refi


    property_management_fee = rent * (payload.property_managment_fee_precentages_from_rent / 100.0)
  

    maintenance = rent * (payload.maintenance_percent / 100.0)
    capex = rent * (payload.capex_percent / 100.0)
    vacancy = rent * (payload.vacancy_percent / 100.0)

    operating_expenses = (
        payload.taxes
        + payload.insurance
        + property_management_fee
        + payload.hoa
        + maintenance
        + capex
        + vacancy
    )

    HML_payoff = (1-(down_payment_precent/100)) * purchase_price
    down_payment_in_cash = (down_payment_precent/100) * purchase_price
    total_cash_invested = down_payment_in_cash + closing_costs_buy + HML_points + rehab_cost + HML_interest_in_cash
    cash_out_from_deal = loan_amount - HML_payoff - closing_cost_refi - total_cash_invested
    
    monthly_interest_rate = (payload.interest_rate / 100.0) / 12.0
    total_payments = loan_term_years * 12
    factor = (1 + monthly_interest_rate) ** total_payments
    mortgage_payment = loan_amount * monthly_interest_rate * factor / (factor - 1)

    net_operating_income = rent - operating_expenses
    cash_flow = net_operating_income - mortgage_payment
    dscr = net_operating_income / mortgage_payment 
    return CalcCashFlowRes(cash_flow=cash_flow, dscr=dscr, cash_out=cash_out_from_deal)


