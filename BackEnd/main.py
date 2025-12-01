from fastapi import FastAPI, HTTPException
from ReqRes.analyzeDeal.analyzeDealReq import analyzeDealReq
from ReqRes.analyzeDeal.analyzeDealRes import analyzeDealRes

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
) 



def validate_inputs(payload: analyzeDealReq):
    validation_errors = []
    # Dollar values in thousands
    if payload.arv_in_thousands <= 0:
        validation_errors.append("ARV (in thousands) must be greater than 0.")

    if payload.purchase_price_in_thousands <= 0:
        validation_errors.append("Purchase price (in thousands) must be greater than 0.")

    if payload.rehab_cost_in_thousands < 0:
        validation_errors.append("Rehab cost (in thousands) cannot be negative.")

    if payload.closing_costs_buy < 0:
        validation_errors.append("Closing costs (buy) cannot be negative.")

    if payload.closing_cost_refi_in_thousands < 0:
        validation_errors.append("Refi closing costs (in thousands) cannot be negative.")

    # Lending Terms
    if payload.down_payment < 0 or payload.down_payment > 100:
        validation_errors.append("Down payment percentage must be between 0% and 100%.")

    if payload.ltv_as_precent <= 0 or payload.ltv_as_precent > 100:
        validation_errors.append("LTV must be between 0% and 100%.")

    if payload.HML_points < 0 or payload.HML_points > 100:
        validation_errors.append("HML points must be between 0% and 100%.")

    if payload.HML_interest_rate <= 0 or payload.HML_interest_rate > 100:
        validation_errors.append("HML interest rate must be between 0% and 100%.")

    if payload.Months_until_refi <= 0:
        validation_errors.append("Months until refi must be a positive number.")

    if payload.loan_term_years <= 0:
        validation_errors.append("Loan term must be at least 1 year.")

    # DSCR long-term financing
    if payload.interest_rate <= 0 or payload.interest_rate > 100:
        validation_errors.append("Interest rate must be between 0% and 100%.")

    # Rent + Operating Expenses
    if payload.rent <= 0:
        validation_errors.append("Rent must be greater than 0.")

    if payload.vacancy_percent < 0 or payload.vacancy_percent > 100:
        validation_errors.append("Vacancy percentage must be between 0% and 100%.")

    if payload.property_managment_fee_precentages_from_rent < 0 or payload.property_managment_fee_precentages_from_rent > 100:
        validation_errors.append("Property management percentage must be between 0% and 100%.")

    if payload.maintenance_percent < 0 or payload.maintenance_percent > 100:
        validation_errors.append("Maintenance percentage must be between 0% and 100%.")

    if payload.capex_percent_of_rent < 0 or payload.capex_percent_of_rent > 100:
        validation_errors.append("CapEx percentage must be between 0% and 100%.")

    if payload.annual_property_taxes < 0:
        validation_errors.append("Annual property taxes cannot be negative.")

    if payload.annual_insurance < 0:
        validation_errors.append("Annual insurance cannot be negative.")

    if payload.montly_hoa < 0:
        validation_errors.append("HOA dues cannot be negative.")

    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))

def thousands_to_dollars(value: float) -> float:
    return value * 1000.0


def calc_montly_operating_expenses(payload):
    property_management_fee = payload.rent * (payload.property_managment_fee_precentages_from_rent / 100.0)
    maintenance = payload.rent * (payload.maintenance_percent / 100.0)
    capex = payload.rent * (payload.capex_percent / 100.0)
    vacancy = payload.rent * (payload.vacancy_percent / 100.0)
    monthly_taxes = payload.taxes / 12.0
    monthly_insurance = payload.insurance / 12.0
    hoa = payload.hoa
    return monthly_taxes + monthly_insurance + property_management_fee + hoa + maintenance + capex + vacancy
    
def calc_cash_out_from_deal(arv, ltv, down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash,rehab_cost,HML_interest_in_cash,closing_cost_refi, use_HM_for_rehab):
    loan_amount = arv * ltv
    HML_payoff = get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    down_payment_in_cash = (down_payment_precent/100) * purchase_price
    total_cash_invested = down_payment_in_cash + closing_costs_buy + HML_points_in_cash + rehab_cost * (1-int(use_HM_for_rehab)) + HML_interest_in_cash
    return loan_amount - HML_payoff - closing_cost_refi - total_cash_invested

