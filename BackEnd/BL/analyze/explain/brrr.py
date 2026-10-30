"""Explain a `BrrrResultsWithIntermediates`: the step-by-step narrative behind every BRRRR headline metric.

Companion to `compute_brrr_with_intermediates` (`BL/analyze/analyzeBRRR.py`). Every value comes
from the record; every equation stated in a formula is first verified against that record
(`check`, or the fold inside `add_sum`), so the narrative cannot drift from the math.
`tests/test_explain.py` additionally fails if a record field is never read here.

Sum-type steps list their terms in the same left-to-right order the calculator adds them
(see the `brrrSteps/`); that is what lets the guard use exact equality on unrounded Decimals.
The story follows the lifecycle: Buy, Rehab, Rent/Holding, Refinance.
"""

from decimal import Decimal

from BL.analyze.brrr_results_with_intermediates import BrrrResultsWithIntermediates
from BL.analyze.common.calc_breakdown import CalcBreakdown, check, fmt_money, fmt_pct, fmt_num
from BL.analyze.common.deal_math import (
    calc_hml_interest,
    calc_prepaid_interest_refi,
    calc_holding_costs,
    calc_mortgage_payment,
    calc_cash_on_cash,
    calc_roi,
    calc_seller_tax_credit,
    seller_paid_current_year_taxes_by_default,
    recording_transfer_default,
    recording_transfer_buy_default,
    deed_transfer_tax_buy_default,
    title_escrow_buy_default,
    title_escrow_refi_default,
    lowest_arv_default,
    DAYS_PER_MONTH,
    HYSA_DEPOSIT_MONTHS_OF_PRINCIPAL_AND_INTEREST,
    PROPERTY_TAX_NOVEMBER_PAYMENT_FACTOR,
    TITLE_ESCROW_BUY_STANDARD,
    TITLE_ESCROW_BUY_WE_PAY_ALL,
    TITLE_ESCROW_BUY_WE_PAY_ALL_TOP,
)

# The headline metrics, in reading order: (result field, label, unit).
# The PDF derives both its summary table and its breakdown sections from this.
BRRR_SECTIONS = [
    ("cash_flow", "Monthly Cash Flow", "money"),
    ("dscr", "DSCR", "ratio"),
    ("cash_on_cash", "Cash on Cash", "pct"),
    ("roi", "ROI", "pct"),
    ("net_profit", "Net Profit", "money"),
    ("equity", "Equity (post-refi)", "money"),
    ("cash_to_close_buy", "Cash to Close (Buy)", "money"),
    ("total_hard_money_cost", "Total Hard Money Cost", "money"),
    ("stolen_money", "Stolen Money (draw spread)", "money"),
    ("cash_out_routi", "Cash-Out Wire (Refi)", "money"),
    ("cash_out_routi_conservative", "Cash-Out Wire (Lowest ARV)", "money"),
    ("cash_out", "Cash Out from Deal", "money"),
    ("total_cash_needed_for_deal", "Cash Needed", "money"),
]

CASH_NEEDED = "total_cash_needed_for_deal"
WIRE = "cash_out_routi"
WIRE_LOW = "cash_out_routi_conservative"
CLOSE = "cash_to_close_buy"
HM_COST = "total_hard_money_cost"


def _fmt_months(months: Decimal) -> str:
    """A month count with up to 2 decimals, trailing zeros dropped (3, 3.5, 3.07)."""
    return f"{float(months):.2f}".rstrip("0").rstrip(".")


def _title_escrow_buy_formula(title_mode: str, purchase_price: Decimal, title_escrow_buy: Decimal) -> str:
    """How the title/escrow default was picked: the flat standard fee, or the we-pay-all price tier."""
    if title_mode != "we_pay_all":
        return (f"Standard deal → flat {fmt_money(TITLE_ESCROW_BUY_STANDARD)}: we pay only the lender's title policy, its endorsements "
                f"and the settlement/search fees; the seller pays the owner's policy")
    (lowest_tier_upper_bound, lowest_tier_fee), (middle_tier_upper_bound, middle_tier_fee) = TITLE_ESCROW_BUY_WE_PAY_ALL
    tier_table = (f"under {fmt_money(lowest_tier_upper_bound)} → {fmt_money(lowest_tier_fee)} · "
                  f"{fmt_money(lowest_tier_upper_bound)} to {fmt_money(middle_tier_upper_bound)} → {fmt_money(middle_tier_fee)} · "
                  f"above {fmt_money(middle_tier_upper_bound)} → {fmt_money(TITLE_ESCROW_BUY_WE_PAY_ALL_TOP)}")
    if purchase_price < lowest_tier_upper_bound:
        chosen_bracket = f"under {fmt_money(lowest_tier_upper_bound)}"
    elif purchase_price <= middle_tier_upper_bound:
        chosen_bracket = f"between {fmt_money(lowest_tier_upper_bound)} and {fmt_money(middle_tier_upper_bound)}"
    else:
        chosen_bracket = f"above {fmt_money(middle_tier_upper_bound)}"
    return (f"We pay all closing costs → we pay every title charge, and the fee is set by the purchase price tier ({tier_table}). "
            f"Purchase {fmt_money(purchase_price)} is {chosen_bracket} → {fmt_money(title_escrow_buy)}")


def _default_note(user_value, what_it_is: str) -> str:
    return f"Formula default for {what_it_is}; type a value to override." if user_value is None else f"{what_it_is} as entered."


