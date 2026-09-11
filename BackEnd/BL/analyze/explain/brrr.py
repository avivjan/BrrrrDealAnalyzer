"""Explain a `BrrrCalc`: the step-by-step narrative behind every BRRRR headline metric.

Companion to `compute_brrr` (`BL/analyze/analyzeBRRR.py`). Every value comes
from the calc record; every equation stated in a formula is first verified
against that record with `check`, so the narrative cannot drift from the math.
`tests/test_explain.py` additionally fails if a `BrrrCalc` field is never read here.
"""

from decimal import Decimal

from BL.analyze.brrr_calc import BrrrCalc
from BL.analyze.common.calc_breakdown import CalcBreakdown, check, fmt_money, fmt_pct, fmt_num
from BL.analyze.common.deal_math import (
    calc_montly_operating_expenses,
    get_HML_amount,
    calc_mortgage_payment,
    calc_cash_on_cash,
    calc_roi,
)


def explain_brrr(payload, calc: BrrrCalc) -> dict[str, list[dict]]:
    bd = CalcBreakdown()

    # -- monthly operating expenses --------------------------------------------
    check(calc.operating_expenses == calc_montly_operating_expenses(payload), "operating expenses")
    bd.add(
        "cash_flow",
        "Monthly Operating Expenses",
        calc.operating_expenses,
        f"Rent ({fmt_money(payload.rent)}) × (Vacancy {fmt_pct(payload.vacancy_percent)} + Mgmt {fmt_pct(payload.property_managment_fee_precentages_from_rent)} + Maint {fmt_pct(payload.maintenance_percent)} + CapEx {fmt_pct(payload.capex_percent_of_rent)}) + Taxes ({fmt_money(payload.annual_property_taxes)})/12 + Insurance ({fmt_money(payload.annual_insurance)})/12 + HOA ({fmt_money(payload.montly_hoa)}) = {fmt_money(calc.operating_expenses)}",
    )

    # -- cash out at the refinance ---------------------------------------------
    check(calc.loan_amount == calc.arv * calc.ltv, "refi loan amount")
    bd.add(
        ["cash_out", "equity"],
        "Refi Loan Amount",
        calc.loan_amount,
        f"ARV ({fmt_money(calc.arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(calc.loan_amount)}",
    )
    check(calc.hml_amount == get_HML_amount(calc.purchase_price, payload.down_payment, calc.rehab_cost, payload.use_HM_for_rehab), "HML payoff")
    bd.add(
        "cash_out",
        "HML Payoff at Refi",
        calc.hml_amount,
        (f"Purchase Loan + Rehab ({fmt_money(calc.hml_amount)}) — full HM stack carried into refi"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.hml_amount)}"),
    )
    check(calc.down_payment_cash == (payload.down_payment / Decimal("100")) * calc.purchase_price, "down payment")
    check(calc.total_cash_invested == calc.down_payment_cash + calc.closing_costs_buy + calc.hml_points + calc.rehab_cash + calc.hml_interest + calc.holding_costs, "total cash invested")
    bd.add(
        "cash_out",
        "Total Cash Invested (pre-refi)",
        calc.total_cash_invested,
        f"Down Payment ({fmt_money(calc.down_payment_cash)}) + Closing ({fmt_money(calc.closing_costs_buy)}) + HML Points ({fmt_money(calc.hml_points)}) + Rehab Out-of-Pocket ({fmt_money(calc.rehab_cash)}) + HML Interest ({fmt_money(calc.hml_interest)}) + Holding ({fmt_money(calc.holding_costs)}) = {fmt_money(calc.total_cash_invested)}",
    )
    check(calc.cash_out_routi == calc.loan_amount - calc.hml_amount - calc.closing_costs_refi - calc.refi_points - calc.cash_reserve, "refi wire")
    check(calc.cash_out == calc.cash_out_routi - calc.total_cash_invested, "cash out")
    bd.add(
        ["net_profit", "roi", "cash_on_cash", "cash_out"],
        "Cash Out from Deal",
        calc.cash_out,
        f"Refi Loan ({fmt_money(calc.loan_amount)}) − HML Payoff ({fmt_money(calc.hml_amount)}) − Refi Closing ({fmt_money(calc.closing_costs_refi)}) − Refi Points ({fmt_money(calc.refi_points)}) − Cash Reserve ({fmt_money(calc.cash_reserve)}) − Total Cash Invested ({fmt_money(calc.total_cash_invested)}) = {fmt_money(calc.cash_out)}",
    )

    # -- monthly cash flow -----------------------------------------------------
    check(calc.mortgage_payment == calc_mortgage_payment(calc.arv, calc.ltv, payload.interest_rate, payload.loan_term_years), "mortgage payment")
    bd.add(
        ["cash_flow", "dscr"],
        "Monthly Mortgage Payment",
        calc.mortgage_payment,
        f"Amortize Loan ({fmt_money(calc.loan_amount)} = ARV {fmt_money(calc.arv)} × LTV {fmt_pct(payload.ltv_as_precent)}) at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(calc.mortgage_payment)}",
    )
    check(calc.net_operating_income == payload.rent - calc.operating_expenses, "NOI")
    bd.add(
        "cash_flow",
        "Net Operating Income (NOI)",
        calc.net_operating_income,
        f"Rent ({fmt_money(payload.rent)}) − Operating Expenses ({fmt_money(calc.operating_expenses)}) = {fmt_money(calc.net_operating_income)}",
    )
    check(calc.cash_flow == calc.net_operating_income - calc.mortgage_payment, "cash flow")
    bd.add(
        ["cash_flow", "roi", "cash_on_cash"],
        "Monthly Cash Flow",
        calc.cash_flow,
        f"NOI ({fmt_money(calc.net_operating_income)}) − Mortgage ({fmt_money(calc.mortgage_payment)}) = {fmt_money(calc.cash_flow)}",
    )

    # -- DSCR ------------------------------------------------------------------
    check(calc.pitia == calc.mortgage_payment + payload.annual_property_taxes / Decimal("12.0") + payload.annual_insurance / Decimal("12.0") + payload.montly_hoa, "PITIA")
    check(calc.dscr == (payload.rent / calc.pitia if calc.pitia else Decimal("0")), "DSCR")
    bd.add(
        "dscr",
        "DSCR",
        calc.dscr,
        (f"Rent ({fmt_money(payload.rent)}) / PITIA ({fmt_money(calc.pitia)} = Mortgage + Taxes/12 + Ins/12 + HOA) = {fmt_num(calc.dscr)}"
         if calc.pitia else "PITIA is 0 → DSCR undefined"),
    )

    # -- cash on cash ----------------------------------------------------------
    check(calc.cash_on_cash == calc_cash_on_cash(calc.cash_out, calc.cash_flow), "cash on cash")
    if calc.cash_out >= 0:
        coc_formula = f"Cash Out ({fmt_money(calc.cash_out)}) ≥ 0 → no equity at risk (∞)"
    elif calc.cash_flow <= 0:
        coc_formula = f"Cash Flow ({fmt_money(calc.cash_flow)}) ≤ 0 → CoC undefined (-∞)"
    else:
        coc_formula = f"Annual Cash Flow ({fmt_money(calc.cash_flow * 12)}) / |Cash Out| ({fmt_money(abs(calc.cash_out))}) × 100 = {fmt_pct(calc.cash_on_cash)}"
    bd.add("cash_on_cash", "Cash on Cash", calc.cash_on_cash, coc_formula)

    # -- equity and net profit -------------------------------------------------
    check(calc.equity == calc.arv * (1 - calc.ltv) + calc.cash_reserve, "equity")
    bd.add(
        ["net_profit", "roi", "equity"],
        "Equity (post-refi)",
        calc.equity,
        f"ARV ({fmt_money(calc.arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Cash Reserve ({fmt_money(calc.cash_reserve)}) = {fmt_money(calc.equity)}",
    )
    check(calc.net_profit == calc.equity + calc.cash_out, "net profit")
    bd.add(
        ["net_profit", "roi"],
        "Net Profit",
        calc.net_profit,
        f"Equity ({fmt_money(calc.equity)}) + Cash Out ({fmt_money(calc.cash_out)}) = {fmt_money(calc.net_profit)}",
    )

    # -- ROI -------------------------------------------------------------------
    check(calc.roi == calc_roi(calc.cash_out, calc.cash_flow, calc.net_profit), "ROI")
    if calc.cash_out >= 0:
        roi_formula = f"Cash Out ({fmt_money(calc.cash_out)}) ≥ 0 → no equity at risk (∞)"
    elif calc.cash_flow <= 0:
        roi_formula = f"Cash Flow ({fmt_money(calc.cash_flow)}) ≤ 0 → ROI undefined (-∞)"
    else:
        roi_formula = f"(Annual Cash Flow ({fmt_money(calc.cash_flow * 12)}) + Net Profit ({fmt_money(calc.net_profit)})) / |Cash Out| ({fmt_money(abs(calc.cash_out))}) × 100 = {fmt_pct(calc.roi)}"
    bd.add("roi", "ROI", calc.roi, roi_formula)

    # -- total cash needed -----------------------------------------------------
    both = ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"]
    bd.add(
        both,
        "Down Payment (cash)",
        calc.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.down_payment_cash)}",
    )
    bd.add(
        both,
        "Closing Costs (Buy)",
        calc.closing_costs_buy,
        f"{fmt_money(calc.closing_costs_buy)}",
    )
    check(calc.hml_points == payload.HML_points / Decimal("100.0") * calc.hml_amount, "HML points")
    bd.add(
        both,
        "HML Points (cash)",
        calc.hml_points,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(calc.hml_amount)}) = {fmt_money(calc.hml_points)}",
    )
    check(calc.rehab_cash == calc.rehab_cost * (1 - int(payload.use_HM_for_rehab)), "rehab cash")
    bd.add(
        both,
        "Rehab Cash (out-of-pocket)",
        calc.rehab_cash,
        (f"Rehab ({fmt_money(calc.rehab_cost)}) is financed via HM → no out-of-pocket = {fmt_money(calc.rehab_cash)}"
         if payload.use_HM_for_rehab
         else f"Rehab ({fmt_money(calc.rehab_cost)}) paid in cash = {fmt_money(calc.rehab_cash)}"),
    )
    bd.add(
        "total_cash_needed_for_deal",
        "HML Interest (cash, until refi)",
        calc.hml_interest,
        f"{fmt_money(calc.hml_interest)} accrued over {payload.days_until_refi} days at {fmt_pct(payload.HML_interest_rate)}/yr ÷ 360 per diem",
    )
    bd.add(
        "total_cash_needed_for_deal",
        "Holding Costs (until refi)",
        calc.holding_costs,
        f"Taxes + Insurance + HOA accrued over {payload.days_until_refi} days = {fmt_money(calc.holding_costs)}",
    )
    check(calc.refi_shortfall == max(Decimal("0"), -calc.cash_out_routi), "refi shortfall")
    if calc.refi_shortfall > 0:
        bd.add(
            both,
            "Refi Shortfall (cash to refi table)",
            calc.refi_shortfall,
            f"Refi wire ({fmt_money(calc.cash_out_routi)}) is negative → investor brings {fmt_money(calc.refi_shortfall)} at refi closing",
        )
    shortfall_text = f" + Refi Shortfall ({fmt_money(calc.refi_shortfall)})" if calc.refi_shortfall > 0 else ""
    check(calc.total_cash_needed == calc.down_payment_cash + calc.holding_costs + calc.closing_costs_buy + calc.hml_points + calc.rehab_cash + calc.hml_interest + calc.refi_shortfall, "total cash needed")
    bd.add(
        "total_cash_needed_for_deal",
        "Total Cash Needed",
        calc.total_cash_needed,
        f"Down Payment ({fmt_money(calc.down_payment_cash)}) + Closing ({fmt_money(calc.closing_costs_buy)}) + HML Points ({fmt_money(calc.hml_points)}) + Rehab Cash ({fmt_money(calc.rehab_cash)}) + HML Interest ({fmt_money(calc.hml_interest)}) + Holding ({fmt_money(calc.holding_costs)}){shortfall_text} = {fmt_money(calc.total_cash_needed)}",
    )
    check(calc.buffered_closing == calc.closing_costs_buy * Decimal("1.1"), "closing buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer",
        "Closing × 1.1 buffer",
        calc.buffered_closing,
        f"Closing ({fmt_money(calc.closing_costs_buy)}) × 1.1 = {fmt_money(calc.buffered_closing)}",
    )
    check(calc.buffered_interest == calc.hml_interest * Decimal("1.5"), "interest buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer",
        "HML Interest × 1.5 buffer",
        calc.buffered_interest,
        f"HML Interest ({fmt_money(calc.hml_interest)}) × 1.5 = {fmt_money(calc.buffered_interest)}",
    )
    check(calc.buffered_holding == calc.holding_costs * Decimal("1.5"), "holding buffer")
    bd.add(
        "total_cash_needed_for_deal_with_buffer",
        "Holding × 1.5 buffer",
        calc.buffered_holding,
        f"Holding ({fmt_money(calc.holding_costs)}) × 1.5 = {fmt_money(calc.buffered_holding)}",
    )
    check(calc.rehab_float == Decimal("0.1") * calc.rehab_cost, "rehab float")
    bd.add(
        "total_cash_needed_for_deal_with_buffer",
        "Rehab float buffer (10% of rehab)",
        calc.rehab_float,
        f"10% × Rehab ({fmt_money(calc.rehab_cost)}) = {fmt_money(calc.rehab_float)} — kept on hand for draws/deposits even when HM funds the rehab",
    )
    check(calc.total_cash_needed_with_buffer == calc.down_payment_cash + calc.buffered_holding + calc.buffered_closing + calc.hml_points + (calc.rehab_cash + calc.rehab_float) + calc.buffered_interest + calc.refi_shortfall, "total cash needed (buffered)")
    bd.add(
        "total_cash_needed_for_deal_with_buffer",
        "Total Cash Needed (Buffered)",
        calc.total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(calc.down_payment_cash)}) + Closing×1.1 ({fmt_money(calc.buffered_closing)}) + HML Points ({fmt_money(calc.hml_points)}) + Rehab Cash ({fmt_money(calc.rehab_cash)}) + Rehab Float ({fmt_money(calc.rehab_float)}) + HML Interest×1.5 ({fmt_money(calc.buffered_interest)}) + Holding×1.5 ({fmt_money(calc.buffered_holding)}){shortfall_text} = {fmt_money(calc.total_cash_needed_with_buffer)}",
    )
    return bd.to_dict()
