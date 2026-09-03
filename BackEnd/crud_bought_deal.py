"""Backwards-compatible shim -- moved to DAL/crud/bought_deal.py."""

from DAL.crud.bought_deal import (  # noqa: F401
    add_bought_brrr_deal,
    add_bought_flip_deal,
    get_all_bought_brrr_deals,
    get_all_bought_flip_deals,
    update_bought_brrr_deal,
    update_bought_flip_deal,
    delete_bought_brrr_deal,
    delete_bought_flip_deal,
    create_bought_from_active_brrr,
    create_bought_from_active_flip,
)
