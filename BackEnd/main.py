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
from ReqRes.boughtDeal.boughtDealReq import (
    BoughtBrrrDealCreate, BoughtBrrrDealRes,
    BoughtFlipDealCreate, BoughtFlipDealRes
)

from crud_active_deal import (
    add_brrr_deal, add_flip_deal,
    get_all_brrr_deals, get_all_flip_deals,
    update_brrr_deal, update_flip_deal,
    delete_brrr_deal, delete_flip_deal,
    duplicate_brrr_deal, duplicate_flip_deal
)
from crud_bought_deal import (
    add_bought_brrr_deal, add_bought_flip_deal,
    get_all_bought_brrr_deals, get_all_bought_flip_deals,
    update_bought_brrr_deal, update_bought_flip_deal,
    delete_bought_brrr_deal, delete_bought_flip_deal,
    create_bought_from_active_brrr, create_bought_from_active_flip
)
from crud_liquidity import (
    get_all_transactions, get_transaction, add_transaction,
    update_transaction, delete_transaction,
    get_settings, upsert_settings,
)
from crud_pipeline_template import (
    ensure_defaults as ensure_pipeline_defaults,
    list_templates as list_pipeline_templates,
    upsert_template as upsert_pipeline_template,
    get_stats as get_pipeline_stats,
)
from ReqRes.liquidity.liquidityReq import (
    LiquidityTransactionCreate, LiquidityTransactionUpdate, LiquidityTransactionRes,
    LiquiditySettingsUpdate, LiquiditySettingsRes,
)
from ReqRes.pipelineTemplate import (
    PipelineTemplateUpsert,
    PipelineTemplateRes,
    PipelineTemplateStatsRes,
)
from ReqRes.email.sendOfferReq import SendOfferReq
from ReqRes.email.sendOfferRes import SendOfferRes
from db import Base, engine, SessionLocal, get_db
from models import (
    BrrrActiveDeal, FlipActiveDeal, BoughtBrrrDeal, BoughtFlipDeal,
    LiquidityTransaction, PipelineTemplate,
    DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT,
    DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT,
)
from sqlalchemy import text, inspect as sa_inspect
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

Base.metadata.create_all(bind=engine)

def _run_migrations():
    inspector = sa_inspect(engine)
    table_names = inspector.get_table_names()

    if "active_deals" in table_names:
        columns = [col["name"] for col in inspector.get_columns("active_deals")]
        if "refi_points" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE active_deals ADD COLUMN refi_points NUMERIC(5,2) DEFAULT 1.5"
                ))
                conn.execute(text(
                    "UPDATE active_deals SET refi_points = 1.5 WHERE refi_points IS NULL"
                ))

    if "liquidity_transactions" in table_names:
        columns = [col["name"] for col in inspector.get_columns("liquidity_transactions")]

        # Rename legacy columns to their current model names
        renames = {"date": "effective_date", "amount": "amount_k"}
        for old_name, new_name in renames.items():
            if old_name in columns and new_name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE liquidity_transactions RENAME COLUMN {old_name} TO {new_name}"
                    ))
                columns = [new_name if c == old_name else c for c in columns]
            elif old_name in columns and new_name in columns:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"UPDATE liquidity_transactions SET {new_name} = {old_name} WHERE {new_name} IS NULL"
                    ))
                    conn.execute(text(
                        f"ALTER TABLE liquidity_transactions DROP COLUMN {old_name}"
                    ))
                columns = [c for c in columns if c != old_name]

        # Drop any leftover columns not in the current model
        expected = {"id", "effective_date", "description", "amount_k", "created_at", "updated_at"}
        for col in columns:
            if col not in expected:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE liquidity_transactions DROP COLUMN {col}"
                    ))

    if "liquidity_settings" in table_names:
        columns = [col["name"] for col in inspector.get_columns("liquidity_settings")]
        if "opening_balance_date" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE liquidity_settings ADD COLUMN opening_balance_date DATE DEFAULT CURRENT_DATE NOT NULL"
                ))
        if "reserve_k" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE liquidity_settings ADD COLUMN reserve_k NUMERIC(14,4) DEFAULT 5 NOT NULL"
                ))
        if "opening_balance_k" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE liquidity_settings ADD COLUMN opening_balance_k NUMERIC(14,4) DEFAULT 0 NOT NULL"
                ))

    # Migrate `bought_stage` from INTEGER -> TEXT, mapping legacy numeric IDs
    # to the stable slug IDs used by the default pipeline template. Idempotent.
    _migrate_bought_stage_to_string(inspector, "bought_brrrr_deals", DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT)
    _migrate_bought_stage_to_string(inspector, "bought_flip_deals", DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT)


