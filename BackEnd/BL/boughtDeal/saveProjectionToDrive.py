"""HTML to Drive (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md): the deal's interactive HTML report, the same
one as the report download, built from the saved Bought deal and saved in the deal's own Google Drive folder as
"<YYYY-MM-DD> deal projection.html"."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional, Union

from sqlalchemy.orm import Session

from BL.analyze.analyzeBRRR import calculate_brrr_results
from BL.analyze.analyzeFlip import calculate_flip_results
from BL.common import deal_drive_folder
from BL.common.deal_drive_folder import DEAL_FOLDER_ITSELF, drive_folder_id_of_deal
from BL.common.deal_response import create_bought_deal_response
from BL.reports.common.deal_html_report import build_deal_html_report
from DAL.data_models import BoughtBrrrDeal, BoughtFlipDeal

DEAL_PROJECTION_FILE_NAME_SUFFIX = "deal projection.html"


@dataclass(frozen=True)
class SavedDealProjection:
    file_name: str
    drive_file_id: str
    drive_folder_url: str


def deal_projection_file_name(projection_date: date) -> str:
    return f"{projection_date.isoformat()} {DEAL_PROJECTION_FILE_NAME_SUFFIX}"


def deal_projection_html(deal: Union[BoughtBrrrDeal, BoughtFlipDeal]) -> str:
    """The interactive report of the saved deal, with its inputs section, exactly as the report download builds it."""
    deal_type = "BRRRR" if isinstance(deal, BoughtBrrrDeal) else "FLIP"
    result = calculate_brrr_results(deal) if deal_type == "BRRRR" else calculate_flip_results(deal)
    deal_inputs = create_bought_deal_response(deal).model_dump(by_alias=True)
    return build_deal_html_report(address=deal.address or "Property", deal_type=deal_type, result=result.model_dump(), deal_inputs=deal_inputs)


def save_bought_deal_projection_to_drive(db: Session, deal_id: str, deal_type: str, projection_date: Optional[date]) -> Optional[SavedDealProjection]:
    """None when there is no such Bought deal. Raises `DealDriveFolderMissing` / `DealDriveFolderLinkInvalid` (the
    deal's link) or `DealDriveFolderUploadFailed` (the Drive script)."""
    deal_model = BoughtBrrrDeal if deal_type == "BRRRR" else BoughtFlipDeal
    try:
        deal = db.get(deal_model, uuid.UUID(str(deal_id)))
    except ValueError:
        return None
    if deal is None:
        return None
    folder_id = drive_folder_id_of_deal(deal)
    file_name = deal_projection_file_name(projection_date or date.today())
    drive_file_id, drive_folder_url = deal_drive_folder.save_file_to_deal_drive_folder(
        folder_id, DEAL_FOLDER_ITSELF, file_name, deal_projection_html(deal).encode("utf-8"))
    return SavedDealProjection(file_name=file_name, drive_file_id=drive_file_id,
                               drive_folder_url=drive_folder_url or (deal.google_drive_link or "").strip())