def explain_brrr(payload, results: BrrrResultsWithIntermediates) -> dict[str, list[dict]]:
    breakdown = CalcBreakdown(results)
    # The derived dates, as text.
    refi_date_suffix = f" on {results.refi_closing_date.isoformat()}"
    tenant_date_suffix = f" (tenant from {results.tenant_occupied_date.isoformat()})"
    rehab_completed_date_suffix = f" on {results.rehab_completed_date.isoformat()}"

    # -- monthly cash flow: a regular year after the refi -------------------------
    check(results.property_tax_bill_paid_on_november_30 == payload.annual_property_taxes * PROPERTY_TAX_NOVEMBER_PAYMENT_FACTOR, "property tax bill paid on Nov 30")
    check(results.monthly_taxes == results.property_tax_bill_paid_on_november_30 / 12, "monthly property tax")
    breakdown.add(
        ["cash_flow", "dscr"], "Property Tax per Month (regular year)", results.monthly_taxes,
        f"This year's bill ({fmt_money(payload.annual_property_taxes)}) × 0.96 = {fmt_money(results.property_tax_bill_paid_on_november_30)} paid on Nov 30 ÷ 12 = {fmt_money(results.monthly_taxes)}",
        note="Paid on Nov 30 with the 4% November discount. The refi never changes the tax, so a regular year costs the same bill.",
    )
    check(results.insurance_bill_at_refi == (payload.annual_insurance if payload.insurance_bill_at_refi_closing is None else payload.insurance_bill_at_refi_closing), "insurance bill at refi")
    check(results.monthly_insurance == (results.insurance_bill_at_refi / 12 if payload.monthly_insurance_after_refi is None else payload.monthly_insurance_after_refi), "monthly insurance after refi")
    breakdown.add(
        ["cash_flow", "dscr"], "Insurance per Month (regular year)", results.monthly_insurance,
        (f"Insurance bill at the refi ({fmt_money(results.insurance_bill_at_refi)}) ÷ 12 = {fmt_money(results.monthly_insurance)}"
         if payload.monthly_insurance_after_refi is None else f"As entered: {fmt_money(results.monthly_insurance)}"),
        note=_default_note(payload.monthly_insurance_after_refi, "the regular-year insurance per month")
             + " The insurance paid at the purchase, monthly until the refi and at the refi count in the cash out and Cash Needed only;"
               " the bill at the refi pays the first year, which this monthly figure still charges.",
    )
    breakdown.add_sum("cash_flow", "Monthly Operating Expenses", results.operating_expenses, [
        (f"Vacancy {fmt_pct(payload.vacancy_percent)} of rent", results.vacancy),
        (f"Management {fmt_pct(payload.property_managment_fee_precentages_from_rent)} of rent", results.management_fee),
        (f"Maintenance {fmt_pct(payload.maintenance_percent)} of rent", results.maintenance),
        (f"CapEx {fmt_pct(payload.capex_percent_of_rent)} of rent", results.capex),
        ("Property Tax per Month", results.monthly_taxes),
        ("Insurance per Month", results.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ], note="A regular year after the refi: steady monthly figures only, never a closing lump.")
    breakdown.add_sum("cash_flow", "Net Operating Income (NOI)", results.net_operating_income, [
        ("Rent", payload.rent),
        ("Operating Expenses", results.operating_expenses, "-"),
    ])
    check(results.refi_loan_amount == results.arv * results.ltv, "refi loan amount")
    breakdown.add(
        ["cash_out", WIRE, "equity"], "Refi Loan Amount", results.refi_loan_amount,
        f"ARV ({fmt_money(results.arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(results.refi_loan_amount)}",
    )
    check(results.mortgage_payment == calc_mortgage_payment(results.arv, results.ltv, payload.interest_rate, payload.loan_term_years), "mortgage payment")
    breakdown.add(
        ["cash_flow", "dscr"], "Monthly Mortgage Payment", results.mortgage_payment,
        f"Refi Loan ({fmt_money(results.refi_loan_amount)}) amortized at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(results.mortgage_payment)}",
        note="A 0% loan repays straight-line: loan ÷ number of months." if payload.interest_rate == 0 else None,
    )
    breakdown.add_sum(["cash_flow", "roi", "cash_on_cash"], "Monthly Cash Flow", results.cash_flow, [
        ("NOI", results.net_operating_income),
        ("Mortgage", results.mortgage_payment, "-"),
    ])

    # -- DSCR ------------------------------------------------------------------
    breakdown.add_sum("dscr", "PITIA", results.pitia, [
        ("Mortgage", results.mortgage_payment),
        ("Property Tax per Month", results.monthly_taxes),
        ("Insurance per Month", results.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ], note="Principal, interest, taxes, insurance and association dues of a regular year: the monthly debt service the rent must cover.")
    check(results.dscr == (payload.rent / results.pitia if results.pitia else Decimal("0")), "DSCR")
    breakdown.add(
        "dscr", "DSCR", results.dscr,
        (f"Rent ({fmt_money(payload.rent)}) ÷ PITIA ({fmt_money(results.pitia)}) = {fmt_num(results.dscr)}"
         if results.pitia else "PITIA is $0 → DSCR undefined, reported as 0"),
        unit="ratio",
    )

    # -- BUY: the hard-money stack ---------------------------------------------
    check(results.purchase_loan_amount == results.purchase_price * (1 - payload.down_payment / Decimal("100.0")), "purchase loan")
    breakdown.add(
        [CLOSE, HM_COST], "Purchase Loan (hard money)", results.purchase_loan_amount,
        f"Purchase ({fmt_money(results.purchase_price)}) × (1 − Down Payment {fmt_pct(payload.down_payment)}) = {fmt_money(results.purchase_loan_amount)}",
    )
    check(results.down_payment_cash == (payload.down_payment / Decimal("100")) * results.purchase_price, "down payment")
    breakdown.add(
        [CLOSE, CASH_NEEDED], "Down Payment (cash)", results.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(results.purchase_price)}) = {fmt_money(results.down_payment_cash)}",
    )
    check(results.construction_budget == payload.construction_loan_budget_in_thousands * Decimal("1000.0"), "construction budget")
    breakdown.add_sum([HM_COST, WIRE, "cash_out"], "Hard Money Loan (total principal)", results.hml_amount, [
        ("Purchase Loan", results.purchase_loan_amount),
        ("Construction Budget", results.construction_budget),
    ], note=("A $0 construction budget means the rehab is paid in cash." if results.construction_budget == 0
             else "The lender funds the construction budget; interest accrues on it from day one."))
    check(results.hml_points == payload.HML_points / Decimal("100.0") * results.hml_amount, "HML points")
    breakdown.add(
        [CLOSE, HM_COST], "HML Points (cash at closing)", results.hml_points,
        f"{fmt_pct(payload.HML_points)} × Hard Money Loan ({fmt_money(results.hml_amount)}) = {fmt_money(results.hml_points)}",
    )
    check(results.hml_per_diem == calc_hml_interest(results.hml_amount, payload.HML_interest_rate, 1), "HML per diem")
    check(results.hml_interest == calc_hml_interest(results.hml_amount, payload.HML_interest_rate, payload.days_until_refi), "HML interest")
    breakdown.add(
        HM_COST, "HML Interest (until refi)", results.hml_interest,
        f"Hard Money Loan ({fmt_money(results.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 360 = {fmt_money(results.hml_per_diem)} per diem × {payload.days_until_refi} days = {fmt_money(results.hml_interest)}",
        note="Hard money accrues per diem on a 360-day year.",
    )
    check(results.prepaid_interest_buy == calc_hml_interest(results.hml_amount, payload.HML_interest_rate, results.hml_interest_days_prepaid_at_purchase_closing), "prepaid interest (buy)")
    check(results.hml_interest_accrued_into_refi_payoff == calc_hml_interest(results.hml_amount, payload.HML_interest_rate, results.hml_interest_days_accrued_into_refi_payoff), "accrued interest at payoff")
    check(results.hml_interest_paid_monthly == results.hml_interest - results.prepaid_interest_buy - results.hml_interest_accrued_into_refi_payoff, "interest split")
    breakdown.add(
        CLOSE, "Prepaid Interest (Buy)", results.prepaid_interest_buy,
        f"Per diem ({fmt_money(results.hml_per_diem)}) × {results.hml_interest_days_prepaid_at_purchase_closing} days from {results.buy_closing_date.isoformat()} through month end = {fmt_money(results.prepaid_interest_buy)}",
        note=(f"Interest is paid in arrears on the 1st: {results.hml_interest_days_prepaid_at_purchase_closing} days prepaid here, {results.hml_interest_days_paid_monthly} days paid monthly "
              f"({fmt_money(results.hml_interest_paid_monthly)}), {results.hml_interest_days_accrued_into_refi_payoff} days inside the payoff ({fmt_money(results.hml_interest_accrued_into_refi_payoff)})."),
    )
    # The part of the HML interest paid out of pocket on the 1st of each month: a month's interest
    # times the months it is paid for. Filed under the Total Cash Invested sections so that sum links it.
    hml_monthly_interest = calc_hml_interest(results.hml_amount, payload.HML_interest_rate, DAYS_PER_MONTH)
    hml_months_paid_monthly = Decimal(results.hml_interest_days_paid_monthly) / DAYS_PER_MONTH
    check(abs(hml_monthly_interest * hml_months_paid_monthly - results.hml_interest_paid_monthly) < Decimal("0.005"), "HML interest paid monthly")
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "HML Interest paid monthly", results.hml_interest_paid_monthly,
        f"Monthly HML interest: per diem ({fmt_money(results.hml_per_diem)}) × 30 days = {fmt_money(hml_monthly_interest)}/month"
        f" × {_fmt_months(hml_months_paid_monthly)} months ({results.hml_interest_days_paid_monthly} days paid monthly ÷ 30) = {fmt_money(results.hml_interest_paid_monthly)}",
        note=(f"Of the HML Interest until refi ({fmt_money(results.hml_interest)}, {payload.days_until_refi} days): "
              f"− Prepaid Interest (Buy) {fmt_money(results.prepaid_interest_buy)} ({results.hml_interest_days_prepaid_at_purchase_closing} days, already in Cash to Close) "
              f"− Accrued Interest inside the HML payoff {fmt_money(results.hml_interest_accrued_into_refi_payoff)} ({results.hml_interest_days_accrued_into_refi_payoff} days, paid by the refi wire) "
              f"= {fmt_money(results.hml_interest_paid_monthly)} paid from your pocket on the 1st of each month."),
    )
    breakdown.add_sum(HM_COST, "Total Hard Money Cost", results.total_hard_money_cost, [
        ("HML Points", results.hml_points),
        ("HML Interest", results.hml_interest),
        ("Loan Charges (Buy)", payload.loan_charges_buy),
    ])

    # -- BUY: the settlement -----------------------------------------------------
    check(results.deed_transfer_tax_buy == deed_transfer_tax_buy_default(payload.title_mode_buy, results.purchase_price), "deed transfer tax")
    breakdown.add(
        CLOSE, "Deed Transfer Tax (Buy)", results.deed_transfer_tax_buy,
        (f"We pay all closing costs → we also pay the seller's deed transfer tax: 0.70% × Purchase ({fmt_money(results.purchase_price)}) = {fmt_money(results.deed_transfer_tax_buy)}"
         if payload.title_mode_buy == "we_pay_all" else
         "Standard deal → the seller pays the deed transfer tax (a seller debit on the settlement statement), so it costs us $0"),
        note=("The deed transfer tax (documentary stamps on the deed) is 0.70% of the price and is normally the seller's. "
              + ("Because we pay all closing costs we take it over; it is added into Recording & Transfer (Buy)."
                 if payload.title_mode_buy == "we_pay_all" else
                 f"Choosing 'we pay all closing costs' would add it to our costs: 0.70% × {fmt_money(results.purchase_price)} = {fmt_money(deed_transfer_tax_buy_default('we_pay_all', results.purchase_price))}.")),
    )
    check(results.recording_transfer_buy == (recording_transfer_buy_default(results.hml_amount, results.deed_transfer_tax_buy) if payload.recording_transfer_buy is None else payload.recording_transfer_buy), "recording (buy)")
    breakdown.add(
        CLOSE, "Recording & Transfer (Buy)", results.recording_transfer_buy,
        f"$250 + 0.55% × Hard Money Loan ({fmt_money(results.hml_amount)}) + Deed Transfer Tax ({fmt_money(results.deed_transfer_tax_buy)}) = {fmt_money(results.recording_transfer_buy)}"
        if payload.recording_transfer_buy is None else f"As entered: {fmt_money(results.recording_transfer_buy)}",
        note=_default_note(payload.recording_transfer_buy, "government recording and transfer charges") + " The 0.55% (0.35% + 0.20%) is on the whole loan recorded, purchase loan plus construction budget.",
    )
    check(results.title_escrow_buy == (title_escrow_buy_default(payload.title_mode_buy, results.purchase_price) if payload.title_escrow_buy is None else payload.title_escrow_buy), "title (buy)")
    breakdown.add(
        CLOSE, "Title & Escrow (Buy)", results.title_escrow_buy,
        (_title_escrow_buy_formula(payload.title_mode_buy, results.purchase_price, results.title_escrow_buy)
         if payload.title_escrow_buy is None else f"As entered: {fmt_money(results.title_escrow_buy)}"),
        note=_default_note(payload.title_escrow_buy, "title, escrow and settlement charges"),
    )
    check(results.notary_buy == ((Decimal("250") if payload.online_notary_fee_buy is None else payload.online_notary_fee_buy) if payload.online_notary_buy else Decimal("0")), "notary (buy)")
    breakdown.add(CLOSE, "Online Notary (Buy)", results.notary_buy,
                  f"Remote closing → {fmt_money(results.notary_buy)}" if payload.online_notary_buy else "Not a remote closing → $0",
                  note=(None if not payload.online_notary_buy else _default_note(payload.online_notary_fee_buy, "the $250 notary fee")))
    insurance_bill_at_purchase_is_inside_closing = payload.insurance_purchase_bill_payment_timing == "inside_purchase_closing"
    check(results.insurance_bill_at_purchase_inside_closing == (payload.annual_insurance if insurance_bill_at_purchase_is_inside_closing else 0), "insurance at purchase (inside closing)")
    check(results.insurance_bill_at_purchase_outside_closing == (0 if insurance_bill_at_purchase_is_inside_closing else payload.annual_insurance), "insurance at purchase (outside closing)")
    breakdown.add(
        CLOSE, "Insurance Bill at Purchase (inside closing)", results.insurance_bill_at_purchase_inside_closing,
        (f"Paid through the purchase settlement → {fmt_money(results.insurance_bill_at_purchase_inside_closing)}" if insurance_bill_at_purchase_is_inside_closing
         else "Paid outside the purchase closing → $0 here (in Total Cash Invested instead)"),
    )
    breakdown.add_sum([CLOSE, CASH_NEEDED], "Closing Costs (Buy)", results.closing_costs_buy_total, [
        ("Loan Charges", payload.loan_charges_buy),
        ("Recording & Transfer", results.recording_transfer_buy),
        ("Title & Escrow", results.title_escrow_buy),
        ("Online Notary", results.notary_buy),
        ("Other", payload.other_closing_costs_buy),
        ("Insurance Bill (inside closing)", results.insurance_bill_at_purchase_inside_closing),
    ])
    check(results.seller_paid_current_year_taxes == (payload.seller_paid_current_year_taxes if payload.seller_paid_current_year_taxes is not None else seller_paid_current_year_taxes_by_default(results.buy_closing_date)), "seller paid taxes")
    check(results.seller_tax_credit_formula == calc_seller_tax_credit(payload.annual_property_taxes, results.buy_closing_date, results.seller_paid_current_year_taxes), "seller tax credit")
    tax_formula = (
        f"Seller already paid this year's taxes → buyer credits the seller for {results.buy_closing_date.isoformat()} through Dec 31: {fmt_money(results.seller_tax_credit_formula)}"
        if results.seller_paid_current_year_taxes else
        f"Taxes ({fmt_money(payload.annual_property_taxes)}) × seller's days (Jan 1 to the day before {results.buy_closing_date.isoformat()}) ÷ days in the year = {fmt_money(results.seller_tax_credit_formula)}"
    )
    check(results.seller_tax_credit == (results.seller_tax_credit_formula if payload.seller_tax_credit_at_purchase_closing is None else payload.seller_tax_credit_at_purchase_closing), "seller tax credit (effective)")
    if payload.seller_tax_credit_at_purchase_closing is not None:
        tax_formula = f"As entered from the settlement statement: {fmt_money(results.seller_tax_credit)} (the proration would give {fmt_money(results.seller_tax_credit_formula)})"
    breakdown.add(CLOSE, "Seller Tax Credit", results.seller_tax_credit, tax_formula,
           note="Taxes are billed in November for the calendar year; positive = the seller credits the buyer on the settlement statement, "
                "and that credit is set aside in the property's tax bucket the day after closing.")
    check(results.seller_tax_credit_set_aside_in_tax_bucket == max(Decimal("0"), results.seller_tax_credit), "seller tax credit set aside")
    # Filed under the same sections as the Total Cash Invested sum: when the credit is positive
    # the record holds one Decimal object under both fields, and the breakdown only links such an
    # operand to a step inside the sum's own sections.
    breakdown.add([CASH_NEEDED, "cash_out"], "Seller Tax Credit set aside in the tax bucket", results.seller_tax_credit_set_aside_in_tax_bucket,
           (f"Credit received at closing ({fmt_money(results.seller_tax_credit)}) → put in the property's tax bucket the day after"
            if results.seller_tax_credit > 0 else
            "$0: a negative credit is the buyer's reimbursement to the seller and stays in Cash to Close" if results.seller_tax_credit < 0 else
            "No credit at closing → nothing to set aside ($0)"),
           note="The buyer pays the whole year's bill in November, so the seller's share is held, not spent: it lowers the wire but never Cash Needed.")
    breakdown.add_sum([CLOSE, CASH_NEEDED], "Cash to Close (Buy)", results.cash_to_close_buy, [
        ("Down Payment", results.down_payment_cash),
        ("Closing Costs (Buy)", results.closing_costs_buy_total),
        ("HML Points", results.hml_points),
        ("Prepaid Interest (Buy)", results.prepaid_interest_buy),
        ("Seller Tax Credit", results.seller_tax_credit, "-"),
        ("Earnest Money Deposit", payload.earnest_money_deposit, "-"),
    ], note="The wire to the title company on purchase day. Earnest money is already in escrow, so it is credited here.")

    # -- REHAB: draws -------------------------------------------------------------
    check(results.rehab_contingency == results.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    breakdown.add_sum(["stolen_money", "cash_out"], "Actual Rehab Cost (with contingency)", results.rehab_cost, [
        ("Rehab", results.rehab_cost_base),
        (f"Contingency {fmt_pct(payload.rehab_contingency_percent)}", results.rehab_contingency),
    ])
    breakdown.add_sum("stolen_money", "Stolen Money (draw spread)", results.stolen_money, [
        ("Construction Budget", results.construction_budget),
        ("Actual Rehab Cost", results.rehab_cost, "-"),
    ], note=("Positive: the lender's draws exceed the spend, so that much comes out before the refi."
             if results.stolen_money > 0 else "Negative or zero: the investor funds the rehab beyond the budget."))
    check(results.rehab_paid_cash_out_of_pocket == results.rehab_cost - results.construction_budget, "rehab cash")
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Rehab Out-of-Pocket", results.rehab_paid_cash_out_of_pocket,
        f"Actual Rehab ({fmt_money(results.rehab_cost)}) − Construction Budget ({fmt_money(results.construction_budget)}) = {fmt_money(results.rehab_paid_cash_out_of_pocket)}",
        note="Negative = cash returned through draws, which reduces what is invested.",
    )

    # -- RENT / HOLDING ------------------------------------------------------------
    check(results.hoa_dues_until_refi == calc_holding_costs(Decimal("0"), Decimal("0"), payload.montly_hoa, payload.days_until_refi), "HOA until refi")
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "HOA until Refi", results.hoa_dues_until_refi,
        f"HOA ({fmt_money(payload.montly_hoa)}) × 12 × {payload.days_until_refi} days ÷ 360 = {fmt_money(results.hoa_dues_until_refi)}",
        note="Taxes and insurance are not accrued day by day: they are paid as the bills and deposits they really are (below).",
    )
    # -- insurance, purchase to refi ---------------------------------------------------
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Insurance Bill at Purchase (outside closing)", results.insurance_bill_at_purchase_outside_closing,
        (f"Paid separately from the purchase settlement → {fmt_money(results.insurance_bill_at_purchase_outside_closing)}" if not insurance_bill_at_purchase_is_inside_closing
         else "Paid through the purchase settlement → $0 here (inside Cash to Close (Buy))"),
    )
    check(results.insurance_paid_monthly_until_refi == payload.monthly_insurance_until_refi * Decimal(payload.days_until_refi) / DAYS_PER_MONTH, "insurance paid monthly until refi")
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Insurance paid monthly until Refi", results.insurance_paid_monthly_until_refi,
        f"{fmt_money(payload.monthly_insurance_until_refi)}/mo × {payload.days_until_refi} days ÷ 30 = {fmt_money(results.insurance_paid_monthly_until_refi)}",
    )
    insurance_bill_at_refi_is_inside_closing = payload.insurance_refi_bill_payment_timing == "inside_refi_closing"
    check(results.insurance_bill_at_refi_inside_closing == (results.insurance_bill_at_refi if insurance_bill_at_refi_is_inside_closing else 0), "insurance at refi (inside closing)")
    check(results.insurance_bill_at_refi_outside_closing == (0 if insurance_bill_at_refi_is_inside_closing else results.insurance_bill_at_refi), "insurance at refi (outside closing)")
    breakdown.add(
        [WIRE, WIRE_LOW, CASH_NEEDED, "cash_out"], "Insurance Bill at Refi", results.insurance_bill_at_refi,
        (f"Same as the bill at purchase: {fmt_money(results.insurance_bill_at_refi)}" if payload.insurance_bill_at_refi_closing is None
         else f"As entered: {fmt_money(results.insurance_bill_at_refi)}"),
        note=("Paid through the refi settlement: it comes off both cash-out wires." if insurance_bill_at_refi_is_inside_closing
              else "Paid outside the refi closing: in Total Cash Invested, the wires are untouched."),
    )
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Insurance Bill at Refi (outside closing)", results.insurance_bill_at_refi_outside_closing,
        (f"Paid separately from the refi settlement → {fmt_money(results.insurance_bill_at_refi_outside_closing)}" if not insurance_bill_at_refi_is_inside_closing
         else "Paid through the refi settlement → $0 here (inside the refi closing costs)"),
    )
    # -- the property's tax bucket, purchase to refi --------------------------------------
    full_tax_bill_collected_at_refi = payload.property_tax_collection_at_refi == "full_tax_bill_collected_at_refi"
    check(results.property_tax_bucket_deposit_count_until_first_payment >= 1, "tax bucket deposit count")
    deposit_formula = (
        f"(Bill × 0.96 ({fmt_money(results.property_tax_bill_paid_on_november_30)}) − Seller Tax Credit set aside ({fmt_money(results.seller_tax_credit_set_aside_in_tax_bucket)})) "
        f"÷ {results.property_tax_bucket_deposit_count_until_first_payment} deposits on the 15ths through {results.first_property_tax_payment_date.isoformat()} = {fmt_money(results.property_tax_bucket_deposit)}"
    )
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Tax Bucket Deposit (each 15th)", results.property_tax_bucket_deposit,
        deposit_formula if payload.monthly_property_tax_bucket_deposit is None else f"As entered: {fmt_money(results.property_tax_bucket_deposit)}",
        note=_default_note(payload.monthly_property_tax_bucket_deposit, "the deposit into the property's tax bucket")
             + " The seller's credit goes into the bucket at closing; the deposits fill it up to the Nov 30 bill.",
    )
    check(results.property_tax_bucket_deposit_after_first_payment == results.monthly_taxes, "tax bucket deposit after Nov 30")
    check(results.property_tax_paid_into_bucket_until_refi
          == results.property_tax_bucket_deposit * results.property_tax_bucket_first_bill_deposit_count_until_refi
          + results.property_tax_bucket_deposit_after_first_payment * Decimal(results.property_tax_bucket_later_deposit_count_until_refi), "tax paid into the bucket")
    first_bill_deposit_count_text = f"{int(results.property_tax_bucket_first_bill_deposit_count_until_refi)} deposits on the 15ths until the refi{refi_date_suffix}"
    later_deposits_text = (f" + {results.property_tax_bucket_later_deposit_count_until_refi} deposits of {fmt_money(results.property_tax_bucket_deposit_after_first_payment)} after the Nov 30 bill"
                           if results.property_tax_bucket_later_deposit_count_until_refi else "")
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Tax paid into the Bucket until Refi", results.property_tax_paid_into_bucket_until_refi,
        f"{fmt_money(results.property_tax_bucket_deposit)} × {first_bill_deposit_count_text}{later_deposits_text} = {fmt_money(results.property_tax_paid_into_bucket_until_refi)}",
    )
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Tax Bucket Shortfall topped up on Nov 30", results.property_tax_bucket_shortfall_topped_up_on_november_30,
        (f"The Nov 30 bill ({fmt_money(results.property_tax_bill_paid_on_november_30)}) fell inside the hold and the bucket was short → {fmt_money(results.property_tax_bucket_shortfall_topped_up_on_november_30)} topped up"
         if results.property_tax_bucket_shortfall_topped_up_on_november_30 > 0 else "The bucket covers any Nov 30 bill inside the hold → $0"),
    )
    if full_tax_bill_collected_at_refi:
        check(results.property_tax_lump_sum_at_refi_closing == (payload.annual_property_taxes if payload.property_tax_lump_sum_at_refi_closing is None else payload.property_tax_lump_sum_at_refi_closing), "tax lump at refi")
    else:
        check(results.property_tax_lump_sum_at_refi_closing == 0 and results.property_tax_bucket_balance_released_at_refi == 0, "no tax lump at refi")
    breakdown.add(
        [WIRE, WIRE_LOW, CASH_NEEDED], "Tax Lump collected at Refi", results.property_tax_lump_sum_at_refi_closing,
        ((f"The refi lender collects the whole bill: {fmt_money(results.property_tax_lump_sum_at_refi_closing)}" if payload.property_tax_lump_sum_at_refi_closing is None
          else f"As entered: {fmt_money(results.property_tax_lump_sum_at_refi_closing)}")
         if full_tax_bill_collected_at_refi else "The owner's bucket pays the Nov 30 bill → no lump at the refi ($0)"),
        note="A refi settlement line: it comes off both cash-out wires." if full_tax_bill_collected_at_refi else None,
    )
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Tax Bucket Balance released at Refi", results.property_tax_bucket_balance_released_at_refi,
        (f"Seller Tax Credit set aside + deposits until the refi + any shortfall topped up − any Nov 30 bill already paid = {fmt_money(results.property_tax_bucket_balance_released_at_refi)} back to you"
         if full_tax_bill_collected_at_refi else "The bucket keeps paying the Nov 30 bill → nothing comes back ($0)"),
        note="The refi lender now pays the Nov 30 bill, so the bucket is no longer needed." if full_tax_bill_collected_at_refi else None,
    )
    check(results.utilities_until_rented == payload.monthly_utilities_until_rented * Decimal(payload.days_until_rented) / DAYS_PER_MONTH, "utilities until rented")
    breakdown.add(
        CASH_NEEDED, "Utilities until Rented", results.utilities_until_rented,
        f"{fmt_money(payload.monthly_utilities_until_rented)}/mo × {payload.days_until_rented} days ÷ 30 = {fmt_money(results.utilities_until_rented)}" + tenant_date_suffix,
    )
    check(results.days_tenant_occupied_before_refi == max(0, int(payload.days_until_refi) - int(payload.days_until_rented)), "days rented")
    check(results.pre_refi_rental_income == payload.rent * Decimal(results.days_tenant_occupied_before_refi) / DAYS_PER_MONTH, "pre-refi rent")
    breakdown.add(
        [CASH_NEEDED, "cash_out"], "Pre-Refi Rental Income", results.pre_refi_rental_income,
        f"Rent ({fmt_money(payload.rent)}) × {results.days_tenant_occupied_before_refi} days rented before the refi ÷ 30 = {fmt_money(results.pre_refi_rental_income)}",
        note="Rent collected between tenant placement and the refi offsets the holding costs." if results.days_tenant_occupied_before_refi else "The tenant is placed at or after the refi, so no rent offsets the holding costs.",
    )

    # -- REFINANCE: settlement lines -----------------------------------------------
    for section_key, refi_loan, settlement_lines, arv_label in (
        (WIRE, results.refi_loan_amount,
         (results.broker_points_refi, results.recording_transfer_refi, results.title_escrow_refi, results.closing_costs_refi_total, results.prepaid_interest_refi), ""),
        (WIRE_LOW, results.conservative_refi_loan_amount,
         (results.broker_points_refi_conservative, results.recording_transfer_refi_conservative, results.title_escrow_refi_conservative,
          results.closing_costs_refi_total_conservative, results.prepaid_interest_refi_conservative), " (Lowest ARV)"),
    ):
        broker_points, recording_transfer, title_escrow, closing_costs_total, prepaid_interest = settlement_lines
        check(broker_points == payload.refi_points / Decimal("100") * refi_loan, f"broker points{arv_label}")
        breakdown.add(section_key, f"Broker Points (Refi){arv_label}", broker_points, f"{fmt_pct(payload.refi_points)} × Refi Loan ({fmt_money(refi_loan)}) = {fmt_money(broker_points)}")
        check(recording_transfer == (recording_transfer_default(refi_loan) if payload.recording_transfer_refi is None else payload.recording_transfer_refi), f"recording (refi){arv_label}")
        breakdown.add(section_key, f"Recording & Transfer (Refi){arv_label}", recording_transfer,
               f"0.55% × Refi Loan ({fmt_money(refi_loan)}) + $250 = {fmt_money(recording_transfer)}" if payload.recording_transfer_refi is None else f"As entered: {fmt_money(recording_transfer)}",
               note=_default_note(payload.recording_transfer_refi, "government recording and transfer charges"))
        check(title_escrow == (title_escrow_refi_default(refi_loan) if payload.title_escrow_refi is None else payload.title_escrow_refi), f"title (refi){arv_label}")
        breakdown.add(section_key, f"Title & Escrow (Refi){arv_label}", title_escrow,
               f"$800 + 0.45% × Refi Loan ({fmt_money(refi_loan)}) = {fmt_money(title_escrow)}" if payload.title_escrow_refi is None else f"As entered: {fmt_money(title_escrow)}",
               note=_default_note(payload.title_escrow_refi, "title, escrow and settlement charges"))
        breakdown.add_sum(section_key, f"Closing Costs (Refi){arv_label}", closing_costs_total, [
            ("Loan Charges", payload.loan_charges_refi),
            ("Recording & Transfer", recording_transfer),
            ("Title & Escrow", title_escrow),
            ("Online Notary", results.notary_refi),
            ("Underwriting", payload.refi_underwriting_fee),
            ("Broker Points", broker_points),
            ("Broker Processing", payload.broker_processing_fee_refi),
            ("Other", payload.other_closing_costs_refi),
            ("Insurance Bill (inside closing)", results.insurance_bill_at_refi_inside_closing),
            ("Tax Lump collected at Refi", results.property_tax_lump_sum_at_refi_closing),
        ], note="The appraisal and the survey are paid outside the refi closing (POC), so they are in Total Cash Invested, not here.")
        check(prepaid_interest == calc_prepaid_interest_refi(refi_loan, payload.interest_rate, results.dscr_interest_days_prepaid_at_refi_closing), f"prepaid interest (refi){arv_label}")
        breakdown.add(section_key, f"Prepaid Interest (Refi){arv_label}", prepaid_interest,
               f"Refi Loan ({fmt_money(refi_loan)}) × {fmt_pct(payload.interest_rate)}/yr ÷ 360 × {results.dscr_interest_days_prepaid_at_refi_closing} days from {results.refi_closing_date.isoformat()} through month end = {fmt_money(prepaid_interest)}",
               note="The DSCR loan's per-diem interest is collected at closing through the end of the month (360-day year, as the refi settlement statements quote it).")
    check(results.notary_refi == ((Decimal("250") if payload.online_notary_fee_refi is None else payload.online_notary_fee_refi) if payload.online_notary_refi else Decimal("0")), "notary (refi)")
    check(results.vacancy_reserve == (payload.rent if payload.vacancy_reserve is None else payload.vacancy_reserve), "vacancy reserve")
    check(results.hysa_deposit_at_refi == (HYSA_DEPOSIT_MONTHS_OF_PRINCIPAL_AND_INTEREST * results.mortgage_payment if payload.hysa_deposit_at_refi is None else payload.hysa_deposit_at_refi), "HYSA deposit")
    breakdown.add(
        ["cash_out", "equity", CASH_NEEDED], "HYSA Deposit at Refi", results.hysa_deposit_at_refi,
        (f"3 months × Monthly Mortgage Payment ({fmt_money(results.mortgage_payment)}) = {fmt_money(results.hysa_deposit_at_refi)}"
         if payload.hysa_deposit_at_refi is None else f"As entered: {fmt_money(results.hysa_deposit_at_refi)}"),
        note=_default_note(payload.hysa_deposit_at_refi, "the high-yield savings deposit (3 months of principal and interest)"),
    )
    breakdown.add_sum(["cash_out", "equity", CASH_NEEDED], "Reserves set aside at Refi", results.reserves_total, [
        ("Maintenance Reserve", payload.maintenance_reserve),
        ("Vacancy Reserve", results.vacancy_reserve),
        ("CapEx Reserve", payload.capex_reserve),
        ("HYSA Deposit", results.hysa_deposit_at_refi),
    ], note=("Vacancy reserve defaults to one month of rent; type a value to override. " if payload.vacancy_reserve is None else "")
            + "Your own money set aside after the wire, not the lender's escrow: it stays in the deal (lowers the cash out) and, "
              "because a sale releases it, counts as equity.")
    breakdown.add_sum([WIRE, WIRE_LOW, "cash_out"], "HML Payoff at Refi", results.hml_payoff, [
        ("Hard Money Loan", results.hml_amount),
        ("Accrued Interest (1st of month → payoff)", results.hml_interest_accrued_into_refi_payoff),
    ])

    # -- REFINANCE: the wires -------------------------------------------------------
    check(results.appraisal_and_survey_paid_outside_closing == payload.appraisal_fee + payload.survey_fee, "appraisal and survey")
    breakdown.add_sum([CASH_NEEDED, "cash_out"], "Appraisal & Survey (paid outside closing)", results.appraisal_and_survey_paid_outside_closing, [
        ("Appraisal", payload.appraisal_fee),
        ("Survey", payload.survey_fee),
    ], note=f"Paid on their own at the end of the rehab{rehab_completed_date_suffix} (POC on the refi settlement statement), so they are not refi closing costs.")
    breakdown.add_sum(["cash_out", CASH_NEEDED], "Total Cash Invested (pre-refi)", results.total_cash_invested, [
        ("Earnest Money Deposit", payload.earnest_money_deposit),
        ("Cash to Close (Buy)", results.cash_to_close_buy),
        ("Seller Tax Credit set aside in the tax bucket", results.seller_tax_credit_set_aside_in_tax_bucket),
        ("Insurance Bill at Purchase (outside closing)", results.insurance_bill_at_purchase_outside_closing),
        ("Rehab Out-of-Pocket", results.rehab_paid_cash_out_of_pocket),
        ("HML Interest paid monthly", results.hml_interest_paid_monthly),
        ("HOA until Refi", results.hoa_dues_until_refi),
        ("Insurance paid monthly until Refi", results.insurance_paid_monthly_until_refi),
        ("Tax paid into the Bucket until Refi", results.property_tax_paid_into_bucket_until_refi),
        ("Tax Bucket Shortfall topped up on Nov 30", results.property_tax_bucket_shortfall_topped_up_on_november_30),
        ("Utilities until Rented", results.utilities_until_rented),
        ("Maintenance before Refi", payload.maintenance_before_refi),
        ("Appliances", payload.appliances),
        ("Appraisal & Survey", results.appraisal_and_survey_paid_outside_closing),
        ("Insurance Bill at Refi (outside closing)", results.insurance_bill_at_refi_outside_closing),
        ("Pre-Refi Rental Income", results.pre_refi_rental_income, "-"),
        ("Tax Bucket Balance released at Refi", results.property_tax_bucket_balance_released_at_refi, "-"),
    ], note="Every dollar actually spent before the refinance, plus the seller tax credit put back into the tax bucket the day after closing; "
            "the rehab cushion is held, not spent, so it is not here.")
    breakdown.add_sum([WIRE, "cash_out"], f"Cash-Out Wire (Refi{refi_date_suffix})", results.cash_out_routi, [
        ("Refi Loan", results.refi_loan_amount),
        ("HML Payoff", results.hml_payoff, "-"),
        ("Closing Costs (Refi)", results.closing_costs_refi_total, "-"),
        ("Prepaid Interest (Refi)", results.prepaid_interest_refi, "-"),
    ], note=("Negative: that much cash is brought to the refi closing table." if results.cash_out_routi < 0
             else "The 'Due to Borrower' line of the refi settlement statement, before the reserves and what was invested."))
    check(results.lowest_arv == (lowest_arv_default(results.arv) if payload.lowest_arv_in_thousands is None else payload.lowest_arv_in_thousands * Decimal("1000.0")), "lowest ARV")
    breakdown.add(WIRE_LOW, "Lowest ARV (stress test)", results.lowest_arv,
           f"90% × ARV ({fmt_money(results.arv)}) = {fmt_money(results.lowest_arv)}" if payload.lowest_arv_in_thousands is None else f"As entered: {fmt_money(results.lowest_arv)}",
           note=_default_note(payload.lowest_arv_in_thousands, "the lowest appraisal to plan for") + " The baseline ARV is untouched.")
    check(results.conservative_refi_loan_amount == results.lowest_arv * results.ltv, "conservative refi loan")
    breakdown.add(WIRE_LOW, "Refi Loan (Lowest ARV)", results.conservative_refi_loan_amount,
           f"Lowest ARV ({fmt_money(results.lowest_arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(results.conservative_refi_loan_amount)}")
    breakdown.add_sum(WIRE_LOW, "Cash-Out Wire (Lowest ARV)", results.cash_out_routi_conservative, [
        ("Refi Loan (Lowest ARV)", results.conservative_refi_loan_amount),
        ("HML Payoff", results.hml_payoff, "-"),
        ("Closing Costs (Refi, Lowest ARV)", results.closing_costs_refi_total_conservative, "-"),
        ("Prepaid Interest (Refi, Lowest ARV)", results.prepaid_interest_refi_conservative, "-"),
    ], note="The loan-dependent fees follow the lower loan; typed-in fees stay as entered.")
    check(results.cash_to_refi_table_conservative == max(Decimal("0"), -results.cash_out_routi_conservative), "cash to refi table (conservative)")
    breakdown.add([WIRE_LOW, CASH_NEEDED], "Cash to Refi Table (Lowest ARV)", results.cash_to_refi_table_conservative,
           (f"Wire ({fmt_money(results.cash_out_routi_conservative)}) is negative → {fmt_money(results.cash_to_refi_table_conservative)} brought to the table"
            if results.cash_to_refi_table_conservative > 0 else f"Wire ({fmt_money(results.cash_out_routi_conservative)}) is not negative → nothing to bring"))
    check(results.reserves_funded_from_own_pocket_at_lowest_arv == max(Decimal("0"), results.reserves_total - max(Decimal("0"), results.cash_out_routi_conservative)), "reserves from own pocket (conservative)")
    breakdown.add([WIRE_LOW, CASH_NEEDED], "Reserves the Lowest-ARV Wire cannot fund", results.reserves_funded_from_own_pocket_at_lowest_arv,
           (f"Reserves ({fmt_money(results.reserves_total)}) − what the wire brings ({fmt_money(max(Decimal('0'), results.cash_out_routi_conservative))}) = {fmt_money(results.reserves_funded_from_own_pocket_at_lowest_arv)} from your pocket"
            if results.reserves_funded_from_own_pocket_at_lowest_arv > 0 else f"The lowest-ARV wire covers the reserves ({fmt_money(results.reserves_total)}) → $0"))
    breakdown.add_sum(["net_profit", "roi", "cash_on_cash", "cash_out"], "Cash Out from Deal", results.cash_out, [
        ("Cash-Out Wire", results.cash_out_routi),
        ("Reserves set aside at Refi", results.reserves_total, "-"),
        ("Total Cash Invested", results.total_cash_invested, "-"),
    ], note=("Negative: that much of your own money is still left in the deal after the refi, the reserves included."
             if results.cash_out < 0 else "Positive: the refi returns more than was invested and set aside."))

    # -- returns ---------------------------------------------------------------
    check(results.cash_on_cash == calc_cash_on_cash(results.cash_out, results.cash_flow), "cash on cash")
    if results.cash_out >= 0:
        coc_formula = f"Cash Out ({fmt_money(results.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif results.cash_flow <= 0:
        coc_formula = f"Cash Flow ({fmt_money(results.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        coc_formula = f"Annual Cash Flow ({fmt_money(results.cash_flow * 12)}) ÷ |Cash Out| ({fmt_money(abs(results.cash_out))}) × 100 = {fmt_pct(results.cash_on_cash)}"
    breakdown.add("cash_on_cash", "Cash on Cash", results.cash_on_cash, coc_formula, unit="pct")

    check(results.equity == results.arv * (1 - results.ltv) + results.reserves_total, "equity")
    breakdown.add(
        ["net_profit", "roi", "equity"], "Equity (post-refi)", results.equity,
        f"ARV ({fmt_money(results.arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Reserves ({fmt_money(results.reserves_total)}) = {fmt_money(results.equity)}",
        note="The reserves you set aside at the refi are released with confidence at a sale, so they count as equity." if results.reserves_total else None,
    )
    breakdown.add_sum(["net_profit", "roi"], "Net Profit", results.net_profit, [
        ("Equity", results.equity),
        ("Cash Out", results.cash_out),
    ])
    check(results.roi == calc_roi(results.cash_out, results.cash_flow, results.net_profit), "ROI")
    if results.cash_out >= 0:
        roi_formula = f"Cash Out ({fmt_money(results.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif results.cash_flow <= 0:
        roi_formula = f"Cash Flow ({fmt_money(results.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        roi_formula = f"(Annual Cash Flow ({fmt_money(results.cash_flow * 12)}) + Net Profit ({fmt_money(results.net_profit)})) ÷ |Cash Out| ({fmt_money(abs(results.cash_out))}) × 100 = {fmt_pct(results.roi)}"
    breakdown.add("roi", "ROI", results.roi, roi_formula, unit="pct")

    # -- cash needed -----------------------------------------------------------
    check(results.hml_interest_first_month_days == max(0, int(DAYS_PER_MONTH) - results.hml_interest_days_prepaid_at_purchase_closing), "HML interest days (first month)")
    check(results.hml_interest_first_month == calc_hml_interest(results.hml_amount, payload.HML_interest_rate, results.hml_interest_first_month_days), "HML interest (first month)")
    breakdown.add(
        CASH_NEEDED, "HML Interest (first month)", results.hml_interest_first_month,
        (f"Per diem ({fmt_money(results.hml_per_diem)}) × (30 − {results.hml_interest_days_prepaid_at_purchase_closing} days already prepaid in Cash to Close) = "
         f"{results.hml_interest_first_month_days} days = {fmt_money(results.hml_interest_first_month)}"),
        note="The interest from the closing day through month end is prepaid inside Cash to Close (Buy), so only the rest of the first month is added here.",
    )
    hoa_dues_first_month = calc_holding_costs(Decimal("0"), Decimal("0"), payload.montly_hoa, DAYS_PER_MONTH)
    check(results.holding_costs_first_month == hoa_dues_first_month + payload.monthly_insurance_until_refi + results.property_tax_bucket_deposit, "holding costs (first month)")
    breakdown.add(
        CASH_NEEDED, "Holding Costs (first month)", results.holding_costs_first_month,
        (f"HOA ({fmt_money(payload.montly_hoa)}) × 12 × 30 days ÷ 360 ({fmt_money(hoa_dues_first_month)}) + Insurance per month until refi ({fmt_money(payload.monthly_insurance_until_refi)}) "
         f"+ one Tax Bucket Deposit ({fmt_money(results.property_tax_bucket_deposit)}) = {fmt_money(results.holding_costs_first_month)}"),
    )
    breakdown.add_sum(CASH_NEEDED, "Cash Needed Floor", results.cash_needed_floor, [
        ("Earnest Money Deposit", payload.earnest_money_deposit),
        ("Cash to Close (Buy)", results.cash_to_close_buy),
        ("Insurance Bill at Purchase (outside closing)", results.insurance_bill_at_purchase_outside_closing),
        ("Rehab Cushion", payload.rehab_cushion),
        ("Utilities (first month)", payload.monthly_utilities_until_rented),
        ("HML Interest (first month)", results.hml_interest_first_month),
        ("Holding Costs (first month)", results.holding_costs_first_month),
    ], note="The least the deal can take whatever the draws, the rent and the refi wire later give back: the deposit, the purchase wire, the insurance bill when it is paid outside it, the cushion held for draws and surprises, and the first month of utilities, hard-money interest, HOA, insurance paid monthly and one tax-bucket deposit.")
    breakdown.add_sum(CASH_NEEDED, "Cash Needed through Refi", results.cash_needed_through_refi, [
        ("Total Cash Invested", results.total_cash_invested),
        ("Rehab Cushion", payload.rehab_cushion),
        ("Cash to Refi Table (Lowest ARV)", results.cash_to_refi_table_conservative),
        ("Reserves the Lowest-ARV Wire cannot fund", results.reserves_funded_from_own_pocket_at_lowest_arv),
    ], note="Everything spent through the refinance, plus the cushion, plus the cash brought to the refi table and the reserves the wire cannot fund if the appraisal comes in at the lowest ARV.")
    check(results.cash_needed_floor_top_up == max(Decimal("0"), results.cash_needed_floor - results.cash_needed_through_refi), "cash needed floor top-up")
    breakdown.add(
        CASH_NEEDED, "Floor Top-Up", results.cash_needed_floor_top_up,
        (f"Cash Needed Floor ({fmt_money(results.cash_needed_floor)}) − Cash Needed through Refi ({fmt_money(results.cash_needed_through_refi)}) = {fmt_money(results.cash_needed_floor_top_up)}"
         if results.cash_needed_floor_top_up > 0
         else f"Cash Needed through Refi ({fmt_money(results.cash_needed_through_refi)}) already covers the floor ({fmt_money(results.cash_needed_floor)}) → $0"),
        note="Lifts Cash Needed to the floor when the draws, the rent collected and the refi wire would otherwise put it below what day one and the first month take.",
    )
    breakdown.add_sum(CASH_NEEDED, "Cash Needed", results.total_cash_needed, [
        ("Cash Needed through Refi", results.cash_needed_through_refi),
        ("Floor Top-Up", results.cash_needed_floor_top_up),
    ], note="The larger of the floor and the through-refi figure: the single out-of-pocket figure, planned on the lowest-ARV stress test and never below what day one and the first month take.")
    return breakdown.to_dict()
