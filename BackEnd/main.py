from fastapi import FastAPI, HTTPException
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
    validation_errors = []

    if payload.arv <= 0:
        validation_errors.append("ARV must be greater than 0.")

    if payload.purchase_price <= 0:
        validation_errors.append("Purchase price must be greater than 0.")

    if payload.ltv <= 0 or payload.ltv > 100:
        validation_errors.append("LTV must be between 0 and 100%.")

    if payload.down_payment < 0 or payload.down_payment > 100:
        validation_errors.append("Down payment must be between 0 and 100%.")

    if payload.loan_term_years <= 0:
        validation_errors.append("Loan term must be at least 1 year.")

    if payload.interest_rate <= 0 or payload.interest_rate > 100:
        validation_errors.append("Interest rate must be between 0 and 100%.")

    if payload.rent <= 0:
        validation_errors.append("Monthly rent must be greater than 0.")

    if payload.vacancy_percent < 0 or payload.vacancy_percent > 100:
        validation_errors.append("Vacancy percentage must be between 0 and 100%.")

    if (
        payload.property_managment_fee_precentages_from_rent < 0
        or payload.property_managment_fee_precentages_from_rent > 100
    ):
        validation_errors.append("Property management percentage must be between 0 and 100%.")

    if payload.maintenance_percent < 0 or payload.maintenance_percent > 100:
        validation_errors.append("Maintenance percentage must be between 0 and 100%.")

    if payload.capex_percent < 0 or payload.capex_percent > 100:
        validation_errors.append("CapEx percentage must be between 0 and 100%.")

    if payload.rehab_cost < 0:
        validation_errors.append("Rehab cost cannot be negative.")

    if payload.closing_costs_buy < 0 or payload.closing_cost_refi < 0:
        validation_errors.append("Closing costs cannot be negative.")

    if payload.HML_points < 0 or payload.HML_interest_in_cash < 0:
        validation_errors.append("HML points and interest cannot be negative.")

    if payload.taxes < 0 or payload.insurance < 0 or payload.hoa < 0:
        validation_errors.append("Carrying costs (taxes, insurance, HOA) cannot be negative.")

    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))

    def thousands_to_dollars(value: float) -> float:
        return value * 1000.0

    scaled_currency_inputs = {
        "arv": thousands_to_dollars(payload.arv),
        "purchase_price": thousands_to_dollars(payload.purchase_price),
        "rehab_cost": thousands_to_dollars(payload.rehab_cost),
        "closing_costs_buy": thousands_to_dollars(payload.closing_costs_buy),
        "HML_interest_in_cash": thousands_to_dollars(payload.HML_interest_in_cash),
        "closing_cost_refi": thousands_to_dollars(payload.closing_cost_refi),
    }

    arv = scaled_currency_inputs["arv"]
    purchase_price = scaled_currency_inputs["purchase_price"]
    rehab_cost = scaled_currency_inputs["rehab_cost"]
    closing_costs_buy = scaled_currency_inputs["closing_costs_buy"]
    HML_interest_in_cash = scaled_currency_inputs["HML_interest_in_cash"]
    closing_cost_refi = scaled_currency_inputs["closing_cost_refi"]
    hoa = payload.hoa

    rent = payload.rent
    ltv = payload.ltv/100
    loan_amount = arv * ltv
    loan_term_years = payload.loan_term_years

    down_payment_precent = payload.down_payment
    hml_principal = (1 - down_payment_precent/100.0) * purchase_price
    HML_points = payload.HML_points/100.0 * hml_principal

    property_management_fee = rent * (payload.property_managment_fee_precentages_from_rent / 100.0)

    maintenance = rent * (payload.maintenance_percent / 100.0)
    capex = rent * (payload.capex_percent / 100.0)
    vacancy = rent * (payload.vacancy_percent / 100.0)

    monthly_taxes = payload.taxes / 12.0
    monthly_insurance = payload.insurance / 12.0

    operating_expenses = (
        monthly_taxes
        + monthly_insurance
        + property_management_fee
        + hoa
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
    if total_payments <= 0:
        raise HTTPException(status_code=400, detail="Loan term must be at least one month.")

    factor = (1 + monthly_interest_rate) ** total_payments
    denominator = factor - 1
    if denominator == 0:
        raise HTTPException(status_code=400, detail="Unable to calculate mortgage payment with the provided rate and term.")

    mortgage_payment = loan_amount * monthly_interest_rate * factor / denominator

    net_operating_income = rent - operating_expenses
    cash_flow = net_operating_income - mortgage_payment
    dscr = net_operating_income / mortgage_payment

    return CalcCashFlowRes(cash_flow=cash_flow, dscr=dscr, cash_out=cash_out_from_deal, messages=None)


