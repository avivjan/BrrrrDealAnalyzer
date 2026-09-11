"""Explain a `BrrrCalc`: the step-by-step narrative behind every BRRRR headline metric.

Companion to `compute_brrr` (`BL/analyze/analyzeBRRR.py`). Every value comes
from the calc record; every equation stated in a formula is first verified
against that record (`check`, or the fold inside `add_sum`), so the narrative
cannot drift from the math. `tests/test_explain.py` additionally fails if a
`BrrrCalc` field is never read here.

Sum-type steps list their terms in the same left-to-right order the
calculator adds them (see `deal_math.py`); that is what lets the guard use
exact equality on unrounded Decimals.
"""

from decimal import Decimal

from BL.analyze.brrr_calc import BrrrCalc
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


def explain_brrr(payload, calc: BrrrCalc) -> dict[str, list[dict]]:
    bd = CalcBreakdown()
    hm = bool(payload.use_HM_for_rehab)

    # -- rehab basis -----------------------------------------------------------
    check(calc.rehab_contingency == calc.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    bd.add_sum("cash_out", "Rehab Cost (with contingency)", calc.rehab_cost, [
        ("Rehab", calc.rehab_cost_base),
        (f"Contingency {fmt_pct(payload.rehab_contingency_percent)}", calc.rehab_contingency),
    ])

    # -- monthly cash flow -----------------------------------------------------
    bd.add_sum("cash_flow", "Monthly Operating Expenses", calc.operating_expenses, [
        (f"Vacancy {fmt_pct(payload.vacancy_percent)} of rent", calc.vacancy),
        (f"Management {fmt_pct(payload.property_managment_fee_precentages_from_rent)} of rent", calc.management_fee),
        (f"Maintenance {fmt_pct(payload.maintenance_percent)} of rent", calc.maintenance),
        (f"CapEx {fmt_pct(payload.capex_percent_of_rent)} of rent", calc.capex),
        ("Taxes ÷ 12", calc.monthly_taxes),
        ("Insurance ÷ 12", calc.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ])
    bd.add_sum("cash_flow", "Net Operating Income (NOI)", calc.net_operating_income, [
        ("Rent", payload.rent),
        ("Operating Expenses", calc.operating_expenses, "-"),
    ])
    check(calc.loan_amount == calc.arv * calc.ltv, "refi loan amount")
    bd.add(
        ["cash_out", "equity"], "Refi Loan Amount", calc.loan_amount,
        f"ARV ({fmt_money(calc.arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(calc.loan_amount)}",
    )
    check(calc.mortgage_payment == calc_mortgage_payment(calc.arv, calc.ltv, payload.interest_rate, payload.loan_term_years), "mortgage payment")
    bd.add(
        ["cash_flow", "dscr"], "Monthly Mortgage Payment", calc.mortgage_payment,
        f"Refi Loan ({fmt_money(calc.loan_amount)}) amortized at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(calc.mortgage_payment)}",
        note="A 0% loan repays straight-line: loan ÷ number of months." if payload.interest_rate == 0 else None,
    )
    bd.add_sum(["cash_flow", "roi", "cash_on_cash"], "Monthly Cash Flow", calc.cash_flow, [
        ("NOI", calc.net_operating_income),
        ("Mortgage", calc.mortgage_payment, "-"),
    ])

    # -- DSCR ------------------------------------------------------------------
    bd.add_sum("dscr", "PITIA", calc.pitia, [
        ("Mortgage", calc.mortgage_payment),
        ("Taxes ÷ 12", calc.monthly_taxes),
        ("Insurance ÷ 12", calc.monthly_insurance),
        ("HOA", payload.montly_hoa),
    ], note="Principal, interest, taxes, insurance and association dues: the monthly debt service the rent must cover.")
    check(calc.dscr == (payload.rent / calc.pitia if calc.pitia else Decimal("0")), "DSCR")
    bd.add(
        "dscr", "DSCR", calc.dscr,
        (f"Rent ({fmt_money(payload.rent)}) ÷ PITIA ({fmt_money(calc.pitia)}) = {fmt_num(calc.dscr)}"
         if calc.pitia else "PITIA is $0 → DSCR undefined, reported as 0"),
        unit="ratio",
    )

    # -- cash out at the refinance ---------------------------------------------
    check(calc.hml_amount == get_HML_amount(calc.purchase_price, payload.down_payment, calc.rehab_cost, hm), "HML payoff")
    bd.add(
        "cash_out", "HML Payoff at Refi", calc.hml_amount,
        (f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(calc.purchase_price)}) + Rehab ({fmt_money(calc.rehab_cost)}) = {fmt_money(calc.hml_amount)}"
         if hm else
         f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.hml_amount)}"),
        note=("Hard money funds the rehab, so the whole stack is paid off at the refi."
              if hm else "Rehab is paid in cash, so only the purchase loan is paid off at the refi."),
    )
    check(calc.down_payment_cash == (payload.down_payment / Decimal("100")) * calc.purchase_price, "down payment")
    bd.add_sum("cash_out", "Total Cash Invested (pre-refi)", calc.total_cash_invested, [
        ("Down Payment", calc.down_payment_cash),
        ("Closing", calc.closing_costs_buy),
        ("HML Points", calc.hml_points),
        ("Rehab Out-of-Pocket", calc.rehab_cash),
        ("HML Interest", calc.hml_interest),
        ("Holding", calc.holding_costs),
    ])
    check(calc.cash_out_routi == calc.loan_amount - calc.hml_amount - calc.closing_costs_refi - calc.refi_points - calc.cash_reserve, "refi wire")
    bd.add_sum(["net_profit", "roi", "cash_on_cash", "cash_out"], "Cash Out from Deal", calc.cash_out, [
        ("Refi Loan", calc.loan_amount),
        ("HML Payoff", calc.hml_amount, "-"),
        ("Refi Closing", calc.closing_costs_refi, "-"),
        ("Refi Points", calc.refi_points, "-"),
        ("Cash Reserve", calc.cash_reserve, "-"),
        ("Total Cash Invested", calc.total_cash_invested, "-"),
    ], note=("Negative: that much of your own money is still left in the deal after the refi."
             if calc.cash_out < 0 else "Positive: the refi returns more than was invested."))

    # -- returns ---------------------------------------------------------------
    check(calc.cash_on_cash == calc_cash_on_cash(calc.cash_out, calc.cash_flow), "cash on cash")
    if calc.cash_out >= 0:
        coc_formula = f"Cash Out ({fmt_money(calc.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif calc.cash_flow <= 0:
        coc_formula = f"Cash Flow ({fmt_money(calc.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        coc_formula = f"Annual Cash Flow ({fmt_money(calc.cash_flow * 12)}) ÷ |Cash Out| ({fmt_money(abs(calc.cash_out))}) × 100 = {fmt_pct(calc.cash_on_cash)}"
    bd.add("cash_on_cash", "Cash on Cash", calc.cash_on_cash, coc_formula, unit="pct")

    check(calc.equity == calc.arv * (1 - calc.ltv) + calc.cash_reserve, "equity")
    bd.add(
        ["net_profit", "roi", "equity"], "Equity (post-refi)", calc.equity,
        f"ARV ({fmt_money(calc.arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Cash Reserve ({fmt_money(calc.cash_reserve)}) = {fmt_money(calc.equity)}",
        note="The cash reserve is escrowed at the refi and returned at exit, so it counts as equity." if calc.cash_reserve else None,
    )
    bd.add_sum(["net_profit", "roi"], "Net Profit", calc.net_profit, [
        ("Equity", calc.equity),
        ("Cash Out", calc.cash_out),
    ])
    check(calc.roi == calc_roi(calc.cash_out, calc.cash_flow, calc.net_profit), "ROI")
    if calc.cash_out >= 0:
        roi_formula = f"Cash Out ({fmt_money(calc.cash_out)}) ≥ 0 → no cash left in the deal, return is infinite (∞)"
    elif calc.cash_flow <= 0:
        roi_formula = f"Cash Flow ({fmt_money(calc.cash_flow)}) ≤ 0 → return undefined (-∞)"
    else:
        roi_formula = f"(Annual Cash Flow ({fmt_money(calc.cash_flow * 12)}) + Net Profit ({fmt_money(calc.net_profit)})) ÷ |Cash Out| ({fmt_money(abs(calc.cash_out))}) × 100 = {fmt_pct(calc.roi)}"
    bd.add("roi", "ROI", calc.roi, roi_formula, unit="pct")

    # -- total cash needed -----------------------------------------------------
    bd.add(
        CASH_NEEDED, "Down Payment (cash)", calc.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.down_payment_cash)}",
    )
    bd.add(CASH_NEEDED, "Closing Costs (Buy)", calc.closing_costs_buy, f"From the inputs: {fmt_money(calc.closing_costs_buy)}")
    check(calc.hml_points == payload.HML_points / Decimal("100.0") * calc.hml_amount, "HML points")
    bd.add(
        CASH_NEEDED, "HML Points (cash)", calc.hml_points,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(calc.hml_amount)}) = {fmt_money(calc.hml_points)}",
    )
    check(calc.rehab_cash == calc.rehab_cost * (1 - int(hm)), "rehab cash")
    bd.add(
        CASH_NEEDED, "Rehab Cash (out-of-pocket)", calc.rehab_cash,
        (f"Rehab ({fmt_money(calc.rehab_cost)}) is financed by hard money → {fmt_money(calc.rehab_cash)} out of pocket"
         if hm else f"Rehab ({fmt_money(calc.rehab_cost)}) paid in cash = {fmt_money(calc.rehab_cash)}"),
    )
    check(calc.hml_interest == calc_HML_interest_in_cash(calc.purchase_price, payload.down_payment, calc.rehab_cost, payload.days_until_refi, payload.HML_interest_rate, hm), "HML interest")
    bd.add(
        "total_cash_needed_for_deal", "HML Interest (cash, until refi)", calc.hml_interest,
        f"HML Amount ({fmt_money(calc.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr × {payload.days_until_refi} days ÷ 360 = {fmt_money(calc.hml_interest)}",
        note="Hard money accrues per diem on a 360-day year.",
    )
    check(calc.holding_costs == calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi), "holding costs")
    bd.add(
        "total_cash_needed_for_deal", "Holding Costs (until refi)", calc.holding_costs,
        f"(Taxes ({fmt_money(payload.annual_property_taxes)}) + Insurance ({fmt_money(payload.annual_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) × 12) × {payload.days_until_refi} days ÷ 360 = {fmt_money(calc.holding_costs)}",
    )
    check(calc.refi_shortfall == max(Decimal("0"), -calc.cash_out_routi), "refi shortfall")
    shortfall = []
    if calc.refi_shortfall > 0:
        bd.add(
            CASH_NEEDED, "Refi Shortfall (cash to refi table)", calc.refi_shortfall,
            f"Refi wire ({fmt_money(calc.cash_out_routi)}) is negative → {fmt_money(calc.refi_shortfall)} brought to the refi closing table",
            note="The new loan does not cover the hard-money payoff plus refi costs and reserve.",
        )
        shortfall = [("Refi Shortfall", calc.refi_shortfall)]
    bd.add_sum("total_cash_needed_for_deal", "Total Cash Needed", calc.total_cash_needed, [
        ("Down Payment", calc.down_payment_cash),
        ("Closing", calc.closing_costs_buy),
        ("HML Points", calc.hml_points),
        ("Rehab Cash", calc.rehab_cash),
        ("HML Interest", calc.hml_interest),
        ("Holding", calc.holding_costs),
        *shortfall,
    ])
    check(calc.buffered_closing == calc.closing_costs_buy * Decimal("1.1"), "closing buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "Closing × 1.1 buffer", calc.buffered_closing,
        f"Closing ({fmt_money(calc.closing_costs_buy)}) × 1.1 = {fmt_money(calc.buffered_closing)}",
    )
    check(calc.buffered_interest == calc.hml_interest * Decimal("1.5"), "interest buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "HML Interest × 1.5 buffer", calc.buffered_interest,
        f"HML Interest ({fmt_money(calc.hml_interest)}) × 1.5 = {fmt_money(calc.buffered_interest)}",
        note="The ×1.5 covers delays in permits, rehab or tenant placement.",
    )
    check(calc.buffered_holding == calc.holding_costs * Decimal("1.5"), "holding buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "Holding × 1.5 buffer", calc.buffered_holding,
        f"Holding ({fmt_money(calc.holding_costs)}) × 1.5 = {fmt_money(calc.buffered_holding)}",
    )
    check(calc.rehab_float == Decimal("0.1") * calc.rehab_cost, "rehab float")
    bd.add(
        "total_cash_needed_for_deal_with_buffer", "Rehab float buffer (10% of rehab)", calc.rehab_float,
        f"10% × Rehab ({fmt_money(calc.rehab_cost)}) = {fmt_money(calc.rehab_float)}",
        note="Kept on hand for draws and deposits even when hard money funds the rehab.",
    )
    bd.add_sum("total_cash_needed_for_deal_with_buffer", "Total Cash Needed (Buffered)", calc.total_cash_needed_with_buffer, [
        ("Down Payment", calc.down_payment_cash),
        ("Closing × 1.1", calc.buffered_closing),
        ("HML Points", calc.hml_points),
        ("Rehab Cash", calc.rehab_cash),
        ("Rehab Float", calc.rehab_float),
        ("HML Interest × 1.5", calc.buffered_interest),
        ("Holding × 1.5", calc.buffered_holding),
        *shortfall,
    ])
    return bd.to_dict()
