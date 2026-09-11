"""Explain a `BrrrResultsWithIntermediates`: the step-by-step narrative behind every BRRRR headline metric.

Companion to `compute_brrr_with_intermediates` (`BL/analyze/analyzeBRRR.py`). Every value comes
from the results_w_intermediates record; every equation stated in a formula is first verified
against that record (`check`, or the fold inside `add_sum`), so the narrative
cannot drift from the math. `tests/test_explain.py` additionally fails if a
`BrrrResultsWithIntermediates` field is never read here.

Sum-type steps list their terms in the same left-to-right order the
calculator adds them (see `deal_math.py`); that is what lets the guard use
exact equality on unrounded Decimals.
"""

from decimal import Decimal

from BL.analyze.brrr_results_with_intermediates import BrrrResultsWithIntermediates
from BL.analyze.common.calc_breakdown import CalcBreakdown, check, fmt_money, fmt_pct, fmt_num
from BL.analyze.common.deal_math import (
    get_HML_amount,
    calc_HML_interest_in_cash,
    calc_holding_costs,
    calc_mortgage_payment,
    calc_cash_on_cash,
    calc_roi,
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
    ("cash_out", "Cash Out from Deal", "money"),
    ("total_cash_needed_for_deal", "Total Cash Needed", "money"),
    ("total_cash_needed_for_deal_with_buffer", "Cash Needed (Buffered)", "money"),
]

CASH_NEEDED = ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"]


