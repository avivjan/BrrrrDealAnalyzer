"""Explain a `FlipResultsWithIntermediates`: the step-by-step narrative behind every Flip headline metric.

Companion to `compute_flip_with_intermediates` (`BL/analyze/analyzeFlip.py`). Every value comes
from the results_w_intermediates record; every equation stated in a formula is first verified
against that record (`check`, or the fold inside `add_sum`), so the narrative
cannot drift from the math. `tests/test_explain.py` additionally fails if a
`FlipResultsWithIntermediates` field is never read here.

Sum-type steps list their terms in the same left-to-right order the
calculator adds them (see `deal_math.py`); that is what lets the guard use
exact equality on unrounded Decimals.
"""

from decimal import Decimal

from BL.analyze.flip_results_with_intermediates import FlipResultsWithIntermediates
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


def explain_flip(payload, results_w_intermediates: FlipResultsWithIntermediates) -> dict[str, list[dict]]:
    bd = CalcBreakdown()
    hm = bool(payload.use_HM_for_rehab)
    months = payload.holding_time_months

    # -- rehab basis -----------------------------------------------------------
    check(results_w_intermediates.rehab_contingency == results_w_intermediates.rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0")), "rehab contingency")
    bd.add_sum("net_profit", "Rehab Cost (with contingency)", results_w_intermediates.rehab_cost, [
        ("Rehab", results_w_intermediates.rehab_cost_base),
        (f"Contingency {fmt_pct(payload.rehab_contingency_percent)}", results_w_intermediates.rehab_contingency),
    ])

    # -- hard money over the hold ----------------------------------------------
    check(results_w_intermediates.hml_amount == get_HML_amount(results_w_intermediates.purchase_price, payload.down_payment, results_w_intermediates.rehab_cost, hm), "HML amount")
    bd.add(
        "total_hml_interest", "HML Amount", results_w_intermediates.hml_amount,
        (f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(results_w_intermediates.purchase_price)}) + Rehab ({fmt_money(results_w_intermediates.rehab_cost)}) = {fmt_money(results_w_intermediates.hml_amount)}"
         if hm else
         f"(1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(results_w_intermediates.purchase_price)}) = {fmt_money(results_w_intermediates.hml_amount)}"),
        note="Hard money funds the rehab too." if hm else "Rehab is paid in cash; hard money covers the purchase only.",
    )
    check(results_w_intermediates.hml_points == (payload.HML_points / Decimal("100.0")) * results_w_intermediates.hml_amount, "HML points")
    bd.add(
        "net_profit", "HML Points (cash)", results_w_intermediates.hml_points,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(results_w_intermediates.hml_amount)}) = {fmt_money(results_w_intermediates.hml_points)}",
    )
    check(results_w_intermediates.monthly_hml_interest == (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * results_w_intermediates.hml_amount, "monthly HML interest")
    bd.add(
        "total_hml_interest", "Monthly HML Interest", results_w_intermediates.monthly_hml_interest,
        f"HML Amount ({fmt_money(results_w_intermediates.hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 12 = {fmt_money(results_w_intermediates.monthly_hml_interest)}",
    )
    check(results_w_intermediates.total_hml_interest == results_w_intermediates.monthly_hml_interest * months, "total HML interest")
    bd.add(
        ["net_profit", "total_hml_interest", "total_holding_costs"], "Total HML Interest (over holding period)", results_w_intermediates.total_hml_interest,
        f"Monthly Interest ({fmt_money(results_w_intermediates.monthly_hml_interest)}) × {months} months = {fmt_money(results_w_intermediates.total_hml_interest)}",
    )

    # -- operating and holding costs -------------------------------------------
    check(results_w_intermediates.monthly_taxes == payload.annual_property_taxes / Decimal("12.0"), "monthly taxes")
    check(results_w_intermediates.monthly_insurance == payload.annual_insurance / Decimal("12.0"), "monthly insurance")
    bd.add_sum("total_holding_costs", "Monthly Operating Costs", results_w_intermediates.monthly_operating, [
        ("Taxes ÷ 12", results_w_intermediates.monthly_taxes),
        ("Insurance ÷ 12", results_w_intermediates.monthly_insurance),
        ("HOA", payload.montly_hoa),
        ("Utilities", payload.monthly_utilities),
    ])
    check(results_w_intermediates.total_operating == results_w_intermediates.monthly_operating * months, "total operating")
    bd.add(
        ["net_profit", "total_holding_costs"], "Total Operating Costs (during holding)", results_w_intermediates.total_operating,
        f"Monthly Operating ({fmt_money(results_w_intermediates.monthly_operating)}) × {months} months = {fmt_money(results_w_intermediates.total_operating)}",
    )
    bd.add_sum(["net_profit", "total_holding_costs"], "Total Holding Costs", results_w_intermediates.total_holding_costs, [
        ("HML Interest", results_w_intermediates.total_hml_interest),
        ("Operating", results_w_intermediates.total_operating),
    ])

    # -- selling ----------------------------------------------------------------
    check(results_w_intermediates.agent_fees_percent == payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee, "agent fees")
    check(results_w_intermediates.selling_costs == results_w_intermediates.sale_price * (results_w_intermediates.agent_fees_percent / Decimal("100.0")) + results_w_intermediates.selling_closing_costs, "selling costs")
    bd.add(
        "net_profit", "Selling Costs", results_w_intermediates.selling_costs,
        f"Sale Price ({fmt_money(results_w_intermediates.sale_price)}) × Agent Fees {fmt_pct(results_w_intermediates.agent_fees_percent)} + Selling Closing ({fmt_money(results_w_intermediates.selling_closing_costs)}) = {fmt_money(results_w_intermediates.selling_costs)}",
        note=f"Agent fees are the buyer's {fmt_pct(payload.buyer_agent_selling_fee)} plus the seller's {fmt_pct(payload.seller_agent_selling_fee)}.",
    )

    # -- total cash needed -----------------------------------------------------
    check(results_w_intermediates.down_payment_cash == (payload.down_payment / Decimal("100")) * results_w_intermediates.purchase_price, "down payment")
    bd.add(
        CASH_NEEDED, "Down Payment (cash)", results_w_intermediates.down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(results_w_intermediates.purchase_price)}) = {fmt_money(results_w_intermediates.down_payment_cash)}",
    )
    bd.add(CASH_NEEDED, "Closing Costs (Buy)", results_w_intermediates.closing_costs_buy, f"From the inputs: {fmt_money(results_w_intermediates.closing_costs_buy)}")
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
    bd.add(
        "total_cash_needed", "HML Interest (cash, during holding)", results_w_intermediates.total_hml_interest,
        f"Monthly Interest ({fmt_money(results_w_intermediates.monthly_hml_interest)}) × {months} months = {fmt_money(results_w_intermediates.total_hml_interest)}",
    )
    bd.add(
        "total_cash_needed", "Operating Costs (during holding)", results_w_intermediates.total_operating,
        f"Monthly Operating ({fmt_money(results_w_intermediates.monthly_operating)}) × {months} months = {fmt_money(results_w_intermediates.total_operating)}",
    )
    bd.add_sum("total_cash_needed", "Total Cash Needed", results_w_intermediates.total_cash_needed, [
        ("Down Payment", results_w_intermediates.down_payment_cash),
        ("Closing", results_w_intermediates.closing_costs_buy),
        ("HML Points", results_w_intermediates.hml_points),
        ("Rehab Cash", results_w_intermediates.rehab_cash),
        ("HML Interest", results_w_intermediates.total_hml_interest),
        ("Operating", results_w_intermediates.total_operating),
    ])
    check(results_w_intermediates.buffered_closing == results_w_intermediates.closing_costs_buy * Decimal("1.1"), "closing buffer")
    bd.add(
        "total_cash_needed_with_buffer", "Closing × 1.1 buffer", results_w_intermediates.buffered_closing,
        f"Closing ({fmt_money(results_w_intermediates.closing_costs_buy)}) × 1.1 = {fmt_money(results_w_intermediates.buffered_closing)}",
    )
    check(results_w_intermediates.buffered_interest == results_w_intermediates.total_hml_interest * Decimal("1.5"), "interest buffer")
    bd.add(
        "total_cash_needed_with_buffer", "HML Interest × 1.5 buffer", results_w_intermediates.buffered_interest,
        f"HML Interest ({fmt_money(results_w_intermediates.total_hml_interest)}) × 1.5 = {fmt_money(results_w_intermediates.buffered_interest)}",
        note="The ×1.5 covers delays in permits, rehab or the sale.",
    )
    check(results_w_intermediates.buffered_operating == results_w_intermediates.total_operating * Decimal("1.5"), "operating buffer")
    bd.add(
        "total_cash_needed_with_buffer", "Operating × 1.5 buffer", results_w_intermediates.buffered_operating,
        f"Operating ({fmt_money(results_w_intermediates.total_operating)}) × 1.5 = {fmt_money(results_w_intermediates.buffered_operating)}",
    )
    check(results_w_intermediates.rehab_float == Decimal("0.1") * results_w_intermediates.rehab_cost, "rehab float")
    bd.add(
        "total_cash_needed_with_buffer", "Rehab float buffer (10% of rehab)", results_w_intermediates.rehab_float,
        f"10% × Rehab ({fmt_money(results_w_intermediates.rehab_cost)}) = {fmt_money(results_w_intermediates.rehab_float)}",
        note="Kept on hand for draws and deposits even when hard money funds the rehab.",
    )
    bd.add_sum("total_cash_needed_with_buffer", "Total Cash Needed (Buffered)", results_w_intermediates.total_cash_needed_with_buffer, [
        ("Down Payment", results_w_intermediates.down_payment_cash),
        ("Closing × 1.1", results_w_intermediates.buffered_closing),
        ("HML Points", results_w_intermediates.hml_points),
        ("Rehab Cash", results_w_intermediates.rehab_cash),
        ("Rehab Float", results_w_intermediates.rehab_float),
        ("HML Interest × 1.5", results_w_intermediates.buffered_interest),
        ("Operating × 1.5", results_w_intermediates.buffered_operating),
    ])

    # -- cost basis and profit -------------------------------------------------
    bd.add_sum("roi", "Total Cash Invested", results_w_intermediates.total_cash_invested, [
        ("Down Payment", results_w_intermediates.down_payment_cash),
        ("Closing", results_w_intermediates.closing_costs_buy),
        ("HML Points", results_w_intermediates.hml_points),
        ("Holding", results_w_intermediates.total_holding_costs),
        ("Rehab Out-of-Pocket", results_w_intermediates.rehab_cash),
    ])
    bd.add_sum("net_profit", "Total Cost Basis", results_w_intermediates.total_cost_basis, [
        ("Purchase", results_w_intermediates.purchase_price),
        ("Rehab", results_w_intermediates.rehab_cost),
        ("Closing", results_w_intermediates.closing_costs_buy),
        ("Holding", results_w_intermediates.total_holding_costs),
        ("Selling", results_w_intermediates.selling_costs),
        ("HML Points", results_w_intermediates.hml_points),
    ])
    bd.add_sum("net_profit", "Gross Profit", results_w_intermediates.gross_profit, [
        ("Sale Price", results_w_intermediates.sale_price),
        ("Total Cost Basis", results_w_intermediates.total_cost_basis, "-"),
    ])
    check(results_w_intermediates.capital_gains_tax == (results_w_intermediates.gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0")) if results_w_intermediates.gross_profit > 0 else Decimal("0")), "capital gains tax")
    bd.add(
        "net_profit", "Capital Gains Tax", results_w_intermediates.capital_gains_tax,
        (f"Gross Profit ({fmt_money(results_w_intermediates.gross_profit)}) × {fmt_pct(payload.capital_gains_tax_rate)} = {fmt_money(results_w_intermediates.capital_gains_tax)}"
         if results_w_intermediates.gross_profit > 0 else f"Gross Profit ({fmt_money(results_w_intermediates.gross_profit)}) ≤ 0 → no tax owed"),
    )
    bd.add_sum(["net_profit", "roi"], "Net Profit (after tax)", results_w_intermediates.net_profit, [
        ("Gross Profit", results_w_intermediates.gross_profit),
        ("Capital Gains Tax", results_w_intermediates.capital_gains_tax, "-"),
    ])

    # -- ROI -------------------------------------------------------------------
    if results_w_intermediates.total_cash_invested > 0:
        check(results_w_intermediates.roi == (results_w_intermediates.net_profit / results_w_intermediates.total_cash_invested) * Decimal("100.0"), "ROI")
        roi_formula = f"Net Profit ({fmt_money(results_w_intermediates.net_profit)}) ÷ Total Cash Invested ({fmt_money(results_w_intermediates.total_cash_invested)}) × 100 = {fmt_pct(results_w_intermediates.roi)}"
    elif results_w_intermediates.net_profit > 0:
        check(results_w_intermediates.roi == Decimal("-1"), "ROI (infinite)")
        roi_formula = f"No cash invested with Net Profit {fmt_money(results_w_intermediates.net_profit)} → return is infinite (∞)"
    elif results_w_intermediates.net_profit < 0:
        check(results_w_intermediates.roi == Decimal("-2"), "ROI (-infinite)")
        roi_formula = f"No cash invested with Net Profit {fmt_money(results_w_intermediates.net_profit)} → return is -∞"
    else:
        check(results_w_intermediates.roi == Decimal("0"), "ROI (break-even)")
        roi_formula = "No cash invested and no profit → ROI = 0%"
    bd.add(["roi", "annualized_roi"], "ROI", results_w_intermediates.roi, roi_formula, unit="pct")

    check(results_w_intermediates.holding_years == months / Decimal("12.0"), "holding years")
    if results_w_intermediates.total_cash_invested <= 0:
        check(results_w_intermediates.annualized_roi == results_w_intermediates.roi, "annualized ROI (sentinel)")
        ann_formula = "ROI is unbounded (no cash invested) → Annualized ROI carries the same sentinel"
    elif results_w_intermediates.holding_years > 0:
        check(results_w_intermediates.annualized_roi == results_w_intermediates.roi / results_w_intermediates.holding_years, "annualized ROI")
        ann_formula = f"ROI ({fmt_pct(results_w_intermediates.roi)}) ÷ Holding Years ({fmt_num(results_w_intermediates.holding_years)}) = {fmt_pct(results_w_intermediates.annualized_roi)}"
    else:
        check(results_w_intermediates.annualized_roi == Decimal("0"), "annualized ROI (no hold)")
        ann_formula = "Holding time is 0 → Annualized ROI = 0%"
    bd.add("annualized_roi", "Annualized ROI", results_w_intermediates.annualized_roi, ann_formula, unit="pct",
           note=f"Holding Years = {months} months ÷ 12.")
    return bd.to_dict()
