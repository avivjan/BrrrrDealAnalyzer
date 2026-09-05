"""Flip step: total cash invested, total cost basis and gross profit.

Called by `calculate_flip_results` in `BL/analyze/analyzeFlip.py`.
"""

from BL.analyze.common.calc_breakdown import fmt_money


def cash_invested_and_cost_basis_step(
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
