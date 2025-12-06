from typing import Union, List
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from ReqRes.analyzeBRRR.analyzeBRRRReq import analyzeBRRRReq
from ReqRes.analyzeBRRR.analyzeBRRRRes import analyzeBRRRRes
from ReqRes.analyzeFlip.analyzeFlipReq import analyzeFlipReq
from ReqRes.analyzeFlip.analyzeFlipRes import analyzeFlipRes
from ReqRes.activeDeal.activeDealReq import (
    BrrrActiveDealCreate, BrrrActiveDealRes,
    FlipActiveDealCreate, FlipActiveDealRes
)

from crud_active_deal import (
    add_brrr_deal, add_flip_deal,
    get_all_brrr_deals, get_all_flip_deals,
    update_brrr_deal, update_flip_deal,
    delete_brrr_deal, delete_flip_deal,
    duplicate_brrr_deal, duplicate_flip_deal
)
from db import Base, engine, get_db
from models import BrrrActiveDeal, FlipActiveDeal

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://bigwhalescalculatorfront.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def thousands_to_dollars(value: Decimal) -> Decimal:
    return value * Decimal("1000.0")

def get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab):
    return purchase_price * (1 - down_payment_precent / Decimal("100.0")) + rehab_cost * int(use_HM_for_rehab)

# --- BRRRR Logic ---

def validate_brrr_inputs(payload: analyzeBRRRReq):
    validation_errors = []
    
    # 1. Base Value Checks (Must be positive)
    if payload.arv_in_thousands <= 0:
        validation_errors.append("ARV (in thousands) must be greater than 0.")
    if payload.purchase_price_in_thousands <= 0:
        validation_errors.append("Purchase price (in thousands) must be greater than 0.")
    if payload.rent <= 0:
        validation_errors.append("Rent must be greater than 0.")

    # 2. Non-Negative Checks
    if payload.rehab_cost_in_thousands < 0:
        validation_errors.append("Rehab cost cannot be negative.")
    if payload.rehab_contingency_percent < 0 or payload.rehab_contingency_percent > 100:
        validation_errors.append("Rehab contingency percentage must be between 0% and 100%.")
    if payload.closing_costs_buy_in_thousands < 0:
        validation_errors.append("Closing costs (buy) cannot be negative.")
    if payload.closing_cost_refi_in_thousands < 0:
        validation_errors.append("Refi closing costs cannot be negative.")
    if payload.annual_property_taxes < 0:
        validation_errors.append("Annual property taxes cannot be negative.")
    if payload.annual_insurance < 0:
        validation_errors.append("Annual insurance cannot be negative.")
    if payload.montly_hoa < 0:
        validation_errors.append("HOA dues cannot be negative.")

    # 3. Lending Terms (Percentage Ranges 0-100)
    if payload.down_payment < 0 or payload.down_payment > 100:
        validation_errors.append("Down payment percentage must be between 0% and 100%.")
    if payload.ltv_as_precent <= 0 or payload.ltv_as_precent > 100:
        validation_errors.append("LTV must be between 0% and 100%.")
    if payload.HML_points < 0 or payload.HML_points > 100:
        validation_errors.append("HML points must be between 0% and 100%.")
    if payload.HML_interest_rate < 0 or payload.HML_interest_rate > 100:
        validation_errors.append("HML interest rate must be between 0% and 100%.")
    
    # 4. Timeframes
    if payload.Months_until_refi <= 0:
        validation_errors.append("Months until refi must be a positive number.")
    if payload.loan_term_years <= 0:
        validation_errors.append("Loan term must be at least 1 year.")

    # 5. Long-term Financing
    if payload.interest_rate < 0 or payload.interest_rate > 100:
        validation_errors.append("Interest rate must be between 0% and 100%.")

    # 6. Operating Expenses (Percentage Ranges)
    if payload.vacancy_percent < 0 or payload.vacancy_percent > 100:
        validation_errors.append("Vacancy percentage must be between 0% and 100%.")
    if payload.property_managment_fee_precentages_from_rent < 0 or payload.property_managment_fee_precentages_from_rent > 100:
        validation_errors.append("Property management percentage must be between 0% and 100%.")
    if payload.maintenance_percent < 0 or payload.maintenance_percent > 100:
        validation_errors.append("Maintenance percentage must be between 0% and 100%.")
    if payload.capex_percent_of_rent < 0 or payload.capex_percent_of_rent > 100:
        validation_errors.append("CapEx percentage must be between 0% and 100%.")

    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))

