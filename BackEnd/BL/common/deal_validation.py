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
    if payload.cash_reserve_in_thousands < 0:
        validation_errors.append("Cash reserve cannot be negative.")
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
    if payload.days_until_refi <= 0:
        validation_errors.append("Days until refi must be a positive number.")
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
