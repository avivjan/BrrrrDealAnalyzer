"""Input validation for the BRRRR/Flip calculators.

Raises `fastapi.HTTPException` directly rather than a framework-agnostic
domain exception. That is a deliberate, reviewed exception to "BL stays
framework-agnostic": the alternative (a `DealValidationError` + a global
`@app.exception_handler`) is otherwise equivalent for every caller, but it
changes the *type name* of the exception these functions raise, which is
observable by anything introspecting it directly (as this refactor's own
regression harness does, at `calc_mortgage_payment` and
`calculate_brrr_results/zero_interest_refi`). Keeping the literal
`HTTPException` keeps that -- and every HTTP 400 response -- bit-identical.
"""

from fastapi import HTTPException

from ReqRes.common.analyze_inputs import analyzeBRRRReq, analyzeFlipReq


# (field, label) of every dollar line item of the BRRRR lifecycle; `None` = formula default, so skipped.
_BRRR_NON_NEGATIVE_DOLLARS = [
    ("earnest_money_deposit", "Earnest money deposit"),
    ("loan_charges_buy", "Loan charges (buy)"),
    ("recording_transfer_buy", "Recording and transfer charges (buy)"),
    ("title_escrow_buy", "Title and escrow charges (buy)"),
    ("other_closing_costs_buy", "Other closing costs (buy)"),
    ("online_notary_fee_buy", "Online notary fee (buy)"),
    ("rehab_cushion", "Rehab cushion"),
    ("monthly_utilities_until_rented", "Monthly utilities until rented"),
    ("maintenance_before_refi", "Maintenance before refi"),
    ("appliances", "Appliances"),
    ("loan_charges_refi", "Loan charges (refi)"),
    ("recording_transfer_refi", "Recording and transfer charges (refi)"),
    ("title_escrow_refi", "Title and escrow charges (refi)"),
    ("appraisal_fee", "Appraisal fee"),
    ("survey_fee", "Survey fee"),
    ("refi_underwriting_fee", "Refi underwriting fee"),
    ("broker_processing_fee_refi", "Broker processing fee (refi)"),
    ("other_closing_costs_refi", "Other closing costs (refi)"),
    ("online_notary_fee_refi", "Online notary fee (refi)"),
    ("maintenance_reserve", "Maintenance reserve"),
    ("vacancy_reserve", "Vacancy reserve"),
    ("capex_reserve", "CapEx reserve"),
]


def _is_negative(value) -> bool:
    return value is not None and value < 0


def _is_outside_percent_range(value) -> bool:
    return value is not None and (value < 0 or value > 100)


def _brrr_range_and_sign_errors(payload) -> list[str]:
    """The range and sign rules every BRRRR input must satisfy, whoever supplies it.

    Shared by the calculator's validator (a complete `analyzeBRRRReq`) and the saved-deal
    validator (a `BrrrActiveDealCreate`, whose fields are Optional): a `None` field is
    "not set" and is skipped, never a violation. The "must be greater than 0" rules on
    ARV, purchase price and rent are deliberately NOT here -- a brand-new deal on the
    board is saved with those at 0 until the owner fills them in.
    """
    validation_errors = []

    # 1. Non-Negative Checks
    if _is_negative(payload.rehab_cost_in_thousands):
        validation_errors.append("Rehab cost cannot be negative.")
    if _is_outside_percent_range(payload.rehab_contingency_percent):
        validation_errors.append("Rehab contingency percentage must be between 0% and 100%.")
    if _is_outside_percent_range(payload.refi_points):
        validation_errors.append("Broker points must be between 0% and 100%.")
    for field, label in _BRRR_NON_NEGATIVE_DOLLARS:
        if _is_negative(getattr(payload, field)):
            validation_errors.append(f"{label} cannot be negative.")
    if _is_negative(payload.construction_loan_budget_in_thousands):
        validation_errors.append("Construction loan budget cannot be negative.")
    if _is_negative(payload.days_until_rented):
        validation_errors.append("Days until rented cannot be negative.")
    if payload.lowest_arv_in_thousands is not None and payload.lowest_arv_in_thousands <= 0:
        validation_errors.append("Lowest ARV must be greater than 0.")
    if _is_negative(payload.annual_property_taxes):
        validation_errors.append("Annual property taxes cannot be negative.")
    if _is_negative(payload.annual_insurance):
        validation_errors.append("Annual insurance cannot be negative.")
    if _is_negative(payload.montly_hoa):
        validation_errors.append("HOA dues cannot be negative.")

    # 2. Lending Terms (Percentage Ranges 0-100)
    if _is_outside_percent_range(payload.down_payment):
        validation_errors.append("Down payment percentage must be between 0% and 100%.")
    if payload.ltv_as_precent is not None and (payload.ltv_as_precent <= 0 or payload.ltv_as_precent > 100):
        validation_errors.append("LTV must be between 0% and 100%.")
    if _is_outside_percent_range(payload.HML_points):
        validation_errors.append("HML points must be between 0% and 100%.")
    if _is_outside_percent_range(payload.HML_interest_rate):
        validation_errors.append("HML interest rate must be between 0% and 100%.")

    # 3. Timeframes
    if payload.days_until_refi is not None and payload.days_until_refi <= 0:
        validation_errors.append("Days until refi must be a positive number.")
    if payload.loan_term_years is not None and payload.loan_term_years <= 0:
        validation_errors.append("Loan term must be at least 1 year.")

    # 4. Long-term Financing
    if _is_outside_percent_range(payload.interest_rate):
        validation_errors.append("Interest rate must be between 0% and 100%.")

    # 5. Operating Expenses (Percentage Ranges)
    if _is_outside_percent_range(payload.vacancy_percent):
        validation_errors.append("Vacancy percentage must be between 0% and 100%.")
    if _is_outside_percent_range(payload.property_managment_fee_precentages_from_rent):
        validation_errors.append("Property management percentage must be between 0% and 100%.")
    if _is_outside_percent_range(payload.maintenance_percent):
        validation_errors.append("Maintenance percentage must be between 0% and 100%.")
    if _is_outside_percent_range(payload.capex_percent_of_rent):
        validation_errors.append("CapEx percentage must be between 0% and 100%.")

    return validation_errors


