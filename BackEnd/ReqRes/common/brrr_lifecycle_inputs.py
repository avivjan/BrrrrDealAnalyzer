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
InsurancePurchaseBillPaymentTiming = Literal["inside_purchase_closing", "outside_purchase_closing"]
InsuranceRefiBillPaymentTiming = Literal["inside_refi_closing", "outside_refi_closing"]
PropertyTaxCollectionAtRefi = Literal["no_tax_collected_at_refi", "full_tax_bill_collected_at_refi"]

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
        "Government recording and transfer charges at purchase, in dollars. None = formula: $250 + 0.55% of the "
        "whole hard-money loan (purchase loan + construction budget) + the deed transfer tax (0.70% of the "
        "purchase price when we pay all closing costs, else $0)."))] = None
    title_mode_buy: Annotated[TitleModeBuy, Field(alias="titleModeBuy", description=(
        "'standard' = buyer pays the lender's policy only ($1,000 default); 'we_pay_all' = buyer pays all "
        "title charges ($2,050 under $150k, $2,200 to $200k, $2,400 above)."))] = "standard"
    title_escrow_buy: Annotated[Optional[Decimal], Field(alias="titleEscrowBuy", description=(
        "Title, escrow and settlement charges at purchase, in dollars. None = formula by title mode."))] = None
    online_notary_buy: Annotated[bool, Field(alias="onlineNotaryBuy", description=(
        "Remote online notary at purchase: adds the notary fee to the buy closing costs."))] = True
    online_notary_fee_buy: Annotated[Optional[Decimal], Field(alias="onlineNotaryFeeBuy", description=(
        "Online notary fee at purchase, in dollars, applied only when onlineNotaryBuy is true. None = $250."))] = None
    other_closing_costs_buy: Annotated[Decimal, Field(alias="otherClosingCostsBuy", description=(
        "Any other purchase settlement lines (HOA transfer, warranty...), in dollars."))] = Decimal("0")
    other_closing_costs_buy_note: Annotated[Optional[str], Field(alias="otherClosingCostsBuyNote", max_length=500, description=(
        "What the other purchase closing costs are for (free text)."))] = None
    seller_paid_current_year_taxes: Annotated[Optional[bool], Field(alias="sellerPaidCurrentYearTaxes", description=(
        "Whether the seller already paid this year's property tax bill (billed in November). None = auto: "
        "true for an October to December closing (the title takes this year's bill at closing). Sets the direction of "
        "the seller tax credit; once paid, the tax bucket fills toward next year's bill from Dec 15."))] = None
    seller_tax_credit_at_purchase_closing: Annotated[Optional[Decimal], Field(alias="sellerTaxCreditAtPurchaseClosing", description=(
        "Property-tax proration on the purchase settlement statement, in dollars (the county-tax and assessment "
        "lines together). Positive = the seller credits the buyer; negative = the buyer reimburses the seller. "
        "None = formula: this year's bill (annual_property_taxes) prorated by the closing date."))] = None
    insurance_purchase_bill_payment_timing: Annotated[InsurancePurchaseBillPaymentTiming, Field(alias="insurancePurchaseBillPaymentTiming", description=(
        "Where the insurance bill at purchase (annual_insurance) is paid: 'inside_purchase_closing' = a line of the "
        "purchase settlement, in Cash to Close (Buy); 'outside_purchase_closing' = paid separately, in Total Cash Invested."))] = "inside_purchase_closing"

    # -- Rehab -----------------------------------------------------------------
    construction_loan_budget_in_thousands: Annotated[Decimal, Field(alias="constructionLoanBudget", description=(
        "Rehab budget financed by the hard-money lender, in thousands (35 = $35,000). 0 = rehab paid in "
        "cash. Budget minus actual rehab is the 'stolen money' draw spread."))] = Decimal("0")
    rehab_cushion: Annotated[Decimal, Field(alias="rehabCushion", description=(
        "Cash kept on hand for first draws, permits and surprises, in dollars. Counted in Cash Needed, not spent."))] = Decimal("5000")
    days_until_rehab_completed: Annotated[int, Field(alias="daysUntilRehabCompleted", description=(
        "Whole days from the purchase close until the rehab is complete. Must fall between the purchase close and "
        "the tenant-occupied day (0 <= days <= daysUntilRented)."))] = 45

    # -- Rent & holding ---------------------------------------------------------
    days_until_rented: Annotated[int, Field(alias="daysUntilRented", description=(
        "Whole days from the purchase close until a tenant occupies. Rent from then to the refi offsets holding costs."))] = 90
    monthly_utilities_until_rented: Annotated[Decimal, Field(alias="monthlyUtilitiesUntilRented", description=(
        "Electric, water and lawn per month while vacant, in dollars."))] = Decimal("80")
    maintenance_before_refi: Annotated[Decimal, Field(alias="maintenanceBeforeRefi", description=(
        "Post-rehab punch list, cleanings and repairs before the refi, in dollars."))] = Decimal("500")
    appliances: Annotated[Decimal, Field(description="Appliances bought for the tenant, in dollars.")] = Decimal("630")
    monthly_insurance_until_refi: Annotated[Decimal, Field(alias="monthlyInsuranceUntilRefi", description=(
        "Insurance paid monthly between the purchase and the refi, in dollars per month (30-day months)."))] = Decimal("0")
    monthly_property_tax_bucket_deposit: Annotated[Optional[Decimal], Field(alias="monthlyPropertyTaxBucketDeposit", description=(
        "The deposit into the property's tax bucket on each 15th until the refi, in dollars. None = formula: "
        "(this year's bill x 0.96 - the seller tax credit already in the bucket) / the 15ths left until Nov 30."))] = None

    # -- Refinance ---------------------------------------------------------------
    loan_charges_refi: Annotated[Decimal, Field(alias="loanChargesRefi", description=(
        "Refi lender charges, in dollars."))] = Decimal("200")
    recording_transfer_refi: Annotated[Optional[Decimal], Field(alias="recordingTransferRefi", description=(
        "Government recording and transfer charges at refi, in dollars. None = formula: 0.55% of the refi loan + $250."))] = None
    title_escrow_refi: Annotated[Optional[Decimal], Field(alias="titleEscrowRefi", description=(
        "Title, escrow and settlement charges at refi, in dollars. None = formula: $800 + 0.45% of the refi loan."))] = None
    online_notary_refi: Annotated[bool, Field(alias="onlineNotaryRefi", description=(
        "Remote online notary at refi: adds the notary fee to the refi closing costs."))] = True
    online_notary_fee_refi: Annotated[Optional[Decimal], Field(alias="onlineNotaryFeeRefi", description=(
        "Online notary fee at refi, in dollars, applied only when onlineNotaryRefi is true. None = $250."))] = None
    appraisal_fee: Annotated[Decimal, Field(alias="appraisalFee", description=(
        "Refi appraisal, in dollars. Paid outside the refi closing at the end of the rehab: in Total Cash Invested, "
        "not in the refi closing costs."))] = Decimal("700")
    survey_fee: Annotated[Decimal, Field(alias="surveyFee", description=(
        "Survey, in dollars ($385 / $450 / $485 are common). Paid outside the refi closing at the end of the rehab: "
        "in Total Cash Invested, not in the refi closing costs."))] = Decimal("385")
    refi_underwriting_fee: Annotated[Decimal, Field(alias="refiUnderwritingFee", description=(
        "Refi underwriting fee, in dollars (presets: MyLoanPathway $2,240, Clear2Mortgage $1,500, Cake Mortgage $2,195)."))] = Decimal("2000")
    broker_processing_fee_refi: Annotated[Decimal, Field(alias="brokerProcessingFeeRefi", description=(
        "Broker processing fee at refi, in dollars ($0 by default; $395 when the broker charges one)."))] = Decimal("0")
    other_closing_costs_refi: Annotated[Decimal, Field(alias="otherClosingCostsRefi", description=(
        "Any other refi settlement lines, in dollars."))] = Decimal("0")
    other_closing_costs_refi_note: Annotated[Optional[str], Field(alias="otherClosingCostsRefiNote", max_length=500, description=(
        "What the other refi closing costs are for (free text)."))] = None
    insurance_bill_at_refi_closing: Annotated[Optional[Decimal], Field(alias="insuranceBillAtRefiClosing", description=(
        "Insurance bill paid at the refi, in dollars. None = the insurance bill at purchase (annual_insurance)."))] = None
    insurance_refi_bill_payment_timing: Annotated[InsuranceRefiBillPaymentTiming, Field(alias="insuranceRefiBillPaymentTiming", description=(
        "Where the insurance bill at the refi is paid: 'inside_refi_closing' = a line of the refi settlement, off both "
        "cash-out wires; 'outside_refi_closing' = paid separately, in Total Cash Invested."))] = "inside_refi_closing"
    monthly_insurance_after_refi: Annotated[Optional[Decimal], Field(alias="monthlyInsuranceAfterRefi", description=(
        "Insurance per month in a regular year after the refi (cash flow, PITIA, DSCR), in dollars. "
        "None = the insurance bill at the refi / 12."))] = None
    property_tax_collection_at_refi: Annotated[PropertyTaxCollectionAtRefi, Field(alias="propertyTaxCollectionAtRefi", description=(
        "'no_tax_collected_at_refi' = the owner's tax bucket keeps paying the Nov 30 bill; "
        "'full_tax_bill_collected_at_refi' = the refi lender collects the whole bill as a lump (off both wires) and "
        "the bucket balance at the refi comes back to the owner."))] = "no_tax_collected_at_refi"
    property_tax_lump_sum_at_refi_closing: Annotated[Optional[Decimal], Field(alias="propertyTaxLumpSumAtRefiClosing", description=(
        "The tax lump the refi settlement collects, in dollars; used only with 'full_tax_bill_collected_at_refi'. "
        "None = this year's bill (annual_property_taxes)."))] = None
    maintenance_reserve: Annotated[Decimal, Field(alias="maintenanceReserve", description=(
        "Maintenance reserve the owner sets aside at the refi, in dollars. Stays in the deal (lowers cash out, not "
        "the wire) and counts as equity."))] = Decimal("1500")
    vacancy_reserve: Annotated[Optional[Decimal], Field(alias="vacancyReserve", description=(
        "Vacancy reserve the owner sets aside at the refi, in dollars. None = formula: one month of gross rent."))] = None
    capex_reserve: Annotated[Decimal, Field(alias="capexReserve", description=(
        "CapEx reserve the owner sets aside at the refi, in dollars."))] = Decimal("2500")
    hysa_deposit_at_refi: Annotated[Optional[Decimal], Field(alias="hysaDepositAtRefi", description=(
        "Deposit into the high-yield savings account at the refi, the fourth reserve, in dollars. "
        "None = formula: 3 months of the DSCR loan's principal and interest."))] = None
    lowest_arv_in_thousands: Annotated[Optional[Decimal], Field(alias="lowestArv", description=(
        "Stress-test appraisal, in thousands. None = formula: 90% of ARV. Drives the conservative cash-out "
        "wire; never changes the baseline ARV."))] = None
