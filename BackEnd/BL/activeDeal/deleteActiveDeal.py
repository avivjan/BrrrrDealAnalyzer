from sqlalchemy.orm import Session

from DAL.crud.active_deal import delete_brrr_deal, delete_flip_deal


def delete_deal(db: Session, deal_id: str, deal_type: str) -> bool:
    """Returns True if a matching deal was deleted.

    We need deal_type here to know which table to delete from. Or we try both.
    Let's try deleting from BRRRR first, if not found try Flip.
    Risk: Deleting wrong deal if ID exists in both.
    BETTER: Require type param. Defaults to BRRRR for backward compatibility?
    Actually, let's try to pass it as query param.
    """
    if deal_type == "BRRRR":
        if delete_brrr_deal(db, deal_id):
            db.commit()
            return True
    elif deal_type == "FLIP":
        if delete_flip_deal(db, deal_id):
            db.commit()
            return True

    # If not specified or failed, maybe try the other if strict mode is off?
    # Let's return False (the router turns this into a 404).
    return False
