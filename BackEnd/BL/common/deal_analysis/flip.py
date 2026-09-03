"""The Flip calculation, broken into named steps that mirror the
`breakdowns` dict's own metric groupings.

`calculate_flip_results` accepts either the Pydantic request model
(`analyzeFlipReq`) or an ORM deal row -- everything here is duck-typed
attribute access, which is what lets `BL.common.deal_response.create_deal_response`
pass a `FlipActiveDeal` straight in. Every step function below follows the
same contract: it takes only the already-computed values it needs, does its
slice of `calc_*` calls *and* its slice of `breakdown.add(...)` calls, and
returns only the new value(s) later steps or the final response need.

This is a pure reorganization of what was previously one ~225-line function --
every calculation, every `breakdown.add()` call (keys, label, formula text),
and every explanatory comment is unchanged, just relocated.
"""

from decimal import Decimal

from ReqRes.common.analyze_results import analyzeFlipRes
from BL.common.calc_breakdown import CalcBreakdown, fmt_money, fmt_pct, fmt_num
from BL.common.deal_math import (
    thousands_to_dollars,
    get_HML_amount,
    get_total_cash_needed_for_deal,
)


def _dollar_basis_and_rehab_cost(payload, breakdown):
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency
    breakdown.add(
        "net_profit",
        "Rehab Cost (with contingency)",
        rehab_cost,
        f"Base ({fmt_money(rehab_cost_base)}) + Contingency {fmt_pct(payload.rehab_contingency_percent)} ({fmt_money(contingency)}) = {fmt_money(rehab_cost)}",
    )
    sale_price = thousands_to_dollars(payload.sale_price_in_thousands)
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    return purchase_price, sale_price, closing_costs_buy, rehab_cost


