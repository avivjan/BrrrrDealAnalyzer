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


def _default_note(input_value, what: str) -> str:
    return f"Formula default for {what}; type a value to override." if input_value is None else f"{what} as entered."


def explain_brrr(payload, r: BrrrResultsWithIntermediates) -> dict[str, list[dict]]:
    bd = CalcBreakdown()
    dated = r.buy_closing_date is not None
    # The derived dates read as text wherever they are known.
    refi_on = f" on {r.refi_closing_date.isoformat()}" if r.refi_closing_date is not None else ""
    tenant_on = f" (tenant from {r.tenant_occupied_date.isoformat()})" if r.tenant_occupied_date is not None else ""

    # -- monthly cash flow -----------------------------------------------------
    bd.add_sum("cash_flow", "Monthly Operating Expenses", r.operating_expenses, [
        (f"Vacancy {fmt_pct(payload.vacancy_percent)} of rent", r.vacancy),
        (f"Management {fmt_pct(payload.property_managment_fee_precentages_from_rent)} of rent", r.management_fee),
        (f"Maintenance {fmt_pct(payload.maintenance_percent)} of rent", r.maintenance),
        (f"CapEx {fmt_pct(payload.capex_percent_of_rent)} of rent", r.capex),
        ("Taxes ÷ 12", r.monthly_taxes),
        ("Insurance ÷ 12", r.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ])
    bd.add_sum("cash_flow", "Net Operating Income (NOI)", r.net_operating_income, [
        ("Rent", payload.rent),
        ("Operating Expenses", r.operating_expenses, "-"),
    ])
    check(r.refi_loan_amount == r.arv * r.ltv, "refi loan amount")
    bd.add(
        ["cash_out", WIRE, "equity"], "Refi Loan Amount", r.refi_loan_amount,
        f"ARV ({fmt_money(r.arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(r.refi_loan_amount)}",
    )
    check(r.mortgage_payment == calc_mortgage_payment(r.arv, r.ltv, payload.interest_rate, payload.loan_term_years), "mortgage payment")
    bd.add(
        ["cash_flow", "dscr"], "Monthly Mortgage Payment", r.mortgage_payment,
        f"Refi Loan ({fmt_money(r.refi_loan_amount)}) amortized at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(r.mortgage_payment)}",
        note="A 0% loan repays straight-line: loan ÷ number of months." if payload.interest_rate == 0 else None,
    )
    bd.add_sum(["cash_flow", "roi", "cash_on_cash"], "Monthly Cash Flow", r.cash_flow, [
        ("NOI", r.net_operating_income),
        ("Mortgage", r.mortgage_payment, "-"),
    ])

    # -- DSCR ------------------------------------------------------------------
    bd.add_sum("dscr", "PITIA", r.pitia, [
        ("Mortgage", r.mortgage_payment),
        ("Taxes ÷ 12", r.monthly_taxes),
        ("Insurance ÷ 12", r.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ], note="Principal, interest, taxes, insurance and association dues: the monthly debt service the rent must cover.")
    check(r.dscr == (payload.rent / r.pitia if r.pitia else Decimal("0")), "DSCR")
    bd.add(
        "dscr", "DSCR", r.dscr,
        (f"Rent ({fmt_money(payload.rent)}) ÷ PITIA ({fmt_money(r.pitia)}) = {fmt_num(r.dscr)}"
         if r.pitia else "PITIA is $0 → DSCR undefined, reported as 0"),
        unit="ratio",
    )

    # -- BUY: the hard-money stack ---------------------------------------------
    check(r.purchase_loan_amount == r.purchase_price * (1 - payload.down_payment / Decimal("100.0")), "purchase loan")
    bd.add(
        [CLOSE, HM_COST], "Purchase Loan (hard money)", r.purchase_loan_amount,
        f"Purchase ({fmt_money(r.purchase_price)}) × (1 − Down Payment {fmt_pct(payload.down_payment)}) = {fmt_money(r.purchase_loan_amount)}",
    )
    check(r.down_payment_cash == (payload.down_payment / Decimal("100")) * r.purchase_price, "down payment")
    bd.add(
        [CLOSE, CASH_NEEDED], "Down Payment (cash)", r.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(r.purchase_price)}) = {fmt_money(r.down_payment_cash)}",
    )
    check(r.construction_budget == payload.construction_loan_budget_in_thousands * Decimal("1000.0"), "construction budget")
    bd.add_sum([HM_COST, WIRE, "cash_out"], "Hard Money Loan (total principal)", r.hml_amount, [
        ("Purchase Loan", r.purchase_loan_amount),
        ("Construction Budget", r.construction_budget),
    ], note=("A $0 construction budget means the rehab is paid in cash." if r.construction_budget == 0
             else "The lender funds the construction budget; interest accrues on it from day one."))
    check(r.hml_points == payload.HML_points / Decimal("100.0") * r.hml_amount, "HML points")
    bd.add(
        [CLOSE, HM_COST], "HML Points (cash at closing)", r.hml_points,
        f"{fmt_pct(payload.HML_points)} × Hard Money Loan ({fmt_money(r.hml_amount)}) = {fmt_money(r.hml_points)}",
    )
    check(r.hml_per_diem == calc_hml_interest(r.hml_amount, payload.HML_interest_rate, 1), "HML per diem")
    check(r.hml_interest == calc_hml_interest(r.hml_amount, payload.HML_interest_rate, payload.days_until_refi), "HML interest")
    bd.add(
        HM_COST, "HML Interest (until refi)", r.hml_interest,
        f"Hard Money Loan ({fmt_money(r.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 360 = {fmt_money(r.hml_per_diem)} per diem × {payload.days_until_refi} days = {fmt_money(r.hml_interest)}",
        note="Hard money accrues per diem on a 360-day year.",
    )
    check(r.prepaid_interest_buy == calc_hml_interest(r.hml_amount, payload.HML_interest_rate, r.prepaid_days_buy), "prepaid interest (buy)")
    check(r.hml_accrued_interest_at_payoff == calc_hml_interest(r.hml_amount, payload.HML_interest_rate, r.accrued_days_at_payoff), "accrued interest at payoff")
    check(r.hml_monthly_interest_paid == r.hml_interest - r.prepaid_interest_buy - r.hml_accrued_interest_at_payoff, "interest split")
    bd.add(
        CLOSE, "Prepaid Interest (Buy)", r.prepaid_interest_buy,
        (f"Per diem ({fmt_money(r.hml_per_diem)}) × {r.prepaid_days_buy} days from {r.buy_closing_date.isoformat()} through month end = {fmt_money(r.prepaid_interest_buy)}"
         if dated else "No buy closing date → no prepaid interest is modelled ($0)"),
        note=(f"Interest is paid in arrears on the 1st: {r.prepaid_days_buy} days prepaid here, {r.monthly_interest_days} days paid monthly "
              f"({fmt_money(r.hml_monthly_interest_paid)}), {r.accrued_days_at_payoff} days inside the payoff ({fmt_money(r.hml_accrued_interest_at_payoff)})."
              if dated else f"Without a closing date all {r.monthly_interest_days} days of interest are treated as paid monthly ({fmt_money(r.hml_monthly_interest_paid)})."),
    )
    bd.add_sum(HM_COST, "Total Hard Money Cost", r.total_hard_money_cost, [
        ("HML Points", r.hml_points),
        ("HML Interest", r.hml_interest),
        ("Loan Charges (Buy)", payload.loan_charges_buy),
    ])

    # -- BUY: the settlement -----------------------------------------------------
    check(r.recording_transfer_buy == (recording_transfer_default(r.purchase_loan_amount) if payload.recording_transfer_buy is None else payload.recording_transfer_buy), "recording (buy)")
    bd.add(
        CLOSE, "Recording & Transfer (Buy)", r.recording_transfer_buy,
        f"0.55% × Purchase Loan ({fmt_money(r.purchase_loan_amount)}) + $250 = {fmt_money(r.recording_transfer_buy)}"
        if payload.recording_transfer_buy is None else f"As entered: {fmt_money(r.recording_transfer_buy)}",
        note=_default_note(payload.recording_transfer_buy, "government recording and transfer charges"),
    )
    check(r.title_escrow_buy == (title_escrow_buy_default(payload.title_mode_buy, r.purchase_price) if payload.title_escrow_buy is None else payload.title_escrow_buy), "title (buy)")
    bd.add(
        CLOSE, "Title & Escrow (Buy)", r.title_escrow_buy,
        (f"Title mode '{payload.title_mode_buy}' at a {fmt_money(r.purchase_price)} price → {fmt_money(r.title_escrow_buy)}"
         if payload.title_escrow_buy is None else f"As entered: {fmt_money(r.title_escrow_buy)}"),
        note=_default_note(payload.title_escrow_buy, "title, escrow and settlement charges"),
    )
    check(r.notary_buy == (Decimal("250") if payload.online_notary_buy else Decimal("0")), "notary (buy)")
    bd.add(CLOSE, "Online Notary (Buy)", r.notary_buy, "Remote closing → $250" if payload.online_notary_buy else "Not a remote closing → $0")
    bd.add_sum([CLOSE, CASH_NEEDED], "Closing Costs (Buy)", r.closing_costs_buy_total, [
        ("Loan Charges", payload.loan_charges_buy),
        ("Recording & Transfer", r.recording_transfer_buy),
        ("Title & Escrow", r.title_escrow_buy),
        ("Online Notary", r.notary_buy),
        ("Other", payload.other_closing_costs_buy),
    ])
    if dated:
        check(r.seller_paid_current_year_taxes == (payload.seller_paid_current_year_taxes if payload.seller_paid_current_year_taxes is not None else r.buy_closing_date.month == 12), "seller paid taxes")
        check(r.seller_tax_credit == calc_seller_tax_credit(payload.annual_property_taxes, r.buy_closing_date, r.seller_paid_current_year_taxes), "seller tax credit")
        tax_formula = (
            f"Seller already paid this year's taxes → buyer credits the seller for {r.buy_closing_date.isoformat()} through Dec 31: {fmt_money(r.seller_tax_credit)}"
            if r.seller_paid_current_year_taxes else
            f"Taxes ({fmt_money(payload.annual_property_taxes)}) × seller's days (Jan 1 to the day before {r.buy_closing_date.isoformat()}) ÷ days in the year = {fmt_money(r.seller_tax_credit)}"
        )
    else:
        check(r.seller_paid_current_year_taxes is None and r.seller_tax_credit == 0, "seller tax credit without date")
        tax_formula = "No buy closing date → no tax proration is modelled ($0)"
    bd.add(CLOSE, "Seller Tax Credit", r.seller_tax_credit, tax_formula,
           note="Taxes are billed in November for the calendar year; positive = the seller credits the buyer on the settlement statement.")
    bd.add_sum([CLOSE, CASH_NEEDED], "Cash to Close (Buy)", r.cash_to_close_buy, [
        ("Down Payment", r.down_payment_cash),
        ("Closing Costs (Buy)", r.closing_costs_buy_total),
        ("HML Points", r.hml_points),
        ("Prepaid Interest (Buy)", r.prepaid_interest_buy),
        ("Seller Tax Credit", r.seller_tax_credit, "-"),
        ("Earnest Money Deposit", payload.earnest_money_deposit, "-"),
    ], note="The wire to the title company on purchase day. Earnest money is already in escrow, so it is credited here.")

    # -- REHAB: draws -------------------------------------------------------------
    check(r.rehab_contingency == r.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    bd.add_sum(["stolen_money", "cash_out"], "Actual Rehab Cost (with contingency)", r.rehab_cost, [
        ("Rehab", r.rehab_cost_base),
        (f"Contingency {fmt_pct(payload.rehab_contingency_percent)}", r.rehab_contingency),
    ])
    bd.add_sum("stolen_money", "Stolen Money (draw spread)", r.stolen_money, [
        ("Construction Budget", r.construction_budget),
        ("Actual Rehab Cost", r.rehab_cost, "-"),
    ], note=("Positive: the lender's draws exceed the spend, so that much comes out before the refi."
             if r.stolen_money > 0 else "Negative or zero: the investor funds the rehab beyond the budget."))
    check(r.rehab_cash == r.rehab_cost - r.construction_budget, "rehab cash")
    bd.add(
        [CASH_NEEDED, "cash_out"], "Rehab Out-of-Pocket", r.rehab_cash,
        f"Actual Rehab ({fmt_money(r.rehab_cost)}) − Construction Budget ({fmt_money(r.construction_budget)}) = {fmt_money(r.rehab_cash)}",
        note="Negative = cash returned through draws, which reduces what is invested.",
    )

    # -- RENT / HOLDING ------------------------------------------------------------
    check(r.holding_costs == calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi), "holding costs")
    bd.add(
        CASH_NEEDED, "Holding Costs (until refi)", r.holding_costs,
        f"(Taxes ({fmt_money(payload.annual_property_taxes)}) + Insurance ({fmt_money(payload.annual_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) × 12) × {payload.days_until_refi} days ÷ 360 = {fmt_money(r.holding_costs)}",
    )
    check(r.utilities_until_rented == payload.monthly_utilities_until_rented * Decimal(payload.days_until_rented) / DAYS_PER_MONTH, "utilities until rented")
    bd.add(
        CASH_NEEDED, "Utilities until Rented", r.utilities_until_rented,
        f"{fmt_money(payload.monthly_utilities_until_rented)}/mo × {payload.days_until_rented} days ÷ 30 = {fmt_money(r.utilities_until_rented)}" + tenant_on,
    )
    check(r.days_rented_before_refi == max(0, int(payload.days_until_refi) - int(payload.days_until_rented)), "days rented")
    check(r.pre_refi_rental_income == payload.rent * Decimal(r.days_rented_before_refi) / DAYS_PER_MONTH, "pre-refi rent")
    bd.add(
        [CASH_NEEDED, "cash_out"], "Pre-Refi Rental Income", r.pre_refi_rental_income,
        f"Rent ({fmt_money(payload.rent)}) × {r.days_rented_before_refi} days rented before the refi ÷ 30 = {fmt_money(r.pre_refi_rental_income)}",
        note="Rent collected between tenant placement and the refi offsets the holding costs." if r.days_rented_before_refi else "The tenant is placed at or after the refi, so no rent offsets the holding costs.",
    )

    # -- REFINANCE: settlement lines -----------------------------------------------
    for key, loan, lines, label in (
        (WIRE, r.refi_loan_amount,
         (r.broker_points_refi, r.recording_transfer_refi, r.title_escrow_refi, r.closing_costs_refi_total, r.prepaid_interest_refi), ""),
        (WIRE_LOW, r.conservative_refi_loan_amount,
         (r.broker_points_refi_conservative, r.recording_transfer_refi_conservative, r.title_escrow_refi_conservative,
          r.closing_costs_refi_total_conservative, r.prepaid_interest_refi_conservative), " (Lowest ARV)"),
    ):
        broker, recording, title, total, prepaid = lines
        check(broker == payload.refi_points / Decimal("100") * loan, f"broker points{label}")
        bd.add(key, f"Broker Points (Refi){label}", broker, f"{fmt_pct(payload.refi_points)} × Refi Loan ({fmt_money(loan)}) = {fmt_money(broker)}")
        check(recording == (recording_transfer_default(loan) if payload.recording_transfer_refi is None else payload.recording_transfer_refi), f"recording (refi){label}")
        bd.add(key, f"Recording & Transfer (Refi){label}", recording,
               f"0.55% × Refi Loan ({fmt_money(loan)}) + $250 = {fmt_money(recording)}" if payload.recording_transfer_refi is None else f"As entered: {fmt_money(recording)}",
               note=_default_note(payload.recording_transfer_refi, "government recording and transfer charges"))
        check(title == (title_escrow_refi_default(loan) if payload.title_escrow_refi is None else payload.title_escrow_refi), f"title (refi){label}")
        bd.add(key, f"Title & Escrow (Refi){label}", title,
               f"$800 + 0.45% × Refi Loan ({fmt_money(loan)}) = {fmt_money(title)}" if payload.title_escrow_refi is None else f"As entered: {fmt_money(title)}",
               note=_default_note(payload.title_escrow_refi, "title, escrow and settlement charges"))
        bd.add_sum(key, f"Closing Costs (Refi){label}", total, [
            ("Loan Charges", payload.loan_charges_refi),
            ("Recording & Transfer", recording),
            ("Title & Escrow", title),
            ("Online Notary", r.notary_refi),
            ("Appraisal", payload.appraisal_fee),
            ("Survey", payload.survey_fee),
            ("Underwriting", payload.refi_underwriting_fee),
            ("Broker Points", broker),
            ("Broker Processing", payload.broker_processing_fee_refi),
            ("Other", payload.other_closing_costs_refi),
        ])
        check(prepaid == calc_prepaid_interest_refi(loan, payload.interest_rate, r.prepaid_days_refi), f"prepaid interest (refi){label}")
        bd.add(key, f"Prepaid Interest (Refi){label}", prepaid,
               (f"Refi Loan ({fmt_money(loan)}) × {fmt_pct(payload.interest_rate)}/yr ÷ 365 × {r.prepaid_days_refi} days from {r.refi_closing_date.isoformat()} through month end = {fmt_money(prepaid)}"
                if dated else "No buy closing date → no refi date, no prepaid interest is modelled ($0)"),
               note="The DSCR loan's per-diem interest is collected at closing through the end of the month (365-day year).")
    check(r.notary_refi == (Decimal("250") if payload.online_notary_refi else Decimal("0")), "notary (refi)")
    check(r.vacancy_reserve == (payload.rent if payload.vacancy_reserve is None else payload.vacancy_reserve), "vacancy reserve")
    bd.add_sum([WIRE, WIRE_LOW, "equity"], "Reserves Escrowed at Refi", r.reserves_total, [
        ("Maintenance Reserve", payload.maintenance_reserve),
        ("Vacancy Reserve", r.vacancy_reserve),
        ("CapEx Reserve", payload.capex_reserve),
    ], note=("Vacancy reserve defaults to one month of rent; type a value to override. " if payload.vacancy_reserve is None else "")
            + "Reserves are held by the lender and returned at exit, so they count as equity.")
    bd.add_sum([WIRE, WIRE_LOW, "cash_out"], "HML Payoff at Refi", r.hml_payoff, [
        ("Hard Money Loan", r.hml_amount),
        ("Accrued Interest (1st of month → payoff)", r.hml_accrued_interest_at_payoff),
    ])

    # -- REFINANCE: the wires -------------------------------------------------------
    bd.add_sum(["cash_out", CASH_NEEDED], "Total Cash Invested (pre-refi)", r.total_cash_invested, [
        ("Earnest Money Deposit", payload.earnest_money_deposit),
        ("Cash to Close (Buy)", r.cash_to_close_buy),
        ("Rehab Out-of-Pocket", r.rehab_cash),
        ("HML Interest paid monthly", r.hml_monthly_interest_paid),
        ("Holding Costs", r.holding_costs),
        ("Utilities until Rented", r.utilities_until_rented),
        ("Maintenance before Refi", payload.maintenance_before_refi),
        ("Appliances", payload.appliances),
        ("Pre-Refi Rental Income", r.pre_refi_rental_income, "-"),
    ], note="Every dollar actually spent before the refinance; the rehab cushion is held, not spent, so it is not here.")
    bd.add_sum([WIRE, "cash_out"], f"Cash-Out Wire (Refi{refi_on})", r.cash_out_routi, [
        ("Refi Loan", r.refi_loan_amount),
        ("HML Payoff", r.hml_payoff, "-"),
        ("Closing Costs (Refi)", r.closing_costs_refi_total, "-"),
        ("Prepaid Interest (Refi)", r.prepaid_interest_refi, "-"),
        ("Reserves", r.reserves_total, "-"),
    ], note=("Negative: that much cash is brought to the refi closing table." if r.cash_out_routi < 0
             else "The cash received at the refi closing table, before subtracting what was invested."))
    check(r.lowest_arv == (lowest_arv_default(r.arv) if payload.lowest_arv_in_thousands is None else payload.lowest_arv_in_thousands * Decimal("1000.0")), "lowest ARV")
    bd.add(WIRE_LOW, "Lowest ARV (stress test)", r.lowest_arv,
           f"90% × ARV ({fmt_money(r.arv)}) = {fmt_money(r.lowest_arv)}" if payload.lowest_arv_in_thousands is None else f"As entered: {fmt_money(r.lowest_arv)}",
           note=_default_note(payload.lowest_arv_in_thousands, "the lowest appraisal to plan for") + " The baseline ARV is untouched.")
    check(r.conservative_refi_loan_amount == r.lowest_arv * r.ltv, "conservative refi loan")
    bd.add(WIRE_LOW, "Refi Loan (Lowest ARV)", r.conservative_refi_loan_amount,
           f"Lowest ARV ({fmt_money(r.lowest_arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(r.conservative_refi_loan_amount)}")
    bd.add_sum(WIRE_LOW, "Cash-Out Wire (Lowest ARV)", r.cash_out_routi_conservative, [
        ("Refi Loan (Lowest ARV)", r.conservative_refi_loan_amount),
        ("HML Payoff", r.hml_payoff, "-"),
        ("Closing Costs (Refi, Lowest ARV)", r.closing_costs_refi_total_conservative, "-"),
        ("Prepaid Interest (Refi, Lowest ARV)", r.prepaid_interest_refi_conservative, "-"),
        ("Reserves", r.reserves_total, "-"),
    ], note="The loan-dependent fees follow the lower loan; typed-in fees stay as entered.")
    check(r.cash_to_refi_table_conservative == max(Decimal("0"), -r.cash_out_routi_conservative), "cash to refi table (conservative)")
    bd.add(WIRE_LOW, "Cash to Refi Table (Lowest ARV)", r.cash_to_refi_table_conservative,
           (f"Wire ({fmt_money(r.cash_out_routi_conservative)}) is negative → {fmt_money(r.cash_to_refi_table_conservative)} brought to the table"
            if r.cash_to_refi_table_conservative > 0 else f"Wire ({fmt_money(r.cash_out_routi_conservative)}) is not negative → nothing to bring"))
    bd.add_sum(WIRE_LOW, "Cash Needed (Lowest ARV)", r.cash_needed_conservative, [
        ("Total Cash Invested", r.total_cash_invested),
        ("Rehab Cushion", payload.rehab_cushion),
        ("Cash to Refi Table (Lowest ARV)", r.cash_to_refi_table_conservative),
    ])
    bd.add_sum(["net_profit", "roi", "cash_on_cash", "cash_out"], "Cash Out from Deal", r.cash_out, [
        ("Cash-Out Wire", r.cash_out_routi),
        ("Total Cash Invested", r.total_cash_invested, "-"),
    ], note=("Negative: that much of your own money is still left in the deal after the refi."
             if r.cash_out < 0 else "Positive: the refi returns more than was invested."))

    # -- returns ---------------------------------------------------------------
    check(r.cash_on_cash == calc_cash_on_cash(r.cash_out, r.cash_flow), "cash on cash")
    if r.cash_out >= 0:
        coc_formula = f"Cash Out ({fmt_money(r.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif r.cash_flow <= 0:
        coc_formula = f"Cash Flow ({fmt_money(r.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        coc_formula = f"Annual Cash Flow ({fmt_money(r.cash_flow * 12)}) ÷ |Cash Out| ({fmt_money(abs(r.cash_out))}) × 100 = {fmt_pct(r.cash_on_cash)}"
    bd.add("cash_on_cash", "Cash on Cash", r.cash_on_cash, coc_formula, unit="pct")

    check(r.equity == r.arv * (1 - r.ltv) + r.reserves_total, "equity")
    bd.add(
        ["net_profit", "roi", "equity"], "Equity (post-refi)", r.equity,
        f"ARV ({fmt_money(r.arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Reserves ({fmt_money(r.reserves_total)}) = {fmt_money(r.equity)}",
        note="The reserves are escrowed at the refi and returned at exit, so they count as equity." if r.reserves_total else None,
    )
    bd.add_sum(["net_profit", "roi"], "Net Profit", r.net_profit, [
        ("Equity", r.equity),
        ("Cash Out", r.cash_out),
    ])
    check(r.roi == calc_roi(r.cash_out, r.cash_flow, r.net_profit), "ROI")
    if r.cash_out >= 0:
        roi_formula = f"Cash Out ({fmt_money(r.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif r.cash_flow <= 0:
        roi_formula = f"Cash Flow ({fmt_money(r.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        roi_formula = f"(Annual Cash Flow ({fmt_money(r.cash_flow * 12)}) + Net Profit ({fmt_money(r.net_profit)})) ÷ |Cash Out| ({fmt_money(abs(r.cash_out))}) × 100 = {fmt_pct(r.roi)}"
    bd.add("roi", "ROI", r.roi, roi_formula, unit="pct")

    # -- cash needed -----------------------------------------------------------
    check(r.refi_shortfall == max(Decimal("0"), -r.cash_out_routi), "refi shortfall")
    if r.refi_shortfall > 0:
        bd.add(
            CASH_NEEDED, "Refi Shortfall (cash to refi table)", r.refi_shortfall,
            f"Refi wire ({fmt_money(r.cash_out_routi)}) is negative → {fmt_money(r.refi_shortfall)} brought to the refi closing table",
            note="The new loan does not cover the hard-money payoff plus refi costs and reserves.",
        )
    bd.add_sum(CASH_NEEDED, "Cash Needed", r.total_cash_needed, [
        ("Total Cash Invested", r.total_cash_invested),
        ("Rehab Cushion", payload.rehab_cushion),
        ("Refi Shortfall", r.refi_shortfall),
    ], note="The single out-of-pocket figure through the refinance: everything spent, plus the cushion held for draws and surprises, plus any cash brought to the refi table.")
    return bd.to_dict()