def calc_montly_operating_expenses(payload):
    property_management_fee = payload.rent * (payload.property_managment_fee_precentages_from_rent / Decimal("100.0"))
    maintenance = payload.rent * (payload.maintenance_percent / Decimal("100.0"))
    capex = payload.rent * (payload.capex_percent_of_rent / Decimal("100.0"))
    vacancy = payload.rent * (payload.vacancy_percent / Decimal("100.0"))
    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    hoa = payload.montly_hoa
    return monthly_taxes + monthly_insurance + property_management_fee + hoa + maintenance + capex + vacancy

def calcDSCR(rent, taxes, insurance, hoa, mortgage_payment):
    monthly_taxes = taxes / Decimal("12.0")
    monthly_insurance = insurance / Decimal("12.0")
    pitia = mortgage_payment + monthly_taxes + monthly_insurance + hoa
    if pitia == 0: return Decimal("0")
    return rent / pitia

def calc_cash_out_from_deal(arv, ltv, down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, use_HM_for_rehab, holding_costs_until_refi):
    loan_amount = arv * ltv
    HML_payoff = get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    down_payment_in_cash = (down_payment_precent/Decimal("100")) * purchase_price
    total_cash_invested = down_payment_in_cash + closing_costs_buy + HML_points_in_cash + rehab_cost * (1-int(use_HM_for_rehab)) + HML_interest_in_cash + holding_costs_until_refi
    return loan_amount - HML_payoff - closing_cost_refi - total_cash_invested

def calc_mortgage_payment(arv, ltv, interest_rate, loan_term_years):
    loan_amount = arv * ltv
    monthly_interest_rate = (interest_rate / Decimal("100.0")) / Decimal("12.0")
    total_payments = loan_term_years * 12
    factor = (1 + monthly_interest_rate) ** total_payments
    denominator = factor - 1
    if denominator == 0:
        raise HTTPException(status_code=400, detail="Unable to calculate mortgage payment.")
    return loan_amount * monthly_interest_rate * factor / denominator

def calc_cash_on_cash(cash_out_from_deal, cash_flow):
    if cash_out_from_deal >= 0: return Decimal("-1") 
    elif cash_flow <= 0: return Decimal("-2")
    else: return (cash_flow * 12 / abs(cash_out_from_deal)) * Decimal("100.0")
        
def calc_roi(cash_out_from_deal, cash_flow, net_profit):
    if cash_out_from_deal >= 0: return Decimal("-1")
    elif cash_flow <= 0: return Decimal("-2")
    else: return ((cash_flow * 12 + net_profit )/ abs(cash_out_from_deal)) * Decimal("100.0")
    
def calc_holding_costs(taxes, insurance, hoa, months):
    monthly_taxes = taxes / Decimal("12.0")
    monthly_insurance = insurance / Decimal("12.0")
    monthly_holding = monthly_taxes + monthly_insurance + hoa
    return monthly_holding * months

def calc_HML_interest_in_cash(purchase_price, down_payment_precent, rehab_cost, Months_until_refi, HML_interest_rate, use_HM_for_rehab):
    HML_montly_interest = HML_interest_rate / Decimal("12") / Decimal("100.0") * get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    return HML_montly_interest * Months_until_refi  

def get_total_cash_needed_for_deal(down_payment_precent, purchase_price, holding_cost_until_refi, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, use_HM_for_rehab):
    down_payment_in_cash = (down_payment_precent/Decimal("100")) * purchase_price
    return down_payment_in_cash + holding_cost_until_refi + closing_costs_buy + HML_points_in_cash + rehab_cost * (1-int(use_HM_for_rehab)) + HML_interest_in_cash

