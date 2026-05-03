"""DB-backed CRUD for the REPS feature.

Two small reference tables live in the app DB:
- `reps_people`     — contractors / agents the user tags on log entries.
- `reps_properties` — prospect addresses the user types into the autocomplete
                      that aren't yet in `bought_brrrr_deals` / `bought_flip_deals`.

The actual time entries themselves are NOT stored here — those go directly to
each user's Google Sheet, which is the audit-of-record. This file only manages
the reference data the frontend needs to render the entry form.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from models import (
    RepsPerson,
    RepsProperty,
    BoughtBrrrDeal,
    BoughtFlipDeal,
)
from ReqRes.reps.repsReq import (
    RepsPersonCreate,
    RepsPersonUpdate,
    RepsPropertyOption,
)


# --- People --------------------------------------------------------------- #

def list_people(db: Session) -> List[RepsPerson]:
    return db.query(RepsPerson).order_by(RepsPerson.name.asc()).all()


def add_person(db: Session, payload: RepsPersonCreate) -> RepsPerson:
    person = RepsPerson(
        name=payload.name.strip(),
        role=(payload.role or None),
        notes=(payload.notes or None),
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def update_person(
    db: Session, person_id: str, payload: RepsPersonUpdate
) -> Optional[RepsPerson]:
    person = db.query(RepsPerson).filter(RepsPerson.id == person_id).first()
    if not person:
        return None
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return person


def delete_person(db: Session, person_id: str) -> bool:
    person = db.query(RepsPerson).filter(RepsPerson.id == person_id).first()
    if not person:
        return False
    db.delete(person)
    db.commit()
    return True


# --- Properties / Prospects ---------------------------------------------- #

def list_property_options(db: Session) -> List[RepsPropertyOption]:
    """Bought-deal addresses (priority) + prospect names, deduplicated.

    The autocomplete wants bought deals first (they are the source of truth
    for properties the user actually owns) and prospects underneath. We
    dedupe case-insensitively so a typed prospect that later becomes a
    bought deal doesn't appear twice.
    """
    bought_addresses: List[str] = []
    for cls in (BoughtBrrrDeal, BoughtFlipDeal):
        for row in db.query(cls.address).filter(cls.address.isnot(None)).all():
            addr = (row[0] or "").strip()
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

    prospects = db.query(RepsProperty).order_by(RepsProperty.name.asc()).all()
    for p in prospects:
        key = (p.name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(RepsPropertyOption(name=p.name, source="prospect"))

    return options


def upsert_prospect(db: Session, name: str) -> RepsProperty:
    """Save a free-typed property name as a prospect. Idempotent on name (case-insensitive)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Property name cannot be empty.")

    existing = (
        db.query(RepsProperty)
        .filter(RepsProperty.name.ilike(name))
        .first()
    )
    if existing:
        return existing

    prospect = RepsProperty(name=name, is_prospect=True)
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return prospect


def delete_prospect(db: Session, prospect_id: str) -> bool:
    prospect = db.query(RepsProperty).filter(RepsProperty.id == prospect_id).first()
    if not prospect:
        return False
    db.delete(prospect)
    db.commit()
    return True