def _lowest_arv_exceeds_arv(payload) -> bool:
    """Only meaningful once both appraisals are known and positive; a lowest ARV of 0 or less is
    reported separately by `_brrr_range_and_sign_errors`."""
    return (payload.lowest_arv_in_thousands is not None and payload.lowest_arv_in_thousands > 0
            and payload.arv_in_thousands is not None and payload.arv_in_thousands > 0
            and payload.lowest_arv_in_thousands > payload.arv_in_thousands)


def validate_brrr_inputs(payload: analyzeBRRRReq):
    """The calculator's gate (`POST /analyze/brrr`, the PDF): every input must be usable now."""
    validation_errors = []

    # Base Value Checks (Must be positive)
    if payload.arv_in_thousands <= 0:
        validation_errors.append("ARV (in thousands) must be greater than 0.")
    if payload.purchase_price_in_thousands <= 0:
        validation_errors.append("Purchase price (in thousands) must be greater than 0.")
    if payload.rent <= 0:
        validation_errors.append("Rent must be greater than 0.")

    validation_errors.extend(_brrr_range_and_sign_errors(payload))
    if _lowest_arv_exceeds_arv(payload):
        validation_errors.append("Lowest ARV cannot exceed ARV.")

    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))


def validate_brrr_inputs_for_saved_deal(payload):
    """The board's gate (POST/PUT on active and bought BRRRR deals).

    A saved deal is re-analyzed on every read with no validation of its own
    (`BL.common.deal_response`), so anything the calculator would reject must be kept out of
    the row here: out-of-range percents, negative dollar lines, a loan term under a year
    (which makes the mortgage payment unable to compute and takes the whole board down with
    it), a lowest ARV above the ARV. Unlike the calculator this allows the blank new-deal
    zeros -- ARV, purchase price and rent at 0 -- because that is how a deal starts on the
    board. Takes a `BrrrActiveDealCreate` (or the bought subclass); `None` means "not set".
    """
    validation_errors = _brrr_range_and_sign_errors(payload)
    if _lowest_arv_exceeds_arv(payload):
        validation_errors.append("Lowest ARV cannot exceed ARV.")
    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))


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
    if payload.HML_interest_rate < 0 or payload.HML_interest_rate > 100:
        validation_errors.append("HML interest rate must be between 0% and 100%.")
    if payload.capital_gains_tax_rate < 0 or payload.capital_gains_tax_rate > 100:
        validation_errors.append("Capital gains tax rate must be between 0% and 100%.")

    if payload.closing_costs_buy_in_thousands < 0:
        validation_errors.append("Closing costs (buy) cannot be negative.")
    if payload.annual_property_taxes < 0:
        validation_errors.append("Annual property taxes cannot be negative.")
    if payload.annual_insurance < 0:
        validation_errors.append("Annual insurance cannot be negative.")
    if payload.montly_hoa < 0:
        validation_errors.append("HOA dues cannot be negative.")
    if payload.monthly_utilities < 0:
        validation_errors.append("Monthly utilities cannot be negative.")

    if payload.buyer_agent_selling_fee < 0 or payload.buyer_agent_selling_fee > 100:
        validation_errors.append("Buyer agent fee must be between 0% and 100%.")
    if payload.seller_agent_selling_fee < 0 or payload.seller_agent_selling_fee > 100:
        validation_errors.append("Seller agent fee must be between 0% and 100%.")
    if payload.selling_closing_costs_in_thousands < 0:
        validation_errors.append("Selling closing cost cannot be negative.")

    if validation_errors:
        raise HTTPException(status_code=400, detail=" ".join(validation_errors))
