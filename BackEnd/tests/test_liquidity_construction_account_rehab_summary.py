"""The rehab summary made when a construction account is closed out
(tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md): its content, PDF, CSV and e-mail; its Drive request;
when it is recorded; how it is delivered and retried; Send again; the downloads; and deleting the deal."""

from __future__ import annotations

import csv
import io
import json
from datetime import date

import pytest

from BL.liquidity.constructionAccount import rehab_summary_delivery, rehab_summary_google_drive
from BL.liquidity.constructionAccount.rehab_summary_report import (
    RehabSummaryStatistic, build_rehab_summary_content, build_rehab_summary_pdf, build_rehab_summary_transactions_csv,
    rehab_summary_email_html, rehab_summary_file_base_name,
)
from DAL.data_models.liquidity.construction_account_models import LiquidityConstructionAccountRehabSummary
from ReqRes.common.liquidity_construction_account_schemas import ConstructionAccountTransactionRes
from db import SessionLocal
from tests.test_liquidity_construction_account import (  # noqa: F401  (fixtures)
    FakeMercury, _link, _refresh, _status, bought_deal, mercury,
)


@pytest.fixture
def rehab_summary_outbox(monkeypatch):
    """Both channels succeed, and what they were given is kept here."""
    outbox = {"emails": [], "drive_files": []}

    def send_email(**email):
        outbox["emails"].append(email)

    def save_to_drive(folder_name, file_name, file_bytes):
        outbox["drive_files"].append((folder_name, file_name, file_bytes))
        return f"drive-file-{len(outbox['drive_files'])}", "https://drive.google.com/drive/folders/rehab-folder"

    monkeypatch.setenv("REHAB_SUMMARY_EMAIL", "owner@example.com")
    monkeypatch.setattr(rehab_summary_delivery, "send_rehab_summary_email", send_email)
    monkeypatch.setattr(rehab_summary_delivery, "save_rehab_summary_file_to_drive", save_to_drive)
    return outbox


def _a_rehab_run_through_the_account(client, mercury: FakeMercury, deal_id: str) -> str:
    _link(client, deal_id)
    mercury.move("construction", "deposit", 5000, internal=True)
    mercury.move("construction", "draw-1", 70000, counterparty_name="Lender LLC")
    mercury.move("construction", "gc-payment-1", -50000, counterparty_name="=HYPERLINK(\"http://evil\")")
    _refresh(client)
    return f"/liquidity/construction-accounts/{deal_id}"


def _summaries_of(deal_id: str) -> list[LiquidityConstructionAccountRehabSummary]:
    with SessionLocal() as db:
        return (db.query(LiquidityConstructionAccountRehabSummary)
                .filter(LiquidityConstructionAccountRehabSummary.bought_brrr_deal_id == __import__("uuid").UUID(deal_id)).all())


