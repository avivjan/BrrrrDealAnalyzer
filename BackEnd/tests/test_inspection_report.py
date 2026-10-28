"""The report sent when an inspection is finished: a PDF, e-mailed and saved to Drive
(tasks/todo/InspectionCompletionReport.md)."""

from __future__ import annotations

import io

from pypdf import PdfReader

from BL.inspection.common import inspection_report_delivery
from BL.inspection.common.inspection_photo_google_drive import INSPECTIONS_DRIVE_FOLDER_NAME, build_drive_request_body
from BL.inspection.common.inspection_report import escape_attribute
from DAL.data_models import PropertyInspectionReport
from db import SessionLocal
from tests.inspection_helpers import (  # noqa: F401 -- fixtures
    PUBLIC_WRITE_HEADERS,
    SMALLEST_VALID_JPEG,
    complete_with_override,
    create_bought_deal,
    create_public_inspection,
    find_keys_anywhere,
    inspection_photo_drive,
    inspection_report_outbox,
    update_item,
)


def pdf_text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def stored_reports() -> list[PropertyInspectionReport]:
    with SessionLocal() as db:
        return db.query(PropertyInspectionReport).order_by(PropertyInspectionReport.created_at).all()


def finished_inspection(client) -> dict:
    inspection = create_public_inspection(client, property_address="44 Gulf Blvd, Clearwater, FL", inspector_name="Yarden")
    update_item(client, inspection["id"], "roof", item_status="replace", item_field_values={"roof_type": "tile", "roof_install_year": 2001}, item_notes="Cracked tiles <b>everywhere</b>")
    update_item(client, inspection["id"], "windows", item_status="repair", item_field_values={"windows_needing_replacement_count": 4})
    update_item(client, inspection["id"], "sewer", item_status="ok", item_field_values={"sewer_type": "septic", "septic_last_pump_date": "2024-02-01"})
    return inspection


