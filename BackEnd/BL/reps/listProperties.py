from typing import List
from sqlalchemy.orm import Session

from ReqRes.common.reps_schemas import RepsPropertyOption
from DAL.crud.reps import get_bought_deal_addresses, list_prospects


def list_property_options(db: Session) -> List[RepsPropertyOption]:
    """Bought-deal addresses (priority) + prospect names, deduplicated.

    The autocomplete wants bought deals first (they are the source of truth
    for properties the user actually owns) and prospects underneath. We
    dedupe case-insensitively so a typed prospect that later becomes a
    bought deal doesn't appear twice.
    """
    bought_addresses: List[str] = []
    for addr in get_bought_deal_addresses(db):
        addr = (addr or "").strip()
        if addr:
            bought_addresses.append(addr)

    seen: set[str] = set()
    options: List[RepsPropertyOption] = []
    for addr in bought_addresses:
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append(RepsPropertyOption(name=addr, source="bought"))

    prospects = list_prospects(db)
    for p in prospects:
        key = (p.name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(RepsPropertyOption(name=p.name, source="prospect"))

    return options
