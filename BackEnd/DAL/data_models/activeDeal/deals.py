from sqlalchemy import Column, Integer, JSON, Numeric

from db import Base
from DAL.data_models.common.base_deal import BaseDeal


class BrrrActiveDeal(Base, BaseDeal):
    __tablename__ = "active_deals"

    # BRRRR Specific
    arv_in_thousands = Column(Numeric(14, 4), nullable=False) # Used for Refi LTV
    # Whole days from purchase close to refi close. Replaced the old
    # `Months_until_refi` (see `_migrate_months_until_refi_to_days`); the calc
    # accrues HML interest per diem on a 360-day year, so days is the natural
    # unit and 1 month == 30 days exactly.
    days_until_refi = Column(Integer, nullable=False, server_default='180', default=180)
    closing_cost_refi_in_thousands = Column(Numeric(14, 4), nullable=False, default=0.0)
    refi_points = Column(Numeric(5, 2), nullable=False, server_default='1.5', default=1.5)
    # Cash deposited toward the DSCR loan principal at refi (in thousands).
    # Trades off cash_out for equity; existing rows default to 0 via migration.
    cash_reserve_in_thousands = Column(Numeric(14, 4), nullable=False, server_default='0', default=0.0)
    loan_term_years = Column(Integer, nullable=False, default=30)
    ltv_as_precent = Column(Numeric(5, 2), nullable=False)
    interest_rate = Column(Numeric(5, 2), nullable=False) # Long term loan rate
    rent = Column(Numeric(12, 2), nullable=False)
    vacancy_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    property_managment_fee_precentages_from_rent = Column(Numeric(5, 2), nullable=False, default=0.0)
    maintenance_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    capex_percent_of_rent = Column(Numeric(5, 2), nullable=False, default=0.0)


class FlipActiveDeal(Base, BaseDeal):
    __tablename__ = "flip_deals"

    sale_price_in_thousands = Column(Numeric(14, 4), nullable=False) # ARV
    holding_time_months = Column(Integer, nullable=False)

    buyer_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    seller_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    selling_closing_costs_in_thousands = Column(Numeric(14, 4), nullable=False, default=0.0)

    monthly_utilities = Column(Numeric(12, 2), nullable=False, default=0.0)
    capital_gains_tax_rate = Column(Numeric(5, 2), nullable=False, default=0.0)

    sale_comps = Column(JSON, nullable=True)
