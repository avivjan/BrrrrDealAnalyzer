from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, func, Numeric
from sqlalchemy.orm import declarative_mixin, declared_attr

from db import Base


@declarative_mixin
class BaseDeal:
    id = Column(Integer, primary_key=True, index=True)
    section = Column(Integer, nullable=False)
    stage = Column(Integer, nullable=False)
    address = Column(String, nullable=False)
    sqft = Column(Numeric(10, 2), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Numeric(4, 2), nullable=True)
    zillow_link = Column(String, nullable=True)
    overall_design = Column(String, nullable=True)
    crime_rate = Column(String, nullable=True)
    pics_link = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    task = Column(String, nullable=True)
    niche = Column(String, nullable=True)
    sold_comps = Column(JSON, nullable=True)
    # rent_comps might be specific to BRRRR, but flips might look at rent comps too for backup strategy? 
    # Prompt says: "if type === 'FLIP', rename 'Rent Comps' to 'For Sale Comps'". 
    # So the field can probably be shared or renamed/aliased. Let's keep it shared as 'comps_2' or keep 'rent_comps' and 'sale_comps'.
    # Existing DB has 'rent_comps'. I'll keep it in Base for simplicity or move to BRRRR.
    # If I move it to BRRRR, Flip won't have it.
    # Let's keep rent_comps in BaseDeal but use it for Sale Comps in Flip or add sale_comps?
    # Prompt: "rename 'Rent Comps' to 'For Sale Comps'". This implies reusing the slot or UI change.
    # Let's add 'sale_comps' for Flip and keep 'rent_comps' for BRRRR.
    # Or just keep 'rent_comps' in Base and ignore it for Flip? 
    # Wait, existing data has 'rent_comps'.
    rent_comps = Column(JSON, nullable=True) 
    
    notes = Column(String, nullable=True)

    purchase_price_in_thousands = Column(Numeric(12, 2), nullable=False)
    rehab_cost_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
    down_payment = Column(Numeric(5, 2), nullable=False)
    closing_costs_buy_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
    use_HM_for_rehab = Column(Boolean, nullable=False, default=False)
    HML_points = Column(Numeric(5, 2), nullable=False, default=0.0)
    HML_interest_rate = Column(Numeric(5, 2), nullable=False)
    
    # Holding costs (Shared mostly)
    annual_property_taxes = Column(Numeric(12, 2), nullable=False, default=0.0)
    annual_insurance = Column(Numeric(12, 2), nullable=False, default=0.0)
    montly_hoa = Column(Numeric(12, 2), nullable=False, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BrrrActiveDeal(Base, BaseDeal):
    __tablename__ = "active_deals"

    # BRRRR Specific
    arv_in_thousands = Column(Numeric(12, 2), nullable=False) # Used for Refi LTV
    Months_until_refi = Column(Numeric(5, 1), nullable=False) # Can be half month?
    closing_cost_refi_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
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
    
    sale_price_in_thousands = Column(Numeric(12, 2), nullable=False) # ARV
    holding_time_months = Column(Integer, nullable=False)
    
    buyer_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    seller_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    selling_closing_costs_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
    
    monthly_utilities = Column(Numeric(12, 2), nullable=False, default=0.0)
    capital_gains_tax_rate = Column(Numeric(5, 2), nullable=False, default=0.0)
    
    sale_comps = Column(JSON, nullable=True)