class TestDelivery:
    def test_finishing_emails_the_pdf_and_saves_it_in_the_inspections_drive_folder(self, client, inspection_report_outbox, inspection_photo_drive, monkeypatch):  # noqa: F811
        monkeypatch.setenv("INSPECTION_REPORT_EMAIL", "bigwhalesllc@gmail.com")
        inspection = finished_inspection(client)
        client.post(
            f"/public/inspections/{inspection['id']}/items/roof/photos",
            files={"full_image": ("p.jpg", SMALLEST_VALID_JPEG, "image/jpeg"), "thumbnail_image": ("t.jpg", SMALLEST_VALID_JPEG, "image/jpeg")},
            headers=PUBLIC_WRITE_HEADERS,
        )
        response = complete_with_override(client, inspection["id"])
        assert response.status_code == 200, response.text

        assert len(inspection_report_outbox.sent_emails) == 1
        email = inspection_report_outbox.sent_emails[0]
        assert email["recipients"] == ["bigwhalesllc@gmail.com"]
        assert email["subject"] == "Inspection completed – 44 Gulf Blvd, Clearwater, FL"
        assert "Replace: Roof" in email["text_body"]
        assert "Windows to replace: 4" in email["text_body"]
        assert "https://drive.google.com/drive/folders/test-folder" in email["text_body"]
        assert f"/inspections/{inspection['id']}/summary" in email["text_body"]
        assert "&lt;b&gt;everywhere&lt;/b&gt;" in email["html_body"]  # user text is escaped in the HTML
        assert email["attachments"][0].filename.startswith("Inspection report ")
        assert email["attachments"][0].filename.endswith(".pdf")

        # Same folder as the inspection's photos.
        assert len(inspection_report_outbox.saved_reports) == 1
        saved = inspection_report_outbox.saved_reports[0]
        assert saved["folder_name"] == inspection_photo_drive.saved_folder_names[0]
        assert saved["folder_name"].endswith(f"({inspection['id'][:8]})")
        assert saved["report_pdf"] == email["attachments"][0].content

        [report] = stored_reports()
        assert (report.email_delivery_status, report.drive_delivery_status) == ("delivered", "delivered")
        assert report.drive_file_id == "drive-report-1"
        assert client.get(f"/public/inspections/{inspection['id']}").json()["report_delivery_status"] == "delivered"

    def test_the_pdf_holds_the_results_but_no_deal_data(self, client, inspection_report_outbox, brrrr_payload):  # noqa: F811
        deal = create_bought_deal(client, brrrr_payload)
        inspection = client.post(f"/bought-deals/{deal['id']}/inspections?deal_type=BRRRR", json={"inspector_name": "Aviv"}, headers=PUBLIC_WRITE_HEADERS).json()
        update_item(client, inspection["id"], "roof", item_status="replace", item_field_values={"roof_type": "tile"}, item_notes="Cracked tiles <b>everywhere</b>")
        update_item(client, inspection["id"], "sewer", item_status="ok", item_field_values={"sewer_type": "city", "septic_last_pump_date": "2024-02-01"})
        complete_with_override(client, inspection["id"], "No attic access during the visit")

        text = pdf_text(inspection_report_outbox.saved_reports[0]["report_pdf"])
        assert deal["address"] in text
        assert "Replace (1)" in text and "Roof type: Tile" in text
        assert "Cracked tiles <b>everywhere</b>" in text  # printed as text, never as markup
        assert "No attic access during the visit" in text
        assert "Windows to replace: 0" in text
        assert "Not checked" in text
        assert "2024" not in text  # the septic date no longer applies to a city sewer
        assert deal["id"] not in text

    def test_finishing_again_sends_a_new_report(self, client, inspection_report_outbox):  # noqa: F811
        inspection = finished_inspection(client)
        complete_with_override(client, inspection["id"])
        update_item(client, inspection["id"], "hvac", item_status="repair")
        complete_with_override(client, inspection["id"])
        assert len(inspection_report_outbox.sent_emails) == 2
        assert len(stored_reports()) == 2
        assert "HVAC" in inspection_report_outbox.sent_emails[1]["text_body"]

    def test_a_failed_delivery_never_undoes_the_finish_and_is_retried_at_most_three_times(self, client, inspection_report_outbox):  # noqa: F811
        inspection_report_outbox.email_should_fail = True
        inspection_report_outbox.drive_should_fail = True
        inspection = finished_inspection(client)
        response = complete_with_override(client, inspection["id"])
        assert response.status_code == 200
        assert client.get(f"/public/inspections/{inspection['id']}").json()["inspection_status"] == "completed"
        [report] = stored_reports()
        assert (report.email_delivery_status, report.email_last_error_type) == ("failed", "MemberLoanEmailNotSent")
        assert client.get(f"/public/inspections/{inspection['id']}").json()["report_delivery_status"] == "will_retry"

        assert inspection_report_delivery.retry_failed_inspection_report_deliveries() == 1
        inspection_report_outbox.email_should_fail = False
        assert inspection_report_delivery.retry_failed_inspection_report_deliveries() == 1
        [report] = stored_reports()
        assert (report.email_delivery_status, report.email_attempt_count) == ("delivered", 3)
        assert (report.drive_delivery_status, report.drive_attempt_count) == ("failed", 3)
        assert inspection_report_delivery.retry_failed_inspection_report_deliveries() == 0  # out of attempts
        assert len(inspection_report_outbox.sent_emails) == 1

    def test_without_mail_or_drive_settings_finishing_still_works(self, client):
        inspection = finished_inspection(client)
        assert complete_with_override(client, inspection["id"]).status_code == 200
        assert client.get(f"/public/inspections/{inspection['id']}").json()["report_delivery_status"] == "will_retry"

    def test_reports_per_inspection_are_capped_each_day(self, client, inspection_report_outbox, monkeypatch):  # noqa: F811
        monkeypatch.setattr(inspection_report_delivery, "MAXIMUM_REPORTS_PER_INSPECTION_PER_DAY", 2)
        from BL.inspection import publicInspection

        monkeypatch.setattr(publicInspection, "MAXIMUM_REPORTS_PER_INSPECTION_PER_DAY", 2)
        inspection = finished_inspection(client)
        for _ in range(3):
            assert complete_with_override(client, inspection["id"]).status_code == 200
        assert len(inspection_report_outbox.sent_emails) == 2

    def test_the_public_delivery_status_carries_no_address_or_file_id(self, client, inspection_report_outbox):  # noqa: F811
        inspection = finished_inspection(client)
        body = complete_with_override(client, inspection["id"]).json()
        assert body["report_delivery_status"] in {"sending", "delivered"}
        public_body = client.get(f"/public/inspections/{inspection['id']}").text
        assert "bigwhalesllc" not in public_body
        assert "drive-report" not in public_body and "drive.google.com" not in public_body
        assert find_keys_anywhere(client.get(f"/public/inspections/{inspection['id']}").json(), ("email", "drive")) == []


class TestDriveScriptRequests:
    def test_reports_go_under_the_inspections_folder_with_a_signed_save_report_request(self):
        assert INSPECTIONS_DRIVE_FOLDER_NAME == "inspections"
        body = build_drive_request_body(action="save_report", secret="s3cret", timestamp=1700000000, subject="folder/Inspection report.pdf", image=b"%PDF-1.4")
        assert body["action"] == "save_report"
        assert body["signature"] and body["image_sha256"]

    def test_attribute_escaping_covers_both_quote_styles(self):
        assert escape_attribute("""a"b'c<d>""") == "a&quot;b&#39;c&lt;d&gt;"
