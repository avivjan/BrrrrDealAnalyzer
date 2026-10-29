"""The lifecycle columns of a BRRRR deal, mixed into both `active_deals` and `bought_brrrr_deals`.

One declaration so a column can never exist on one table and silently drop on `move_to_bought`
(which copies `__table__.columns`). Defaults here == the DDL defaults in
`migrations/steps/brrr_lifecycle_columns.py` == the Pydantic defaults in
`ReqRes/common/brrr_lifecycle_inputs.py` (a PUT rewrites every column).

`nullable=True` with `default=None` means "use the formula" -- see the ReqRes module.
"""

from sqlalchemy import Column, Boolean, Date, Integer, Numeric, String
from sqlalchemy.orm import declarative_mixin


@declarative_mixin
class BrrrLifecycleColumns:
    # Buy
    buy_closing_date = Column(Date, nullable=True)
    earnest_money_deposit = Column(Numeric(12, 2), nullable=False, server_default='5000', default=5000)
    loan_charges_buy = Column(Numeric(12, 2), nullable=False, server_default='900', default=900)
    recording_transfer_buy = Column(Numeric(12, 2), nullable=True)
    title_mode_buy = Column(String(20), nullable=False, server_default='standard', default='standard')
    title_escrow_buy = Column(Numeric(12, 2), nullable=True)
    online_notary_buy = Column(Boolean, nullable=False, server_default='true', default=True)
    online_notary_fee_buy = Column(Numeric(12, 2), nullable=True)
    other_closing_costs_buy = Column(Numeric(12, 2), nullable=False, server_default='0', default=0)
    other_closing_costs_buy_note = Column(String(500), nullable=True)
    seller_paid_current_year_taxes = Column(Boolean, nullable=True)
    seller_tax_credit_at_purchase_closing = Column(Numeric(12, 2), nullable=True)
    insurance_purchase_bill_payment_timing = Column(String(30), nullable=False, server_default='inside_purchase_closing', default='inside_purchase_closing')

    # Rehab
    construction_loan_budget_in_thousands = Column(Numeric(14, 4), nullable=False, server_default='0', default=0)
    rehab_cushion = Column(Numeric(12, 2), nullable=False, server_default='5000', default=5000)
    days_until_rehab_completed = Column(Integer, nullable=False, server_default='45', default=45)

    # Rent & holding
    days_until_rented = Column(Integer, nullable=False, server_default='90', default=90)
    monthly_utilities_until_rented = Column(Numeric(12, 2), nullable=False, server_default='80', default=80)
    maintenance_before_refi = Column(Numeric(12, 2), nullable=False, server_default='500', default=500)
    appliances = Column(Numeric(12, 2), nullable=False, server_default='630', default=630)
    monthly_insurance_until_refi = Column(Numeric(12, 2), nullable=False, server_default='0', default=0)
    monthly_property_tax_bucket_deposit = Column(Numeric(12, 2), nullable=True)

    # Refinance
    loan_charges_refi = Column(Numeric(12, 2), nullable=False, server_default='200', default=200)
    recording_transfer_refi = Column(Numeric(12, 2), nullable=True)
    title_escrow_refi = Column(Numeric(12, 2), nullable=True)
    online_notary_refi = Column(Boolean, nullable=False, server_default='true', default=True)
    online_notary_fee_refi = Column(Numeric(12, 2), nullable=True)
    appraisal_fee = Column(Numeric(12, 2), nullable=False, server_default='700', default=700)
    survey_fee = Column(Numeric(12, 2), nullable=False, server_default='385', default=385)
    refi_underwriting_fee = Column(Numeric(12, 2), nullable=False, server_default='2000', default=2000)
    broker_processing_fee_refi = Column(Numeric(12, 2), nullable=False, server_default='0', default=0)
    other_closing_costs_refi = Column(Numeric(12, 2), nullable=False, server_default='0', default=0)
    other_closing_costs_refi_note = Column(String(500), nullable=True)
    insurance_bill_at_refi_closing = Column(Numeric(12, 2), nullable=True)
    insurance_refi_bill_payment_timing = Column(String(30), nullable=False, server_default='inside_refi_closing', default='inside_refi_closing')
    monthly_insurance_after_refi = Column(Numeric(12, 2), nullable=True)
    property_tax_collection_at_refi = Column(String(40), nullable=False, server_default='no_tax_collected_at_refi', default='no_tax_collected_at_refi')
    property_tax_lump_sum_at_refi_closing = Column(Numeric(12, 2), nullable=True)
    maintenance_reserve = Column(Numeric(12, 2), nullable=False, server_default='1500', default=1500)
    vacancy_reserve = Column(Numeric(12, 2), nullable=True)
    capex_reserve = Column(Numeric(12, 2), nullable=False, server_default='2500', default=2500)
    hysa_deposit_at_refi = Column(Numeric(12, 2), nullable=True)
    lowest_arv_in_thousands = Column(Numeric(14, 4), nullable=True)
