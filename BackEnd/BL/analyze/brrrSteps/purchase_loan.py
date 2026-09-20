"""BRRRR step: the hard-money stack at purchase -- purchase loan, down payment, total principal."""

from decimal import Decimal

from BL.analyze.common.deal_math import calc_down_payment_in_cash


def purchase_loan_step(payload, purchase_price, construction_budget):
    purchase_loan_amount = purchase_price * (1 - payload.down_payment / Decimal("100.0"))
    down_payment_cash = calc_down_payment_in_cash(payload.down_payment, purchase_price)
    # The lender funds the whole construction budget (interest accrues on it from day 1;
    # a 0 budget is a cash rehab). Paid off, with the purchase loan, at the refi.
    hml_amount = purchase_loan_amount + construction_budget
    return purchase_loan_amount, down_payment_cash, hml_amount
