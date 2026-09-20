"""The lifecycle inputs of a BRRRR deal, shared by the calculator request and the saved-deal models.

One declaration, inherited by `analyzeBRRRReq` (ReqRes/common/analyze_inputs.py) and
`BrrrActiveDealCreate` (ReqRes/common/active_deal_schemas.py; the bought models inherit from
that), so the two can never drift. Column names match `DAL/data_models/common/brrr_lifecycle.py`.

Units: plain dollars unless the name ends in `_in_thousands`; percentages as 0-100; dates ISO.

`None` on a field marked "None = formula" means "use the formula default" -- the engine computes
the effective value (`BL/analyze/brrrSteps/`) and returns it as `*_effective` on the result so
the UI can show the greyed default next to the input. A typed value overrides the formula;
sending `null` again restores it.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

TitleModeBuy = Literal["standard", "we_pay_all"]

# Fixed fees the engine applies when a checkbox is on.
ONLINE_NOTARY_FEE = Decimal("250")

# Presets offered by the UI (the amount fields stay free-form numbers).
LOAN_CHARGES_BUY_PRESETS = {"3shacks": Decimal("900"), "212": Decimal("1900")}
REFI_UNDERWRITING_FEE_PRESETS = {
    "MyLoanPathway": Decimal("2240"),
    "Clear2Mortgage": Decimal("1500"),
    "Cake Mortgage": Decimal("2195"),
}


class BrrrLifecycleInputs(BaseModel):
    # -- Buy -------------------------------------------------------------------
    buy_closing_date: Annotated[Optional[date], Field(alias="buyClosingDate", description=(
        "Purchase closing date (ISO). Anchors prepaid interest, the seller tax credit and the refi / "
        "tenant dates. None = unknown: the date-driven figures are left out."))] = None
    earnest_money_deposit: Annotated[Decimal, Field(alias="earnestMoneyDeposit", description=(
        "Earnest money already paid to escrow, in dollars; credited against Cash to Close (Buy)."))] = Decimal("5000")
    loan_charges_buy: Annotated[Decimal, Field(alias="loanChargesBuy", description=(
        "Hard-money lender charges at purchase, in dollars (presets: 3shacks $900, 212 $1,900)."))] = Decimal("900")
    recording_transfer_buy: Annotated[Optional[Decimal], Field(alias="recordingTransferBuy", description=(
        "Government recording and transfer charges at purchase, in dollars. None = formula: "
        "0.55% of the purchase loan + $250."))] = None
    title_mode_buy: Annotated[TitleModeBuy, Field(alias="titleModeBuy", description=(
        "'standard' = buyer pays the lender's policy only ($1,000 default); 'we_pay_all' = buyer pays all "
        "title charges ($2,050 under $150k, $2,200 to $200k, $2,400 above)."))] = "standard"
    title_escrow_buy: Annotated[Optional[Decimal], Field(alias="titleEscrowBuy", description=(
        "Title, escrow and settlement charges at purchase, in dollars. None = formula by title mode."))] = None
    online_notary_buy: Annotated[bool, Field(alias="onlineNotaryBuy", description=(
        "Remote online notary at purchase: adds $250 to the buy closing costs."))] = True
    other_closing_costs_buy: Annotated[Decimal, Field(alias="otherClosingCostsBuy", description=(
        "Any other purchase settlement lines (HOA transfer, warranty...), in dollars."))] = Decimal("0")
    seller_paid_current_year_taxes: Annotated[Optional[bool], Field(alias="sellerPaidCurrentYearTaxes", description=(
        "Whether the seller already paid this year's property tax bill (billed in November). None = auto: "
        "true only for a December closing. Sets the direction of the seller tax credit."))] = None

    # -- Rehab -----------------------------------------------------------------
    construction_loan_budget_in_thousands: Annotated[Decimal, Field(alias="constructionLoanBudget", description=(
        "Rehab budget financed by the hard-money lender, in thousands (35 = $35,000). 0 = rehab paid in "
        "cash. Budget minus actual rehab is the 'stolen money' draw spread."))] = Decimal("0")
    rehab_cushion: Annotated[Decimal, Field(alias="rehabCushion", description=(
        "Cash kept on hand for first draws, permits and surprises, in dollars. Counted in Cash Needed, not spent."))] = Decimal("5000")

    # -- Rent & holding ---------------------------------------------------------
    days_until_rented: Annotated[int, Field(alias="daysUntilRented", description=(
        "Whole days from the purchase close until a tenant occupies. Rent from then to the refi offsets holding costs."))] = 90
    monthly_utilities_until_rented: Annotated[Decimal, Field(alias="monthlyUtilitiesUntilRented", description=(
        "Electric, water and lawn per month while vacant, in dollars."))] = Decimal("80")
    maintenance_before_refi: Annotated[Decimal, Field(alias="maintenanceBeforeRefi", description=(
        "Post-rehab punch list, cleanings and repairs before the refi, in dollars."))] = Decimal("500")
    appliances: Annotated[Decimal, Field(description="Appliances bought for the tenant, in dollars.")] = Decimal("630")

    # -- Refinance ---------------------------------------------------------------
    loan_charges_refi: Annotated[Decimal, Field(alias="loanChargesRefi", description=(
        "Refi lender charges, in dollars."))] = Decimal("200")
    recording_transfer_refi: Annotated[Optional[Decimal], Field(alias="recordingTransferRefi", description=(
        "Government recording and transfer charges at refi, in dollars. None = formula: 0.55% of the refi loan + $250."))] = None
    title_escrow_refi: Annotated[Optional[Decimal], Field(alias="titleEscrowRefi", description=(
        "Title, escrow and settlement charges at refi, in dollars. None = formula: $800 + 0.45% of the refi loan."))] = None
    online_notary_refi: Annotated[bool, Field(alias="onlineNotaryRefi", description=(
        "Remote online notary at refi: adds $250 to the refi closing costs."))] = True
    appraisal_fee: Annotated[Decimal, Field(alias="appraisalFee", description="Refi appraisal, in dollars.")] = Decimal("700")
    survey_fee: Annotated[Decimal, Field(alias="surveyFee", description="Survey, in dollars ($385 / $450 / $485 are common).")] = Decimal("385")
    refi_underwriting_fee: Annotated[Decimal, Field(alias="refiUnderwritingFee", description=(
        "Refi underwriting fee, in dollars (presets: MyLoanPathway $2,240, Clear2Mortgage $1,500, Cake Mortgage $2,195)."))] = Decimal("2000")
    broker_processing_fee_refi: Annotated[Decimal, Field(alias="brokerProcessingFeeRefi", description=(
        "Broker processing fee at refi, in dollars ($395 typical, $0 possible)."))] = Decimal("395")
    other_closing_costs_refi: Annotated[Decimal, Field(alias="otherClosingCostsRefi", description=(
        "Any other refi settlement lines, in dollars."))] = Decimal("0")
    maintenance_reserve: Annotated[Decimal, Field(alias="maintenanceReserve", description=(
        "Maintenance reserve escrowed by the refi lender, in dollars. Recoverable: reduces the wire, counts as equity."))] = Decimal("1500")
    vacancy_reserve: Annotated[Optional[Decimal], Field(alias="vacancyReserve", description=(
        "Vacancy reserve escrowed at refi, in dollars. None = formula: one month of gross rent."))] = None
    capex_reserve: Annotated[Decimal, Field(alias="capexReserve", description=(
        "CapEx reserve escrowed at refi, in dollars."))] = Decimal("2500")
    lowest_arv_in_thousands: Annotated[Optional[Decimal], Field(alias="lowestArv", description=(
        "Stress-test appraisal, in thousands. None = formula: 90% of ARV. Drives the conservative cash-out "
        "wire; never changes the baseline ARV."))] = None
