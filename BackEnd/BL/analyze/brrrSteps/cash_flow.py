"""BRRRR step: net operating income and monthly cash flow."""


def cash_flow_step(payload, operating_expenses, mortgage_payment):
    net_operating_income = payload.rent - operating_expenses
    cash_flow = net_operating_income - mortgage_payment
    return net_operating_income, cash_flow
