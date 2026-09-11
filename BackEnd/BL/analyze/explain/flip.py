"""Explain a `FlipCalc`: the step-by-step narrative behind every Flip headline metric.

Companion to `compute_flip` (`BL/analyze/analyzeFlip.py`). Every value comes
from the calc record; every equation stated in a formula is first verified
against that record (`check`, or the fold inside `add_sum`), so the narrative
cannot drift from the math. `tests/test_explain.py` additionally fails if a
`FlipCalc` field is never read here.

Sum-type steps list their terms in the same left-to-right order the
calculator adds them (see `deal_math.py`); that is what lets the guard use
exact equality on unrounded Decimals.
"""

from decimal import Decimal

from BL.analyze.flip_calc import FlipCalc
from BL.analyze.common.calc_breakdown import CalcBreakdown, check, fmt_money, fmt_pct, fmt_num
from BL.analyze.common.deal_math import get_HML_amount

# The headline metrics, in reading order: (result field, label, unit).
# The PDF derives both its summary table and its breakdown sections from this.
FLIP_SECTIONS = [
    ("net_profit", "Net Profit", "money"),
    ("roi", "ROI", "pct"),
    ("annualized_roi", "Annualized ROI", "pct"),
    ("total_holding_costs", "Total Holding Costs", "money"),
    ("total_hml_interest", "Total HML Interest", "money"),
    ("total_cash_needed", "Total Cash Needed", "money"),
    ("total_cash_needed_with_buffer", "Cash Needed (Buffered)", "money"),
]

CASH_NEEDED = ["total_cash_needed", "total_cash_needed_with_buffer"]