def explain_brrr(payload, results_w_intermediates: BrrrResultsWithIntermediates) -> dict[str, list[dict]]:
    bd = CalcBreakdown()
    hm = bool(payload.use_HM_for_rehab)

    # -- rehab basis -----------------------------------------------------------
    check(results_w_intermediates.rehab_contingency == results_w_intermediates.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    bd.add_sum("cash_out", "Rehab Cost (with contingency)", results_w_intermediates.rehab_cost, [
        ("Rehab", results_w_intermediates.rehab_cost_base),
        (f"Contingency {fmt_pct(payload.rehab_contingency_percent)}", results_w_intermediates.rehab_contingency),
    ])

    # -- monthly cash flow -----------------------------------------------------
    bd.add_sum("cash_flow", "Monthly Operating Expenses", results_w_intermediates.operating_expenses, [
        (f"Vacancy {fmt_pct(payload.vacancy_percent)} of rent", results_w_intermediates.vacancy),
        (f"Management {fmt_pct(payload.property_managment_fee_precentages_from_rent)} of rent", results_w_intermediates.management_fee),
        (f"Maintenance {fmt_pct(payload.maintenance_percent)} of rent", results_w_intermediates.maintenance),
        (f"CapEx {fmt_pct(payload.capex_percent_of_rent)} of rent", results_w_intermediates.capex),
        ("Taxes ÷ 12", results_w_intermediates.monthly_taxes),
        ("Insurance ÷ 12", results_w_intermediates.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ])
    bd.add_sum("cash_flow", "Net Operating Income (NOI)", results_w_intermediates.net_operating_income, [
        ("Rent", payload.rent),
        ("Operating Expenses", results_w_intermediates.operating_expenses, "-"),
    ])
    check(results_w_intermediates.loan_amount == results_w_intermediates.arv * results_w_intermediates.ltv, "refi loan amount")
    bd.add(
        ["cash_out", "equity"], "Refi Loan Amount", results_w_intermediates.loan_amount,
        f"ARV ({fmt_money(results_w_intermediates.arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(results_w_intermediates.loan_amount)}",
    )
    check(results_w_intermediates.mortgage_payment == calc_mortgage_payment(results_w_intermediates.arv, results_w_intermediates.ltv, payload.interest_rate, payload.loan_term_years), "mortgage payment")
    bd.add(
        ["cash_flow", "dscr"], "Monthly Mortgage Payment", results_w_intermediates.mortgage_payment,
        f"Refi Loan ({fmt_money(results_w_intermediates.loan_amount)}) amortized at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(results_w_intermediates.mortgage_payment)}",
        note="A 0% loan repays straight-line: loan ÷ number of months." if payload.interest_rate == 0 else None,
    )
    bd.add_sum(["cash_flow", "roi", "cash_on_cash"], "Monthly Cash Flow", results_w_intermediates.cash_flow, [
        ("NOI", results_w_intermediates.net_operating_income),
        ("Mortgage", results_w_intermediates.mortgage_payment, "-"),
    ])

    # -- DSCR ------------------------------------------------------------------
    bd.add_sum("dscr", "PITIA", results_w_intermediates.pitia, [
        ("Mortgage", results_w_intermediates.mortgage_payment),
        ("Taxes ÷ 12", results_w_intermediates.monthly_taxes),
        ("Insurance ÷ 12", results_w_intermediates.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ], note="Principal, interest, taxes, insurance and association dues: the monthly debt service the rent must cover.")
    check(results_w_intermediates.dscr == (payload.rent / results_w_intermediates.pitia if results_w_intermediates.pitia else Decimal("0")), "DSCR")
    bd.add(
        "dscr", "DSCR", results_w_intermediates.dscr,
        (f"Rent ({fmt_money(payload.rent)}) ÷ PITIA ({fmt_money(results_w_intermediates.pitia)}) = {fmt_num(results_w_intermediates.dscr)}"
         if results_w_intermediates.pitia else "PITIA is $0 → DSCR undefined, reported as 0"),
        unit="ratio",
    )

    # -- cash out at the refinance ---------------------------------------------
    check(results_w_intermediates.hml_amount == get_HML_amount(results_w_intermediates.purchase_price, payload.down_payment, results_w_intermediates.rehab_cost, hm), "HML payoff")
    bd.add(
        "cash_out", "HML Payoff at Refi", results_w_intermediates.hml_amount,
        (f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(results_w_intermediates.purchase_price)}) + Rehab ({fmt_money(results_w_intermediates.rehab_cost)}) = {fmt_money(results_w_intermediates.hml_amount)}"
         if hm else
         f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(results_w_intermediates.purchase_price)}) = {fmt_money(results_w_intermediates.hml_amount)}"),
        note=("Hard money funds the rehab, so the whole stack is paid off at the refi."
              if hm else "Rehab is paid in cash, so only the purchase loan is paid off at the refi."),
    )
    check(results_w_intermediates.down_payment_cash == (payload.down_payment / Decimal("100")) * results_w_intermediates.purchase_price, "down payment")
    bd.add_sum("cash_out", "Total Cash Invested (pre-refi)", results_w_intermediates.total_cash_invested, [
        ("Down Payment", results_w_intermediates.down_payment_cash),
        ("Closing", results_w_intermediates.closing_costs_buy),
        ("HML Points", results_w_intermediates.hml_points),
        ("Rehab Out-of-Pocket", results_w_intermediates.rehab_cash),
        ("HML Interest", results_w_intermediates.hml_interest),
        ("Holding", results_w_intermediates.holding_costs),
    ])
    check(results_w_intermediates.cash_out_routi == results_w_intermediates.loan_amount - results_w_intermediates.hml_amount - results_w_intermediates.closing_costs_refi - results_w_intermediates.refi_points - results_w_intermediates.cash_reserve, "refi wire")
    bd.add_sum(["net_profit", "roi", "cash_on_cash", "cash_out"], "Cash Out from Deal", results_w_intermediates.cash_out, [
        ("Refi Loan", results_w_intermediates.loan_amount),
        ("HML Payoff", results_w_intermediates.hml_amount, "-"),
        ("Refi Closing", results_w_intermediates.closing_costs_refi, "-"),
        ("Refi Points", results_w_intermediates.refi_points, "-"),
        ("Cash Reserve", results_w_intermediates.cash_reserve, "-"),
        ("Total Cash Invested", results_w_intermediates.total_cash_invested, "-"),
    ], note=("Negative: that much of your own money is still left in the deal after the refi."
             if results_w_intermediates.cash_out < 0 else "Positive: the refi returns more than was invested."))

    # -- returns ---------------------------------------------------------------
    check(results_w_intermediates.cash_on_cash == calc_cash_on_cash(results_w_intermediates.cash_out, results_w_intermediates.cash_flow), "cash on cash")
    if results_w_intermediates.cash_out >= 0:
        coc_formula = f"Cash Out ({fmt_money(results_w_intermediates.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif results_w_intermediates.cash_flow <= 0:
        coc_formula = f"Cash Flow ({fmt_money(results_w_intermediates.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        coc_formula = f"Annual Cash Flow ({fmt_money(results_w_intermediates.cash_flow * 12)}) ÷ |Cash Out| ({fmt_money(abs(results_w_intermediates.cash_out))}) × 100 = {fmt_pct(results_w_intermediates.cash_on_cash)}"
    bd.add("cash_on_cash", "Cash on Cash", results_w_intermediates.cash_on_cash, coc_formula, unit="pct")

    check(results_w_intermediates.equity == results_w_intermediates.arv * (1 - results_w_intermediates.ltv) + results_w_intermediates.cash_reserve, "equity")
    bd.add(
        ["net_profit", "roi", "equity"], "Equity (post-refi)", results_w_intermediates.equity,
        f"ARV ({fmt_money(results_w_intermediates.arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Cash Reserve ({fmt_money(results_w_intermediates.cash_reserve)}) = {fmt_money(results_w_intermediates.equity)}",
        note="The cash reserve is escrowed at the refi and returned at exit, so it counts as equity." if results_w_intermediates.cash_reserve else None,
    )
    bd.add_sum(["net_profit", "roi"], "Net Profit", results_w_intermediates.net_profit, [
        ("Equity", results_w_intermediates.equity),
        ("Cash Out", results_w_intermediates.cash_out),
    ])
    check(results_w_intermediates.roi == calc_roi(results_w_intermediates.cash_out, results_w_intermediates.cash_flow, results_w_intermediates.net_profit), "ROI")
    if results_w_intermediates.cash_out >= 0:
        roi_formula = f"Cash Out ({fmt_money(results_w_intermediates.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif results_w_intermediates.cash_flow <= 0:
        roi_formula = f"Cash Flow ({fmt_money(results_w_intermediates.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        roi_formula = f"(Annual Cash Flow ({fmt_money(results_w_intermediates.cash_flow * 12)}) + Net Profit ({fmt_money(results_w_intermediates.net_profit)})) ÷ |Cash Out| ({fmt_money(abs(results_w_intermediates.cash_out))}) × 100 = {fmt_pct(results_w_intermediates.roi)}"
    bd.add("roi", "ROI", results_w_intermediates.roi, roi_formula, unit="pct")

    # -- total cash needed -----------------------------------------------------
    bd.add(
        CASH_NEEDED, "Down Payment (cash)", results_w_intermediates.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(results_w_intermediates.purchase_price)}) = {fmt_money(results_w_intermediates.down_payment_cash)}",
    )
    bd.add(CASH_NEEDED, "Closing Costs (Buy)", results_w_intermediates.closing_costs_buy, f"From the inputs: {fmt_money(results_w_intermediates.closing_costs_buy)}")
    check(results_w_intermediates.hml_points == payload.HML_points / Decimal("100.0") * results_w_intermediates.hml_amount, "HML points")
    bd.add(
        CASH_NEEDED, "HML Points (cash)", results_w_intermediates.hml_points,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(results_w_intermediates.hml_amount)}) = {fmt_money(results_w_intermediates.hml_points)}",
    )
    check(results_w_intermediates.rehab_cash == results_w_intermediates.rehab_cost * (1 - int(hm)), "rehab cash")
    bd.add(
        CASH_NEEDED, "Rehab Cash (out-of-pocket)", results_w_intermediates.rehab_cash,
        (f"Rehab ({fmt_money(results_w_intermediates.rehab_cost)}) is financed by hard money → {fmt_money(results_w_intermediates.rehab_cash)} out of pocket"
         if hm else f"Rehab ({fmt_money(results_w_intermediates.rehab_cost)}) paid in cash = {fmt_money(results_w_intermediates.rehab_cash)}"),
    )
    check(results_w_intermediates.hml_interest == calc_HML_interest_in_cash(results_w_intermediates.purchase_price, payload.down_payment, results_w_intermediates.rehab_cost, payload.days_until_refi, payload.HML_interest_rate, hm), "HML interest")
    bd.add(
        "total_cash_needed_for_deal", "HML Interest (cash, until refi)", results_w_intermediates.hml_interest,
        f"HML Amount ({fmt_money(results_w_intermediates.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr × {payload.days_until_refi} days ÷ 360 = {fmt_money(results_w_intermediates.hml_interest)}",
        note="Hard money accrues per diem on a 360-day year.",
    )
    check(results_w_intermediates.holding_costs == calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi), "holding costs")
    bd.add(
        "total_cash_needed_for_deal", "Holding Costs (until refi)", results_w_intermediates.holding_costs,
        f"(Taxes ({fmt_money(payload.annual_property_taxes)}) + Insurance ({fmt_money(payload.annual_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) × 12) × {payload.days_until_refi} days ÷ 360 = {fmt_money(results_w_intermediates.holding_costs)}",
    )
    check(results_w_intermediates.refi_shortfall == max(Decimal("0"), -results_w_intermediates.cash_out_routi), "refi shortfall")
    shortfall = []
    if results_w_intermediates.refi_shortfall > 0:
        bd.add(
            CASH_NEEDED, "Refi Shortfall (cash to refi table)", results_w_intermediates.refi_shortfall,
            f"Refi wire ({fmt_money(results_w_intermediates.cash_out_routi)}) is negative → {fmt_money(results_w_intermediates.refi_shortfall)} brought to the refi closing table",
            note="The new loan does not cover the hard-money payoff plus refi costs and reserve.",
        )
        shortfall = [("Refi Shortfall", results_w_intermediates.refi_shortfall)]
    bd.add_sum("total_cash_needed_for_deal", "Total Cash Needed", results_w_intermediates.total_cash_needed, [
        ("Down Payment", results_w_intermediates.down_payment_cash),
        ("Closing", results_w_intermediates.closing_costs_buy),
        ("HML Points", results_w_intermediates.hml_points),
        ("Rehab Cash", results_w_intermediates.rehab_cash),
        ("HML Interest", results_w_intermediates.hml_interest),
        ("Holding", results_w_intermediates.holding_costs),
        *shortfall,
    ])
    check(results_w_intermediates.buffered_closing == results_w_intermediates.closing_costs_buy * Decimal("1.1"), "closing buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "Closing × 1.1 buffer", results_w_intermediates.buffered_closing,
        f"Closing ({fmt_money(results_w_intermediates.closing_costs_buy)}) × 1.1 = {fmt_money(results_w_intermediates.buffered_closing)}",
    )
    check(results_w_intermediates.buffered_interest == results_w_intermediates.hml_interest * Decimal("1.5"), "interest buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "HML Interest × 1.5 buffer", results_w_intermediates.buffered_interest,
        f"HML Interest ({fmt_money(results_w_intermediates.hml_interest)}) × 1.5 = {fmt_money(results_w_intermediates.buffered_interest)}",
        note="The ×1.5 covers delays in permits, rehab or tenant placement.",
    )
    check(results_w_intermediates.buffered_holding == results_w_intermediates.holding_costs * Decimal("1.5"), "holding buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "Holding × 1.5 buffer", results_w_intermediates.buffered_holding,
        f"Holding ({fmt_money(results_w_intermediates.holding_costs)}) × 1.5 = {fmt_money(results_w_intermediates.buffered_holding)}",
    )
    check(results_w_intermediates.rehab_float == Decimal("0.1") * results_w_intermediates.rehab_cost, "rehab float")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "Rehab float buffer (10% of rehab)", results_w_intermediates.rehab_float,
        f"10% × Rehab ({fmt_money(results_w_intermediates.rehab_cost)}) = {fmt_money(results_w_intermediates.rehab_float)}",
        note="Kept on hand for draws and deposits even when hard money funds the rehab.",
    )
    bd.add_sum("total_cash_needed_for_deal_with_buffer", "Total Cash Needed (Buffered)", results_w_intermediates.total_cash_needed_with_buffer, [
        ("Down Payment", results_w_intermediates.down_payment_cash),
        ("Closing × 1.1", results_w_intermediates.buffered_closing),
        ("HML Points", results_w_intermediates.hml_points),
        ("Rehab Cash", results_w_intermediates.rehab_cash),
        ("Rehab Float", results_w_intermediates.rehab_float),
        ("HML Interest × 1.5", results_w_intermediates.buffered_interest),
        ("Holding × 1.5", results_w_intermediates.buffered_holding),
        *shortfall,
    ])
    return bd.to_dict()
