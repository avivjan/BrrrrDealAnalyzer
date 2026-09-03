from typing import Union, List, Optional
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Body, File, Form, UploadFile, Query
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

from ReqRes.liquidity.liquidityReq import (
    LiquidityTransactionCreate, LiquidityTransactionUpdate, LiquidityTransactionRes,
    LiquidityRecurringTransactionCreate, LiquidityRecurringTransactionUpdate,
    LiquidityRecurringTransactionRes,
    LiquiditySettingsUpdate, LiquiditySettingsRes,
)
from ReqRes.pipelineTemplate import (
    PipelineTemplateUpsert,
    PipelineTemplateRes,
    PipelineTemplateStatsRes,
)
from ReqRes.email.sendOfferReq import SendOfferReq
from ReqRes.email.sendOfferRes import SendOfferRes
from db import engine, SessionLocal, get_db
from models import (
    LiquidityTransaction, LiquidityRecurringTransaction,
    LIQUIDITY_RECURRING_FREQUENCIES,
)
from ReqRes.reps.repsReq import (
    RepsLogCreate, RepsLogRes, RepsEntriesEnvelope,
    RepsPersonCreate, RepsPersonUpdate, RepsPersonRes,
    RepsPropertyOption, RepsPropertyCreate,
    RepsActivityCategoryRes, RepsActivityCategoryCreate,
    RepsUploadBatchRes,
)
import reps_service
from mercury_service import MercuryApiError, MercuryConfigError
import bootstrap
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

bootstrap.run(engine, SessionLocal)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://bigwhales.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---

from BL.analyze.analyzeBRRR.analyzeBRRR import analyze_brrr as analyze_brrr_bl
from BL.analyze.analyzeFlip.analyzeFlip import analyze_flip as analyze_flip_bl

@app.post("/analyze/brrr", response_model=analyzeBRRRRes)
def analyze_brrr(payload: analyzeBRRRReq) -> analyzeBRRRRes:
    return analyze_brrr_bl(payload)

@app.post("/analyze/flip", response_model=analyzeFlipRes)
def analyze_flip(payload: analyzeFlipReq) -> analyzeFlipRes:
    return analyze_flip_bl(payload)


# --- PDF Deal Report ---

from fastapi.responses import Response

from BL.reports.reportBrrrPdf.reportBrrrPdf import report_brrr_pdf as report_brrr_pdf_bl
from BL.reports.reportFlipPdf.reportFlipPdf import report_flip_pdf as report_flip_pdf_bl


def _safe_filename(address: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (address or "deal"))
    return cleaned.strip("_") or "deal"


def _disposition(value: str) -> str:
    """Normalize the optional `disposition` query param.
    `inline` (default) → preview in the browser; `attachment` → force download."""
    return "attachment" if (value or "").lower() == "attachment" else "inline"


@app.post("/reports/brrr-pdf")
def report_brrr_pdf(
    payload: analyzeBRRRReq,
    address: str = "Property",
    disposition: str = "inline",
) -> Response:
    pdf_bytes = report_brrr_pdf_bl(payload, address)
    filename = f"BigWhales_BRRRR_{_safe_filename(address)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{_disposition(disposition)}; filename="{filename}"'},
    )


@app.post("/reports/flip-pdf")
def report_flip_pdf(
    payload: analyzeFlipReq,
    address: str = "Property",
    disposition: str = "inline",
) -> Response:
    pdf_bytes = report_flip_pdf_bl(payload, address)
    filename = f"BigWhales_FLIP_{_safe_filename(address)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{_disposition(disposition)}; filename="{filename}"'},
    )


from BL.activeDeal.getActiveDeals.getActiveDeals import get_active_deals as get_active_deals_bl
from BL.activeDeal.addActiveDeal.addActiveDeal import add_active_deal as add_active_deal_bl
from BL.activeDeal.updateActiveDeal.updateActiveDeal import update_deal as update_deal_bl
from BL.activeDeal.deleteActiveDeal.deleteActiveDeal import delete_deal as delete_deal_bl
from BL.activeDeal.duplicateActiveDeal.duplicateActiveDeal import duplicate_deal as duplicate_deal_bl