def calc_mortgage_payment(arv, ltv, interest_rate, loan_term_years):
    loan_amount = arv * ltv
    monthly_interest_rate = (interest_rate / 100.0) / 12.0
    total_payments = loan_term_years * 12
    factor = (1 + monthly_interest_rate) ** total_payments
    denominator = factor - 1
    if denominator == 0:
        raise HTTPException(status_code=400, detail="Unable to calculate mortgage payment with the provided rate and term.")
    return loan_amount * monthly_interest_rate * factor / denominator

def calc_cash_on_cash(cash_out_from_deal, cash_flow):
    if cash_out_from_deal >= 0:
        return -1 # show as infinity
    elif cash_flow <= 0:
        return -2 # show as negative infinity
    else:
        return cash_flow * 12 / cash_out_from_deal
        
def calc_roi(cash_out_from_deal, cash_flow, equity):
    if cash_out_from_deal >= 0:
        return -1 # show as infinity
    elif cash_flow <= 0:
        return -2 # show as negative infinity
    else:
        return (cash_flow * 12 + equity )/ cash_out_from_deal
    
def get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab):
    return purchase_price * (1-down_payment_precent/100) + rehab_cost * int(use_HM_for_rehab)
     
     
def calc_HML_interest_in_cash(purchase_price, down_payment_precent, rehab_cost, Months_until_refi, HML_interest_rate, use_HM_for_rehab):
    HML_montly_interest = HML_interest_rate / 12 / 100.0 * get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    return HML_montly_interest * Months_until_refi  


def get_total_cash_needed_for_deal(down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, use_HM_for_rehab):
    down_payment_in_cash = (down_payment_precent/100) * purchase_price
    return down_payment_in_cash + closing_costs_buy + HML_points_in_cash + rehab_cost * (1-int(use_HM_for_rehab)) + HML_interest_in_cash

    #________________________________________________________________________
    #________________________________________________________________________
    #________________________________________________________________________
    #________________________________________________________________________
    
    
@app.get("/helloworld")
def helloworld() -> dict:
    return {"message": "Hello, World!"}
    
@app.post("/analyzeDeal", response_model=analyzeDealRes)
def analyzeDeal(payload: analyzeDealReq) -> analyzeDealRes:
    validate_inputs(payload)

    arv = thousands_to_dollars(payload.arv_in_thousands)
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost = thousands_to_dollars(payload.rehab_cost_in_thousands)
    down_payment_precent = payload.down_payment
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    use_HM_for_rehab = payload.use_HM_for_rehab
    Months_until_refi = payload.Months_until_refi
    HML_interest_rate = payload.HML_interest_rate
    closing_cost_refi = thousands_to_dollars(payload.closing_cost_refi_in_thousands)
    loan_term_years = payload.loan_term_years
    ltv = payload.ltv_as_precent/100
    interest_rate = payload.interest_rate
    rent = payload.rent

    HML_interest_in_cash = calc_HML_interest_in_cash(purchase_price, down_payment_precent, rehab_cost, Months_until_refi, HML_interest_rate, use_HM_for_rehab)
    HML_points_in_cash = payload.HML_points/100.0 * get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    
    operating_expenses = calc_montly_operating_expenses(payload)
    cash_out_from_deal = calc_cash_out_from_deal(arv, ltv, down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, use_HM_for_rehab)
    mortgage_payment = calc_mortgage_payment(arv, ltv, interest_rate, loan_term_years)

    net_operating_income = rent - operating_expenses
    cash_flow = net_operating_income - mortgage_payment
    dscr = net_operating_income / mortgage_payment
    cash_on_cash = calc_cash_on_cash(cash_out_from_deal, cash_flow)
    equity = arv * (1-ltv)
    net_profit = equity + cash_out_from_deal
    roi = calc_roi(cash_out_from_deal, cash_flow, equity)
    total_cash_needed_for_deal = get_total_cash_needed_for_deal(down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, use_HM_for_rehab)
    
    return analyzeDealRes(
        cash_flow=cash_flow,
        dscr=dscr,
        cash_out=cash_out_from_deal,
        cash_on_cash=cash_on_cash,
        roi=roi,
        equity=equity,
        net_profit=net_profit,
        total_cash_needed_for_deal = total_cash_needed_for_deal,
        messages=None,
    )