def explain_flip(payload, calc: FlipCalc) -> dict[str, list[dict]]:
    bd = CalcBreakdown()
    hm = bool(payload.use_HM_for_rehab)
    months = payload.holding_time_months

    # -- rehab basis -----------------------------------------------------------
    check(calc.rehab_contingency == calc.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    bd.add_sum("net_profit", "Rehab Cost (with contingency)", calc.rehab_cost, [
        ("Rehab", calc.rehab_cost_base),
        (f"Contingency {fmt_pct(payload.rehab_contingency_percent)}", calc.rehab_contingency),
    ])

    # -- hard money over the hold ----------------------------------------------
    check(calc.hml_amount == get_HML_amount(calc.purchase_price, payload.down_payment, calc.rehab_cost, hm), "HML amount")
    bd.add(
        "total_hml_interest", "HML Amount", calc.hml_amount,
        (f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(calc.purchase_price)}) + Rehab ({fmt_money(calc.rehab_cost)}) = {fmt_money(calc.hml_amount)}"
         if hm else
         f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.hml_amount)}"),
        note="Hard money funds the rehab too." if hm else "Rehab is paid in cash; hard money covers the purchase only.",
    )
    check(calc.hml_points == (payload.HML_points / Decimal("100.0")) * calc.hml_amount, "HML points")
    bd.add(
        "net_profit", "HML Points (cash)", calc.hml_points,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(calc.hml_amount)}) = {fmt_money(calc.hml_points)}",
    )
    check(calc.monthly_hml_interest == (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * calc.hml_amount, "monthly HML interest")
    bd.add(
        "total_hml_interest", "Monthly HML Interest", calc.monthly_hml_interest,
        f"HML Amount ({fmt_money(calc.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 12 = {fmt_money(calc.monthly_hml_interest)}",
    )
    check(calc.total_hml_interest == calc.monthly_hml_interest * months, "total HML interest")
    bd.add(
        ["net_profit", "total_hml_interest", "total_holding_costs"], "Total HML Interest (over holding period)", calc.total_hml_interest,
        f"Monthly Interest ({fmt_money(calc.monthly_hml_interest)}) × {months} months = {fmt_money(calc.total_hml_interest)}",
    )

    # -- operating and holding costs -------------------------------------------
    check(calc.monthly_taxes == payload.annual_property_taxes / Decimal("12.0"), "monthly taxes")
    check(calc.monthly_insurance == payload.annual_insurance / Decimal("12.0"), "monthly insurance")
    bd.add_sum("total_holding_costs", "Monthly Operating Costs", calc.monthly_operating, [
        ("Taxes ÷ 12", calc.monthly_taxes),
        ("Insurance ÷ 12", calc.monthly_insurance),
        ("HOA", payload.montly_hoa),
        ("Utilities", payload.monthly_utilities),
    ])
    check(calc.total_operating == calc.monthly_operating * months, "total operating")
    bd.add(
        ["net_profit", "total_holding_costs"], "Total Operating Costs (during holding)", calc.total_operating,
        f"Monthly Operating ({fmt_money(calc.monthly_operating)}) × {months} months = {fmt_money(calc.total_operating)}",
    )
    bd.add_sum(["net_profit", "total_holding_costs"], "Total Holding Costs", calc.total_holding_costs, [
        ("HML Interest", calc.total_hml_interest),
        ("Operating", calc.total_operating),
    ])

    # -- selling ----------------------------------------------------------------
    check(calc.agent_fees_percent == payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee, "agent fees")
    check(calc.selling_costs == calc.sale_price * (calc.agent_fees_percent / Decimal("100.0")) + calc.selling_closing_costs, "selling costs")
    bd.add(
        "net_profit", "Selling Costs", calc.selling_costs,
        f"Sale Price ({fmt_money(calc.sale_price)}) × Agent Fees {fmt_pct(calc.agent_fees_percent)} + Selling Closing ({fmt_money(calc.selling_closing_costs)}) = {fmt_money(calc.selling_costs)}",
        note=f"Agent fees are the buyer's {fmt_pct(payload.buyer_agent_selling_fee)} plus the seller's {fmt_pct(payload.seller_agent_selling_fee)}.",
    )

    # -- total cash needed -----------------------------------------------------
    check(calc.down_payment_cash == (payload.down_payment / Decimal("100")) * calc.purchase_price, "down payment")
    bd.add(
        CASH_NEEDED, "Down Payment (cash)", calc.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(calc.purchase_price)}) = {fmt_money(calc.down_payment_cash)}",
    )
    bd.add(CASH_NEEDED, "Closing Costs (Buy)", calc.closing_costs_buy, f"From the inputs: {fmt_money(calc.closing_costs_buy)}")
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
    bd.add(
        "total_cash_needed", "HML Interest (cash, during holding)", calc.total_hml_interest,
        f"Monthly Interest ({fmt_money(calc.monthly_hml_interest)}) × {months} months = {fmt_money(calc.total_hml_interest)}",
    )
    bd.add(
        "total_cash_needed", "Operating Costs (during holding)", calc.total_operating,
        f"Monthly Operating ({fmt_money(calc.monthly_operating)}) × {months} months = {fmt_money(calc.total_operating)}",
    )
    bd.add_sum("total_cash_needed", "Total Cash Needed", calc.total_cash_needed, [
        ("Down Payment", calc.down_payment_cash),
        ("Closing", calc.closing_costs_buy),
        ("HML Points", calc.hml_points),
        ("Rehab Cash", calc.rehab_cash),
        ("HML Interest", calc.total_hml_interest),
        ("Operating", calc.total_operating),
    ])
    check(calc.buffered_closing == calc.closing_costs_buy * Decimal("1.1"), "closing buffer")
    bd.add(
        "total_cash_needed_with_buffer", "Closing × 1.1 buffer", calc.buffered_closing,
        f"Closing ({fmt_money(calc.closing_costs_buy)}) × 1.1 = {fmt_money(calc.buffered_closing)}",
    )
    check(calc.buffered_interest == calc.total_hml_interest * Decimal("1.5"), "interest buffer")
    bd.add(
        "total_cash_needed_with_buffer", "HML Interest × 1.5 buffer", calc.buffered_interest,
        f"HML Interest ({fmt_money(calc.total_hml_interest)}) × 1.5 = {fmt_money(calc.buffered_interest)}",
        note="The ×1.5 covers delays in permits, rehab or the sale.",
    )
    check(calc.buffered_operating == calc.total_operating * Decimal("1.5"), "operating buffer")
    bd.add(
        "total_cash_needed_with_buffer", "Operating × 1.5 buffer", calc.buffered_operating,
        f"Operating ({fmt_money(calc.total_operating)}) × 1.5 = {fmt_money(calc.buffered_operating)}",
    )
    check(calc.rehab_float == Decimal("0.1") * calc.rehab_cost, "rehab float")
    bd.add(
        "total_cash_needed_with_buffer", "Rehab float buffer (10% of rehab)", calc.rehab_float,
        f"10% × Rehab ({fmt_money(calc.rehab_cost)}) = {fmt_money(calc.rehab_float)}",
        note="Kept on hand for draws and deposits even when hard money funds the rehab.",
    )
    bd.add_sum("total_cash_needed_with_buffer", "Total Cash Needed (Buffered)", calc.total_cash_needed_with_buffer, [
        ("Down Payment", calc.down_payment_cash),
        ("Closing × 1.1", calc.buffered_closing),
        ("HML Points", calc.hml_points),
        ("Rehab Cash", calc.rehab_cash),
        ("Rehab Float", calc.rehab_float),
        ("HML Interest × 1.5", calc.buffered_interest),
        ("Operating × 1.5", calc.buffered_operating),
    ])

    # -- cost basis and profit -------------------------------------------------
    bd.add_sum("roi", "Total Cash Invested", calc.total_cash_invested, [
        ("Down Payment", calc.down_payment_cash),
        ("Closing", calc.closing_costs_buy),
        ("HML Points", calc.hml_points),
        ("Holding", calc.total_holding_costs),
        ("Rehab Out-of-Pocket", calc.rehab_cash),
    ])
    bd.add_sum("net_profit", "Total Cost Basis", calc.total_cost_basis, [
        ("Purchase", calc.purchase_price),
        ("Rehab", calc.rehab_cost),
        ("Closing", calc.closing_costs_buy),
        ("Holding", calc.total_holding_costs),
        ("Selling", calc.selling_costs),
        ("HML Points", calc.hml_points),
    ])
    bd.add_sum("net_profit", "Gross Profit", calc.gross_profit, [
        ("Sale Price", calc.sale_price),
        ("Total Cost Basis", calc.total_cost_basis, "-"),
    ])
    check(calc.capital_gains_tax == (calc.gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0")) if calc.gross_profit > 0 else Decimal("0")), "capital gains tax")
    bd.add(
        "net_profit", "Capital Gains Tax", calc.capital_gains_tax,
        (f"Gross Profit ({fmt_money(calc.gross_profit)}) × {fmt_pct(payload.capital_gains_tax_rate)} = {fmt_money(calc.capital_gains_tax)}"
         if calc.gross_profit > 0 else f"Gross Profit ({fmt_money(calc.gross_profit)}) ≤ 0 → no tax owed"),
    )
    bd.add_sum(["net_profit", "roi"], "Net Profit (after tax)", calc.net_profit, [
        ("Gross Profit", calc.gross_profit),
        ("Capital Gains Tax", calc.capital_gains_tax, "-"),
    ])

    # -- ROI -------------------------------------------------------------------
    if calc.total_cash_invested > 0:
        check(calc.roi == (calc.net_profit / calc.total_cash_invested) * Decimal("100.0"), "ROI")
        roi_formula = f"Net Profit ({fmt_money(calc.net_profit)}) ÷ Total Cash Invested ({fmt_money(calc.total_cash_invested)}) × 100 = {fmt_pct(calc.roi)}"
    elif calc.net_profit > 0:
        check(calc.roi == Decimal("-1"), "ROI (infinite)")
        roi_formula = f"No cash invested with Net Profit {fmt_money(calc.net_profit)} → return is infinite (∞)"
    elif calc.net_profit < 0:
        check(calc.roi == Decimal("-2"), "ROI (-infinite)")
        roi_formula = f"No cash invested with Net Profit {fmt_money(calc.net_profit)} → return is -∞"
    else:
        check(calc.roi == Decimal("0"), "ROI (break-even)")
        roi_formula = "No cash invested and no profit → ROI = 0%"
    bd.add(["roi", "annualized_roi"], "ROI", calc.roi, roi_formula, unit="pct")

    check(calc.holding_years == months / Decimal("12.0"), "holding years")
    if calc.total_cash_invested <= 0:
        check(calc.annualized_roi == calc.roi, "annualized ROI (sentinel)")
        ann_formula = "ROI is unbounded (no cash invested) → Annualized ROI carries the same sentinel"
    elif calc.holding_years > 0:
        check(calc.annualized_roi == calc.roi / calc.holding_years, "annualized ROI")
        ann_formula = f"ROI ({fmt_pct(calc.roi)}) ÷ Holding Years ({fmt_num(calc.holding_years)}) = {fmt_pct(calc.annualized_roi)}"
    else:
        check(calc.annualized_roi == Decimal("0"), "annualized ROI (no hold)")
        ann_formula = "Holding time is 0 → Annualized ROI = 0%"
    bd.add("annualized_roi", "Annualized ROI", calc.annualized_roi, ann_formula, unit="pct",
           note=f"Holding Years = {months} months ÷ 12.")
    return bd.to_dict()
