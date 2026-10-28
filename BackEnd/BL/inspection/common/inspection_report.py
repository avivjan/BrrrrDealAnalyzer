"""The report sent when an inspection is finished: a PDF, plus the e-mail around it.

The PDF holds the start info, then the Replace and Repair items with their
fields, notes and photo thumbnails, then the windows to replace, the OK
items, the items not checked and the link to the inspection. It never holds
deal data. All user text goes through `escape` before it reaches ReportLab's
Paragraph mini-markup, and the e-mail's HTML is escaped the same way.

    INSPECTION_REPORT_EMAIL       where the report goes (default bigwhalesllc@gmail.com)
    INSPECTION_REPORT_SENDER      the Gmail account it is sent from (default bigwhalesllc@gmail.com;
                                  its app password is EMAIL_PASSWORD, as for offers and the Member Loan)
    INSPECTION_APP_ORIGIN         the site's address for links (default AUTH_APP_ORIGIN, then the first allowed origin)
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from BL.auth.common import settings as auth_settings
from BL.inspection.common.inspection_checklist_config import (
    ITEM_STATUS_NOT_CHECKED,
    ITEM_STATUS_OK,
    ITEM_STATUS_REPAIR,
    ITEM_STATUS_REPLACE,
    UNKNOWN_FIELD_VALUE,
    all_inspection_checklist_items,
    visible_field_values,
)
from BL.inspection.common.inspection_views import WINDOWS_ITEM_KEY, WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY
from DAL.data_models import PropertyInspection, PropertyInspectionItem, PropertyInspectionPhoto

DEFAULT_INSPECTION_REPORT_EMAIL = "bigwhalesllc@gmail.com"
THUMBNAIL_WIDTH_IN_PDF = 1.45 * inch
THUMBNAILS_PER_ROW_IN_PDF = 4

STATUS_LABELS = {ITEM_STATUS_REPLACE: "Replace", ITEM_STATUS_REPAIR: "Repair", ITEM_STATUS_OK: "OK", ITEM_STATUS_NOT_CHECKED: "Not checked"}
STATUS_COLORS = {ITEM_STATUS_REPLACE: colors.HexColor("#b42318"), ITEM_STATUS_REPAIR: colors.HexColor("#92400e"), ITEM_STATUS_OK: colors.HexColor("#15803d")}


def escape_attribute(value: str) -> str:
    """Escaped for an attribute value in either quote style (links in the PDF and the e-mail)."""

    return escape(value, {'"': "&quot;", "'": "&#39;"})


def inspection_report_email_address() -> str:
    return (os.getenv("INSPECTION_REPORT_EMAIL") or "").strip() or DEFAULT_INSPECTION_REPORT_EMAIL


def inspection_report_sender_address() -> str:
    return (os.getenv("INSPECTION_REPORT_SENDER") or "").strip() or DEFAULT_INSPECTION_REPORT_EMAIL


def inspection_app_origin() -> str:
    origin = (os.getenv("INSPECTION_APP_ORIGIN") or "").strip() or (os.getenv("AUTH_APP_ORIGIN") or "").strip()
    return (origin or auth_settings.allowed_origins()[0]).rstrip("/")


def inspection_summary_link(inspection_id: Any) -> str:
    return f"{inspection_app_origin()}/inspections/{inspection_id}/summary"


def format_field_value(field: dict, value: Any) -> str:
    if value == UNKNOWN_FIELD_VALUE:
        return "Unknown"
    if field["type"] == "choice":
        return next((option["label"] for option in field["options"] if option["value"] == value), str(value))
    if field["type"] == "date_or_unknown" and isinstance(value, str):
        try:
            return date.fromisoformat(value).strftime("%b %d, %Y")
        except ValueError:
            return value
    return str(value)


@dataclass
class ReportItem:
    item_key: str
    item_label: str
    item_status: str
    answered_fields: List[tuple[str, str]]
    item_notes: Optional[str]
    thumbnails: List[bytes]


@dataclass
class InspectionReportContent:
    property_address: str
    inspection_date: date
    inspector_name: Optional[str]
    completed_at: Optional[datetime]
    completion_override_reason: Optional[str]
    items_by_status: dict
    windows_needing_replacement_count: int
    photo_count: int
    summary_link: str


def build_inspection_report_content(
    inspection: PropertyInspection, items: Iterable[PropertyInspectionItem], photos: Iterable[PropertyInspectionPhoto]
) -> InspectionReportContent:
    stored_items_by_key = {item.item_key: item for item in items}
    photos = list(photos)
    items_by_status: dict = {status: [] for status in STATUS_LABELS}
    windows_needing_replacement_count = 0
    for checklist_item in all_inspection_checklist_items():
        stored_item = stored_items_by_key.get(checklist_item["key"])
        status = stored_item.item_status if stored_item else ITEM_STATUS_NOT_CHECKED
        field_values = visible_field_values(checklist_item, stored_item.item_field_values or {}) if stored_item and status != ITEM_STATUS_NOT_CHECKED else {}
        fields_by_key = {field["key"]: field for field in checklist_item["fields"]}
        if checklist_item["key"] == WINDOWS_ITEM_KEY and status != ITEM_STATUS_NOT_CHECKED:
            windows_needing_replacement_count = int(field_values.get(WINDOWS_NEEDING_REPLACEMENT_FIELD_KEY) or 0)
        items_by_status[status].append(
            ReportItem(
                item_key=checklist_item["key"],
                item_label=checklist_item["label"],
                item_status=status,
                answered_fields=[(fields_by_key[key]["label"], format_field_value(fields_by_key[key], value)) for key, value in field_values.items()],
                item_notes=stored_item.item_notes if stored_item else None,
                thumbnails=[photo.thumbnail_jpeg for photo in photos if photo.item_key == checklist_item["key"]],
            )
        )
    return InspectionReportContent(
        property_address=inspection.property_address,
        inspection_date=inspection.inspection_date,
        inspector_name=inspection.inspector_name,
        completed_at=inspection.completed_at,
        completion_override_reason=inspection.completion_override_reason,
        items_by_status=items_by_status,
        windows_needing_replacement_count=windows_needing_replacement_count,
        photo_count=len(photos),
        summary_link=inspection_summary_link(inspection.id),
    )


def inspection_report_file_name(content: InspectionReportContent) -> str:
    finished_at = (content.completed_at or datetime.now()).strftime("%Y-%m-%d %H-%M")
    return f"Inspection report {finished_at}.pdf"


# --- PDF ---------------------------------------------------------------- #


def _thumbnail_image(jpeg: bytes) -> Optional[Image]:
    try:
        width, height = ImageReader(io.BytesIO(jpeg)).getSize()
    except Exception:  # noqa: BLE001 -- a broken thumbnail is left out, never a failed report
        return None
    return Image(io.BytesIO(jpeg), width=THUMBNAIL_WIDTH_IN_PDF, height=THUMBNAIL_WIDTH_IN_PDF * height / max(width, 1))


def build_inspection_report_pdf(content: InspectionReportContent) -> bytes:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InspectionTitle", parent=styles["Title"], alignment=0, fontSize=20, spaceAfter=4)
    heading_style = ParagraphStyle("InspectionHeading", parent=styles["Heading2"], spaceBefore=12, spaceAfter=4)
    item_style = ParagraphStyle("InspectionItem", parent=styles["Heading4"], spaceBefore=8, spaceAfter=2)
    body_style = ParagraphStyle("InspectionBody", parent=styles["BodyText"], fontSize=10, leading=13)
    muted_style = ParagraphStyle("InspectionMuted", parent=body_style, textColor=colors.HexColor("#475569"))

    story: list = [
        Paragraph("Property inspection report", muted_style),
        Paragraph(escape(content.property_address), title_style),
    ]
    start_info = [
        ["Date", escape(content.inspection_date.strftime("%B %d, %Y"))],
        ["Inspector", escape(content.inspector_name or "—")],
        ["Finished", escape(content.completed_at.strftime("%B %d, %Y %H:%M UTC") if content.completed_at else "—")],
        ["Photos", str(content.photo_count)],
    ]
    start_table = Table([[Paragraph(label, muted_style), Paragraph(value, body_style)] for label, value in start_info], colWidths=[1.1 * inch, 5.4 * inch], hAlign="LEFT")
    start_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [start_table]
    if content.completion_override_reason:
        story += [Spacer(1, 6), Paragraph("<b>Finished before every critical item was checked:</b> " + escape(content.completion_override_reason), body_style)]

    for status in (ITEM_STATUS_REPLACE, ITEM_STATUS_REPAIR):
        status_items = content.items_by_status[status]
        story.append(Paragraph(f'<font color="{STATUS_COLORS[status].hexval()}">{STATUS_LABELS[status]}</font> ({len(status_items)})', heading_style))
        if not status_items:
            story.append(Paragraph(f"Nothing marked {STATUS_LABELS[status]}.", muted_style))
        for report_item in status_items:
            story.append(Paragraph(escape(report_item.item_label), item_style))
            for field_label, field_value in report_item.answered_fields:
                story.append(Paragraph(f"{escape(field_label)}: <b>{escape(field_value)}</b>", body_style))
            if report_item.item_notes:
                story.append(Paragraph(escape(report_item.item_notes).replace("\n", "<br/>"), body_style))
            thumbnails = [image for image in (_thumbnail_image(jpeg) for jpeg in report_item.thumbnails) if image]
            if thumbnails:
                rows = [thumbnails[index:index + THUMBNAILS_PER_ROW_IN_PDF] for index in range(0, len(thumbnails), THUMBNAILS_PER_ROW_IN_PDF)]
                rows[-1] += [""] * (THUMBNAILS_PER_ROW_IN_PDF - len(rows[-1]))
                photo_table = Table(rows, colWidths=[THUMBNAIL_WIDTH_IN_PDF + 6] * THUMBNAILS_PER_ROW_IN_PDF, hAlign="LEFT")
                photo_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
                story += [Spacer(1, 4), photo_table]

    story.append(Paragraph(f"Windows to replace: {content.windows_needing_replacement_count}", heading_style))
    ok_items = content.items_by_status[ITEM_STATUS_OK]
    story.append(Paragraph(f'<font color="{STATUS_COLORS[ITEM_STATUS_OK].hexval()}">OK</font> ({len(ok_items)})', heading_style))
    for report_item in ok_items:
        details = "; ".join(f"{escape(label)}: {escape(value)}" for label, value in report_item.answered_fields)
        story.append(Paragraph(f"<b>{escape(report_item.item_label)}</b>" + (f" — {details}" if details else ""), body_style))
    not_checked_items = content.items_by_status[ITEM_STATUS_NOT_CHECKED]
    if not_checked_items:
        story.append(Paragraph(f"Not checked ({len(not_checked_items)})", heading_style))
        story.append(Paragraph(escape(", ".join(item.item_label for item in not_checked_items)), body_style))
    story += [Spacer(1, 14), Paragraph(f'Open the inspection: <link href="{escape_attribute(content.summary_link)}">{escape(content.summary_link)}</link>', muted_style)]

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title=f"Inspection report – {content.property_address}", author="Big Whales",
    )
    document.build(story)
    return buffer.getvalue()


# --- e-mail ------------------------------------------------------------- #


def inspection_report_email_subject(content: InspectionReportContent) -> str:
    return f"Inspection completed – {content.property_address}"


def _counts_line(content: InspectionReportContent) -> str:
    return ", ".join(f"{STATUS_LABELS[status]}: {len(content.items_by_status[status])}" for status in STATUS_LABELS)


def inspection_report_email_text(content: InspectionReportContent, drive_folder_url: Optional[str]) -> str:
    lines = [
        f"Inspection completed: {content.property_address}",
        f"Date: {content.inspection_date.isoformat()}" + (f" · Inspector: {content.inspector_name}" if content.inspector_name else ""),
        _counts_line(content),
        f"Windows to replace: {content.windows_needing_replacement_count}",
    ]
    if content.completion_override_reason:
        lines.append(f"Finished early because: {content.completion_override_reason}")
    for status in (ITEM_STATUS_REPLACE, ITEM_STATUS_REPAIR):
        for report_item in content.items_by_status[status]:
            details = "; ".join(f"{label}: {value}" for label, value in report_item.answered_fields)
            lines.append(f"- {STATUS_LABELS[status]}: {report_item.item_label}" + (f" ({details})" if details else "") + (f" — {report_item.item_notes}" if report_item.item_notes else ""))
    lines += ["", f"Inspection: {content.summary_link}"]
    if drive_folder_url:
        lines.append(f"Drive folder: {drive_folder_url}")
    lines.append("The full report is attached as a PDF.")
    return "\n".join(lines)


def inspection_report_email_html(content: InspectionReportContent, drive_folder_url: Optional[str]) -> str:
    rows = []
    for status in (ITEM_STATUS_REPLACE, ITEM_STATUS_REPAIR):
        for report_item in content.items_by_status[status]:
            details = "; ".join(f"{escape(label)}: <b>{escape(value)}</b>" for label, value in report_item.answered_fields)
            notes = f"<br><span style='color:#475569'>{escape(report_item.item_notes)}</span>" if report_item.item_notes else ""
            rows.append(
                f"<li><b style='color:{STATUS_COLORS[status].hexval()}'>{STATUS_LABELS[status]}</b> · {escape(report_item.item_label)}"
                + (f" — {details}" if details else "") + notes + "</li>"
            )
    override = f"<p><b>Finished early because:</b> {escape(content.completion_override_reason)}</p>" if content.completion_override_reason else ""
    drive_link = f" · <a href='{escape_attribute(drive_folder_url)}'>Drive folder</a>" if drive_folder_url else ""
    return (
        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#0f172a'>"
        f"<h2 style='margin:0 0 4px'>Inspection completed</h2><p style='margin:0 0 12px;font-size:16px'>{escape(content.property_address)}</p>"
        f"<p>{escape(content.inspection_date.isoformat())}" + (f" · {escape(content.inspector_name)}" if content.inspector_name else "") + "</p>"
        f"<p>{escape(_counts_line(content))} · Windows to replace: {content.windows_needing_replacement_count}</p>"
        + override
        + (f"<ul>{''.join(rows)}</ul>" if rows else "<p>Nothing to repair or replace.</p>")
        + f"<p><a href='{escape_attribute(content.summary_link)}'>Open the inspection</a>{drive_link}</p>"
        "<p style='color:#475569'>The full report is attached as a PDF.</p></div>"
    )
