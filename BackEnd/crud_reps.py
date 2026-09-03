"""Backwards-compatible shim -- moved to DAL/crud/reps.py (persistence) and
BL/reps/ (business logic)."""

from DAL.crud.reps import (  # noqa: F401
    list_people,
    add_person,
    update_person,
    delete_person,
    get_bought_deal_addresses,
    list_prospects,
    upsert_prospect,
    delete_prospect,
    ensure_activity_category_defaults,
    list_activity_categories,
    add_activity_category,
    delete_activity_category,
)
from BL.reps.listProperties.listProperties import list_property_options  # noqa: F401
