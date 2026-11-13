"""/liquidity/construction-accounts/* against a fake Mercury (tasks/todo/ConstructionAccountPerRehab.md).

The deal throughout: construction budget $70,000, rehab cost $50,000 (so the original steal is $20,000), cushion
$5,000. Its plan: deposit $5,000 on the purchase closing (2026-01-10), $25,000 back on the rehab completion (2026-02-24).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from BL.liquidity import mercuryBalance as mercury_balance_module
from BL.liquidity.common.mercury_client import MercuryApiError
from BL.liquidity.constructionAccount import construction_accounts as construction_accounts_module

BEFORE_THE_DEAL = "2025-12-01"
DURING_THE_REHAB = "2026-02-01"
DEPOSIT, RETURN, TOP_UP = "construction_account_deposit", "construction_account_balance_returned_at_rehab_end", "construction_account_top_up_needed"


class FakeMercury:
    """Two workspaces. AJYK: checking, a tax bucket and two construction accounts. OTHER: one checking."""

    def __init__(self):
        self.is_down = False
        self.balance_by_account_id = {"checking": 80000, "tax": 4000, "construction": 0, "construction-2": 0, "other-checking": 9000}
        self.workspace_by_account_id = {"checking": "AJYK", "tax": "AJYK", "construction": "AJYK", "construction-2": "AJYK", "other-checking": "OTHER"}
        self.transactions_by_account_id: dict[str, list[dict]] = {account_id: [] for account_id in self.balance_by_account_id}

    def summarize_balance(self) -> dict:
        if self.is_down:
            raise MercuryApiError("HTTP 500")
        accounts = [{"id": account_id, "name": f"{account_id} account", "account_number_last_four": "1234", "type": "checking",
                     "status": "active", "current_balance_dollars": float(balance), "available_balance_dollars": float(balance),
                     "workspace": self.workspace_by_account_id[account_id]} for account_id, balance in self.balance_by_account_id.items()]
        return {"accounts": accounts, "workspaces": [], "workspace_errors": []}

    def fetch_account_transactions(self, workspace_label: str, account_id: str) -> list[dict]:
        if self.is_down:
            raise MercuryApiError("HTTP 500")
        assert self.workspace_by_account_id[account_id] == workspace_label
        return list(self.transactions_by_account_id[account_id])

    def move(self, account_id: str, transaction_id: str, signed_amount: int, internal: bool = False, status: str = "sent") -> None:
        """One bank transaction on an account: positive = into it."""
        self.transactions_by_account_id[account_id].append({
            "id": transaction_id, "signed_amount_dollars": Decimal(signed_amount), "kind": "internalTransfer" if internal else "wire",
            "status": status, "counterparty_name": transaction_id, "transaction_date": date(2026, 1, 15),
            "is_internal_transfer": internal, "is_failed_or_cancelled": status in {"failed", "cancelled"}})
        if status not in {"failed", "cancelled"}:
            self.balance_by_account_id[account_id] += signed_amount


@pytest.fixture
def mercury(monkeypatch) -> FakeMercury:
    fake_mercury = FakeMercury()
    monkeypatch.setattr(mercury_balance_module, "summarize_balance", fake_mercury.summarize_balance)
    monkeypatch.setattr(construction_accounts_module, "fetch_account_transactions", fake_mercury.fetch_account_transactions)
    return fake_mercury


@pytest.fixture
def bought_deal(client, brrrr_payload) -> dict:
    """A Bought BRRRR deal in the liquidity timeline, with the two accounts that count as cash chosen in the settings."""
    client.put("/liquidity/settings", json={"mercury_account_ids_counted_as_cash": ["checking", "other-checking", "construction", "construction-2"]})
    my_deals_deal = client.post("/active-deals", json={**brrrr_payload, "constructionLoanBudget": 70, "rehabContingency": 0}).json()
    deal = client.post(f"/bought-deals/from-active/{my_deals_deal['id']}", params={"deal_type": "BRRRR"}).json()
    assert client.post(f"/liquidity/deals/bought/{deal['id']}/import", json={"today": BEFORE_THE_DEAL}).status_code == 200
    return deal


def _link(client, deal_id: str, **changes):
    body = {"construction_mercury_account_id": "construction", "primary_checking_mercury_account_id": "checking", **changes}
    return client.put(f"/liquidity/construction-accounts/{deal_id}", json=body)


def _refresh(client, today: str = DURING_THE_REHAB) -> dict:
    return client.post("/liquidity/construction-accounts/refresh", json={"today": today}).json()


def _status(client, deal_id: str) -> dict:
    return next(status for status in client.get("/liquidity/construction-accounts").json() if status["bought_deal_id"] == deal_id)


def _rows(client, deal_id: str) -> dict[str, dict]:
    return {row["source_item_key"]: row for row in client.get("/liquidity/transactions").json()
            if row.get("source_deal_id") == deal_id and row["source_item_key"] in {DEPOSIT, RETURN, TOP_UP}}


def _amounts(client, deal_id: str) -> dict[str, float]:
    return {item_key: row["amount_dollars"] for item_key, row in _rows(client, deal_id).items() if row["done_at"] is None}


class TestLinking:
    def test_an_unlinked_deal_is_listed_with_its_plan_and_its_rows_are_the_schedules(self, client, mercury, bought_deal):
        status = _status(client, bought_deal["id"])
        assert status["is_linked"] is False and status["deal_address"] == bought_deal["address"]
        assert (status["construction_budget_dollars"], status["rehab_cost_dollars"], status["original_steal_dollars"]) == (70000, 50000, 20000)
        assert status["projected_return_at_rehab_end_dollars"] is None
        assert _amounts(client, bought_deal["id"]) == {DEPOSIT: -5000, RETURN: 25000}

    def test_linking_shows_the_accounts_by_name_and_last_four_and_keeps_the_plan_until_money_moves(self, client, mercury, bought_deal):
        response = _link(client, bought_deal["id"])
        assert response.status_code == 200
        status = response.json()
        assert status["is_linked"] is True and status["mercury_workspace_label"] == "AJYK"
        assert status["construction_account"] == {"mercury_account_id": "construction", "name": "construction account", "account_number_last_four": "1234"}
        assert status["primary_checking_account"]["mercury_account_id"] == "checking"
        assert status["amounts_as_of"] is not None and status["mercury_is_unavailable"] is False
        assert (status["remaining_deposit_dollars"], status["projected_return_at_rehab_end_dollars"]) == (5000, 20000)
        assert _amounts(client, bought_deal["id"]) == {DEPOSIT: -5000, RETURN: 25000}

    def test_a_linked_construction_account_is_never_cash_on_hand(self, client, mercury, bought_deal):
        mercury.balance_by_account_id["construction"] = 30000
        assert client.get("/liquidity/mercury-balance").json()["counted_as_cash_balance_dollars"] == 80000 + 9000 + 30000
        _link(client, bought_deal["id"])
        balance = client.get("/liquidity/mercury-balance").json()
        assert balance["counted_as_cash_balance_dollars"] == 80000 + 9000
        construction = next(account for account in balance["accounts"] if account["id"] == "construction")
        assert (construction["is_counted_as_cash"], construction["is_a_linked_construction_account"]) == (False, True)

    @pytest.mark.parametrize("changes, status_code, message", [
        ({"primary_checking_mercury_account_id": "other-checking"}, 422, "same Mercury workspace"),
        ({"primary_checking_mercury_account_id": "tax"}, 422, "counted as cash"),
        ({"primary_checking_mercury_account_id": "construction"}, 422, "two different accounts"),
        ({"construction_mercury_account_id": "no-such-account"}, 422, "not found"),
        ({"construction_mercury_account_id": "../accounts"}, 422, None),
        ({"loan_draws_pulled_before_construction_account_dollars": -1}, 422, None),
    ])
    def test_a_link_that_cannot_work_is_refused(self, client, mercury, bought_deal, changes, status_code, message):
        response = _link(client, bought_deal["id"], **changes)
        assert response.status_code == status_code
        if message:
            assert message in response.json()["detail"]
        assert _status(client, bought_deal["id"])["is_linked"] is False

    def test_an_account_is_one_deals_construction_account_only(self, client, mercury, bought_deal, brrrr_payload):
        _link(client, bought_deal["id"])
        second_my_deals_deal = client.post("/active-deals", json={**brrrr_payload, "address": "2 Second St"}).json()
        second_deal = client.post(f"/bought-deals/from-active/{second_my_deals_deal['id']}", params={"deal_type": "BRRRR"}).json()
        assert _link(client, second_deal["id"]).status_code == 409
        assert _link(client, second_deal["id"], construction_mercury_account_id="construction-2", primary_checking_mercury_account_id="construction").status_code == 422

    def test_unknown_deals_and_unlinked_deals_answer_404(self, client, mercury, bought_deal):
        assert _link(client, "00000000-0000-0000-0000-000000000000").status_code == 404
        assert _link(client, "not-a-uuid").status_code == 404
        assert client.delete(f"/liquidity/construction-accounts/{bought_deal['id']}").status_code == 404
        assert client.get(f"/liquidity/construction-accounts/{bought_deal['id']}/transactions").status_code == 404

    def test_linking_needs_mercury(self, client, mercury, bought_deal):
        mercury.is_down = True
        response = _link(client, bought_deal["id"])
        assert response.status_code == 502 and "500" not in response.json()["detail"]


class TestTheRowsFollowTheAccount:
    def test_the_deposit_lands_draws_and_payments_pass_through_and_a_steal_moves_the_return(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)

        mercury.move("construction", "deposit", 5000, internal=True)
        assert _refresh(client)["changed_row_count"] > 0
        rows = _rows(client, deal_id)
        assert rows[DEPOSIT]["done_at"] is not None                       # the deposit row is done, not deleted
        assert _amounts(client, deal_id) == {RETURN: 25000}

        mercury.move("construction", "draw-1", 30000)
        mercury.move("construction", "gc-payment-1", -18000)
        assert _refresh(client)["changed_row_count"] == 0                 # draws and rehab payments never move the timeline
        status = _status(client, deal_id)
        assert status["current_balance_dollars"] == 17000
        assert (status["loan_draws_pulled"]["total_dollars"], status["loan_draws_remaining_to_pull_dollars"]) == (30000, 40000)
        assert (status["rehab_payments_made"]["total_dollars"], status["unpaid_rehab_remaining_dollars"]) == (18000, 32000)
        assert (status["projected_return_at_rehab_end_dollars"], status["safe_to_steal_now_dollars"]) == (25000, 17000)

        mercury.move("construction", "steal-1", -6000, internal=True)
        _refresh(client)
        assert _amounts(client, deal_id) == {RETURN: 19000}
        assert _refresh(client)["changed_row_count"] == 0                 # idempotent

    def test_stealing_too_much_asks_for_a_top_up_today_and_topping_up_clears_it(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "draw-1", 70000)
        mercury.move("construction", "steal-too-much", -40000, internal=True)   # 35,000 left, 50,000 still to pay
        _refresh(client)
        rows = _rows(client, deal_id)
        assert _amounts(client, deal_id) == {TOP_UP: -15000}
        assert rows[TOP_UP]["effective_date"] == DURING_THE_REHAB
        assert _status(client, deal_id)["top_up_needed_dollars"] == 15000

        _refresh(client, today="2026-02-03")
        assert _rows(client, deal_id)[TOP_UP]["effective_date"] == "2026-02-03"   # always today while it is needed

        mercury.move("construction", "top-up", 15000, internal=True)
        _refresh(client, today="2026-02-03")
        assert _amounts(client, deal_id) == {}

    def test_a_hand_edited_amount_never_holds_a_live_row_back(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        return_row = _rows(client, deal_id)[RETURN]
        client.put(f"/liquidity/transactions/{return_row['id']}", json={"amount_dollars": 99999})
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "steal-1", -1000, internal=True)
        _refresh(client)
        assert _amounts(client, deal_id) == {RETURN: 24000}

    def test_while_mercury_is_down_the_rows_keep_their_last_amounts(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "steal-1", -2000, internal=True)
        _refresh(client)
        as_of = _status(client, deal_id)["amounts_as_of"]

        mercury.move("construction", "steal-2", -1000, internal=True)
        mercury.is_down = True
        refreshed = _refresh(client)
        assert refreshed == {"refreshed_deal_count": 0, "changed_row_count": 0, "mercury_is_unavailable": True}
        assert _amounts(client, deal_id) == {RETURN: 23000}
        assert _status(client, deal_id)["amounts_as_of"] == as_of

    def test_a_change_order_waits_for_the_resync_you_confirm(self, client, mercury, bought_deal, brrrr_payload):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        _refresh(client)

        saved = client.put(f"/bought-deals/{deal_id}", json={**bought_deal, "rehabCost": 58})   # a +$8,000 change order
        assert saved.status_code == 200
        assert _status(client, deal_id)["rows_wait_for_a_resync"] is True
        assert _status(client, deal_id)["projected_return_at_rehab_end_dollars"] == 17000        # the page already knows
        _refresh(client)
        assert _amounts(client, deal_id) == {RETURN: 25000}                                      # the timeline waits

        preview = client.post(f"/liquidity/deals/bought/{deal_id}/import-preview", json={"today": DURING_THE_REHAB}).json()
        return_change = next(change for change in preview["changes"] if change["item_key"] == RETURN)
        assert (return_change["amount_dollars_before"], return_change["amount_dollars_after"]) == (25000, 17000)
        assert next(change for change in preview["changes"] if change["item_key"] == "appliances")["change_kind"] == "unchanged"

        client.post(f"/liquidity/deals/bought/{deal_id}/import", json={"today": DURING_THE_REHAB})
        assert _amounts(client, deal_id) == {RETURN: 17000}
        assert _status(client, deal_id)["rows_wait_for_a_resync"] is False


class TestLinkingInTheMiddleOfARehab:
    def test_the_baselines_say_what_moved_before_the_account_and_stay_editable(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        # $30,000 was pulled into checking before the account existed; only the cushion goes into it.
        _link(client, deal_id, loan_draws_pulled_before_construction_account_dollars=30000)
        mercury.move("construction", "deposit", 5000, internal=True)
        _refresh(client)
        status = _status(client, deal_id)
        assert status["loan_draws_pulled"] == {"from_the_bank_feed_dollars": 0, "before_this_account_dollars": 30000,
                                               "entered_by_hand_dollars": 0, "total_dollars": 30000}
        assert status["projected_return_at_rehab_end_dollars"] == -5000    # 5,000 + (70,000 - 30,000) - 50,000
        assert _amounts(client, deal_id) == {TOP_UP: -5000}

        # Later: $12,000 of rehab had in fact been paid from checking already.
        edited = _link(client, deal_id, loan_draws_pulled_before_construction_account_dollars=30000,
                       rehab_payments_made_before_construction_account_dollars=12000)
        assert edited.status_code == 200 and edited.json()["projected_return_at_rehab_end_dollars"] == 7000
        assert _amounts(client, deal_id) == {RETURN: 7000}

    def test_the_deposit_target_and_the_buffer_to_keep_are_yours_to_set(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        status = _link(client, deal_id, planned_deposit_override_dollars=12000,
                       minimum_balance_to_keep_in_construction_account_dollars=10000).json()
        assert (status["planned_deposit_dollars"], status["planned_deposit_by_the_formula_dollars"]) == (12000, 5000)
        assert _amounts(client, deal_id) == {DEPOSIT: -12000, RETURN: 32000}
        mercury.move("construction", "deposit", 12000, internal=True)
        mercury.move("construction", "draw-1", 20000)
        _refresh(client)
        assert _status(client, deal_id)["safe_to_steal_now_dollars"] == 22000   # 32,000 in the account, 10,000 to keep


class TestManualAdjustments:
    def test_a_payment_or_a_draw_outside_the_account_is_added_edited_and_deleted(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        _refresh(client)
        base_url = f"/liquidity/construction-accounts/{deal_id}/manual-adjustments"

        added = client.post(base_url, json={"adjustment_type": "manual_payment", "amount_dollars": 2000, "date": "2026-01-20",
                                            "note": "Tile on the credit card"})
        assert added.status_code == 201
        status = added.json()
        (adjustment,) = status["manual_adjustments"]
        assert (adjustment["adjustment_type"], adjustment["amount_dollars"], adjustment["note"]) == ("manual_payment", 2000, "Tile on the credit card")
        assert status["rehab_payments_made"]["entered_by_hand_dollars"] == 2000
        assert _amounts(client, deal_id) == {RETURN: 27000}                # paid elsewhere: the account owes $2,000 less

        client.put(f"{base_url}/{adjustment['id']}", json={"adjustment_type": "manual_draw", "amount_dollars": 3000, "date": "2026-01-21"})
        assert _status(client, deal_id)["loan_draws_pulled"]["entered_by_hand_dollars"] == 3000
        assert _amounts(client, deal_id) == {RETURN: 22000}                # a draw wired elsewhere will not reach the account

        assert client.delete(f"{base_url}/{adjustment['id']}").json()["manual_adjustments"] == []
        assert _amounts(client, deal_id) == {RETURN: 25000}

    def test_bad_entries_and_other_deals_entries_are_refused(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        base_url = f"/liquidity/construction-accounts/{deal_id}/manual-adjustments"
        assert client.post(base_url, json={"adjustment_type": "manual_payment", "amount_dollars": 100, "date": "2026-01-20"}).status_code == 404   # not linked
        _link(client, deal_id)
        for body in ({"adjustment_type": "manual_payment", "amount_dollars": 0, "date": "2026-01-20"},
                     {"adjustment_type": "manual_payment", "amount_dollars": -5, "date": "2026-01-20"},
                     {"adjustment_type": "refund", "amount_dollars": 5, "date": "2026-01-20"},
                     {"adjustment_type": "manual_payment", "amount_dollars": 5, "date": "2026-01-20", "note": "x" * 501}):
            assert client.post(base_url, json=body).status_code == 422
        assert client.delete(f"{base_url}/00000000-0000-0000-0000-000000000000").status_code == 404
        assert client.delete(f"{base_url}/not-a-uuid").status_code == 404


class TestTransactionOverrides:
    def test_the_transactions_are_listed_with_their_categories_and_can_be_ignored_or_recategorised(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "draw-1", 30000)
        mercury.move("construction", "materials-for-another-property", -3000)
        mercury.move("construction", "store-refund", 400)
        mercury.move("construction", "bounced-payment", -700, status="failed")
        _refresh(client)
        base_url = f"/liquidity/construction-accounts/{deal_id}/transactions"

        listed = {transaction["mercury_transaction_id"]: transaction for transaction in client.get(base_url).json()}
        assert listed["deposit"]["automatic_category"] == listed["deposit"]["effective_category"] == "own_money"
        assert listed["draw-1"]["automatic_category"] == "loan_draw" and listed["store-refund"]["automatic_category"] == "loan_draw"
        assert listed["materials-for-another-property"]["effective_category"] == "rehab_payment"
        assert listed["bounced-payment"]["effective_category"] is None and listed["bounced-payment"]["bank_status"] == "failed"
        # The refund reads as a draw: $400 more in the account, $400 less still to pull. The $3,000 reads as rehab paid.
        assert _status(client, deal_id)["projected_return_at_rehab_end_dollars"] == 25000

        ignored = client.put(f"{base_url}/materials-for-another-property/override", json={"ignored": True, "note": "For 2 Second St"}).json()
        assert ignored["rehab_payments_made"]["from_the_bank_feed_dollars"] == 0
        refund = client.put(f"{base_url}/store-refund/override", json={"category_override": "rehab_payment"}).json()
        assert refund["loan_draws_pulled"]["from_the_bank_feed_dollars"] == 30000
        assert refund["rehab_payments_made"]["from_the_bank_feed_dollars"] == -400
        # 32,400 in the account + 40,000 still to pull - (50,000 + 400 refunded): the $3,000 spent elsewhere is gone.
        assert refund["projected_return_at_rehab_end_dollars"] == 22000
        assert _amounts(client, deal_id) == {RETURN: 22000}
        listed = {transaction["mercury_transaction_id"]: transaction for transaction in client.get(base_url).json()}
        assert (listed["materials-for-another-property"]["ignored"], listed["materials-for-another-property"]["note"]) == (True, "For 2 Second St")
        assert listed["store-refund"]["effective_category"] == "rehab_payment"

        assert client.delete(f"{base_url}/materials-for-another-property/override").json()["rehab_payments_made"]["from_the_bank_feed_dollars"] == 2600
        assert client.delete(f"{base_url}/materials-for-another-property/override").status_code == 404

    def test_only_a_transaction_of_this_deals_own_account_can_be_overridden(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("checking", "a-checking-transaction", -100)
        base_url = f"/liquidity/construction-accounts/{deal_id}/transactions"
        assert client.put(f"{base_url}/a-checking-transaction/override", json={"ignored": True}).status_code == 404
        assert client.put(f"{base_url}/no-such-transaction/override", json={"ignored": True}).status_code == 404
        assert client.put(f"{base_url}/draw-1/override", json={"category_override": "something_else"}).status_code == 422
        mercury.is_down = True
        assert client.get(base_url).status_code == 502


class TestSwitchingTheAccount:
    def test_the_old_account_must_be_empty_and_its_draws_and_payments_carry_over(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "draw-1", 30000)
        mercury.move("construction", "gc-payment-1", -18000)
        _refresh(client)
        base_url = f"/liquidity/construction-accounts/{deal_id}"

        preview = client.get(f"{base_url}/switch-account-preview").json()
        assert preview == {"old_construction_account_balance_dollars": 17000, "old_account_must_be_emptied_first": True,
                           "loan_draws_pulled_before_construction_account_dollars": 30000,
                           "rehab_payments_made_before_construction_account_dollars": 18000}
        switch_body = {"new_construction_mercury_account_id": "construction-2",
                       "loan_draws_pulled_before_construction_account_dollars": 30000,
                       "rehab_payments_made_before_construction_account_dollars": 18000}
        assert client.post(f"{base_url}/switch-account", json=switch_body).status_code == 409

        mercury.move("construction", "to-the-new-account", -17000, internal=True)
        mercury.move("construction-2", "from-the-old-account", 17000, internal=True)
        switched = client.post(f"{base_url}/switch-account", json=switch_body)
        assert switched.status_code == 200
        status = switched.json()
        assert status["construction_account"]["mercury_account_id"] == "construction-2"
        assert status["previous_construction_mercury_account_ids"] == ["construction"]
        assert status["loan_draws_pulled"] == {"from_the_bank_feed_dollars": 0, "before_this_account_dollars": 30000,
                                               "entered_by_hand_dollars": 0, "total_dollars": 30000}
        assert status["projected_return_at_rehab_end_dollars"] == 25000    # 17,000 + 40,000 - 32,000: unchanged by the switch
        rows = _rows(client, deal_id)
        assert rows[DEPOSIT]["done_at"] is not None and _amounts(client, deal_id) == {RETURN: 25000}
        assert client.post(f"{base_url}/switch-account", json=switch_body).status_code == 422   # already this account


class TestClosingOut:
    def test_ready_closed_out_and_reopened(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "draw-1", 70000)
        mercury.move("construction", "gc-payment-1", -50000)
        _refresh(client)
        base_url = f"/liquidity/construction-accounts/{deal_id}"

        assert client.post(f"{base_url}/mark-ready-for-close-out").json()["marked_ready_for_close_out_at"] is not None

        closed = client.post(f"{base_url}/mark-closed-out").json()
        assert closed["balance_left_in_the_account_dollars"] == 25000     # not emptied yet: the page says so
        assert closed["status"]["closed_out_at"] is not None and closed["status"]["safe_to_steal_now_dollars"] == 0
        assert _rows(client, deal_id)[RETURN]["done_at"] is not None and _amounts(client, deal_id) == {}
        assert _refresh(client) == {"refreshed_deal_count": 0, "changed_row_count": 0, "mercury_is_unavailable": False}

        reopened = client.post(f"{base_url}/reopen").json()
        assert reopened["closed_out_at"] is None
        assert _amounts(client, deal_id) == {RETURN: 25000}


class TestTheList:
    def test_only_bought_deals_in_the_timeline_that_are_not_refinanced_and_every_linked_deal(self, client, mercury, bought_deal, brrrr_payload):
        not_imported = client.post("/active-deals", json={**brrrr_payload, "address": "3 Not Imported St"}).json()
        client.post(f"/bought-deals/from-active/{not_imported['id']}", params={"deal_type": "BRRRR"})
        my_deals_only = client.post("/active-deals", json={**brrrr_payload, "address": "4 My Deals St"}).json()
        client.post(f"/liquidity/deals/my_deals/{my_deals_only['id']}/import", json={"today": BEFORE_THE_DEAL})
        assert [status["bought_deal_id"] for status in client.get("/liquidity/construction-accounts").json()] == [bought_deal["id"]]

        approve_the_refi = {"milestone": "refi_closed", "new_date": "2026-07-09", "approve": True, "today": "2026-07-10"}
        assert client.post(f"/liquidity/deals/bought/{bought_deal['id']}/milestones/apply", json=approve_the_refi).status_code == 200
        assert client.get("/liquidity/construction-accounts").json() == []

    def test_a_linked_deal_stays_listed_after_its_refi(self, client, mercury, bought_deal):
        _link(client, bought_deal["id"])
        approve_the_refi = {"milestone": "refi_closed", "new_date": "2026-07-09", "approve": True, "today": "2026-07-10"}
        client.post(f"/liquidity/deals/bought/{bought_deal['id']}/milestones/apply", json=approve_the_refi)
        assert [status["bought_deal_id"] for status in client.get("/liquidity/construction-accounts").json()] == [bought_deal["id"]]


class TestUnlinkAndDelete:
    def test_unlinking_puts_the_rows_back_on_the_plan_and_drops_the_manual_entries(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id, loan_draws_pulled_before_construction_account_dollars=30000)
        client.post(f"/liquidity/construction-accounts/{deal_id}/manual-adjustments",
                    json={"adjustment_type": "manual_payment", "amount_dollars": 2000, "date": "2026-01-20"})
        # Nothing deposited yet, $30,000 of the lender's money in checking, $2,000 paid elsewhere: 5,000 + 3,000 to bring.
        assert _amounts(client, deal_id) == {DEPOSIT: -5000, TOP_UP: -3000}

        unlinked = client.delete(f"/liquidity/construction-accounts/{deal_id}")
        assert unlinked.status_code == 200 and unlinked.json()["is_linked"] is False
        assert _amounts(client, deal_id) == {DEPOSIT: -5000, RETURN: 25000}
        assert _link(client, deal_id).json()["manual_adjustments"] == []
        assert client.get("/liquidity/mercury-balance").json()["counted_as_cash_balance_dollars"] == 80000 + 9000

    def test_deleting_the_bought_deal_frees_its_construction_account(self, client, mercury, bought_deal, brrrr_payload):
        _link(client, bought_deal["id"])
        assert client.delete(f"/bought-deals/{bought_deal['id']}", params={"deal_type": "BRRRR"}).status_code == 200
        assert client.get("/liquidity/construction-accounts").json() == []
        second_my_deals_deal = client.post("/active-deals", json={**brrrr_payload, "address": "2 Second St"}).json()
        second_deal = client.post(f"/bought-deals/from-active/{second_my_deals_deal['id']}", params={"deal_type": "BRRRR"}).json()
        assert _link(client, second_deal["id"]).status_code == 200
