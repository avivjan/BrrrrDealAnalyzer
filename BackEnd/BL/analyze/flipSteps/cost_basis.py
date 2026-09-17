"""Flip step: total cash invested, total cost basis and gross profit."""


def cash_invested_and_cost_basis_step(
    purchase_price, rehab_cost, closing_costs_buy, total_holding_costs,
    selling_costs, hml_points, down_payment_cash, rehab_cash, sale_price,
):
    total_cash_invested = down_payment_cash + closing_costs_buy + hml_points + total_holding_costs + rehab_cash
    total_cost_basis = purchase_price + rehab_cost + closing_costs_buy + total_holding_costs + selling_costs + hml_points
    gross_profit = sale_price - total_cost_basis
    return total_cash_invested, total_cost_basis, gross_profit
