from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, JSON, func, Numeric, Uuid
from sqlalchemy.orm import declarative_mixin, declared_attr
import uuid

from db import Base


# Stable-ID slugs used when the built-in pipeline defaults are first seeded
# and when migrating legacy integer `bought_stage` values to string IDs.
# NOTE: once assigned, these IDs must never change – they are referenced by
# `bought_stage` on existing deal rows and by keys in `completed_substages`.
DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT: dict[int, str] = {
    1: "purchase",
    2: "prepare_for_closing",
    3: "closed",
    4: "rehab",
    5: "rent",
    6: "prepare_for_refi",
    7: "refinanced",
}

DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT: dict[int, str] = {
    1: "purchase",
    2: "prepare_for_closing",
    3: "closed",
    4: "rehab",
    5: "sell",
    6: "sold",
}


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

    purchase_price_in_thousands = Column(Numeric(12, 2), nullable=False)
    rehab_cost_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
    rehab_contingency_percent = Column(Numeric(5, 2), nullable=False, default=0.0)
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
    refi_points = Column(Numeric(5, 2), nullable=False, server_default='1.5', default=1.5)
    # Cash deposited toward the DSCR loan principal at refi (in thousands).
    # Trades off cash_out for equity; existing rows default to 0 via migration.
    cash_reserve_in_thousands = Column(Numeric(12, 2), nullable=False, server_default='0', default=0.0)
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
    
    
class BoughtBrrrDeal(Base, BaseDeal):
    __tablename__ = "bought_brrrr_deals"

    # BRRRR Specific (same as BrrrActiveDeal)
    arv_in_thousands = Column(Numeric(12, 2), nullable=False)
    Months_until_refi = Column(Numeric(5, 1), nullable=False)
    closing_cost_refi_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
    refi_points = Column(Numeric(5, 2), nullable=False, server_default='1.5', default=1.5)
    cash_reserve_in_thousands = Column(Numeric(12, 2), nullable=False, server_default='0', default=0.0)
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
    sale_price_in_thousands = Column(Numeric(12, 2), nullable=False)
    holding_time_months = Column(Integer, nullable=False)
    buyer_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    seller_agent_selling_fee = Column(Numeric(5, 2), nullable=False, default=0.0)
    selling_closing_costs_in_thousands = Column(Numeric(12, 2), nullable=False, default=0.0)
    monthly_utilities = Column(Numeric(12, 2), nullable=False, default=0.0)
    capital_gains_tax_rate = Column(Numeric(5, 2), nullable=False, default=0.0)
    sale_comps = Column(JSON, nullable=True)

    # Bought deal columns (string stage ID, see note above)
    bought_stage = Column(String, nullable=False, default="purchase")
    completed_substages = Column(JSON, nullable=False, default=dict)
    source_deal_id = Column(Uuid(as_uuid=True), nullable=True)


class PipelineTemplate(Base):
    """Persisted bought-deal pipeline template, one row per deal type.

    `stages` is a JSON array shaped like:
        [
          {"id": "purchase", "name": "Purchase",
           "subStages": [{"id": "purchase_agreement", "label": "Purchase Agreement"}, ...]},
          ...
        ]

    IDs are stable string identifiers. Labels/names are display-only and may
    change freely without impacting existing deals (whose `bought_stage` and
    `completed_substages` keys reference IDs, not labels).
    """

    __tablename__ = "pipeline_templates"

    deal_type = Column(String, primary_key=True)  # "BRRRR" | "FLIP"
    stages = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquidityTransaction(Base):
    """A single cash flow event on the liquidity timeline.
    amount_k is signed: positive = inflow, negative = outflow.
    All amounts are in thousands of dollars ($k).
    """
    __tablename__ = "liquidity_transactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount_k = Column(Numeric(14, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RepsPerson(Base):
    """Audit-trail contact (contractor, agent, lender, etc.) referenced from REPS log entries."""

    __tablename__ = "reps_people"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    role = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RepsProperty(Base):
    """Property/Prospect name referenced from REPS log entries.

    Bought-deal addresses are merged into the dropdown at read time;
    this table stores user-entered prospects (e.g., new addresses typed
    into the autocomplete that aren't bought yet).
    """

    __tablename__ = "reps_properties"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    is_prospect = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RepsActivityCategory(Base):
    """User-managed activity-category dropdown for the REPS log form.

    Seeded with sensible defaults on first boot; users can add their own
    inline from the entry modal. Names are unique (case-insensitive at the
    application layer via crud_reps).
    """

    __tablename__ = "reps_activity_categories"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Seeded once into RepsActivityCategory on first boot.
DEFAULT_REPS_ACTIVITY_CATEGORIES: list[str] = [
    "Acquisition / Underwriting",
    "Construction / Rehab Oversight",
    "Property Management",
    "Tenant / Leasing",
    "Bookkeeping / Admin",
    "Education / Research",
    "Travel — Property",
    "Refinance / Lender Calls",
    "Other",
]


class LiquiditySettings(Base):
    """Singleton row (id=1) holding the opening balance anchor and user prefs.
    opening_balance_k: balance at start-of-day on opening_balance_date, in $k.
    reserve_k: soft-warning threshold, in $k.
    """
    __tablename__ = "liquidity_settings"

    id = Column(Integer, primary_key=True, default=1)
    opening_balance_k = Column(Numeric(14, 4), nullable=False, default=0)
    opening_balance_date = Column(Date, nullable=False)
    reserve_k = Column(Numeric(14, 4), nullable=False, default=5)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