def calculate_brrr_results(payload) -> analyzeBRRRRes:
    arv = thousands_to_dollars(payload.arv_in_thousands)
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency
    
    HML_interest_in_cash = calc_HML_interest_in_cash(purchase_price, payload.down_payment, rehab_cost, payload.Months_until_refi, payload.HML_interest_rate, payload.use_HM_for_rehab)
    HML_points_in_cash = payload.HML_points/Decimal("100.0") * get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    holding_cost_until_refi = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.Months_until_refi)
    
    operating_expenses = calc_montly_operating_expenses(payload)
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    closing_cost_refi = thousands_to_dollars(payload.closing_cost_refi_in_thousands)
    ltv = payload.ltv_as_precent/Decimal("100")
    
    cash_out_from_deal = calc_cash_out_from_deal(arv, ltv, payload.down_payment, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, payload.use_HM_for_rehab, holding_cost_until_refi)
    mortgage_payment = calc_mortgage_payment(arv, ltv, payload.interest_rate, payload.loan_term_years)

    net_operating_income = payload.rent - operating_expenses
    cash_flow = net_operating_income - mortgage_payment
    dscr =  calcDSCR(payload.rent, payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, mortgage_payment)
    cash_on_cash = calc_cash_on_cash(cash_out_from_deal, cash_flow)
    equity = arv * (1-ltv)
    net_profit = equity + cash_out_from_deal
    roi = calc_roi(cash_out_from_deal, cash_flow, net_profit)
    total_cash_needed_for_deal = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, holding_cost_until_refi, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, payload.use_HM_for_rehab)
    
    return analyzeBRRRRes(
        cash_flow=cash_flow, dscr=dscr, cash_out=cash_out_from_deal, cash_on_cash=cash_on_cash,
        roi=roi, equity=equity, net_profit=net_profit, total_cash_needed_for_deal=total_cash_needed_for_deal, messages=None
    )


# --- Flip Logic ---

def validate_flip_inputs(payload: analyzeFlipReq):
    validation_errors = []
    
    if payload.sale_price_in_thousands <= 0:
        validation_errors.append("Sale price (ARV) must be greater than 0.")
    if payload.purchase_price_in_thousands <= 0:
        validation_errors.append("Purchase price must be greater than 0.")
    
    if payload.holding_time_months <= 0:
        validation_errors.append("Holding time must be greater than 0 months.")

    if payload.rehab_cost_in_thousands < 0:
        validation_errors.append("Rehab cost cannot be negative.")
    
    if payload.rehab_contingency_percent < 0 or payload.rehab_contingency_percent > 100:
        validation_errors.append("Rehab contingency percentage must be between 0% and 100%.")

    if payload.down_payment < 0 or payload.down_payment > 100:
        validation_errors.append("Down payment percentage must be between 0% and 100%.")
        
    if payload.HML_points < 0 or payload.HML_points > 100:
        validation_errors.append("HML points must be between 0% and 100%.")
        
    if payload.buyer_agent_selling_fee < 0 or payload.buyer_agent_selling_fee > 100:
        validation_errors.append("Buyer agent fee must be between 0% and 100%.")
    if payload.seller_agent_selling_fee < 0 or payload.seller_agent_selling_fee > 100:
        validation_errors.append("Seller agent fee must be between 0% and 100%.")
    if payload.selling_closing_costs_in_thousands < 0:
        validation_errors.append("Selling closing cost cannot be negative.")

    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))

