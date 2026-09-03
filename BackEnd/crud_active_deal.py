"""Backwards-compatible shim -- moved to DAL/crud/active_deal.py."""

from DAL.crud.active_deal import (  # noqa: F401
    add_brrr_deal,
    add_flip_deal,
    get_all_brrr_deals,
    get_all_flip_deals,
    update_brrr_deal,
    update_flip_deal,
    delete_brrr_deal,
    delete_flip_deal,
    duplicate_brrr_deal,
    duplicate_flip_deal,
)
