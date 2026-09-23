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
    recording_transfer_default,
    recording_transfer_buy_default,
    deed_transfer_tax_buy_default,
    title_escrow_buy_default,
    title_escrow_refi_default,
    lowest_arv_default,
    DAYS_PER_MONTH,
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


def _default_note(user_value, what_it_is: str) -> str:
    return f"Formula default for {what_it_is}; type a value to override." if user_value is None else f"{what_it_is} as entered."


def explain_brrr(payload, results: BrrrResultsWithIntermediates) -> dict[str, list[dict]]:
    breakdown = CalcBreakdown(results)
    has_buy_closing_date = results.buy_closing_date is not None
    # The derived dates read as text wherever they are known.
    refi_date_suffix = f" on {results.refi_closing_date.isoformat()}" if results.refi_closing_date is not None else ""
    tenant_date_suffix = f" (tenant from {results.tenant_occupied_date.isoformat()})" if results.tenant_occupied_date is not None else ""

    # -- monthly cash flow -----------------------------------------------------
    breakdown.add_sum("cash_flow", "Monthly Operating Expenses", results.operating_expenses, [
        (f"Vacancy {fmt_pct(payload.vacancy_percent)} of rent", results.vacancy),
        (f"Management {fmt_pct(payload.property_managment_fee_precentages_from_rent)} of rent", results.management_fee),
        (f"Maintenance {fmt_pct(payload.maintenance_percent)} of rent", results.maintenance),
        (f"CapEx {fmt_pct(payload.capex_percent_of_rent)} of rent", results.capex),
        ("Taxes ÷ 12", results.monthly_taxes),
        ("Insurance ÷ 12", results.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ])
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
        ("Taxes ÷ 12", results.monthly_taxes),
        ("Insurance ÷ 12", results.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ], note="Principal, interest, taxes, insurance and association dues: the monthly debt service the rent must cover.")
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
        (f"Per diem ({fmt_money(results.hml_per_diem)}) × {results.hml_interest_days_prepaid_at_purchase_closing} days from {results.buy_closing_date.isoformat()} through month end = {fmt_money(results.prepaid_interest_buy)}"
         if has_buy_closing_date else "No buy closing date → no prepaid interest is modelled ($0)"),
        note=(f"Interest is paid in arrears on the 1st: {results.hml_interest_days_prepaid_at_purchase_closing} days prepaid here, {results.hml_interest_days_paid_monthly} days paid monthly "
              f"({fmt_money(results.hml_interest_paid_monthly)}), {results.hml_interest_days_accrued_into_refi_payoff} days inside the payoff ({fmt_money(results.hml_interest_accrued_into_refi_payoff)})."
              if has_buy_closing_date else f"Without a closing date all {results.hml_interest_days_paid_monthly} days of interest are treated as paid monthly ({fmt_money(results.hml_interest_paid_monthly)})."),
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
        (f"We pay all closing costs → 0.70% × Purchase ({fmt_money(results.purchase_price)}) = {fmt_money(results.deed_transfer_tax_buy)}"
         if payload.title_mode_buy == "we_pay_all" else "Standard deal → the seller's debit, $0 to us"),
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
        (f"Title mode '{payload.title_mode_buy}' at a {fmt_money(results.purchase_price)} price → {fmt_money(results.title_escrow_buy)}"
         if payload.title_escrow_buy is None else f"As entered: {fmt_money(results.title_escrow_buy)}"),
        note=_default_note(payload.title_escrow_buy, "title, escrow and settlement charges"),
    )
    check(results.notary_buy == ((Decimal("250") if payload.online_notary_fee_buy is None else payload.online_notary_fee_buy) if payload.online_notary_buy else Decimal("0")), "notary (buy)")
    breakdown.add(CLOSE, "Online Notary (Buy)", results.notary_buy,
                  f"Remote closing → {fmt_money(results.notary_buy)}" if payload.online_notary_buy else "Not a remote closing → $0",
                  note=(None if not payload.online_notary_buy else _default_note(payload.online_notary_fee_buy, "the $250 notary fee")))
    breakdown.add_sum([CLOSE, CASH_NEEDED], "Closing Costs (Buy)", results.closing_costs_buy_total, [
        ("Loan Charges", payload.loan_charges_buy),
        ("Recording & Transfer", results.recording_transfer_buy),
        ("Title & Escrow", results.title_escrow_buy),
        ("Online Notary", results.notary_buy),
        ("Other", payload.other_closing_costs_buy),
    ])
    if has_buy_closing_date:
        check(results.seller_paid_current_year_taxes == (payload.seller_paid_current_year_taxes if payload.seller_paid_current_year_taxes is not None else results.buy_closing_date.month == 12), "seller paid taxes")
        check(results.seller_tax_credit == calc_seller_tax_credit(payload.annual_property_taxes, results.buy_closing_date, results.seller_paid_current_year_taxes), "seller tax credit")
        tax_formula = (
            f"Seller already paid this year's taxes → buyer credits the seller for {results.buy_closing_date.isoformat()} through Dec 31: {fmt_money(results.seller_tax_credit)}"
            if results.seller_paid_current_year_taxes else
            f"Taxes ({fmt_money(payload.annual_property_taxes)}) × seller's days (Jan 1 to the day before {results.buy_closing_date.isoformat()}) ÷ days in the year = {fmt_money(results.seller_tax_credit)}"
        )
    else:
        check(results.seller_paid_current_year_taxes is None and results.seller_tax_credit == 0, "seller tax credit without date")
        tax_formula = "No buy closing date → no tax proration is modelled ($0)"
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
    check(results.holding_costs == calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi), "holding costs")
    breakdown.add(
        CASH_NEEDED, "Holding Costs (until refi)", results.holding_costs,
        f"(Taxes ({fmt_money(payload.annual_property_taxes)}) + Insurance ({fmt_money(payload.annual_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) × 12) × {payload.days_until_refi} days ÷ 360 = {fmt_money(results.holding_costs)}",
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
            ("Appraisal", payload.appraisal_fee),
            ("Survey", payload.survey_fee),
            ("Underwriting", payload.refi_underwriting_fee),
            ("Broker Points", broker_points),
            ("Broker Processing", payload.broker_processing_fee_refi),
            ("Other", payload.other_closing_costs_refi),
        ])
        check(prepaid_interest == calc_prepaid_interest_refi(refi_loan, payload.interest_rate, results.dscr_interest_days_prepaid_at_refi_closing), f"prepaid interest (refi){arv_label}")
        breakdown.add(section_key, f"Prepaid Interest (Refi){arv_label}", prepaid_interest,
               (f"Refi Loan ({fmt_money(refi_loan)}) × {fmt_pct(payload.interest_rate)}/yr ÷ 365 × {results.dscr_interest_days_prepaid_at_refi_closing} days from {results.refi_closing_date.isoformat()} through month end = {fmt_money(prepaid_interest)}"
                if has_buy_closing_date else "No buy closing date → no refi date, no prepaid interest is modelled ($0)"),
               note="The DSCR loan's per-diem interest is collected at closing through the end of the month (365-day year).")
    check(results.notary_refi == ((Decimal("250") if payload.online_notary_fee_refi is None else payload.online_notary_fee_refi) if payload.online_notary_refi else Decimal("0")), "notary (refi)")
    check(results.vacancy_reserve == (payload.rent if payload.vacancy_reserve is None else payload.vacancy_reserve), "vacancy reserve")
    breakdown.add_sum([WIRE, WIRE_LOW, "equity"], "Reserves Escrowed at Refi", results.reserves_total, [
        ("Maintenance Reserve", payload.maintenance_reserve),
        ("Vacancy Reserve", results.vacancy_reserve),
        ("CapEx Reserve", payload.capex_reserve),
    ], note=("Vacancy reserve defaults to one month of rent; type a value to override. " if payload.vacancy_reserve is None else "")
            + "Reserves are held by the lender and returned at exit, so they count as equity.")
    breakdown.add_sum([WIRE, WIRE_LOW, "cash_out"], "HML Payoff at Refi", results.hml_payoff, [
        ("Hard Money Loan", results.hml_amount),
        ("Accrued Interest (1st of month → payoff)", results.hml_interest_accrued_into_refi_payoff),
    ])

    # -- REFINANCE: the wires -------------------------------------------------------
    breakdown.add_sum(["cash_out", CASH_NEEDED], "Total Cash Invested (pre-refi)", results.total_cash_invested, [
        ("Earnest Money Deposit", payload.earnest_money_deposit),
        ("Cash to Close (Buy)", results.cash_to_close_buy),
        ("Seller Tax Credit set aside in the tax bucket", results.seller_tax_credit_set_aside_in_tax_bucket),
        ("Rehab Out-of-Pocket", results.rehab_paid_cash_out_of_pocket),
        ("HML Interest paid monthly", results.hml_interest_paid_monthly),
        ("Holding Costs", results.holding_costs),
        ("Utilities until Rented", results.utilities_until_rented),
        ("Maintenance before Refi", payload.maintenance_before_refi),
        ("Appliances", payload.appliances),
        ("Pre-Refi Rental Income", results.pre_refi_rental_income, "-"),
    ], note="Every dollar actually spent before the refinance, plus the seller tax credit put back into the tax bucket the day after closing; "
            "the rehab cushion is held, not spent, so it is not here.")
    breakdown.add_sum([WIRE, "cash_out"], f"Cash-Out Wire (Refi{refi_date_suffix})", results.cash_out_routi, [
        ("Refi Loan", results.refi_loan_amount),
        ("HML Payoff", results.hml_payoff, "-"),
        ("Closing Costs (Refi)", results.closing_costs_refi_total, "-"),
        ("Prepaid Interest (Refi)", results.prepaid_interest_refi, "-"),
        ("Reserves", results.reserves_total, "-"),
    ], note=("Negative: that much cash is brought to the refi closing table." if results.cash_out_routi < 0
             else "The cash received at the refi closing table, before subtracting what was invested."))
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
        ("Reserves", results.reserves_total, "-"),
    ], note="The loan-dependent fees follow the lower loan; typed-in fees stay as entered.")
    check(results.cash_to_refi_table_conservative == max(Decimal("0"), -results.cash_out_routi_conservative), "cash to refi table (conservative)")
    breakdown.add([WIRE_LOW, CASH_NEEDED], "Cash to Refi Table (Lowest ARV)", results.cash_to_refi_table_conservative,
           (f"Wire ({fmt_money(results.cash_out_routi_conservative)}) is negative → {fmt_money(results.cash_to_refi_table_conservative)} brought to the table"
            if results.cash_to_refi_table_conservative > 0 else f"Wire ({fmt_money(results.cash_out_routi_conservative)}) is not negative → nothing to bring"))
    breakdown.add_sum(["net_profit", "roi", "cash_on_cash", "cash_out"], "Cash Out from Deal", results.cash_out, [
        ("Cash-Out Wire", results.cash_out_routi),
        ("Total Cash Invested", results.total_cash_invested, "-"),
    ], note=("Negative: that much of your own money is still left in the deal after the refi."
             if results.cash_out < 0 else "Positive: the refi returns more than was invested."))

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
        note="The reserves are escrowed at the refi and returned at exit, so they count as equity." if results.reserves_total else None,
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
    breakdown.add_sum(CASH_NEEDED, "Cash Needed", results.total_cash_needed, [
        ("Total Cash Invested", results.total_cash_invested),
        ("Rehab Cushion", payload.rehab_cushion),
        ("Cash to Refi Table (Lowest ARV)", results.cash_to_refi_table_conservative),
    ], note="The single out-of-pocket figure through the refinance: everything spent, plus the cushion held for draws and surprises, plus the cash brought to the refi table if the appraisal comes in at the lowest ARV.")
    return breakdown.to_dict()
