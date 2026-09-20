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

    # Rehab
    construction_loan_budget_in_thousands = Column(Numeric(14, 4), nullable=False, server_default='0', default=0)
    rehab_cushion = Column(Numeric(12, 2), nullable=False, server_default='5000', default=5000)

    # Rent & holding
    days_until_rented = Column(Integer, nullable=False, server_default='90', default=90)
    monthly_utilities_until_rented = Column(Numeric(12, 2), nullable=False, server_default='80', default=80)
    maintenance_before_refi = Column(Numeric(12, 2), nullable=False, server_default='500', default=500)
    appliances = Column(Numeric(12, 2), nullable=False, server_default='630', default=630)

    # Refinance
    loan_charges_refi = Column(Numeric(12, 2), nullable=False, server_default='200', default=200)
    recording_transfer_refi = Column(Numeric(12, 2), nullable=True)
    title_escrow_refi = Column(Numeric(12, 2), nullable=True)
    online_notary_refi = Column(Boolean, nullable=False, server_default='true', default=True)
    online_notary_fee_refi = Column(Numeric(12, 2), nullable=True)
    appraisal_fee = Column(Numeric(12, 2), nullable=False, server_default='700', default=700)
    survey_fee = Column(Numeric(12, 2), nullable=False, server_default='385', default=385)
    refi_underwriting_fee = Column(Numeric(12, 2), nullable=False, server_default='2000', default=2000)
    broker_processing_fee_refi = Column(Numeric(12, 2), nullable=False, server_default='395', default=395)
    other_closing_costs_refi = Column(Numeric(12, 2), nullable=False, server_default='0', default=0)
    other_closing_costs_refi_note = Column(String(500), nullable=True)
    maintenance_reserve = Column(Numeric(12, 2), nullable=False, server_default='1500', default=1500)
    vacancy_reserve = Column(Numeric(12, 2), nullable=True)
    capex_reserve = Column(Numeric(12, 2), nullable=False, server_default='2500', default=2500)
    lowest_arv_in_thousands = Column(Numeric(14, 4), nullable=True)
