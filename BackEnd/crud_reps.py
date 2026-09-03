"""Backwards-compatible shim -- moved to DAL/crud/reps.py."""

from DAL.crud.reps import (  # noqa: F401
    list_people,
    add_person,
    update_person,
    delete_person,
    list_property_options,
    upsert_prospect,
    delete_prospect,
    ensure_activity_category_defaults,
    list_activity_categories,
    add_activity_category,
    delete_activity_category,
)