def _hml_costs(payload, breakdown, purchase_price, rehab_cost):
    hml_amount = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    breakdown.add(
        "total_hml_interest",
        "HML Amount",
        hml_amount,
        (f"Purchase Loan + Rehab ({fmt_money(hml_amount)}) — full HM stack"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(purchase_price)}) = {fmt_money(hml_amount)}"),
    )
    hml_points_cash = (payload.HML_points / Decimal("100.0")) * hml_amount
    breakdown.add(
        "net_profit",
        "HML Points (cash)",
        hml_points_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_amount)}) = {fmt_money(hml_points_cash)}",
    )

    monthly_interest = (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * hml_amount
    breakdown.add(
        "total_hml_interest",
        "Monthly HML Interest",
        monthly_interest,
        f"HML Amount ({fmt_money(hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 12 = {fmt_money(monthly_interest)}",
    )
    total_hml_interest = monthly_interest * payload.holding_time_months
    breakdown.add(
        ["net_profit", "total_hml_interest", "total_holding_costs"],
        "Total HML Interest (over holding period)",
        total_hml_interest,
        f"Monthly Interest ({fmt_money(monthly_interest)}) × {payload.holding_time_months} mos = {fmt_money(total_hml_interest)}",
    )
    return hml_amount, hml_points_cash, total_hml_interest


def _operating_and_holding_costs(payload, breakdown, total_hml_interest):
    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    monthly_operating = monthly_taxes + monthly_insurance + payload.montly_hoa + payload.monthly_utilities
    total_operating = monthly_operating * payload.holding_time_months
    breakdown.add(
        ["net_profit", "total_holding_costs"],
        "Total Operating Costs (during holding)",
        total_operating,
        f"(Taxes/12 ({fmt_money(monthly_taxes)}) + Insurance/12 ({fmt_money(monthly_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) + Utilities ({fmt_money(payload.monthly_utilities)})) × {payload.holding_time_months} mos = {fmt_money(total_operating)}",
    )

    total_holding_costs = total_hml_interest + total_operating
    breakdown.add(
        ["net_profit", "total_holding_costs"],
        "Total Holding Costs",
        total_holding_costs,
        f"HML Interest ({fmt_money(total_hml_interest)}) + Operating ({fmt_money(total_operating)}) = {fmt_money(total_holding_costs)}",
    )
    return total_operating, total_holding_costs


def _selling_costs(payload, breakdown, sale_price):
    agent_fees_percent = payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee
    selling_costs = sale_price * (agent_fees_percent / Decimal("100.0")) + thousands_to_dollars(payload.selling_closing_costs_in_thousands)
    breakdown.add(
        "net_profit",
        "Selling Costs",
        selling_costs,
        f"Sale Price ({fmt_money(sale_price)}) × Agent Fees {fmt_pct(agent_fees_percent)} + Closing ({fmt_money(thousands_to_dollars(payload.selling_closing_costs_in_thousands))}) = {fmt_money(selling_costs)}",
    )
    return selling_costs


def _total_cash_needed(
    payload, breakdown, purchase_price, closing_costs_buy, hml_amount, hml_points_cash, rehab_cost,
    total_operating, total_hml_interest,
):
    down_payment_cash = (payload.down_payment / Decimal("100.0")) * purchase_price
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Down Payment (cash)",
        down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(purchase_price)}) = {fmt_money(down_payment_cash)}",
    )
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Closing Costs (Buy)",
        closing_costs_buy,
        f"{fmt_money(closing_costs_buy)}",
    )
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "HML Points (cash)",
        hml_points_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_amount)}) = {fmt_money(hml_points_cash)}",
    )

    total_cash_needed_without_buffer, total_cash_needed_with_buffer = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, total_operating, closing_costs_buy, hml_points_cash, rehab_cost, total_hml_interest, payload.use_HM_for_rehab)
    rehab_cash = rehab_cost if not payload.use_HM_for_rehab else Decimal("0")
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Rehab Cash (out-of-pocket)",
        rehab_cash,
        (f"Rehab ({fmt_money(rehab_cost)}) is financed via HM → no out-of-pocket = {fmt_money(rehab_cash)}"
         if payload.use_HM_for_rehab
         else f"Rehab ({fmt_money(rehab_cost)}) paid in cash = {fmt_money(rehab_cash)}"),
    )
    breakdown.add(
        "total_cash_needed",
        "HML Interest (cash, during holding)",
        total_hml_interest,
        f"Monthly Interest × {payload.holding_time_months} mos = {fmt_money(total_hml_interest)}",
    )
    breakdown.add(
        "total_cash_needed",
        "Operating Costs (during holding)",
        total_operating,
        f"Monthly Operating × {payload.holding_time_months} mos = {fmt_money(total_operating)}",
    )
    breakdown.add(
        "total_cash_needed",
        "Total Cash Needed",
        total_cash_needed_without_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(hml_points_cash)}) + Rehab Cash ({fmt_money(rehab_cash)}) + HML Interest ({fmt_money(total_hml_interest)}) + Operating ({fmt_money(total_operating)}) = {fmt_money(total_cash_needed_without_buffer)}",
    )
    # Buffered version mirrors `get_total_cash_needed_for_deal` internals:
    # operating × 1.5, interest × 1.5, closing × 1.1.
    _flip_buffered_closing = closing_costs_buy * Decimal("1.1")
    _flip_buffered_interest = total_hml_interest * Decimal("1.5")
    _flip_buffered_operating = total_operating * Decimal("1.5")
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Closing × 1.1 buffer",
        _flip_buffered_closing,
        f"Closing ({fmt_money(closing_costs_buy)}) × 1.1 = {fmt_money(_flip_buffered_closing)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "HML Interest × 1.5 buffer",
        _flip_buffered_interest,
        f"HML Interest ({fmt_money(total_hml_interest)}) × 1.5 = {fmt_money(_flip_buffered_interest)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Operating × 1.5 buffer",
        _flip_buffered_operating,
        f"Operating ({fmt_money(total_operating)}) × 1.5 = {fmt_money(_flip_buffered_operating)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Total Cash Needed (Buffered)",
        total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing×1.1 ({fmt_money(_flip_buffered_closing)}) + HML Points ({fmt_money(hml_points_cash)}) + Rehab Cash ({fmt_money(rehab_cash)}) + HML Interest×1.5 ({fmt_money(_flip_buffered_interest)}) + Operating×1.5 ({fmt_money(_flip_buffered_operating)}) = {fmt_money(total_cash_needed_with_buffer)}",
    )
    return total_cash_needed_without_buffer, total_cash_needed_with_buffer, down_payment_cash, rehab_cash


def _cash_invested_and_cost_basis(
    payload, breakdown, purchase_price, rehab_cost, closing_costs_buy, total_holding_costs,
    selling_costs, hml_points_cash, down_payment_cash, rehab_cash, sale_price,
):
    total_cash_invested = down_payment_cash + closing_costs_buy + hml_points_cash + total_holding_costs + rehab_cash
    breakdown.add(
        "roi",
        "Total Cash Invested",
        total_cash_invested,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(hml_points_cash)}) + Holding ({fmt_money(total_holding_costs)}) + Rehab Out-of-Pocket ({fmt_money(rehab_cash)}) = {fmt_money(total_cash_invested)}",
    )

    # Cost basis for profit calc
    total_cost_basis = purchase_price + rehab_cost + closing_costs_buy + total_holding_costs + selling_costs + hml_points_cash
    breakdown.add(
        "net_profit",
        "Total Cost Basis",
        total_cost_basis,
        f"Purchase ({fmt_money(purchase_price)}) + Rehab ({fmt_money(rehab_cost)}) + Closing ({fmt_money(closing_costs_buy)}) + Holding ({fmt_money(total_holding_costs)}) + Selling ({fmt_money(selling_costs)}) + HML Points ({fmt_money(hml_points_cash)}) = {fmt_money(total_cost_basis)}",
    )

    gross_profit = sale_price - total_cost_basis
    breakdown.add(
        "net_profit",
        "Gross Profit",
        gross_profit,
        f"Sale Price ({fmt_money(sale_price)}) − Total Cost Basis ({fmt_money(total_cost_basis)}) = {fmt_money(gross_profit)}",
    )
    return total_cash_invested, gross_profit


