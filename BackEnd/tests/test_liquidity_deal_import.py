"""A BRRRR deal's Cash Needed rows in the liquidity timeline (tasks/todo/DealCashInLiquidity.md, decisions 8-19).

The fixture deal (conftest `brrrr_payload`): contract 2026-01-03, purchase closing 2026-01-10, rehab completed
2026-02-24 (+45), tenant moved in 2026-04-10 (+90), refi 2026-07-09 (+180). `BEFORE_THE_DEAL` is a "today" before
anything happens, so no refi is late unless a test says so.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

BEFORE_THE_DEAL = "2026-01-01"


def _create_my_deals_deal(client, brrrr_payload) -> dict:
    response = client.post("/active-deals", json=brrrr_payload)
    assert response.status_code == 200, response.text
    return response.json()


def _import(client, deal_id, deal_board="my_deals", today=BEFORE_THE_DEAL, **body):
    return client.post(f"/liquidity/deals/{deal_board}/{deal_id}/import", json={"today": today, **body})


def _preview(client, deal_id, deal_board="my_deals", today=BEFORE_THE_DEAL, **body):
    return client.post(f"/liquidity/deals/{deal_board}/{deal_id}/import-preview", json={"today": today, **body})


def _deal_rows(client, deal_id):
    return [row for row in client.get("/liquidity/transactions").json() if row["source_deal_id"] == deal_id]


def _row(rows, item_key, occurrence_number=1):
    return next(row for row in rows if row["source_item_key"] == item_key and row["source_occurrence_number"] == occurrence_number)


def _change(result, item_key, occurrence_number=1):
    return next(change for change in result["changes"] if change["item_key"] == item_key and change["occurrence_number"] == occurrence_number)


class TestImportPreviewAndImport:
    def test_the_preview_lists_every_row_as_added_and_writes_nothing(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        preview = _preview(client, deal["id"]).json()
        schedule_rows = deal["cash_needed_schedule_at_lowest_arv"]["dated_cash_rows"]
        assert preview["change_counts"]["added"] == len(schedule_rows) > 0
        assert preview["deal_address"] == "1 Shared Form St"
        # The rehab cushion goes into the construction account and comes back, so the rows net it out of Cash Needed.
        assert (sum(Decimal(str(change["amount_dollars_after"])) for change in preview["changes"])
                == -(Decimal(str(deal["total_cash_needed_for_deal"])) - Decimal(str(brrrr_payload["rehabCushion"]))))
        assert client.get("/liquidity/transactions").json() == []

    def test_import_creates_one_tagged_row_per_schedule_row(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        assert _import(client, deal["id"]).status_code == 200
        rows = _deal_rows(client, deal["id"])
        assert len(rows) == len(deal["cash_needed_schedule_at_lowest_arv"]["dated_cash_rows"])
        # The schedule's key dates (contract, closing, rehab, tenant, refi) are markers: none becomes a transaction.
        assert deal["cash_needed_schedule_at_lowest_arv"]["deal_milestones"]
        milestone_descriptions = {milestone["description"] for milestone in deal["cash_needed_schedule_at_lowest_arv"]["deal_milestones"]}
        assert not milestone_descriptions & {row["description"] for row in rows}
        assert {row["source_deal_board"] for row in rows} == {"my_deals"}
        deposit = _row(rows, "construction_account_deposit")
        assert (deposit["effective_date"], deposit["amount_dollars"]) == ("2026-01-10", -5000.0)
        assert deposit["originally_planned_date"] == "2026-01-10" and deposit["done_at"] is None
        returned = _row(rows, "construction_account_balance_returned_at_rehab_end")
        assert (returned["effective_date"], returned["amount_dollars"]) == ("2026-02-24", 5000.0)
        assert _row(rows, "appliances")["effective_date"] == "2026-02-24"

    def test_importing_twice_changes_nothing(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        rows_after_the_first_import = _deal_rows(client, deal["id"])
        second = _import(client, deal["id"]).json()
        assert second["change_counts"]["unchanged"] == len(rows_after_the_first_import)
        assert second["change_counts"]["added"] == second["change_counts"]["updated"] == 0
        assert _deal_rows(client, deal["id"]) == rows_after_the_first_import

    def test_an_unknown_deal_is_a_404_and_an_unknown_board_a_422(self, client):
        missing = "11111111-1111-1111-1111-111111111111"
        assert _preview(client, missing).status_code == 404
        assert _preview(client, "not-a-uuid").status_code == 404
        assert _preview(client, missing, deal_board="flip").status_code == 422


class TestResyncKeepsYourChangesPerField:
    def test_a_redated_row_keeps_its_date_and_takes_the_deals_new_amount(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        hml_interest = _row(_deal_rows(client, deal["id"]), "hml_interest_paid_monthly")
        client.put(f"/liquidity/transactions/{hml_interest['id']}", json={"effective_date": "2026-03-03"})

        client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "HMLInterestRate": 12})
        preview = _preview(client, deal["id"]).json()
        change = _change(preview, "hml_interest_paid_monthly")
        assert change["change_kind"] == "updated"
        assert change["date_after"] == "2026-03-03"
        assert change["deal_date_not_applied_because_you_changed_it"] == hml_interest["effective_date"]
        assert change["amount_dollars_after"] < hml_interest["amount_dollars"]   # more interest: more money out
        assert preview["change_counts"]["conflicts_with_your_changes"] >= 1

        _import(client, deal["id"])
        resynced = _row(_deal_rows(client, deal["id"]), "hml_interest_paid_monthly")
        assert (resynced["effective_date"], resynced["user_overrode_date"]) == ("2026-03-03", True)
        assert resynced["amount_dollars"] == change["amount_dollars_after"]

    def test_an_edited_amount_is_kept_and_use_the_deals_value_takes_it_back(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        deposit = _row(_deal_rows(client, deal["id"]), "construction_account_deposit")
        client.put(f"/liquidity/transactions/{deposit['id']}", json={"amount_dollars": -1800})
        client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "rehabCushion": 2100})

        kept = _change(_preview(client, deal["id"]).json(), "construction_account_deposit")
        assert kept["amount_dollars_after"] == -1800 and kept["deal_amount_dollars_not_applied_because_you_changed_it"] == -2100

        _import(client, deal["id"], use_deal_value_for=[{"transaction_id": deposit["id"], "field": "amount"}])
        taken = _row(_deal_rows(client, deal["id"]), "construction_account_deposit")
        assert (taken["amount_dollars"], taken["user_overrode_amount"]) == (-2100, False)

    def test_a_done_row_is_never_touched(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        emd = _row(_deal_rows(client, deal["id"]), "earnest_money_deposit")
        client.post(f"/liquidity/transactions/{emd['id']}/done")
        client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "earnestMoneyDeposit": 9000})
        assert _change(_preview(client, deal["id"]).json(), "earnest_money_deposit")["change_kind"] == "kept_done"
        _import(client, deal["id"])
        assert _row(_deal_rows(client, deal["id"]), "earnest_money_deposit")["amount_dollars"] == -5000

    def test_a_row_the_deal_dropped_goes_unless_you_changed_it(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        rows = _deal_rows(client, deal["id"])
        client.put(f"/liquidity/transactions/{_row(rows, 'survey_fee')['id']}", json={"amount_dollars": -400})
        client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "appliances": 0, "surveyFee": 0})
        _import(client, deal["id"])
        rows_after = _deal_rows(client, deal["id"])
        assert not [row for row in rows_after if row["source_item_key"] == "appliances"]
        assert _row(rows_after, "survey_fee")["no_longer_in_the_deal"] is True


class TestADealSaveFlagsTheRowsOutOfDate:
    def _flag(self, client, deal_id) -> bool:
        return next(deal for deal in client.get("/liquidity/deals", params={"today": BEFORE_THE_DEAL}).json()
                    if deal["deal_id"] == deal_id)["liquidity_rows_out_of_date"]

    def test_a_save_that_changes_the_rows_sets_the_flag_and_a_reimport_clears_it(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "notes": "called the seller"})
        assert self._flag(client, deal["id"]) is False
        client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "rehabCushion": 7000})
        assert self._flag(client, deal["id"]) is True
        assert _row(_deal_rows(client, deal["id"]), "construction_account_deposit")["amount_dollars"] == -5000   # never silently
        _import(client, deal["id"])
        assert self._flag(client, deal["id"]) is False


class TestMilestones:
    def _milestone(self, client, deal_id, action, **body):
        return client.post(f"/liquidity/deals/my_deals/{deal_id}/milestones/{action}", json={"today": BEFORE_THE_DEAL, **body})

    def test_moving_the_purchase_closing_moves_the_later_milestones_and_their_rows(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        preview = self._milestone(client, deal["id"], "preview", milestone="purchase_closed", new_date="2026-01-12").json()
        assert [change["milestone"] for change in preview["milestone_date_changes"]] == [
            "purchase_closed", "rehab_completed", "tenant_moved_in", "refi_closed"]
        assert _change(preview, "cash_to_close_buy")["date_after"] == "2026-01-12"
        assert _change(preview, "appliances")["date_after"] == "2026-02-26"
        assert _row(_deal_rows(client, deal["id"]), "cash_to_close_buy")["effective_date"] == "2026-01-10"   # a preview writes nothing

        assert self._milestone(client, deal["id"], "apply", milestone="purchase_closed", new_date="2026-01-12").status_code == 200
        saved_deal = next(saved for saved in client.get("/active-deals").json() if saved["id"] == deal["id"])
        assert saved_deal["buyClosingDate"] == "2026-01-12" and saved_deal["daysUntilRefi"] == 180
        assert _row(_deal_rows(client, deal["id"]), "cash_to_close_buy")["effective_date"] == "2026-01-12"
        panel = client.get("/liquidity/deals", params={"today": "2026-01-20"}).json()[0]
        purchase_closed = next(milestone for milestone in panel["milestones"] if milestone["milestone"] == "purchase_closed")
        assert purchase_closed["approved_at"] is not None and purchase_closed["is_overdue"] is False
        rehab_completed = next(milestone for milestone in panel["milestones"] if milestone["milestone"] == "rehab_completed")
        assert rehab_completed["planned_date"] == "2026-02-26" and rehab_completed["approved_at"] is None

    def test_a_date_out_of_order_is_refused(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        response = self._milestone(client, deal["id"], "apply", milestone="rehab_completed", new_date="2026-08-01")
        assert response.status_code == 400
        response = self._milestone(client, deal["id"], "preview", milestone="contract_signed", new_date="2026-01-20")
        assert response.status_code == 400


class TestLateRefi:
    LATE_TODAY = "2026-09-15"   # the refi was planned for 2026-07-09

    def _refresh(self, client, today=LATE_TODAY):
        return client.post("/liquidity/deals/refresh-late-refis", json={"today": today}).json()

    def test_the_late_months_become_real_rows_once_and_no_rent(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        first = self._refresh(client)
        assert first["added_row_count"] > 0
        late_rows = [row for row in _deal_rows(client, deal["id"]) if row["created_because_refi_is_late"]]
        assert len(late_rows) == first["added_row_count"]
        assert {row["source_item_key"] for row in late_rows} <= {"hml_interest_paid_monthly", "hoa_dues", "insurance_paid_monthly_until_refi", "utilities"}
        assert all(row["amount_dollars"] < 0 for row in late_rows)
        assert max(row["effective_date"] for row in late_rows) == "2026-10-01"   # up to the first 1st after today
        assert self._refresh(client)["added_row_count"] == 0

    def test_the_late_months_stop_after_two_years_whatever_today_says(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        self._refresh(client, today="2099-01-01")
        late_rows = [row for row in _deal_rows(client, deal["id"]) if row["created_because_refi_is_late"]]
        assert max(row["effective_date"] for row in late_rows) == "2028-07-01"   # 24 months after the planned 2026-07 refi

    def test_approving_the_refi_updates_the_late_rows_instead_of_duplicating_them(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        self._refresh(client)
        late_rows = [row for row in _deal_rows(client, deal["id"]) if row["created_because_refi_is_late"]]
        done_late_row = late_rows[0]
        client.post(f"/liquidity/transactions/{done_late_row['id']}/done")

        client.post(f"/liquidity/deals/my_deals/{deal['id']}/milestones/apply",
                    json={"milestone": "refi_closed", "new_date": "2026-10-05", "today": self.LATE_TODAY})
        rows = _deal_rows(client, deal["id"])
        identities = [(row["source_item_key"], row["source_occurrence_number"]) for row in rows]
        assert len(identities) == len(set(identities))
        assert next(row for row in rows if row["id"] == done_late_row["id"])["done_at"] is not None
        assert {row["id"] for row in late_rows} <= {row["id"] for row in rows}
        assert not any(row["created_because_refi_is_late"] for row in rows if row["id"] != done_late_row["id"])
        assert self._refresh(client)["added_row_count"] == 0

    def test_a_deal_taken_out_of_the_timeline_gets_no_late_months_back(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        emd = _row(_deal_rows(client, deal["id"]), "earnest_money_deposit")
        client.post(f"/liquidity/transactions/{emd['id']}/done")
        client.post(f"/liquidity/deals/my_deals/{deal['id']}/remove-open-rows", json={"earnest_money_refund_date": None})
        assert self._refresh(client)["added_row_count"] == 0
        assert [row["id"] for row in _deal_rows(client, deal["id"])] == [emd["id"]]


class TestRemoveDealFromTimeline:
    """The theater legend's "Remove from timeline" (tasks/todo/LiquidityTheaterMode.md, decision 1 and section F)."""

    def _listed_deal(self, client, deal_id):
        return next((listed for listed in client.get("/liquidity/deals", params={"today": BEFORE_THE_DEAL}).json()
                     if listed["deal_id"] == deal_id), None)

    def test_a_removed_deal_stays_listed_with_no_open_rows_so_its_done_rows_keep_their_address(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        emd = _row(_deal_rows(client, deal["id"]), "earnest_money_deposit")
        client.post(f"/liquidity/transactions/{emd['id']}/done")
        client.post(f"/liquidity/deals/my_deals/{deal['id']}/remove-open-rows", json={"earnest_money_refund_date": None})
        listed = self._listed_deal(client, deal["id"])
        assert (listed["open_row_count"], listed["done_row_count"], listed["deal_address"]) == (0, 1, "1 Shared Form St")

    def test_re_importing_a_removed_deal_brings_its_open_rows_back_and_keeps_the_done_ones_done(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        row_count = len(_deal_rows(client, deal["id"]))
        emd = _row(_deal_rows(client, deal["id"]), "earnest_money_deposit")
        client.post(f"/liquidity/transactions/{emd['id']}/done")
        client.post(f"/liquidity/deals/my_deals/{deal['id']}/remove-open-rows", json={"earnest_money_refund_date": None})

        result = _import(client, deal["id"]).json()
        assert result["change_counts"]["kept_done"] == 1
        assert result["change_counts"]["added"] == row_count - 1
        rows = _deal_rows(client, deal["id"])
        assert len(rows) == row_count
        assert next(row for row in rows if row["id"] == emd["id"])["done_at"] is not None
        assert self._listed_deal(client, deal["id"])["open_row_count"] == row_count - 1


class TestMoveToBoughtAndDelete:
    def test_moving_to_bought_repoints_the_rows_and_the_my_deals_copy_cannot_be_imported(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        row_count = len(_deal_rows(client, deal["id"]))
        bought = client.post(f"/bought-deals/from-active/{deal['id']}", params={"deal_type": "BRRRR"}).json()
        assert _deal_rows(client, deal["id"]) == []
        bought_rows = _deal_rows(client, bought["id"])
        assert len(bought_rows) == row_count and {row["source_deal_board"] for row in bought_rows} == {"bought"}
        assert _preview(client, deal["id"]).status_code == 409
        assert _import(client, deal["id"]).status_code == 409
        assert _import(client, bought["id"], deal_board="bought").json()["change_counts"]["unchanged"] == row_count
        panel = client.get("/liquidity/deals", params={"today": BEFORE_THE_DEAL}).json()
        assert [(deal_in_panel["deal_board"], deal_in_panel["my_deals_deal_id_it_was_moved_from"]) for deal_in_panel in panel] == [("bought", deal["id"])]

        client.delete(f"/active-deals/{deal['id']}", params={"deal_type": "BRRRR"})
        assert len(_deal_rows(client, bought["id"])) == row_count

    def test_deleting_a_deal_removes_its_open_rows_and_keeps_the_done_ones(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        emd = _row(_deal_rows(client, deal["id"]), "earnest_money_deposit")
        client.post(f"/liquidity/transactions/{emd['id']}/done")
        client.delete(f"/active-deals/{deal['id']}", params={"deal_type": "BRRRR"})
        assert [row["id"] for row in _deal_rows(client, deal["id"])] == [emd["id"]]

    def test_a_dead_deal_gives_its_open_rows_up_and_can_get_the_earnest_money_back(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, brrrr_payload)
        _import(client, deal["id"])
        result = client.post(f"/liquidity/deals/my_deals/{deal['id']}/remove-open-rows",
                             json={"earnest_money_refund_date": "2026-01-20"}).json()
        assert result["removed_row_count"] > 0
        assert _deal_rows(client, deal["id"]) == []
        refund = next(row for row in client.get("/liquidity/transactions").json() if row["id"] == result["earnest_money_refund_transaction_id"])
        assert (refund["effective_date"], refund["amount_dollars"], refund["source_deal_id"]) == ("2026-01-20", 5000.0, None)


class TestTimezoneSetting:
    def test_a_known_zone_is_stored_and_an_unknown_one_refused(self, client):
        assert client.get("/liquidity/settings").json()["timezone_name"] == "America/New_York"
        assert client.put("/liquidity/settings", json={"timezone_name": "Asia/Jerusalem"}).json()["timezone_name"] == "Asia/Jerusalem"
        assert client.put("/liquidity/settings", json={"timezone_name": "Mars/Olympus"}).status_code == 422


@pytest.mark.parametrize("today", [None])
def test_today_defaults_to_the_settings_time_zone(client, brrrr_payload, today):
    deal = _create_my_deals_deal(client, brrrr_payload)
    assert client.post(f"/liquidity/deals/my_deals/{deal['id']}/import-preview", json={}).status_code == 200


class TestImportedDealKeyDates:
    """The legend's Transactions show the deal's key dates as its Cash Needed table does
    (tasks/todo/LiquidityDealTransactionsAndHmlMonthlyInterest.md, B)."""

    def test_the_key_dates_are_the_schedule_markers_including_the_november_30_bill_inside_the_hold(self, client, brrrr_payload):
        deal = _create_my_deals_deal(client, {**brrrr_payload, "buyClosingDate": "2026-08-20", "contractDate": "2026-08-01",
                                              "daysUntilRefi": 200})
        _import(client, deal["id"], today="2026-07-01")
        listed = next(listed for listed in client.get("/liquidity/deals", params={"today": "2026-07-01"}).json()
                      if listed["deal_id"] == deal["id"])
        schedule_markers = [(marker["milestone_key"], marker["date"])
                            for marker in deal["cash_needed_schedule_at_lowest_arv"]["deal_milestones"]]
        assert [(key_date["key"], key_date["date"]) for key_date in listed["key_dates"]] == schedule_markers
        assert ("property_tax_bill_paid_on_november_30", "2026-11-30") in schedule_markers
        assert [key_date["date"] for key_date in listed["key_dates"]] == sorted(key_date["date"] for key_date in listed["key_dates"])


def test_the_import_preview_carries_the_deals_key_dates(client, brrrr_payload):
    deal = _create_my_deals_deal(client, {**brrrr_payload, "buyClosingDate": "2026-08-20", "contractDate": "2026-08-01",
                                          "daysUntilRefi": 200})
    preview = _preview(client, deal["id"], today="2026-07-01").json()
    schedule_markers = [(marker["milestone_key"], marker["date"]) for marker in deal["cash_needed_schedule_at_lowest_arv"]["deal_milestones"]]
    assert [(key_date["key"], key_date["date"]) for key_date in preview["key_dates"]] == schedule_markers
    assert ("property_tax_bill_paid_on_november_30", "2026-11-30") in schedule_markers
