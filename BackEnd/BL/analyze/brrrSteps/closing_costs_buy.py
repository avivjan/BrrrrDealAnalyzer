"""BRRRR step: the purchase settlement -- closing-cost lines, seller tax credit, cash to close."""

from decimal import Decimal
from typing import NamedTuple, Optional

from BL.analyze.common.deal_math import (
    effective, recording_transfer_default, title_escrow_buy_default, calc_seller_tax_credit, ONLINE_NOTARY_FEE,
)


class BuySettlement(NamedTuple):
    recording_transfer_buy: Decimal   # effective
    title_escrow_buy: Decimal         # effective
    notary_buy: Decimal
    closing_costs_buy_total: Decimal
    seller_paid_current_year_taxes: Optional[bool]   # effective; None without a closing date
    seller_tax_credit: Decimal        # positive = credit to the buyer
    cash_to_close_buy: Decimal        # the wire to the title company
    total_hard_money_cost: Decimal


def closing_costs_buy_step(payload, purchase_price, purchase_loan_amount, down_payment_cash, hml, timeline) -> BuySettlement:
    recording = effective(payload.recording_transfer_buy, recording_transfer_default(purchase_loan_amount))
    title = effective(payload.title_escrow_buy, title_escrow_buy_default(payload.title_mode_buy, purchase_price))
    notary = ONLINE_NOTARY_FEE if payload.online_notary_buy else Decimal("0")
    closing_total = payload.loan_charges_buy + recording + title + notary + payload.other_closing_costs_buy

    buy = timeline.buy_closing_date
    if buy is None:
        seller_paid, tax_credit = None, Decimal("0")
    else:
        seller_paid = effective(payload.seller_paid_current_year_taxes, buy.month == 12)
        tax_credit = calc_seller_tax_credit(payload.annual_property_taxes, buy, seller_paid)

    cash_to_close = (down_payment_cash + closing_total + hml.hml_points + hml.prepaid_interest_buy
                     - tax_credit - payload.earnest_money_deposit)
    total_hard_money_cost = hml.hml_points + hml.hml_interest + payload.loan_charges_buy
    return BuySettlement(recording, title, notary, closing_total, seller_paid, tax_credit, cash_to_close, total_hard_money_cost)
