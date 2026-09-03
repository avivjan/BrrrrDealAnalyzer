from sqlalchemy import Column, Integer, String, JSON, Numeric, Uuid

from db import Base
from DAL.data_models.common.base_deal import BaseDeal


class BoughtBrrrDeal(Base, BaseDeal):
    __tablename__ = "bought_brrrr_deals"

    # BRRRR Specific (same as BrrrActiveDeal)
    arv_in_thousands = Column(Numeric(14, 4), nullable=False)
    days_until_refi = Column(Integer, nullable=False, server_default='180', default=180)
    closing_cost_refi_in_thousands = Column(Numeric(14, 4), nullable=False, default=0.0)
    refi_points = Column(Numeric(5, 2), nullable=False, server_default='1.5', default=1.5)
    cash_reserve_in_thousands = Column(Numeric(14, 4), nullable=False, server_default='0', default=0.0)
    loan_term_years = Column(Integer, nullable=False, default=30)
    ltv_as_precent = Column(Numeric(5, 2), nullable=False)
    interest_rate = Column(Numeric(5, 2), nullable=False)
    rent = Column(Numeric(12, 2), nullable=False)
    vacancy_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    property_managment_fee_precentages_from_rent = Column(Numeric(5, 2), nullable=False, default=0.0)
    maintenance_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    capex_percent_of_rent = Column(Numeric(5, 2), nullable=False, default=0.0)

    # Bought deal columns
    # `bought_stage` is a stable string ID (slug for defaults, UUID-prefixed for
    # user-added stages). See PipelineTemplate. Stored as TEXT for portability.
    bought_stage = Column(String, nullable=False, default="purchase")
    completed_substages = Column(JSON, nullable=False, default=dict)
    source_deal_id = Column(Uuid(as_uuid=True), nullable=True)


class BoughtFlipDeal(Base, BaseDeal):
    __tablename__ = "bought_flip_deals"

    # Flip Specific (same as FlipActiveDeal)
    sale_price_in_thousands = Column(Numeric(14, 4), nullable=False)
    holding_time_months = Column(Integer, nullable=False)
    buyer_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    seller_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    selling_closing_costs_in_thousands = Column(Numeric(14, 4), nullable=False, default=0.0)
    monthly_utilities = Column(Numeric(12, 2), nullable=False, default=0.0)
    capital_gains_tax_rate = Column(Numeric(5, 2), nullable=False, default=0.0)
    sale_comps = Column(JSON, nullable=True)

    # Bought deal columns (string stage ID, see note above)
    bought_stage = Column(String, nullable=False, default="purchase")
    completed_substages = Column(JSON, nullable=False, default=dict)
    source_deal_id = Column(Uuid(as_uuid=True), nullable=True)
