"""Explain a `FlipCalc`: the step-by-step narrative behind every Flip headline metric.

Companion to `compute_flip` (`BL/analyze/analyzeFlip.py`). Every value comes
from the calc record; every equation stated in a formula is first verified
against that record with `check`, so the narrative cannot drift from the math.
`tests/test_explain.py` additionally fails if a `FlipCalc` field is never read here.
"""

from decimal import Decimal

from BL.analyze.flip_calc import FlipCalc
from BL.analyze.common.calc_breakdown import CalcBreakdown, check, fmt_money, fmt_pct, fmt_num
from BL.analyze.common.deal_math import get_HML_amount


def explain_flip(payload, calc: FlipCalc) -> dict[str, list[dict]]:
    bd = CalcBreakdown()

    # -- dollar basis ----------------------------------------------------------
    check(calc.rehab_contingency == calc.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    check(calc.rehab_cost == calc.rehab_cost_base + calc.rehab_contingency, "rehab cost")
    bd.add(
        "net_profit",
        "Rehab Cost (with contingency)",
        calc.rehab_cost,
        f"Base ({fmt_money(calc.rehab_cost_base)}) + Contingency {fmt_pct(payload.rehab_contingency_percent)} ({fmt_money(calc.rehab_contingency)}) = {fmt_money(calc.rehab_cost)}",
    )

    # -- hard money over the hold ----------------------------------------------
    check(calc.hml_amount == get_HML_amount(calc.purchase_price, payload.down_payment, calc.rehab_cost, payload.use_HM_for_rehab), "HML amount")
    bd.add(
        "total_hml_interest",
        "HML Amount",
        calc.hml_amount,
        (f"Purchase Loan + Rehab ({fmt_money(calc.hml_amount)}) — full HM stack"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.hml_amount)}"),
    )
    check(calc.hml_points == (payload.HML_points / Decimal("100.0")) * calc.hml_amount, "HML points")
    bd.add(
        "net_profit",
        "HML Points (cash)",
        calc.hml_points,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(calc.hml_amount)}) = {fmt_money(calc.hml_points)}",
    )
    check(calc.monthly_hml_interest == (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * calc.hml_amount, "monthly HML interest")
    bd.add(
        "total_hml_interest",
        "Monthly HML Interest",
        calc.monthly_hml_interest,
        f"HML Amount ({fmt_money(calc.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 12 = {fmt_money(calc.monthly_hml_interest)}",
    )
    check(calc.total_hml_interest == calc.monthly_hml_interest * payload.holding_time_months, "total HML interest")
    bd.add(
        ["net_profit", "total_hml_interest", "total_holding_costs"],
        "Total HML Interest (over holding period)",
        calc.total_hml_interest,
        f"Monthly Interest ({fmt_money(calc.monthly_hml_interest)}) × {payload.holding_time_months} mos = {fmt_money(calc.total_hml_interest)}",
    )

    # -- operating and holding costs -------------------------------------------
    check(calc.monthly_taxes == payload.annual_property_taxes / Decimal("12.0"), "monthly taxes")
    check(calc.monthly_insurance == payload.annual_insurance / Decimal("12.0"), "monthly insurance")
    check(calc.monthly_operating == calc.monthly_taxes + calc.monthly_insurance + payload.montly_hoa + payload.monthly_utilities, "monthly operating")
    check(calc.total_operating == calc.monthly_operating * payload.holding_time_months, "total operating")
    bd.add(
        ["net_profit", "total_holding_costs"],
        "Total Operating Costs (during holding)",
        calc.total_operating,
        f"(Taxes/12 ({fmt_money(calc.monthly_taxes)}) + Insurance/12 ({fmt_money(calc.monthly_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) + Utilities ({fmt_money(payload.monthly_utilities)})) × {payload.holding_time_months} mos = {fmt_money(calc.total_operating)}",
    )
    check(calc.total_holding_costs == calc.total_hml_interest + calc.total_operating, "total holding costs")
    bd.add(
        ["net_profit", "total_holding_costs"],
        "Total Holding Costs",
        calc.total_holding_costs,
        f"HML Interest ({fmt_money(calc.total_hml_interest)}) + Operating ({fmt_money(calc.total_operating)}) = {fmt_money(calc.total_holding_costs)}",
    )

    # -- selling ----------------------------------------------------------------
    check(calc.agent_fees_percent == payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee, "agent fees")
    check(calc.selling_costs == calc.sale_price * (calc.agent_fees_percent / Decimal("100.0")) + calc.selling_closing_costs, "selling costs")
    bd.add(
        "net_profit",
        "Selling Costs",
        calc.selling_costs,
        f"Sale Price ({fmt_money(calc.sale_price)}) × Agent Fees {fmt_pct(calc.agent_fees_percent)} + Closing ({fmt_money(calc.selling_closing_costs)}) = {fmt_money(calc.selling_costs)}",
    )

    # -- total cash needed -----------------------------------------------------
    both = ["total_cash_needed", "total_cash_needed_with_buffer"]
    check(calc.down_payment_cash == (payload.down_payment / Decimal("100")) * calc.purchase_price, "down payment")
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
        "total_cash_needed",
        "HML Interest (cash, during holding)",
        calc.total_hml_interest,
        f"Monthly Interest × {payload.holding_time_months} mos = {fmt_money(calc.total_hml_interest)}",
    )
    bd.add(
        "total_cash_needed",
        "Operating Costs (during holding)",
        calc.total_operating,
        f"Monthly Operating × {payload.holding_time_months} mos = {fmt_money(calc.total_operating)}",
    )
    check(calc.total_cash_needed == calc.down_payment_cash + calc.total_operating + calc.closing_costs_buy + calc.hml_points + calc.rehab_cash + calc.total_hml_interest, "total cash needed")
    bd.add(
        "total_cash_needed",
        "Total Cash Needed",
        calc.total_cash_needed,
        f"Down Payment ({fmt_money(calc.down_payment_cash)}) + Closing ({fmt_money(calc.closing_costs_buy)}) + HML Points ({fmt_money(calc.hml_points)}) + Rehab Cash ({fmt_money(calc.rehab_cash)}) + HML Interest ({fmt_money(calc.total_hml_interest)}) + Operating ({fmt_money(calc.total_operating)}) = {fmt_money(calc.total_cash_needed)}",
    )
    check(calc.buffered_closing == calc.closing_costs_buy * Decimal("1.1"), "closing buffer")
    bd.add(
        "total_cash_needed_with_buffer",
        "Closing × 1.1 buffer",
        calc.buffered_closing,
        f"Closing ({fmt_money(calc.closing_costs_buy)}) × 1.1 = {fmt_money(calc.buffered_closing)}",
    )
    check(calc.buffered_interest == calc.total_hml_interest * Decimal("1.5"), "interest buffer")
    bd.add(
        "total_cash_needed_with_buffer",
        "HML Interest × 1.5 buffer",
        calc.buffered_interest,
        f"HML Interest ({fmt_money(calc.total_hml_interest)}) × 1.5 = {fmt_money(calc.buffered_interest)}",
    )
    check(calc.buffered_operating == calc.total_operating * Decimal("1.5"), "operating buffer")
    bd.add(
        "total_cash_needed_with_buffer",
        "Operating × 1.5 buffer",
        calc.buffered_operating,
        f"Operating ({fmt_money(calc.total_operating)}) × 1.5 = {fmt_money(calc.buffered_operating)}",
    )
    check(calc.rehab_float == Decimal("0.1") * calc.rehab_cost, "rehab float")
    bd.add(
        "total_cash_needed_with_buffer",
        "Rehab float buffer (10% of rehab)",
        calc.rehab_float,
        f"10% × Rehab ({fmt_money(calc.rehab_cost)}) = {fmt_money(calc.rehab_float)} — kept on hand for draws/deposits even when HM funds the rehab",
    )
    check(calc.total_cash_needed_with_buffer == calc.down_payment_cash + calc.buffered_operating + calc.buffered_closing + calc.hml_points + (calc.rehab_cash + calc.rehab_float) + calc.buffered_interest, "total cash needed (buffered)")
    bd.add(
        "total_cash_needed_with_buffer",
        "Total Cash Needed (Buffered)",
        calc.total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(calc.down_payment_cash)}) + Closing×1.1 ({fmt_money(calc.buffered_closing)}) + HML Points ({fmt_money(calc.hml_points)}) + Rehab Cash ({fmt_money(calc.rehab_cash)}) + Rehab Float ({fmt_money(calc.rehab_float)}) + HML Interest×1.5 ({fmt_money(calc.buffered_interest)}) + Operating×1.5 ({fmt_money(calc.buffered_operating)}) = {fmt_money(calc.total_cash_needed_with_buffer)}",
    )

    # -- cost basis and profit -------------------------------------------------
    check(calc.total_cash_invested == calc.down_payment_cash + calc.closing_costs_buy + calc.hml_points + calc.total_holding_costs + calc.rehab_cash, "total cash invested")
    bd.add(
        "roi",
        "Total Cash Invested",
        calc.total_cash_invested,
        f"Down Payment ({fmt_money(calc.down_payment_cash)}) + Closing ({fmt_money(calc.closing_costs_buy)}) + HML Points ({fmt_money(calc.hml_points)}) + Holding ({fmt_money(calc.total_holding_costs)}) + Rehab Out-of-Pocket ({fmt_money(calc.rehab_cash)}) = {fmt_money(calc.total_cash_invested)}",
    )
    check(calc.total_cost_basis == calc.purchase_price + calc.rehab_cost + calc.closing_costs_buy + calc.total_holding_costs + calc.selling_costs + calc.hml_points, "total cost basis")
    bd.add(
        "net_profit",
        "Total Cost Basis",
        calc.total_cost_basis,
        f"Purchase ({fmt_money(calc.purchase_price)}) + Rehab ({fmt_money(calc.rehab_cost)}) + Closing ({fmt_money(calc.closing_costs_buy)}) + Holding ({fmt_money(calc.total_holding_costs)}) + Selling ({fmt_money(calc.selling_costs)}) + HML Points ({fmt_money(calc.hml_points)}) = {fmt_money(calc.total_cost_basis)}",
    )
    check(calc.gross_profit == calc.sale_price - calc.total_cost_basis, "gross profit")
    bd.add(
        "net_profit",
        "Gross Profit",
        calc.gross_profit,
        f"Sale Price ({fmt_money(calc.sale_price)}) − Total Cost Basis ({fmt_money(calc.total_cost_basis)}) = {fmt_money(calc.gross_profit)}",
    )
    check(calc.capital_gains_tax == (calc.gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0")) if calc.gross_profit > 0 else Decimal("0")), "capital gains tax")
    bd.add(
        "net_profit",
        "Capital Gains Tax",
        calc.capital_gains_tax,
        (f"Gross Profit ({fmt_money(calc.gross_profit)}) × {fmt_pct(payload.capital_gains_tax_rate)} = {fmt_money(calc.capital_gains_tax)}"
         if calc.gross_profit > 0 else f"Gross Profit ≤ 0 → no tax owed = {fmt_money(calc.capital_gains_tax)}"),
    )
    check(calc.net_profit == calc.gross_profit - calc.capital_gains_tax, "net profit")
    bd.add(
        ["net_profit", "roi"],
        "Net Profit (after tax)",
        calc.net_profit,
        f"Gross Profit ({fmt_money(calc.gross_profit)}) − Capital Gains Tax ({fmt_money(calc.capital_gains_tax)}) = {fmt_money(calc.net_profit)}",
    )

    # -- ROI -------------------------------------------------------------------
    if calc.total_cash_invested > 0:
        check(calc.roi == (calc.net_profit / calc.total_cash_invested) * Decimal("100.0"), "ROI")
        roi_formula = f"Net Profit ({fmt_money(calc.net_profit)}) / Total Cash Invested ({fmt_money(calc.total_cash_invested)}) × 100 = {fmt_pct(calc.roi)}"
    elif calc.net_profit > 0:
        check(calc.roi == Decimal("-1"), "ROI (infinite)")
        roi_formula = f"Total Cash Invested is 0 with Net Profit {fmt_money(calc.net_profit)} → ROI = ∞"
    elif calc.net_profit < 0:
        check(calc.roi == Decimal("-2"), "ROI (-infinite)")
        roi_formula = f"Total Cash Invested is 0 with Net Profit {fmt_money(calc.net_profit)} → ROI = -∞"
    else:
        check(calc.roi == Decimal("0"), "ROI (break-even)")
        roi_formula = "Total Cash Invested is 0 and Net Profit is 0 → ROI = 0%"
    bd.add(["roi", "annualized_roi"], "ROI", calc.roi, roi_formula)

    check(calc.holding_years == payload.holding_time_months / Decimal("12.0"), "holding years")
    if calc.total_cash_invested <= 0:
        check(calc.annualized_roi == calc.roi, "annualized ROI (sentinel)")
        ann_formula = "ROI is unbounded (no cash invested) → Annualized ROI carries the same sentinel"
    elif calc.holding_years > 0:
        check(calc.annualized_roi == calc.roi / calc.holding_years, "annualized ROI")
        ann_formula = f"ROI ({fmt_pct(calc.roi)}) / Holding Years ({fmt_num(calc.holding_years)}) = {fmt_pct(calc.annualized_roi)}"
    else:
        check(calc.annualized_roi == Decimal("0"), "annualized ROI (no hold)")
        ann_formula = "Holding time is 0 → Annualized ROI = 0%"
    bd.add("annualized_roi", "Annualized ROI", calc.annualized_roi, ann_formula)
    return bd.to_dict()