def _migrate_bought_stage_to_string(
    inspector,
    table_name: str,
    slug_by_int: dict[int, str],
) -> None:
    if table_name not in inspector.get_table_names():
        return
    cols = {c["name"]: c for c in inspector.get_columns(table_name)}
    col = cols.get("bought_stage")
    if col is None:
        return

    col_type = str(col.get("type") or "").upper()
    # Already text-like? Nothing to do.
    if any(token in col_type for token in ("CHAR", "TEXT", "STRING", "VARCHAR")):
        return

    default_slug = slug_by_int.get(1, "purchase")
    with engine.begin() as conn:
        # 1) Add a temp text column with a safe default.
        conn.execute(text(
            f"ALTER TABLE {table_name} ADD COLUMN bought_stage_new TEXT"
        ))
        # 2) Translate each legacy int to its canonical slug; anything unknown
        #    clamps to the first default stage so the board never breaks.
        for legacy_int, slug in slug_by_int.items():
            conn.execute(
                text(
                    f"UPDATE {table_name} SET bought_stage_new = :slug "
                    f"WHERE bought_stage = :legacy_int"
                ),
                {"slug": slug, "legacy_int": legacy_int},
            )
        conn.execute(
            text(
                f"UPDATE {table_name} SET bought_stage_new = :default_slug "
                f"WHERE bought_stage_new IS NULL"
            ),
            {"default_slug": default_slug},
        )
        # 3) Drop the old int column and rename the new one into place.
        conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN bought_stage"))
        conn.execute(text(
            f"ALTER TABLE {table_name} RENAME COLUMN bought_stage_new TO bought_stage"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} ALTER COLUMN bought_stage SET NOT NULL"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} ALTER COLUMN bought_stage SET DEFAULT 'purchase'"
        ))


_run_migrations()

# Seed pipeline template rows (BRRRR + FLIP) on first boot. Safe to call often.
with SessionLocal() as _seed_db:
    ensure_pipeline_defaults(_seed_db)


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
    if payload.refi_points < 0 or payload.refi_points > 100:
        validation_errors.append("Refi points must be between 0% and 100%.")
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

def calc_cash_out_from_deal(arv, ltv, down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash, use_HM_for_rehab, holding_costs_until_refi):
    loan_amount = arv * ltv
    HML_payoff = get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    down_payment_in_cash = (down_payment_precent/Decimal("100")) * purchase_price
    total_cash_invested = down_payment_in_cash + closing_costs_buy + HML_points_in_cash + rehab_cost * (1-int(use_HM_for_rehab)) + HML_interest_in_cash + holding_costs_until_refi
    return loan_amount - HML_payoff - closing_cost_refi - refi_points_in_cash - total_cash_invested