def _net_profit_after_tax(payload, breakdown, gross_profit):
    cap_gains = Decimal("0")
    if gross_profit > 0:
        cap_gains = gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0"))
    breakdown.add(
        "net_profit",
        "Capital Gains Tax",
        cap_gains,
        (f"Gross Profit ({fmt_money(gross_profit)}) × {fmt_pct(payload.capital_gains_tax_rate)} = {fmt_money(cap_gains)}"
         if gross_profit > 0 else f"Gross Profit ≤ 0 → no tax owed = {fmt_money(cap_gains)}"),
    )

    net_profit = gross_profit - cap_gains
    breakdown.add(
        ["net_profit", "roi"],
        "Net Profit (after tax)",
        net_profit,
        f"Gross Profit ({fmt_money(gross_profit)}) − Capital Gains Tax ({fmt_money(cap_gains)}) = {fmt_money(net_profit)}",
    )
    return net_profit


def _roi_and_annualized(payload, breakdown, net_profit, total_cash_invested):
    roi = (net_profit / total_cash_invested) * Decimal("100.0") if total_cash_invested > 0 else Decimal("0")
    breakdown.add(
        ["roi", "annualized_roi"],
        "ROI",
        roi,
        (f"Net Profit ({fmt_money(net_profit)}) / Total Cash Invested ({fmt_money(total_cash_invested)}) × 100 = {fmt_pct(roi)}"
         if total_cash_invested > 0 else "Total Cash Invested is 0 → ROI = 0%"),
    )
    years = payload.holding_time_months / Decimal("12.0")
    annualized_roi = (roi / years) if years > 0 else Decimal("0")
    breakdown.add(
        "annualized_roi",
        "Annualized ROI",
        annualized_roi,
        (f"ROI ({fmt_pct(roi)}) / Holding Years ({fmt_num(years)}) = {fmt_pct(annualized_roi)}"
         if years > 0 else "Holding time is 0 → Annualized ROI = 0%"),
    )
    return roi, annualized_roi


def calculate_flip_results(payload) -> analyzeFlipRes:
    """Run every Flip calc step in order and assemble the response.

    Each step below is one self-contained piece of the calculation -- see the
    module docstring for the contract every step function follows. Reading
    top to bottom is reading the calculation itself; the metric keys threaded
    into `breakdown.add()` inside each step are what group these into the
    `breakdowns` dict the frontend/PDF render.
    """
    breakdown = CalcBreakdown()

    purchase_price, sale_price, closing_costs_buy, rehab_cost = _dollar_basis_and_rehab_cost(payload, breakdown)
    hml_amount, hml_points_cash, total_hml_interest = _hml_costs(payload, breakdown, purchase_price, rehab_cost)
    total_operating, total_holding_costs = _operating_and_holding_costs(payload, breakdown, total_hml_interest)
    selling_costs = _selling_costs(payload, breakdown, sale_price)

    total_cash_needed_without_buffer, total_cash_needed_with_buffer, down_payment_cash, rehab_cash = _total_cash_needed(
        payload, breakdown, purchase_price, closing_costs_buy, hml_amount, hml_points_cash, rehab_cost,
        total_operating, total_hml_interest,
    )
    total_cash_invested, gross_profit = _cash_invested_and_cost_basis(
        payload, breakdown, purchase_price, rehab_cost, closing_costs_buy, total_holding_costs,
        selling_costs, hml_points_cash, down_payment_cash, rehab_cash, sale_price,
    )
    net_profit = _net_profit_after_tax(payload, breakdown, gross_profit)
    roi, annualized_roi = _roi_and_annualized(payload, breakdown, net_profit, total_cash_invested)

    return analyzeFlipRes(
        net_profit=net_profit, roi=roi, annualized_roi=annualized_roi,
        total_cash_needed=total_cash_needed_without_buffer,
        total_cash_needed_with_buffer=total_cash_needed_with_buffer,
        total_holding_costs=total_holding_costs,
        total_hml_interest=total_hml_interest, messages=[],
        breakdowns=breakdown.to_dict(),
    )