def calculate_flip_results(payload: analyzeFlipReq) -> analyzeFlipRes:
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency
    sale_price = thousands_to_dollars(payload.sale_price_in_thousands)
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    
    hml_amount = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    hml_points_cash = (payload.HML_points / Decimal("100.0")) * hml_amount
    
    monthly_interest = (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * hml_amount
    total_hml_interest = monthly_interest * payload.holding_time_months
    
    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    monthly_operating = monthly_taxes + monthly_insurance + payload.montly_hoa + payload.monthly_utilities
    total_operating = monthly_operating * payload.holding_time_months
    
    total_holding_costs = total_hml_interest + total_operating
    
    agent_fees_percent = payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee
    selling_costs = sale_price * (agent_fees_percent / Decimal("100.0")) + thousands_to_dollars(payload.selling_closing_costs_in_thousands)
    
    down_payment_cash = (payload.down_payment / Decimal("100.0")) * purchase_price
    rehab_cash = rehab_cost if not payload.use_HM_for_rehab else 10000
    
    total_cash_needed = down_payment_cash + closing_costs_buy + hml_points_cash + total_holding_costs + rehab_cash
    
    # Cost basis for profit calc
    total_cost_basis = purchase_price + rehab_cost + closing_costs_buy + total_holding_costs + selling_costs + hml_points_cash
    
    gross_profit = sale_price - total_cost_basis
    
    cap_gains = Decimal("0")
    if gross_profit > 0:
        cap_gains = gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0"))
        
    net_profit = gross_profit - cap_gains
    
    roi = (net_profit / total_cash_needed) * Decimal("100.0") if total_cash_needed > 0 else Decimal("0")
    years = payload.holding_time_months / Decimal("12.0")
    annualized_roi = (roi / years) if years > 0 else Decimal("0")
    
    return analyzeFlipRes(
        net_profit=net_profit, roi=roi, annualized_roi=annualized_roi,
        total_cash_needed=total_cash_needed, total_holding_costs=total_holding_costs,
        total_hml_interest=total_hml_interest, messages=[]
    )

# --- Endpoints ---

@app.post("/analyze/brrr", response_model=analyzeBRRRRes)
def analyze_brrr(payload: analyzeBRRRReq) -> analyzeBRRRRes:
    validate_brrr_inputs(payload)
    return calculate_brrr_results(payload)

@app.post("/analyze/flip", response_model=analyzeFlipRes)
def analyze_flip(payload: analyzeFlipReq) -> analyzeFlipRes:
    validate_flip_inputs(payload)
    return calculate_flip_results(payload)


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

@app.get("/active-deals", response_model=List[Union[BrrrActiveDealRes, FlipActiveDealRes]])
def get_active_deals(db: Session = Depends(get_db)):
    brrr_deals = get_all_brrr_deals(db)
    flip_deals = get_all_flip_deals(db)
    
    all_deals = []
    all_deals.extend([create_deal_response(d) for d in brrr_deals])
    all_deals.extend([create_deal_response(d) for d in flip_deals])
    
    # Sort by created_at desc
    all_deals.sort(key=lambda x: x.created_at, reverse=True)
    return all_deals


@app.post("/active-deals", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def add_active_deal(
    deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate] = Body(..., discriminator='deal_type'),
    db: Session = Depends(get_db)
):
    if deal.deal_type == "BRRRR":
        created = add_brrr_deal(db, deal)
        return create_deal_response(created)
    elif deal.deal_type == "FLIP":
        created = add_flip_deal(db, deal)
        return create_deal_response(created)
    raise HTTPException(status_code=400, detail="Invalid deal type")

@app.put("/active-deals/{deal_id}", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def update_deal(deal_id: int, deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate], db: Session = Depends(get_db)):
    # Note: IDs might clash if tables use separate auto-increment and we look up just by ID.
    # Ideally we need deal_type in query or unique IDs across tables (UUIDs).
    # Since we have separate tables with independent integer PKs, ID=1 can exist in both.
    # The frontend needs to pass ID AND Type or we need to try both.
    # Current API structure `/active-deals/{deal_id}` implies ID uniqueness or we check both.
    # If the user provides the payload with the type, we know which one to update.
    # But if ID=1 exists in both...
    # Assumption: The user selects a specific deal which has a type known to Frontend.
    # The backend receives the payload with `deal_type`.
    
    if deal.deal_type == "BRRRR":
        updated = update_brrr_deal(db, deal_id, deal)
        if updated: return create_deal_response(updated)
    elif deal.deal_type == "FLIP":
        updated = update_flip_deal(db, deal_id, deal)
        if updated: return create_deal_response(updated)
        
    raise HTTPException(status_code=404, detail="Deal not found")

@app.delete("/active-deals/{deal_id}")
def delete_deal(deal_id: int, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    # We need deal_type here to know which table to delete from.
    # Or we try both.
    # Let's try deleting from BRRRR first, if not found try Flip.
    # Risk: Deleting wrong deal if ID exists in both.
    # BETTER: Require type param. Defaults to BRRRR for backward compatibility?
    # Actually, let's try to pass it as query param.
    
    if deal_type == "BRRRR":
        if delete_brrr_deal(db, deal_id): return {"message": "Deal deleted"}
    elif deal_type == "FLIP":
        if delete_flip_deal(db, deal_id): return {"message": "Deal deleted"}
        
    # If not specified or failed, maybe try the other if strict mode is off?
    # Let's return 404.
    raise HTTPException(status_code=404, detail="Deal not found")

@app.post("/active-deals/{deal_id}/duplicate", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def duplicate_deal(deal_id: int, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if deal_type == "BRRRR":
        new_deal = duplicate_brrr_deal(db, deal_id)
        if new_deal: return create_deal_response(new_deal)
    elif deal_type == "FLIP":
        new_deal = duplicate_flip_deal(db, deal_id)
        if new_deal: return create_deal_response(new_deal)
        
    raise HTTPException(status_code=404, detail="Deal not found")

@app.get("/helloworld")
def helloworld() -> dict:
    return {"message": "Hello, World!"}
