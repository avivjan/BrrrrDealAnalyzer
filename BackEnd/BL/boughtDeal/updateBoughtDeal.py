from datetime import datetime, timezone
from typing import Optional, Union
from sqlalchemy.orm import Session

from ReqRes.common.bought_deal_schemas import BoughtBrrrDealCreate, BoughtFlipDealCreate
from DAL.crud.bought_deal import update_bought_brrr_deal, update_bought_flip_deal
from DAL.data_models import BoughtBrrrDeal, BoughtFlipDeal
from BL.common.deal_response import create_bought_deal_response
from BL.liquidity.dealCashRows.deal_cash_rows import DEAL_BOARD_BOUGHT
from BL.liquidity.dealCashRows.liquidity_deals import mark_liquidity_rows_out_of_date_if_the_save_changed_them
from BL.analyze.common.validation import validate_brrr_inputs_for_saved_deal, validate_flip_inputs_for_saved_deal
from BL.common.deal_drive_folder import drive_folder_id_from_link


class StaleDealFormError(Exception):
    """The form was loaded before the deal's last change (made elsewhere: another tab, the construction account card):
    saving it would silently undo that change."""


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _refuse_a_stale_form(db: Session, deal_model, deal_id: str, updated_at_the_form_was_loaded_with: Optional[datetime]) -> None:
    """Only when the caller says when its form was loaded (the site does; the Claude connector and older clients do not)."""
    if updated_at_the_form_was_loaded_with is None:
        return
    stored = db.query(deal_model.updated_at).filter(deal_model.id == deal_id).scalar()
    if stored is not None and _as_utc(stored) > _as_utc(updated_at_the_form_was_loaded_with):
        raise StaleDealFormError()


def _refuse_a_changed_link_that_is_not_a_drive_folder(db: Session, deal_model, deal_id: str, new_google_drive_link: Optional[str]) -> None:
    """A new link must be a Google Drive folder link (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md). An
    unchanged one is left alone, so an older deal saved before the rule still saves its other fields."""
    new_link = (new_google_drive_link or "").strip()
    stored_link = (db.query(deal_model.google_drive_link).filter(deal_model.id == deal_id).scalar() or "").strip()
    if new_link and new_link != stored_link:
        drive_folder_id_from_link(new_link)


def update_bought_deal(db: Session, deal_id: str, deal: Union[BoughtBrrrDealCreate, BoughtFlipDealCreate],
                       updated_at_the_form_was_loaded_with: Optional[datetime] = None):
    """Returns the updated deal's response, or `None` if no matching row was found. Raises `StaleDealFormError` when the
    form was loaded before the deal's last change (tasks/todo/ConstructionAccountPerRehab.md)."""
    deal_model = BoughtBrrrDeal if deal.deal_type == "BRRRR" else BoughtFlipDeal
    _refuse_a_stale_form(db, deal_model, deal_id, updated_at_the_form_was_loaded_with)
    _refuse_a_changed_link_that_is_not_a_drive_folder(db, deal_model, deal_id, deal.google_drive_link)
    if deal.deal_type == "BRRRR":
        validate_brrr_inputs_for_saved_deal(deal)
        updated = update_bought_brrr_deal(db, deal_id, deal)
        if updated:
            db.commit()
            db.refresh(updated)
            # An imported deal is never re-synced silently: the change waits for a confirm (tasks/todo/DealCashInLiquidity.md).
            mark_liquidity_rows_out_of_date_if_the_save_changed_them(db, DEAL_BOARD_BOUGHT, updated)
            return create_bought_deal_response(updated)
    elif deal.deal_type == "FLIP":
        validate_flip_inputs_for_saved_deal(deal)
        updated = update_bought_flip_deal(db, deal_id, deal)
        if updated:
            db.commit()
            db.refresh(updated)
            return create_bought_deal_response(updated)

    return None
