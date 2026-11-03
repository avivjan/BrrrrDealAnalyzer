"""BRRRR step: the purchase settlement -- closing-cost lines (the insurance bill when paid at closing),
seller tax credit, cash to close."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import (
    effective, recording_transfer_buy_default, deed_transfer_tax_buy_default, title_escrow_buy_itemized_default,
    calc_seller_tax_credit, seller_paid_current_year_taxes_by_default, current_year_property_tax_bill_paid_at_purchase_closing,
    ONLINE_NOTARY_FEE,
)


class BuySettlement(NamedTuple):
    deed_transfer_tax_buy: Decimal    # $0 standard; 0.70% of the price when we pay all closing costs
    recording_transfer_buy: Decimal   # effective
    title_office_and_search_fees_buy: Decimal            # the estimate's $350 settlement + $150 title search + $100 lien search
    owners_title_policy_premium_buy: Decimal             # the estimate's owner's policy (FL promulgated rate); $0 on a standard deal
    lenders_title_policy_and_endorsements_buy: Decimal   # the estimate's lender's policy: $250 + $5/$1k of the loan above the price
    title_escrow_buy: Decimal         # effective: input or the Florida estimate (the three above)
    notary_buy: Decimal
    closing_costs_buy_total: Decimal
    seller_paid_current_year_taxes: bool   # effective; False when we pay the bill at closing
    current_year_property_tax_bill_settled_by_purchase_closing: bool   # seller paid it, or we pay it at closing
    property_tax_bill_paid_at_purchase_closing: Decimal   # this year's bill, a line of the settlement when we pay it there
    seller_tax_credit_formula: Decimal   # the proration by the closing date
    seller_tax_credit: Decimal        # effective: input or the formula; positive = credit to the buyer
    seller_tax_credit_set_aside_in_tax_bucket: Decimal   # max(0, credit): put in the property's tax bucket the day after closing
    cash_to_close_buy: Decimal        # the wire to the title company
    total_hard_money_cost: Decimal


def closing_costs_buy_step(payload, purchase_price, hml_amount, down_payment_cash, hml_and_holding, timeline, insurance) -> BuySettlement:
    deed_transfer_tax_buy = deed_transfer_tax_buy_default(payload.title_mode_buy, purchase_price)
    recording_transfer_buy = effective(payload.recording_transfer_buy, recording_transfer_buy_default(hml_amount, deed_transfer_tax_buy))
    title_escrow_buy_estimate = title_escrow_buy_itemized_default(payload.title_mode_buy, purchase_price, hml_amount)
    title_escrow_buy = effective(payload.title_escrow_buy, title_escrow_buy_estimate.total)
    notary_buy = effective(payload.online_notary_fee_buy, ONLINE_NOTARY_FEE) if payload.online_notary_buy else Decimal("0")
    buy_closing_date = timeline.buy_closing_date
    we_pay_current_year_tax_bill_at_closing = payload.buyer_pays_current_year_tax_bill_at_purchase_closing
    seller_paid_current_year_taxes = (False if we_pay_current_year_tax_bill_at_closing else
                                      effective(payload.seller_paid_current_year_taxes, seller_paid_current_year_taxes_by_default(buy_closing_date)))
    property_tax_bill_paid_at_purchase_closing = (current_year_property_tax_bill_paid_at_purchase_closing(payload.annual_property_taxes, buy_closing_date)
                                                  if we_pay_current_year_tax_bill_at_closing else Decimal("0"))
    closing_costs_buy_total = (payload.loan_charges_buy + recording_transfer_buy + title_escrow_buy + notary_buy + payload.other_closing_costs_buy
                               + insurance.insurance_bill_at_purchase_inside_closing + property_tax_bill_paid_at_purchase_closing)

    seller_tax_credit_formula = calc_seller_tax_credit(payload.annual_property_taxes, buy_closing_date, seller_paid_current_year_taxes)
    # The figure on the settlement statement, when typed, wins over the proration.
    seller_tax_credit = effective(payload.seller_tax_credit_at_purchase_closing, seller_tax_credit_formula)
    # A positive credit is the seller's share of this year's bill, which the buyer pays in November: it
    # comes off the wire today and goes into the property's tax bucket the day after, so Cash Needed never
    # keeps it. A negative credit (seller already paid) is the buyer's reimbursement, a real cost that stays.
    # When we pay the whole bill at closing nothing is left to save for: the credit only offsets that line.
    seller_tax_credit_set_aside_in_tax_bucket = (Decimal("0") if we_pay_current_year_tax_bill_at_closing
                                                 else max(Decimal("0"), seller_tax_credit))

    cash_to_close_buy = (down_payment_cash + closing_costs_buy_total + hml_and_holding.hml_points + hml_and_holding.prepaid_interest_buy
                         - seller_tax_credit - payload.earnest_money_deposit)
    total_hard_money_cost = hml_and_holding.hml_points + hml_and_holding.hml_interest + payload.loan_charges_buy
    return BuySettlement(
        deed_transfer_tax_buy=deed_transfer_tax_buy,
        recording_transfer_buy=recording_transfer_buy,
        title_office_and_search_fees_buy=title_escrow_buy_estimate.title_office_and_search_fees,
        owners_title_policy_premium_buy=title_escrow_buy_estimate.owners_title_policy_premium,
        lenders_title_policy_and_endorsements_buy=title_escrow_buy_estimate.lenders_title_policy_and_endorsements,
        title_escrow_buy=title_escrow_buy,
        notary_buy=notary_buy,
        closing_costs_buy_total=closing_costs_buy_total,
        seller_paid_current_year_taxes=seller_paid_current_year_taxes,
        current_year_property_tax_bill_settled_by_purchase_closing=seller_paid_current_year_taxes or we_pay_current_year_tax_bill_at_closing,
        property_tax_bill_paid_at_purchase_closing=property_tax_bill_paid_at_purchase_closing,
        seller_tax_credit_formula=seller_tax_credit_formula,
        seller_tax_credit=seller_tax_credit,
        seller_tax_credit_set_aside_in_tax_bucket=seller_tax_credit_set_aside_in_tax_bucket,
        cash_to_close_buy=cash_to_close_buy,
        total_hard_money_cost=total_hard_money_cost,
    )
