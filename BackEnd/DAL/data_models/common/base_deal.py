from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, func, Numeric, Uuid
from sqlalchemy.orm import declarative_mixin
import uuid


@declarative_mixin
class BaseDeal:
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
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

    # Money columns are stored in *thousands*. The scale is 4 (not 2) so a
    # thousands value can express an exact dollar: at scale 2 the DB rounds to
    # the nearest $10, which would make a $50,500 purchase price unstorable.
    purchase_price_in_thousands = Column(Numeric(14, 4), nullable=False)
    rehab_cost_in_thousands = Column(Numeric(14, 4), nullable=False, default=0.0)
    rehab_contingency_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
    down_payment = Column(Numeric(5, 2), nullable=False)
    closing_costs_buy_in_thousands = Column(Numeric(14, 4), nullable=False, default=0.0)
    use_HM_for_rehab = Column(Boolean, nullable=False, default=False)
    HML_points = Column(Numeric(5, 2), nullable=False, default=0.0)
    HML_interest_rate = Column(Numeric(5, 2), nullable=False)

    # Holding costs (Shared mostly)
    annual_property_taxes = Column(Numeric(12, 2), nullable=False, default=0.0)
    annual_insurance = Column(Numeric(12, 2), nullable=False, default=0.0)
    montly_hoa = Column(Numeric(12, 2), nullable=False, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
