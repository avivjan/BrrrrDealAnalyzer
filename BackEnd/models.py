from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, func

from db import Base


class ActiveDeal(Base):
    __tablename__ = "active_deals"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(Integer, nullable=False)
    stage = Column(Integer, nullable=False)
    address = Column(String, nullable=False)
    zillow_link = Column(String, nullable=True)
    overall_design = Column(String, nullable=True)
    crime_rate = Column(String, nullable=True)
    pics_link = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    task = Column(String, nullable=True)
    niche = Column(String, nullable=True)
    ltv_min_when_dscr_1_15 = Column(Float, nullable=True)
    sold_comps = Column(JSON, nullable=True)
    rent_comps = Column(JSON, nullable=True)
    notes = Column(String, nullable=True)

    arv_in_thousands = Column(Float, nullable=False)
    purchase_price_in_thousands = Column(Float, nullable=False)
    rehab_cost_in_thousands = Column(Float, nullable=False, default=0.0)
    down_payment = Column(Float, nullable=False)
    closing_costs_buy_in_thousands = Column(Float, nullable=False, default=0.0)
    use_HM_for_rehab = Column(Boolean, nullable=False, default=False)
    HML_points = Column(Float, nullable=False, default=0.0)
    Months_until_refi = Column(Float, nullable=False)
    HML_interest_rate = Column(Float, nullable=False)
    closing_cost_refi_in_thousands = Column(Float, nullable=False, default=0.0)
    loan_term_years = Column(Integer, nullable=False, default=30)
    ltv_as_precent = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)
    rent = Column(Float, nullable=False)
    vacancy_percent = Column(Float, nullable=False, default=0.0)
    property_managment_fee_precentages_from_rent = Column(Float, nullable=False, default=0.0)
    maintenance_percent = Column(Float, nullable=False, default=0.0)
    capex_percent_of_rent = Column(Float, nullable=False, default=0.0)
    annual_property_taxes = Column(Float, nullable=False, default=0.0)
    annual_insurance = Column(Float, nullable=False, default=0.0)
    montly_hoa = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
