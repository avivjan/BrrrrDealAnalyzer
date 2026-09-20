"""BRRRR step: the purchase settlement -- closing-cost lines, seller tax credit, cash to close."""

from decimal import Decimal
from typing import NamedTuple, Optional

from BL.analyze.common.deal_math import (
    effective, recording_transfer_buy_default, deed_transfer_tax_buy_default, title_escrow_buy_default,
    calc_seller_tax_credit, ONLINE_NOTARY_FEE,
)


class BuySettlement(NamedTuple):
    deed_transfer_tax_buy: Decimal    # $0 standard; 0.70% of the price when we pay all closing costs
    recording_transfer_buy: Decimal   # effective
    title_escrow_buy: Decimal         # effective
    notary_buy: Decimal
    closing_costs_buy_total: Decimal
    seller_paid_current_year_taxes: Optional[bool]   # effective; None without a closing date
    seller_tax_credit: Decimal        # positive = credit to the buyer
    cash_to_close_buy: Decimal        # the wire to the title company
    total_hard_money_cost: Decimal


def closing_costs_buy_step(payload, purchase_price, hml_amount, down_payment_cash, hml_and_holding, timeline) -> BuySettlement:
    deed_transfer_tax_buy = deed_transfer_tax_buy_default(payload.title_mode_buy, purchase_price)
    recording_transfer_buy = effective(payload.recording_transfer_buy, recording_transfer_buy_default(hml_amount, deed_transfer_tax_buy))
    title_escrow_buy = effective(payload.title_escrow_buy, title_escrow_buy_default(payload.title_mode_buy, purchase_price))
    notary_buy = effective(payload.online_notary_fee_buy, ONLINE_NOTARY_FEE) if payload.online_notary_buy else Decimal("0")
    closing_costs_buy_total = payload.loan_charges_buy + recording_transfer_buy + title_escrow_buy + notary_buy + payload.other_closing_costs_buy

    buy_closing_date = timeline.buy_closing_date
    if buy_closing_date is None:
        seller_paid_current_year_taxes, seller_tax_credit = None, Decimal("0")
    else:
        seller_paid_current_year_taxes = effective(payload.seller_paid_current_year_taxes, buy_closing_date.month == 12)
        seller_tax_credit = calc_seller_tax_credit(payload.annual_property_taxes, buy_closing_date, seller_paid_current_year_taxes)

    cash_to_close_buy = (down_payment_cash + closing_costs_buy_total + hml_and_holding.hml_points + hml_and_holding.prepaid_interest_buy
                         - seller_tax_credit - payload.earnest_money_deposit)
    total_hard_money_cost = hml_and_holding.hml_points + hml_and_holding.hml_interest + payload.loan_charges_buy
    return BuySettlement(
        deed_transfer_tax_buy=deed_transfer_tax_buy,
        recording_transfer_buy=recording_transfer_buy,
        title_escrow_buy=title_escrow_buy,
        notary_buy=notary_buy,
        closing_costs_buy_total=closing_costs_buy_total,
        seller_paid_current_year_taxes=seller_paid_current_year_taxes,
        seller_tax_credit=seller_tax_credit,
        cash_to_close_buy=cash_to_close_buy,
        total_hard_money_cost=total_hard_money_cost,
    )