def calc_cash_out_routi(arv, ltv, down_payment_precent, purchase_price, rehab_cost, closing_cost_refi, refi_points_in_cash, use_HM_for_rehab):
    loan_amount = arv * ltv
    HML_payoff = get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    return loan_amount - HML_payoff - closing_cost_refi - refi_points_in_cash



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
    
    # 1. Direct Rehab Cash (if not funded) + Float Buffer (for draws)
    # Even if HML pays, we need 10% on hand to start work/pay deposits
    rehab_float_buffer = Decimal("0.1") * rehab_cost
    rehab_out_of_pocket = rehab_cost if not use_HM_for_rehab else Decimal("0")
    total_rehab_cash_needed = rehab_out_of_pocket + rehab_float_buffer

    # 2. Time Contingency (The "Safety Multiplier")
    # Doubling these accounts for delays in permits, rehab, or tenant placement
    total_holding_cash = holding_cost_until_refi * 1.5
    total_interest_cash = HML_interest_in_cash * 1.5
    
    # 3. Closing Buffer
    total_closing_buy = closing_costs_buy * Decimal("1.1")
    
    return (
        down_payment_in_cash + 
        total_holding_cash + 
        total_closing_buy + 
        HML_points_in_cash + 
        total_rehab_cash_needed + 
        total_interest_cash
    )

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
    refi_points_in_cash = (payload.refi_points / Decimal("100")) * arv * ltv
    
    cash_out_from_deal = calc_cash_out_from_deal(arv, ltv, payload.down_payment, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash, payload.use_HM_for_rehab, holding_cost_until_refi)
    cash_out_routi = calc_cash_out_routi(arv, ltv, payload.down_payment, purchase_price, rehab_cost, closing_cost_refi, refi_points_in_cash, payload.use_HM_for_rehab)
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
        cash_flow=cash_flow, dscr=dscr, cash_out=cash_out_from_deal, cash_out_routi=cash_out_routi, cash_on_cash=cash_on_cash,
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
    
    total_cash_needed = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, total_operating, closing_costs_buy, hml_points_cash, rehab_cost, total_hml_interest, payload.use_HM_for_rehab)
    rehab_cash = rehab_cost if not payload.use_HM_for_rehab else Decimal("0")
    
    total_cash_invested = down_payment_cash + closing_costs_buy + hml_points_cash + total_holding_costs + rehab_cash
    
    # Cost basis for profit calc
    total_cost_basis = purchase_price + rehab_cost + closing_costs_buy + total_holding_costs + selling_costs + hml_points_cash
    
    gross_profit = sale_price - total_cost_basis
    
    cap_gains = Decimal("0")
    if gross_profit > 0:
        cap_gains = gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0"))
        
    net_profit = gross_profit - cap_gains
    
    roi = (net_profit / total_cash_invested) * Decimal("100.0") if total_cash_invested > 0 else Decimal("0")
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
def update_deal(deal_id: str, deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate], db: Session = Depends(get_db)):
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
def delete_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
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
def duplicate_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if deal_type == "BRRRR":
        new_deal = duplicate_brrr_deal(db, deal_id)
        if new_deal: return create_deal_response(new_deal)
    elif deal_type == "FLIP":
        new_deal = duplicate_flip_deal(db, deal_id)
        if new_deal: return create_deal_response(new_deal)
        
    raise HTTPException(status_code=404, detail="Deal not found")


# --- Bought Deals ---

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

@app.get("/bought-deals", response_model=List[Union[BoughtBrrrDealRes, BoughtFlipDealRes]])
def get_bought_deals(db: Session = Depends(get_db)):
    brrr_deals = get_all_bought_brrr_deals(db)
    flip_deals = get_all_bought_flip_deals(db)

    all_deals = []
    all_deals.extend([create_bought_deal_response(d) for d in brrr_deals])
    all_deals.extend([create_bought_deal_response(d) for d in flip_deals])

    all_deals.sort(key=lambda x: x.created_at, reverse=True)
    return all_deals

@app.post("/bought-deals", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def add_bought_deal(
    deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate] = Body(..., discriminator='deal_type'),
    db: Session = Depends(get_db)
):
    if deal.deal_type == "BRRRR":
        created = add_bought_brrr_deal(db, deal)
        return create_bought_deal_response(created)
    elif deal.deal_type == "FLIP":
        created = add_bought_flip_deal(db, deal)
        return create_bought_deal_response(created)
    raise HTTPException(status_code=400, detail="Invalid deal type")