class TestTheContent:
    def test_the_numbers_the_pdf_the_csv_guard_and_the_escaped_email(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _a_rehab_run_through_the_account(client, mercury, deal_id)
        from ReqRes.common.liquidity_construction_account_schemas import ConstructionAccountStatusRes
        status = ConstructionAccountStatusRes(**{**_status(client, deal_id), "deal_address": "<script>alert(1)</script> 1 Oak St"})
        transactions = [ConstructionAccountTransactionRes(
            mercury_transaction_id="gc-payment-1", transaction_date=date(2026, 1, 15), counterparty_name="=HYPERLINK(\"http://evil\")",
            signed_amount_dollars=-50000, bank_status="sent", automatic_category="rehab_payment", ignored=False, effective_category="rehab_payment")]
        content = build_rehab_summary_content(status, transactions, date(2026, 3, 1))

        numbers = {statistic.label: statistic.value for statistic in content.statistics}
        assert numbers["Lender draws received"].startswith("$70,000 in 1 draws (100% of the budget)")
        assert numbers["Paid to contractors"].startswith("$50,000")
        assert numbers["Under budget: you keep"] == "$20,000"
        assert numbers["Days from purchase to close-out"].isdigit()

        assert build_rehab_summary_pdf(content).startswith(b"%PDF")
        rows = list(csv.reader(io.StringIO(build_rehab_summary_transactions_csv(content))))
        assert rows[0][:4] == ["date", "source", "counterparty", "amount_dollars"]
        assert rows[1][2].startswith("'=HYPERLINK")     # a spreadsheet never runs it
        assert rows[1][3] == "'-50000.00"               # a negative amount is defused too
        assert "<script>" not in rehab_summary_email_html(content.deal_address, content.statistics, None)
        assert "/" not in rehab_summary_file_base_name(content) and "<" not in rehab_summary_file_base_name(content)

    def test_the_drive_request_is_signed_over_the_folder_the_file_and_its_hash(self):
        body = rehab_summary_google_drive.build_upload_request_body(
            folder_name="1 Oak St (deal)", file_name="Rehab summary.pdf", file_bytes=b"%PDF-1", secret="s3cret", timestamp=1700000000)
        import hashlib
        file_sha256 = hashlib.sha256(b"%PDF-1").hexdigest()
        assert body["file_sha256"] == file_sha256
        assert body["signature"] == rehab_summary_google_drive.upload_signature("s3cret", 1700000000, "1 Oak St (deal)/Rehab summary.pdf", file_sha256)
        assert rehab_summary_google_drive.rehab_summary_drive_folder_name("1/2 Oak St", "abc") == "1 2 Oak St (abc)"

    def test_the_drive_upload_refuses_a_url_that_is_not_apps_script(self, monkeypatch):
        monkeypatch.setenv("REHAB_SUMMARY_DRIVE_UPLOAD_URL", "https://evil.example.com/exec")
        monkeypatch.setenv("REHAB_SUMMARY_DRIVE_UPLOAD_SECRET", "s3cret")
        with pytest.raises(rehab_summary_google_drive.RehabSummaryDriveUploadFailed):
            rehab_summary_google_drive.save_rehab_summary_file_to_drive("folder", "file.pdf", b"%PDF")


class TestClosingOutSendsIt:
    def test_one_summary_per_close_out_never_on_a_preview_and_delivered_both_ways(self, client, mercury, bought_deal, rehab_summary_outbox):
        deal_id = bought_deal["id"]
        base_url = _a_rehab_run_through_the_account(client, mercury, deal_id)

        assert client.post(f"{base_url}/mark-closed-out", params={"preview_only": True}).status_code == 200
        assert _summaries_of(deal_id) == []

        closed = client.post(f"{base_url}/mark-closed-out")
        assert closed.status_code == 200
        assert closed.json()["status_after"]["latest_rehab_summary"] is not None
        assert len(_summaries_of(deal_id)) == 1
        latest = _status(client, deal_id)["latest_rehab_summary"]
        assert latest["overall_delivery_state"] == "delivered"
        assert latest["drive_folder_url"] == "https://drive.google.com/drive/folders/rehab-folder"

        [email] = rehab_summary_outbox["emails"]
        assert email["recipients"] == ["owner@example.com"] and email["subject"].startswith("Rehab completed")
        assert [attachment.filename.rsplit(".", 1)[1] for attachment in email["attachments"]] == ["pdf", "csv"]
        assert "Lender draws received" in email["text_body"]
        assert sorted(name.rsplit(".", 1)[1] for _folder, name, _bytes in rehab_summary_outbox["drive_files"]) == ["csv", "pdf"]

        # Closing out an account already closed out makes no second summary; reopen and close again does.
        client.post(f"{base_url}/mark-closed-out")
        assert len(_summaries_of(deal_id)) == 1
        client.post(f"{base_url}/reopen")
        client.post(f"{base_url}/mark-closed-out")
        assert len(_summaries_of(deal_id)) == 2

    def test_a_failed_channel_is_retried_until_three_attempts_and_only_its_type_is_kept(self, client, mercury, bought_deal, monkeypatch):
        monkeypatch.setenv("REHAB_SUMMARY_EMAIL", "owner@example.com")
        deal_id = bought_deal["id"]
        base_url = _a_rehab_run_through_the_account(client, mercury, deal_id)
        client.post(f"{base_url}/mark-closed-out")   # conftest: both channels "not configured"
        latest = _status(client, deal_id)["latest_rehab_summary"]
        assert latest["overall_delivery_state"] == "will_retry"
        assert latest["email_last_error_type_name"] == "MemberLoanEmailNotSent"

        rehab_summary_delivery.retry_failed_rehab_summary_deliveries()
        rehab_summary_delivery.retry_failed_rehab_summary_deliveries()
        [summary] = _summaries_of(deal_id)
        assert summary.email_delivery_attempt_count == 3 and summary.drive_delivery_attempt_count == 3
        assert rehab_summary_delivery.retry_failed_rehab_summary_deliveries() == 0
        assert _status(client, deal_id)["latest_rehab_summary"]["overall_delivery_state"] == "failed"


class TestSendAgainAndDownloads:
    def test_send_again_needs_a_closed_out_account_and_is_limited_per_day(self, client, mercury, bought_deal, rehab_summary_outbox, monkeypatch):
        deal_id = bought_deal["id"]
        base_url = _a_rehab_run_through_the_account(client, mercury, deal_id)
        assert client.post(f"{base_url}/rehab-summaries").status_code == 409
        client.post(f"{base_url}/mark-closed-out")

        again = client.post(f"{base_url}/rehab-summaries")
        assert again.status_code == 200 and again.json()["overall_delivery_state"] in {"sending", "delivered"}
        assert len(client.get(f"{base_url}/rehab-summaries").json()) == 2
        assert len(rehab_summary_outbox["emails"]) == 2

        monkeypatch.setattr(rehab_summary_delivery, "MAXIMUM_REHAB_SUMMARIES_PER_DEAL_PER_DAY", 2)
        from BL.liquidity.constructionAccount import construction_accounts
        monkeypatch.setattr(construction_accounts, "MAXIMUM_REHAB_SUMMARIES_PER_DEAL_PER_DAY", 2)
        assert client.post(f"{base_url}/rehab-summaries").status_code == 429

    def test_the_pdf_and_csv_download_only_through_their_own_deal(self, client, mercury, bought_deal, rehab_summary_outbox, brrrr_payload):
        deal_id = bought_deal["id"]
        base_url = _a_rehab_run_through_the_account(client, mercury, deal_id)
        client.post(f"{base_url}/mark-closed-out")
        rehab_summary_id = client.get(f"{base_url}/rehab-summaries").json()[0]["rehab_summary_id"]

        pdf = client.get(f"{base_url}/rehab-summaries/{rehab_summary_id}/pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
        assert "attachment" in pdf.headers["content-disposition"]
        csv_answer = client.get(f"{base_url}/rehab-summaries/{rehab_summary_id}/csv")
        assert csv_answer.status_code == 200 and csv_answer.text.startswith("date,source")

        other_deal = client.post("/active-deals", json={**brrrr_payload, "address": "9 Other St"}).json()
        other_bought = client.post(f"/bought-deals/from-active/{other_deal['id']}", params={"deal_type": "BRRRR"}).json()
        assert client.get(f"/liquidity/construction-accounts/{other_bought['id']}/rehab-summaries/{rehab_summary_id}/pdf").status_code == 404
        assert client.get(f"{base_url}/rehab-summaries/not-a-uuid/pdf").status_code == 404

    def test_unlink_keeps_the_summaries_and_deleting_the_deal_removes_them(self, client, mercury, bought_deal, rehab_summary_outbox):
        deal_id = bought_deal["id"]
        base_url = _a_rehab_run_through_the_account(client, mercury, deal_id)
        client.post(f"{base_url}/mark-closed-out")
        client.delete(base_url)
        assert len(_summaries_of(deal_id)) == 1
        assert client.delete(f"/bought-deals/{deal_id}", params={"deal_type": "BRRRR"}).status_code in (200, 204)
        assert _summaries_of(deal_id) == []


def test_the_statistics_are_stored_so_a_retried_email_still_carries_them():
    from BL.liquidity.constructionAccount.rehab_summary_report import statistics_as_stored, statistics_from_stored
    statistics = [RehabSummaryStatistic("Paid to contractors", "$50,000")]
    assert statistics_from_stored(json.loads(json.dumps(statistics_as_stored(statistics)))) == statistics
    assert statistics_from_stored("not a list") == []