@app.get("/active-deals", response_model=List[Union[BrrrActiveDealRes, FlipActiveDealRes]])
def get_active_deals(db: Session = Depends(get_db)):
    return get_active_deals_bl(db)


@app.post("/active-deals", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def add_active_deal(
    deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate] = Body(..., discriminator='deal_type'),
    db: Session = Depends(get_db)
):
    result = add_active_deal_bl(db, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=400, detail="Invalid deal type")

@app.put("/active-deals/{deal_id}", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def update_deal(deal_id: str, deal: Union[BrrrActiveDealCreate, FlipActiveDealCreate], db: Session = Depends(get_db)):
    result = update_deal_bl(db, deal_id, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Deal not found")

@app.delete("/active-deals/{deal_id}")
def delete_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if delete_deal_bl(db, deal_id, deal_type):
        return {"message": "Deal deleted"}
    raise HTTPException(status_code=404, detail="Deal not found")

@app.post("/active-deals/{deal_id}/duplicate", response_model=Union[BrrrActiveDealRes, FlipActiveDealRes])
def duplicate_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    result = duplicate_deal_bl(db, deal_id, deal_type)
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Deal not found")


# --- Bought Deals ---

from BL.boughtDeal.getBoughtDeals.getBoughtDeals import get_bought_deals as get_bought_deals_bl
from BL.boughtDeal.addBoughtDeal.addBoughtDeal import add_bought_deal as add_bought_deal_bl
from BL.boughtDeal.updateBoughtDeal.updateBoughtDeal import update_bought_deal as update_bought_deal_bl
from BL.boughtDeal.deleteBoughtDeal.deleteBoughtDeal import delete_bought_deal as delete_bought_deal_bl
from BL.boughtDeal.moveToBought.moveToBought import move_to_bought as move_to_bought_bl
from DAL.crud.active_deal import get_brrr_deal, get_flip_deal

@app.get("/bought-deals", response_model=List[Union[BoughtBrrrDealRes, BoughtFlipDealRes]])
def get_bought_deals(db: Session = Depends(get_db)):
    return get_bought_deals_bl(db)

@app.post("/bought-deals", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def add_bought_deal(
    deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate] = Body(..., discriminator='deal_type'),
    db: Session = Depends(get_db)
):
    result = add_bought_deal_bl(db, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=400, detail="Invalid deal type")

@app.put("/bought-deals/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def update_bought_deal(deal_id: str, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate], db: Session = Depends(get_db)):
    result = update_bought_deal_bl(db, deal_id, deal)
    if result is not None:
        return result
    raise HTTPException(status_code=404, detail="Bought deal not found")

@app.delete("/bought-deals/{deal_id}")
def delete_bought_deal(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if delete_bought_deal_bl(db, deal_id, deal_type):
        return {"message": "Bought deal deleted"}
    raise HTTPException(status_code=404, detail="Bought deal not found")

@app.post("/bought-deals/from-active/{deal_id}", response_model=Union[BoughtBrrrDealRes, BoughtFlipDealRes])
def move_to_bought(deal_id: str, deal_type: str = "BRRRR", db: Session = Depends(get_db)):
    if deal_type == "BRRRR":
        source = get_brrr_deal(db, deal_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source BRRRR deal not found")
        return move_to_bought_bl(db, source, "BRRRR")
    elif deal_type == "FLIP":
        source = get_flip_deal(db, deal_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source FLIP deal not found")
        return move_to_bought_bl(db, source, "FLIP")

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

from BL.liquidity.listTransactions.listTransactions import list_transactions as list_transactions_bl
from BL.liquidity.createTransaction.createTransaction import create_transaction as create_transaction_bl
from BL.liquidity.updateTransaction.updateTransaction import update_transaction as update_transaction_bl
from BL.liquidity.deleteTransaction.deleteTransaction import delete_transaction as delete_transaction_bl

@app.get("/liquidity/transactions", response_model=List[LiquidityTransactionRes])
def list_liquidity_transactions(db: Session = Depends(get_db)):
    return list_transactions_bl(db)

@app.post("/liquidity/transactions", response_model=LiquidityTransactionRes, status_code=201)
def create_liquidity_transaction(data: LiquidityTransactionCreate, db: Session = Depends(get_db)):
    return create_transaction_bl(db, data)

@app.put("/liquidity/transactions/{txn_id}", response_model=LiquidityTransactionRes)
def update_liquidity_transaction(txn_id: str, data: LiquidityTransactionUpdate, db: Session = Depends(get_db)):
    result = update_transaction_bl(db, txn_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result

@app.delete("/liquidity/transactions/{txn_id}")
def delete_liquidity_transaction(txn_id: str, db: Session = Depends(get_db)):
    if not delete_transaction_bl(db, txn_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted"}


# --- Recurring transactions (e.g. monthly HM interest, weekly rent) ---
# Stored as rules; the frontend expands each rule into virtual events on
# the timeline. Editing the rule retroactively fixes every projected event.

from BL.liquidity.listRecurring.listRecurring import list_recurring as list_recurring_bl
from BL.liquidity.createRecurring.createRecurring import create_recurring as create_recurring_bl
from BL.liquidity.updateRecurring.updateRecurring import update_recurring as update_recurring_bl
from BL.liquidity.deleteRecurring.deleteRecurring import delete_recurring as delete_recurring_bl

@app.get("/liquidity/recurring", response_model=List[LiquidityRecurringTransactionRes])
def list_liquidity_recurring(db: Session = Depends(get_db)):
    return list_recurring_bl(db)


@app.post(
    "/liquidity/recurring",
    response_model=LiquidityRecurringTransactionRes,
    status_code=201,
)
def create_liquidity_recurring(
    data: LiquidityRecurringTransactionCreate, db: Session = Depends(get_db)
):
    try:
        return create_recurring_bl(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put(
    "/liquidity/recurring/{rule_id}", response_model=LiquidityRecurringTransactionRes
)
def update_liquidity_recurring(
    rule_id: str,
    data: LiquidityRecurringTransactionUpdate,
    db: Session = Depends(get_db),
):
    try:
        result = update_recurring_bl(db, rule_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return result


@app.delete("/liquidity/recurring/{rule_id}")
def delete_liquidity_recurring(rule_id: str, db: Session = Depends(get_db)):
    if not delete_recurring_bl(db, rule_id):
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return {"message": "Recurring rule deleted"}


from BL.liquidity.getSettings.getSettings import get_settings as get_settings_bl
from BL.liquidity.updateSettings.updateSettings import update_settings as update_settings_bl

@app.get("/liquidity/settings", response_model=LiquiditySettingsRes)
def get_liquidity_settings(db: Session = Depends(get_db)):
    return get_settings_bl(db)

@app.put("/liquidity/settings", response_model=LiquiditySettingsRes)
def update_liquidity_settings(data: LiquiditySettingsUpdate, db: Session = Depends(get_db)):
    return update_settings_bl(db, data)


from BL.liquidity.mercuryBalance.mercuryBalance import get_mercury_balance as get_mercury_balance_bl

@app.get("/liquidity/mercury-balance")
def get_mercury_balance():
    """
    Fetch the live sum of all active Mercury account balances, in $k.

    The frontend uses this to re-anchor the liquidity timeline's opening
    balance to today on page load.
    """
    try:
        return get_mercury_balance_bl()
    except MercuryConfigError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except MercuryApiError as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- Pipeline Templates (bought-deal stages/substages) ---

from BL.pipelineTemplate.listTemplates.listTemplates import list_templates as list_templates_bl
from BL.pipelineTemplate.updateTemplate.updateTemplate import update_template as update_template_bl
from BL.pipelineTemplate.templateStats.templateStats import template_stats as template_stats_bl

_VALID_DEAL_TYPES = {"BRRRR", "FLIP"}


def _require_valid_deal_type(deal_type: str) -> str:
    if deal_type not in _VALID_DEAL_TYPES:
        raise HTTPException(status_code=400, detail="deal_type must be 'BRRRR' or 'FLIP'")
    return deal_type


@app.get("/pipeline-templates", response_model=List[PipelineTemplateRes])
def list_pipeline_templates_route(db: Session = Depends(get_db)):
    return list_templates_bl(db)


@app.put("/pipeline-templates/{deal_type}", response_model=PipelineTemplateRes)
def update_pipeline_template_route(
    deal_type: str,
    payload: PipelineTemplateUpsert,
    db: Session = Depends(get_db),
):
    _require_valid_deal_type(deal_type)
    return update_template_bl(db, deal_type, payload)  # type: ignore[arg-type]


@app.get("/pipeline-templates/{deal_type}/stats", response_model=PipelineTemplateStatsRes)
def pipeline_template_stats_route(deal_type: str, db: Session = Depends(get_db)):
    _require_valid_deal_type(deal_type)
    return template_stats_bl(db, deal_type)  # type: ignore[arg-type]


from BL.health.helloworld.helloworld import helloworld as helloworld_bl

@app.get("/helloworld")
def helloworld() -> dict:
    return helloworld_bl()


# --- REPS (Real Estate Professional Status) tracker --- #

from BL.reps.common.valid_users import VALID_REPS_USERS as _VALID_REPS_USERS
from BL.reps.log.log import create_log as create_log_bl
from BL.reps.entries.entries import get_entries as get_entries_bl
from BL.reps.uploadBatch.uploadBatch import upload_batch as upload_batch_bl
from BL.reps.upload.upload import upload_single as upload_single_bl
from BL.reps.listProperties.listProperties import list_property_options as list_property_options_bl
from BL.reps.createProspect.createProspect import create_prospect as create_prospect_bl
from BL.reps.deleteProspect.deleteProspect import delete_prospect as delete_prospect_bl
from BL.reps.listPeople.listPeople import list_people as list_people_bl
from BL.reps.createPerson.createPerson import create_person as create_person_bl
from BL.reps.updatePerson.updatePerson import update_person as update_person_bl
from BL.reps.deletePerson.deletePerson import delete_person as delete_person_bl
from BL.reps.listActivityCategories.listActivityCategories import list_activity_categories as list_activity_categories_bl
from BL.reps.createActivityCategory.createActivityCategory import create_activity_category as create_activity_category_bl
from BL.reps.deleteActivityCategory.deleteActivityCategory import delete_activity_category as delete_activity_category_bl
from BL.reps.configStatus.configStatus import get_config_status as get_config_status_bl


def _require_reps_user(user: str) -> str:
    if user not in _VALID_REPS_USERS:
        raise HTTPException(
            status_code=400,
            detail=f"user must be one of {sorted(_VALID_REPS_USERS)}",
        )
    return user


@app.post("/reps/log", response_model=RepsLogRes, status_code=201)
def reps_log_route(payload: RepsLogCreate, db: Session = Depends(get_db)):
    """Append a new REPS entry to the user's Google Sheet (append-only).

    Evidence: each `evidence_items` entry becomes a clickable named link in
    the Sheet's Evidence column (rich text). The user types the label in
    the modal so the auditor sees `Closing meeting` instead of a 240-char
    GCS URL.

    Location: `location_snapshots` get rendered as breadcrumbs (START/STOP/
    PAUSE/RESUME/BOOKMARK/MANUAL/PHOTO) so an auditor can verify the user
    stayed at the property during the session.
    """

    _require_reps_user(payload.user)

    try:
        return create_log_bl(db, payload)
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to append REPS log row")
        raise HTTPException(status_code=500, detail=f"Sheet append failed: {exc}")


@app.get("/reps/entries", response_model=RepsEntriesEnvelope)
def reps_entries_route(user: str = Query(...)):
    """Read the user's full sheet history and return entries + computed stats."""
    _require_reps_user(user)
    try:
        return get_entries_bl(user)
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to read REPS sheet")
        raise HTTPException(status_code=500, detail=f"Sheet read failed: {exc}")


@app.post("/reps/upload-batch", response_model=RepsUploadBatchRes)
async def reps_upload_batch_route(
    user: str = Form(...),
    property_name: Optional[str] = Form(None),
    activity_category: Optional[str] = Form(None),
    log_timestamp: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    """Upload one or many evidence files into a per-log GCS sub-folder.

    The folder + per-file URLs are returned to the frontend, which then sends
    them back inside the `/reps/log` payload so the Sheet stores both the
    folder URL (auditor's index page) and each file URL.
    """

    _require_reps_user(user)
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    log_dt: Optional[datetime] = None
    if log_timestamp:
        try:
            log_dt = datetime.fromisoformat(log_timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail="log_timestamp must be ISO-8601."
            )

    items: List[tuple[str, Optional[str], bytes]] = []
    for f in files:
        contents = await f.read()
        items.append((f.filename or "evidence", f.content_type, contents))

    try:
        return upload_batch_bl(
            user=user,
            property_name=property_name,
            activity_category=activity_category,
            log_timestamp=log_dt,
            items=items,
        )
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("REPS batch upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@app.post("/reps/upload")
async def reps_upload_route(
    user: str = Form(...),
    file: UploadFile = File(...),
):
    """Single-file convenience shim — kept for backward compatibility.

    New clients should call `/reps/upload-batch`.
    """

    _require_reps_user(user)
    try:
        contents = await file.read()
        url = upload_single_bl(
            user=user,
            file_bytes=contents,
            filename=file.filename or "evidence",
            content_type=file.content_type,
        )
    except reps_service.RepsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except reps_service.RepsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("REPS evidence upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")

    return {"url": url, "filename": file.filename}


@app.get("/reps/properties", response_model=List[RepsPropertyOption])
def reps_properties_route(db: Session = Depends(get_db)):
    """Bought-deal addresses (priority) + saved prospects."""
    return list_property_options_bl(db)


@app.post("/reps/properties", response_model=RepsPropertyOption, status_code=201)
def reps_create_prospect_route(payload: RepsPropertyCreate, db: Session = Depends(get_db)):
    try:
        return create_prospect_bl(db, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/reps/properties/{prospect_id}")
def reps_delete_prospect_route(prospect_id: str, db: Session = Depends(get_db)):
    if not delete_prospect_bl(db, prospect_id):
        raise HTTPException(status_code=404, detail="Prospect not found")
    return {"message": "Prospect deleted"}


@app.get("/reps/people", response_model=List[RepsPersonRes])
def reps_list_people_route(db: Session = Depends(get_db)):
    return list_people_bl(db)


@app.post("/reps/people", response_model=RepsPersonRes, status_code=201)
def reps_create_person_route(payload: RepsPersonCreate, db: Session = Depends(get_db)):
    try:
        return create_person_bl(db, payload)
    except Exception as exc:
        # most likely a UNIQUE-name collision
        raise HTTPException(status_code=400, detail=f"Could not add person: {exc}")


@app.put("/reps/people/{person_id}", response_model=RepsPersonRes)
def reps_update_person_route(
    person_id: str, payload: RepsPersonUpdate, db: Session = Depends(get_db)
):
    result = update_person_bl(db, person_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@app.delete("/reps/people/{person_id}")
def reps_delete_person_route(person_id: str, db: Session = Depends(get_db)):
    if not delete_person_bl(db, person_id):
        raise HTTPException(status_code=404, detail="Person not found")
    return {"message": "Person deleted"}


@app.get("/reps/activity-categories", response_model=List[RepsActivityCategoryRes])
def reps_list_activity_categories_route(db: Session = Depends(get_db)):
    return list_activity_categories_bl(db)


@app.post("/reps/activity-categories", response_model=RepsActivityCategoryRes, status_code=201)
def reps_create_activity_category_route(
    payload: RepsActivityCategoryCreate, db: Session = Depends(get_db)
):
    try:
        return create_activity_category_bl(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not add category: {exc}")


@app.delete("/reps/activity-categories/{cat_id}")
def reps_delete_activity_category_route(cat_id: str, db: Session = Depends(get_db)):
    if not delete_activity_category_bl(db, cat_id):
        raise HTTPException(status_code=404, detail="Activity category not found")
    return {"message": "Activity category deleted"}


@app.get("/reps/config-status")
def reps_config_status_route():
    """Lightweight probe so the frontend can show a setup banner if env is missing."""
    return get_config_status_bl()