@app.put("/bought-deals/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def update_bought_deal(deal_id: str, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate], db: Session = Depends(get_db)):
    if deal.deal_type == "BRRRR":
        updated = update_bought_brrr_deal(db, deal_id, deal)
        if updated: return create_bought_deal_response(updated)
    elif deal.deal_type == "FLIP":
        updated = update_bought_flip_deal(db, deal_id, deal)
        if updated: return create_bought_deal_response(updated)

    raise HTTPException(status_code=404, detail="Bought deal not found")

@app.delete("/bought-deals/{deal_id}")
def delete_bought_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if deal_type == "BRRRR":
        if delete_bought_brrr_deal(db, deal_id): return {"message": "Bought deal deleted"}
    elif deal_type == "FLIP":
        if delete_bought_flip_deal(db, deal_id): return {"message": "Bought deal deleted"}

    raise HTTPException(status_code=404, detail="Bought deal not found")

@app.post("/bought-deals/from-active/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def move_to_bought(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if deal_type == "BRRRR":
        source = db.query(BrrrActiveDeal).filter(BrrrActiveDeal.id == deal_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source BRRRR deal not found")
        new_deal = create_bought_from_active_brrr(db, source)
        return create_bought_deal_response(new_deal)
    elif deal_type == "FLIP":
        source = db.query(FlipActiveDeal).filter(FlipActiveDeal.id == deal_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source FLIP deal not found")
        new_deal = create_bought_from_active_flip(db, source)
        return create_bought_deal_response(new_deal)

    raise HTTPException(status_code=400, detail="Invalid deal type")


# --- Email Logic ---

def send_offer_email(details: SendOfferReq):
    logger.info(f"Starting email send process for property: {details.property_address}")
    logger.info(f"Recipient: {details.agent_email} (Agent: {details.agent_name})")
    
    sender_email = "BigWhalesLLC@gmail.com"
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_password:
        logger.error("EMAIL_PASSWORD environment variable is not set")
        return False, "Email password not configured"
    
    # Strip any whitespace (common issue when copying/pasting)
    sender_password = sender_password.strip()
    
    if len(sender_password) != 16:
        logger.warning(f"Email password length is {len(sender_password)} (expected 16 for Gmail App Password)")
    
    logger.info(f"Email password found (length: {len(sender_password)})")
    logger.info(f"Email password starts with: {sender_password[:2]}... (masked for security)")
    
    subject = f"Cash Offer for {details.property_address}"
    logger.info(f"Email subject: {subject}")
    
    body = f"""
<html>
  <head>
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #2c3e50;
        line-height: 1.7;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        margin: 0;
        padding: 40px 20px;
      }}
      .container {{
        max-width: 650px;
        margin: 0 auto;
        background-color: #ffffff;
        padding: 45px;
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        border-top: 6px solid #3498db;
      }}
      .greeting {{
        font-size: 18px;
        color: #2c3e50;
        margin-bottom: 20px;
        font-weight: 500;
      }}
      .intro {{
        font-size: 16px;
        color: #34495e;
        margin-bottom: 25px;
      }}
      .highlight {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px 30px;
        border-radius: 10px;
        margin: 30px 0;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
      }}
      .highlight p {{
        margin: 12px 0;
        font-weight: 600;
        font-size: 16px;
        color: #ffffff;
        line-height: 1.8;
      }}
      .highlight p:first-child {{
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 18px;
        padding-bottom: 15px;
        border-bottom: 2px solid rgba(255,255,255,0.3);
      }}
      .highlight a {{
        color: #ffffff;
        text-decoration: underline;
        font-weight: 600;
      }}
      .cta {{
        font-size: 17px;
        color: #2c3e50;
        font-weight: 600;
        margin: 30px 0;
        text-align: center;
        padding: 15px;
        background-color: #ecf0f1;
        border-radius: 8px;
      }}
      .footer {{
        margin-top: 45px;
        padding: 35px;
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      }}
      .footer p {{
        margin: 8px 0;
        font-size: 20px;
        color: #ffffff;
        font-weight: 600;
      }}
      .footer-name {{
        font-size: 24px !important;
        font-weight: 700 !important;
        margin-bottom: 15px !important;
        letter-spacing: 0.5px;
      }}
      .footer-contact {{
        font-size: 18px !important;
        font-weight: 500 !important;
        margin: 10px 0 !important;
      }}
      .footer a {{
        color: #3498db;
        text-decoration: none;
        font-weight: 600;
        font-size: 18px;
      }}
      .footer a:hover {{
        color: #5dade2;
        text-decoration: underline;
      }}
      a {{
        color: #3498db;
        text-decoration: none;
        font-weight: 600;
      }}
      a:hover {{
        color: #2980b9;
        text-decoration: underline;
      }}
      strong {{
        color: #2c3e50;
        font-weight: 700;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <p class="greeting">Hi {details.agent_name},</p>
      <p class="intro">I’m writing to you regarding the property at <strong>{details.property_address}</strong></p>
      <p class="intro">We are local investors purchasing under our entity, Big Whales AY LLC. (<a href="https://drive.google.com/file/d/1HxskELeQFfljFngV5OFvjuhDeUbQ1Dyx/view">LLC Formation</a>)</p>
      
      <p class="intro">I have structured an offer to eliminate risks for the seller. I am offering a clean, fast closing:</p>
      
      <div class="highlight">
        <p>Purchase Price: ${details.purchase_price:,.2f}</p>
        <p>Terms: 100% - Hard Money (No Financing Contingency) (<a href="https://drive.google.com/file/d/1uP2FbFpFc5SVHWBdVcBCoAfhBijTzyBP/view">PreApproval</a>)</p>
        <p>Inspection: {details.inspection_period_days}-Day inspection period - We are purchasing "As-Is" and will not ask for repairs.</p>
        <p>Closing: 14 Days (or sooner if title is ready)</p>
        <p>Earnest Money: $5,000 can be wired as soon as today</p>
        <p>Other Contingencies: None</p>
      </div>

      <p class="cta">We are ready to sign and get this moving today.</p>
      
      <div class="footer">
        <p class="footer-name">Yarden Kelly - Big Whales AY LLC</p>
        <p class="footer-contact">(786)-600-7210</p>
        <p class="footer-contact"><a href="mailto:BigWhalesLLC@gmail.com">BigWhalesLLC@gmail.com</a></p>
      </div>
    </div>
  </body>
</html>
    """

    logger.info("Creating email message")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = details.agent_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    logger.info("Email message created successfully")

    try:
        logger.info("Connecting to SMTP server (smtp.gmail.com:465)")
        # Using Gmail's SSL port 465
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        logger.info("SMTP connection established")
        
        logger.info("Attempting to login to SMTP server")
        server.login(sender_email, sender_password)
        logger.info("SMTP login successful")
        
        logger.info(f"Sending email to {details.agent_email}")
        server.send_message(msg)
        logger.info("Email sent successfully")
        
        server.quit()
        logger.info("SMTP connection closed")
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication Error: {e}")
        logger.error(f"Error code: {e.smtp_code}, Error message: {e.smtp_error}")
        return False, f"Authentication failed: {str(e)}"
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {e}")
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error sending email: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, f"Error sending email: {str(e)}"

@app.post("/send-offer", response_model=SendOfferRes)
def send_offer_route(payload: SendOfferReq):
    logger.info(f"Received send-offer request: property={payload.property_address}, agent={payload.agent_name}, email={payload.agent_email}")
    try:
        success, message = send_offer_email(payload)
        if not success:
            logger.error(f"Email send failed: {message}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {message}")
        logger.info("Email send completed successfully")
        return SendOfferRes(message=message, success=success)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_offer_route: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Liquidity Timeline ---

def _txn_to_res(txn: LiquidityTransaction) -> LiquidityTransactionRes:
    return LiquidityTransactionRes(
        id=str(txn.id),
        effective_date=txn.effective_date,
        description=txn.description,
        amount_k=float(txn.amount_k),
        created_at=txn.created_at.isoformat() if txn.created_at else None,
        updated_at=txn.updated_at.isoformat() if txn.updated_at else None,
    )

@app.get("/liquidity/transactions", response_model=List[LiquidityTransactionRes])
def list_liquidity_transactions(db: Session = Depends(get_db)):
    return [_txn_to_res(t) for t in get_all_transactions(db)]

@app.post("/liquidity/transactions", response_model=LiquidityTransactionRes, status_code=201)
def create_liquidity_transaction(data: LiquidityTransactionCreate, db: Session = Depends(get_db)):
    txn = add_transaction(db, data)
    return _txn_to_res(txn)

@app.put("/liquidity/transactions/{txn_id}", response_model=LiquidityTransactionRes)
def update_liquidity_transaction(txn_id: str, data: LiquidityTransactionUpdate, db: Session = Depends(get_db)):
    txn = update_transaction(db, txn_id, data)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _txn_to_res(txn)

@app.delete("/liquidity/transactions/{txn_id}")
def delete_liquidity_transaction(txn_id: str, db: Session = Depends(get_db)):
    if not delete_transaction(db, txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted"}

@app.get("/liquidity/settings", response_model=LiquiditySettingsRes)
def get_liquidity_settings(db: Session = Depends(get_db)):
    settings = get_settings(db)
    if not settings:
        from datetime import date as date_type
        default_data = LiquiditySettingsUpdate(
            opening_balance_k=0,
            opening_balance_date=date_type.today(),
            reserve_k=5,
        )
        settings = upsert_settings(db, default_data)
    return LiquiditySettingsRes(
        opening_balance_k=float(settings.opening_balance_k),
        opening_balance_date=settings.opening_balance_date,
        reserve_k=float(settings.reserve_k),
        updated_at=settings.updated_at.isoformat() if settings.updated_at else None,
    )

@app.put("/liquidity/settings", response_model=LiquiditySettingsRes)
def update_liquidity_settings(data: LiquiditySettingsUpdate, db: Session = Depends(get_db)):
    settings = upsert_settings(db, data)
    return LiquiditySettingsRes(
        opening_balance_k=float(settings.opening_balance_k),
        opening_balance_date=settings.opening_balance_date,
        reserve_k=float(settings.reserve_k),
        updated_at=settings.updated_at.isoformat() if settings.updated_at else None,
    )


# --- Pipeline Templates (bought-deal stages/substages) ---

_VALID_DEAL_TYPES = {"BRRRR", "FLIP"}


def _require_valid_deal_type(deal_type: str) -> str:
    if deal_type not in _VALID_DEAL_TYPES:
        raise HTTPException(status_code=400, detail="deal_type must be 'BRRRR' or 'FLIP'")
    return deal_type


@app.get("/pipeline-templates", response_model=List[PipelineTemplateRes])
def list_pipeline_templates_route(db: Session = Depends(get_db)):
    return list_pipeline_templates(db)


@app.put("/pipeline-templates/{deal_type}", response_model=PipelineTemplateRes)
def update_pipeline_template_route(
    deal_type: str,
    payload: PipelineTemplateUpsert,
    db: Session = Depends(get_db),
):
    _require_valid_deal_type(deal_type)
    return upsert_pipeline_template(db, deal_type, payload)  # type: ignore[arg-type]


@app.get("/pipeline-templates/{deal_type}/stats", response_model=PipelineTemplateStatsRes)
def pipeline_template_stats_route(deal_type: str, db: Session = Depends(get_db)):
    _require_valid_deal_type(deal_type)
    return get_pipeline_stats(db, deal_type)  # type: ignore[arg-type]


@app.get("/helloworld")
def helloworld() -> dict:
    return {"message": "Hello, World!"}

