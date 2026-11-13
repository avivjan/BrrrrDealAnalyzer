"""/liquidity/construction-accounts/* against a fake Mercury (tasks/todo/ConstructionAccountPerRehab.md).

The deal throughout: construction budget $70,000, rehab cost $50,000 (so the original steal is $20,000), cushion
$5,000. Its plan: deposit $5,000 on the purchase closing (2026-01-10), $25,000 back on the rehab completion (2026-02-24).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from BL.liquidity.common import mercury_client, mercury_reads
from BL.liquidity.common.mercury_client import MercuryApiError, MercurySlowDownError
from BL.liquidity.constructionAccount import construction_accounts as construction_accounts_module

BEFORE_THE_DEAL = "2025-12-01"
DURING_THE_REHAB = "2026-02-01"
DEPOSIT, RETURN, TOP_UP = "construction_account_deposit", "construction_account_balance_returned_at_rehab_end", "construction_account_top_up_needed"


class FakeMercury:
    """Two workspaces. AJYK: checking, a tax bucket and two construction accounts. OTHER: one checking."""

    def __init__(self):
        self.is_down = False
        self.answers_slow_down = False
        self.accounts_call_count_by_workspace: dict[str, int] = {}
        self.transactions_call_count = 0
        self.balance_by_account_id = {"checking": 80000, "tax": 4000, "construction": 0, "construction-2": 0, "other-checking": 9000}
        self.workspace_by_account_id = {"checking": "AJYK", "tax": "AJYK", "construction": "AJYK", "construction-2": "AJYK", "other-checking": "OTHER"}
        self.transactions_by_account_id: dict[str, list[dict]] = {account_id: [] for account_id in self.balance_by_account_id}

    def fetch_workspace_summary(self, workspace_label: str) -> dict:
        self.accounts_call_count_by_workspace[workspace_label] = self.accounts_call_count_by_workspace.get(workspace_label, 0) + 1
        if self.answers_slow_down:
            raise MercurySlowDownError(retry_after_seconds=None)
        if self.is_down:
            raise MercuryApiError("HTTP 500")
        accounts = [{"id": account_id, "name": f"{account_id} account", "account_number_last_four": "1234", "type": "checking",
                     "status": "active", "current_balance_dollars": float(balance), "available_balance_dollars": float(balance),
                     "workspace": workspace_label} for account_id, balance in self.balance_by_account_id.items()
                    if self.workspace_by_account_id[account_id] == workspace_label]
        total = round(sum(account["current_balance_dollars"] for account in accounts), 2)
        return {"workspace": workspace_label, "total_balance_dollars": total, "total_available_dollars": total,
                "account_count": len(accounts), "accounts": accounts}

    def fetch_account_transactions(self, workspace_label: str, account_id: str, use_cache: bool = True) -> list[dict]:
        self.transactions_call_count += 1
        if self.answers_slow_down:
            raise MercurySlowDownError(retry_after_seconds=None)
        if self.is_down:
            raise MercuryApiError("HTTP 500")
        assert self.workspace_by_account_id[account_id] == workspace_label
        return list(self.transactions_by_account_id[account_id])

    def move(self, account_id: str, transaction_id: str, signed_amount: int, internal: bool = False, status: str = "sent",
             counterparty_name: str = "") -> None:
        """One bank transaction on an account: positive = into it."""
        self.transactions_by_account_id[account_id].append({
            "id": transaction_id, "signed_amount_dollars": Decimal(signed_amount), "kind": "internalTransfer" if internal else "wire",
            "status": status, "counterparty_name": counterparty_name or transaction_id, "transaction_date": date(2026, 1, 15),
            "is_internal_transfer": internal, "is_failed_or_cancelled": status in {"failed", "cancelled"}, "is_pending": status == "pending"})
        if status not in {"failed", "cancelled"}:
            self.balance_by_account_id[account_id] += signed_amount


@pytest.fixture
def mercury(monkeypatch) -> FakeMercury:
    """The fake bank, with the shared pace turned off (its own tests turn it back on) so each refresh reads it."""
    fake_mercury = FakeMercury()
    for name in [name for name in __import__("os").environ if name.startswith("MERCURY_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MERCURY_API_TOKEN_AJYK", "fake-read-token-ajyk")
    monkeypatch.setenv("MERCURY_API_TOKEN_OTHER", "fake-read-token-other")
    monkeypatch.setenv("MERCURY_CACHE_SECONDS", "0")
    monkeypatch.setattr(mercury_reads, "MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE", 0)
    monkeypatch.setattr(mercury_client, "fetch_workspace_summary", fake_mercury.fetch_workspace_summary)
    monkeypatch.setattr(construction_accounts_module, "fetch_account_transactions", fake_mercury.fetch_account_transactions)
    mercury_client.clear_cache()
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


def _refresh_counts(client, today: str = DURING_THE_REHAB) -> tuple:
    refreshed = _refresh(client, today)
    return refreshed["refreshed_deal_count"], refreshed["changed_row_count"], refreshed["mercury_is_unavailable"]


def _status(client, deal_id: str) -> dict:
    return next(status for status in client.get("/liquidity/construction-accounts").json()["accounts"] if status["bought_deal_id"] == deal_id)


def _after(response) -> dict:
    """The deal's status after a confirmed write."""
    assert response.status_code in (200, 201), response.text
    body = response.json()
    assert body["was_preview_only"] is False
    return body["status_after"]


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
        status = _after(response)
        assert status["is_linked"] is True and status["mercury_workspace_label"] == "AJYK"
        assert status["construction_account"] == {"mercury_account_id": "construction", "name": "construction account", "account_number_last_four": "1234"}
        assert status["primary_checking_account"]["mercury_account_id"] == "checking"
        assert status["amounts_as_of"] is not None and status["mercury_is_unavailable"] is False
        assert (status["remaining_deposit_dollars"], status["projected_return_at_rehab_end_dollars"]) == (5000, 20000)
        assert (status["rehab_cushion_dollars"], status["rehab_beyond_the_construction_budget_dollars"], status["total_to_deposit_dollars"]) == (5000, 0, 5000)
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
        assert _refresh_counts(client) == (0, 0, True)
        assert _amounts(client, deal_id) == {RETURN: 23000}
        assert _status(client, deal_id)["amounts_as_of"] == as_of

    def test_a_change_order_waits_for_the_resync_you_confirm(self, client, mercury, bought_deal, brrrr_payload):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        _refresh(client)

        saved = client.put(f"/bought-deals/{deal_id}", json={**bought_deal, "rehabCost": 58})   # a +$8,000 change order
        assert saved.status_code == 200
        assert _status(client, deal_id)["liquidity_rows_are_out_of_date"] is True
        assert _status(client, deal_id)["projected_return_at_rehab_end_dollars"] == 17000        # the page already knows
        _refresh(client)
        assert _amounts(client, deal_id) == {RETURN: 25000}                                      # the timeline waits

        preview = client.post(f"/liquidity/deals/bought/{deal_id}/import-preview", json={"today": DURING_THE_REHAB}).json()
        return_change = next(change for change in preview["changes"] if change["item_key"] == RETURN)
        assert (return_change["amount_dollars_before"], return_change["amount_dollars_after"]) == (25000, 17000)
        assert next(change for change in preview["changes"] if change["item_key"] == "appliances")["change_kind"] == "unchanged"

        client.post(f"/liquidity/deals/bought/{deal_id}/import", json={"today": DURING_THE_REHAB})
        assert _amounts(client, deal_id) == {RETURN: 17000}
        assert _status(client, deal_id)["liquidity_rows_are_out_of_date"] is False


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
        assert _after(edited)["projected_return_at_rehab_end_dollars"] == 7000
        assert _amounts(client, deal_id) == {RETURN: 7000}

    def test_the_cushion_is_the_one_deposit_figure_and_the_buffer_to_keep_is_yours_to_set(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id, minimum_balance_to_keep_in_construction_account_dollars=10000)
        status = _after(client.put(f"/liquidity/construction-accounts/{deal_id}/rehab-figures", json={"rehab_cushion_dollars": 12000}))
        assert (status["rehab_cushion_dollars"], status["total_to_deposit_dollars"], status["suggested_rehab_cushion_dollars"]) == (12000, 12000, 5000)
        assert _amounts(client, deal_id) == {DEPOSIT: -12000, RETURN: 32000}
        bought_deal_now = next(deal for deal in client.get("/bought-deals").json() if deal["id"] == deal_id)
        assert float(bought_deal_now["rehabCushion"]) == 12000                  # one figure, stored on the deal
        mercury.move("construction", "deposit", 12000, internal=True)
        mercury.move("construction", "draw-1", 20000)
        _refresh(client)
        assert _status(client, deal_id)["safe_to_steal_now_dollars"] == 22000   # 32,000 in the account, 10,000 to keep
        assert _status(client, deal_id)["safe_to_steal_now_is_capped_by"] == "buffer_to_keep"


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
        status = _after(added)
        (adjustment,) = status["manual_adjustments"]
        assert (adjustment["adjustment_type"], adjustment["amount_dollars"], adjustment["note"]) == ("manual_payment", 2000, "Tile on the credit card")
        assert status["rehab_payments_made"]["entered_by_hand_dollars"] == 2000
        assert _amounts(client, deal_id) == {RETURN: 27000}                # paid elsewhere: the account owes $2,000 less

        client.put(f"{base_url}/{adjustment['id']}", json={"adjustment_type": "manual_draw", "amount_dollars": 3000, "date": "2026-01-21"})
        assert _status(client, deal_id)["loan_draws_pulled"]["entered_by_hand_dollars"] == 3000
        assert _amounts(client, deal_id) == {RETURN: 22000}                # a draw wired elsewhere will not reach the account

        assert _after(client.delete(f"{base_url}/{adjustment['id']}"))["manual_adjustments"] == []
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

        ignored = _after(client.put(f"{base_url}/materials-for-another-property/override", json={"ignored": True, "note": "For 2 Second St"}))
        assert ignored["rehab_payments_made"]["from_the_bank_feed_dollars"] == 0
        refund = _after(client.put(f"{base_url}/store-refund/override", json={"category_override": "rehab_payment"}))
        assert refund["loan_draws_pulled"]["from_the_bank_feed_dollars"] == 30000
        assert refund["rehab_payments_made"]["from_the_bank_feed_dollars"] == -400
        # 32,400 in the account + 40,000 still to pull - (50,000 + 400 refunded): the $3,000 spent elsewhere is gone.
        assert refund["projected_return_at_rehab_end_dollars"] == 22000
        assert _amounts(client, deal_id) == {RETURN: 22000}
        listed = {transaction["mercury_transaction_id"]: transaction for transaction in client.get(base_url).json()}
        assert (listed["materials-for-another-property"]["ignored"], listed["materials-for-another-property"]["note"]) == (True, "For 2 Second St")
        assert listed["store-refund"]["effective_category"] == "rehab_payment"

        assert _after(client.delete(f"{base_url}/materials-for-another-property/override"))["rehab_payments_made"]["from_the_bank_feed_dollars"] == 2600
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
        status = _after(switched)
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

        assert _after(client.post(f"{base_url}/mark-ready-for-close-out"))["marked_ready_for_close_out_at"] is not None

        closed = client.post(f"{base_url}/mark-closed-out").json()
        assert closed["balance_left_in_the_account_dollars"] == 25000     # not emptied yet: the page says so
        assert closed["status_after"]["closed_out_at"] is not None and closed["status_after"]["safe_to_steal_now_dollars"] == 0
        assert closed["row_descriptions_marked_done"] and closed["changes_the_liquidity_timeline"] is True
        assert _rows(client, deal_id)[RETURN]["done_at"] is not None and _amounts(client, deal_id) == {}
        assert _refresh_counts(client) == (0, 0, False)

        reopened = _after(client.post(f"{base_url}/reopen"))
        assert reopened["closed_out_at"] is None
        assert _amounts(client, deal_id) == {RETURN: 25000}


class TestTheList:
    def test_only_bought_deals_in_the_timeline_that_are_not_refinanced_and_every_linked_deal(self, client, mercury, bought_deal, brrrr_payload):
        not_imported = client.post("/active-deals", json={**brrrr_payload, "address": "3 Not Imported St"}).json()
        client.post(f"/bought-deals/from-active/{not_imported['id']}", params={"deal_type": "BRRRR"})
        my_deals_only = client.post("/active-deals", json={**brrrr_payload, "address": "4 My Deals St"}).json()
        client.post(f"/liquidity/deals/my_deals/{my_deals_only['id']}/import", json={"today": BEFORE_THE_DEAL})
        assert [status["bought_deal_id"] for status in client.get("/liquidity/construction-accounts").json()["accounts"]] == [bought_deal["id"]]

        approve_the_refi = {"milestone": "refi_closed", "new_date": "2026-07-09", "approve": True, "today": "2026-07-10"}
        assert client.post(f"/liquidity/deals/bought/{bought_deal['id']}/milestones/apply", json=approve_the_refi).status_code == 200
        assert client.get("/liquidity/construction-accounts").json()["accounts"] == []

    def test_a_linked_deal_stays_listed_after_its_refi(self, client, mercury, bought_deal):
        _link(client, bought_deal["id"])
        approve_the_refi = {"milestone": "refi_closed", "new_date": "2026-07-09", "approve": True, "today": "2026-07-10"}
        client.post(f"/liquidity/deals/bought/{bought_deal['id']}/milestones/apply", json=approve_the_refi)
        assert [status["bought_deal_id"] for status in client.get("/liquidity/construction-accounts").json()["accounts"]] == [bought_deal["id"]]


class TestUnlinkAndDelete:
    def test_unlinking_puts_the_rows_back_on_the_plan_and_drops_the_manual_entries(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id, loan_draws_pulled_before_construction_account_dollars=30000)
        client.post(f"/liquidity/construction-accounts/{deal_id}/manual-adjustments",
                    json={"adjustment_type": "manual_payment", "amount_dollars": 2000, "date": "2026-01-20"})
        # Nothing deposited yet, $30,000 of the lender's money in checking, $2,000 paid elsewhere: 5,000 + 3,000 to bring.
        assert _amounts(client, deal_id) == {DEPOSIT: -5000, TOP_UP: -3000}

        unlinked = client.delete(f"/liquidity/construction-accounts/{deal_id}")
        assert _after(unlinked)["is_linked"] is False
        assert _amounts(client, deal_id) == {DEPOSIT: -5000, RETURN: 25000}
        assert _after(_link(client, deal_id))["manual_adjustments"] == []
        assert client.get("/liquidity/mercury-balance").json()["counted_as_cash_balance_dollars"] == 80000 + 9000

    def test_deleting_the_bought_deal_frees_its_construction_account(self, client, mercury, bought_deal, brrrr_payload):
        _link(client, bought_deal["id"])
        assert client.delete(f"/bought-deals/{bought_deal['id']}", params={"deal_type": "BRRRR"}).status_code == 200
        assert client.get("/liquidity/construction-accounts").json()["accounts"] == []
        second_my_deals_deal = client.post("/active-deals", json={**brrrr_payload, "address": "2 Second St"}).json()
        second_deal = client.post(f"/bought-deals/from-active/{second_my_deals_deal['id']}", params={"deal_type": "BRRRR"}).json()
        assert _link(client, second_deal["id"]).status_code == 200


class TestEveryWriteCanBePreviewed:
    """The confirmation prompt: a write with preview_only answers what it would change and saves nothing."""

    def test_a_preview_answers_the_same_as_the_confirmed_write_and_saves_nothing(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        _refresh(client)
        rows_before, status_before = _rows(client, deal_id), _status(client, deal_id)
        body = {"adjustment_type": "manual_payment", "amount_dollars": 2000, "date": "2026-01-20"}
        url = f"/liquidity/construction-accounts/{deal_id}/manual-adjustments"

        preview = client.post(url, json=body, params={"preview_only": True}).json()
        assert preview["was_preview_only"] is True and preview["changes_the_liquidity_timeline"] is True
        assert preview["status_before"]["projected_return_at_rehab_end_dollars"] == 25000
        assert preview["status_after"]["projected_return_at_rehab_end_dollars"] == 27000
        (return_change,) = [change for change in preview["liquidity_row_changes"]["changes"] if change["item_key"] == RETURN]
        assert (return_change["amount_dollars_before"], return_change["amount_dollars_after"]) == (25000, 27000)
        assert _rows(client, deal_id) == rows_before and _status(client, deal_id) == status_before   # nothing saved

        confirmed = client.post(url, json=body).json()
        assert confirmed["was_preview_only"] is False
        assert confirmed["status_after"]["projected_return_at_rehab_end_dollars"] == preview["status_after"]["projected_return_at_rehab_end_dollars"]
        assert confirmed["liquidity_row_changes"]["change_counts"] == preview["liquidity_row_changes"]["change_counts"]
        assert _amounts(client, deal_id) == {RETURN: 27000}

    def test_a_preview_of_a_first_link_leaves_no_link(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        preview = client.put(f"/liquidity/construction-accounts/{deal_id}", params={"preview_only": True},
                             json={"construction_mercury_account_id": "construction", "primary_checking_mercury_account_id": "checking"}).json()
        assert preview["status_before"]["is_linked"] is False and preview["status_after"]["is_linked"] is True
        assert _status(client, deal_id)["is_linked"] is False
        assert client.get("/liquidity/mercury-balance").json()["counted_as_cash_balance_dollars"] == 80000 + 9000   # still counted

    def test_a_preview_of_an_edit_keeps_the_saved_link(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        preview = _link(client, deal_id, minimum_balance_to_keep_in_construction_account_dollars=4000)
        assert preview.json()["status_after"]["minimum_balance_to_keep_in_construction_account_dollars"] == 4000
        edit_preview = client.put(f"/liquidity/construction-accounts/{deal_id}", params={"preview_only": True},
                                  json={"construction_mercury_account_id": "construction", "primary_checking_mercury_account_id": "checking",
                                        "minimum_balance_to_keep_in_construction_account_dollars": 9000}).json()
        assert edit_preview["status_after"]["minimum_balance_to_keep_in_construction_account_dollars"] == 9000
        assert _status(client, deal_id)["minimum_balance_to_keep_in_construction_account_dollars"] == 4000
        another_account = client.put(f"/liquidity/construction-accounts/{deal_id}", params={"preview_only": True},
                                     json={"construction_mercury_account_id": "construction-2", "primary_checking_mercury_account_id": "checking"})
        assert another_account.status_code == 409   # changing the account itself is the switch, even in a preview

    def test_an_edit_that_changes_no_row_says_so(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        answer = _link(client, deal_id, minimum_balance_to_keep_in_construction_account_dollars=3000).json()
        assert answer["changes_the_liquidity_timeline"] is False and answer["liquidity_row_changes"]["change_counts"]["updated"] == 0

    def test_a_row_you_edited_by_hand_is_kept_unless_you_take_the_new_value(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        return_row = _rows(client, deal_id)[RETURN]
        client.put(f"/liquidity/transactions/{return_row['id']}", json={"effective_date": "2026-03-15"})   # you moved its date
        url = f"/liquidity/construction-accounts/{deal_id}/rehab-figures"
        moved_rehab = {"rehab_cushion_dollars": 7000}
        kept = client.put(url, json=moved_rehab, params={"preview_only": True}).json()
        (change,) = [change for change in kept["liquidity_row_changes"]["changes"] if change["item_key"] == RETURN]
        assert change["date_after"] == "2026-03-15" and change["deal_date_not_applied_because_you_changed_it"] == "2026-02-24"
        taken = client.put(url, json=moved_rehab, params={"use_the_new_value_for": [f"{return_row['id']}:date"]}).json()
        (change,) = [change for change in taken["liquidity_row_changes"]["changes"] if change["item_key"] == RETURN]
        assert change["date_after"] == "2026-02-24"
        assert client.put(url, json=moved_rehab, params={"use_the_new_value_for": ["not a choice"]}).status_code == 422


class TestTheRehabFigures:
    def test_they_are_written_to_the_bought_deal_and_the_rows_follow(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        url = f"/liquidity/construction-accounts/{deal_id}/rehab-figures"
        before = _status(client, deal_id)
        answer = client.put(url, json={"actual_rehab_cost_dollars": 58000}).json()   # a +$8,000 change order, no account linked yet
        assert answer["status_after"]["rehab_cost_dollars"] == 58000 and answer["status_after"]["original_steal_dollars"] == 12000
        assert answer["status_after"]["deal_updated_at"] > before["deal_updated_at"]
        assert _amounts(client, deal_id) == {DEPOSIT: -5000, RETURN: 17000}
        bought = next(deal for deal in client.get("/bought-deals").json() if deal["id"] == deal_id)
        assert float(bought["rehabCost"]) == 58

        beyond = client.put(url, json={"construction_budget_dollars": 50000, "rehab_contingency_percent": 10}).json()["status_after"]
        assert beyond["rehab_cost_dollars"] == 63800 and beyond["rehab_beyond_the_construction_budget_dollars"] == 13800
        assert beyond["total_to_deposit_dollars"] == 18800      # cushion 5,000 + rehab beyond the budget 13,800
        assert _amounts(client, deal_id) == {DEPOSIT: -18800, RETURN: 5000}

    def test_they_are_validated_like_a_deal_save(self, client, mercury, bought_deal):
        url = f"/liquidity/construction-accounts/{bought_deal['id']}/rehab-figures"
        assert client.put(url, json={}).status_code == 422
        assert client.put(url, json={"actual_rehab_cost_dollars": -1}).status_code == 422
        assert client.put(url, json={"rehab_contingency_percent": 101}).status_code == 422
        assert client.put("/liquidity/construction-accounts/00000000-0000-0000-0000-000000000000/rehab-figures",
                          json={"rehab_cushion_dollars": 1}).status_code == 404
        assert _status(client, bought_deal["id"])["rehab_cost_dollars"] == 50000


class TestAConfirmedWriteSyncsTheWholeDeal:
    def test_a_deal_out_of_date_is_synced_by_the_next_confirmed_write(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        client.put(f"/bought-deals/{deal_id}", json={**bought_deal, "appliances": 900})   # a deal save: the prompt is pending
        assert _status(client, deal_id)["liquidity_rows_are_out_of_date"] is True
        answer = _link(client, deal_id, minimum_balance_to_keep_in_construction_account_dollars=1000).json()
        appliances_change = next(change for change in answer["liquidity_row_changes"]["changes"] if change["item_key"] == "appliances")
        assert appliances_change["amount_dollars_after"] == -900
        assert answer["status_after"]["liquidity_rows_are_out_of_date"] is False

    def test_a_cushion_already_marked_done_carries_over_to_the_new_deposit_row(self, client, mercury, bought_deal):
        import db as app_db
        from sqlalchemy import text
        deal_id = bought_deal["id"]
        with app_db.engine.begin() as conn:   # a deal imported before the construction account rows
            conn.execute(text("UPDATE liquidity_transactions SET source_item_key = 'rehab_cushion', done_at = now() "
                              "WHERE source_item_key = :deposit AND source_deal_id = :deal_id"), {"deposit": DEPOSIT, "deal_id": deal_id})
            conn.execute(text("UPDATE bought_brrrr_deals SET liquidity_rows_out_of_date = TRUE WHERE id = :deal_id"), {"deal_id": deal_id})
        client.post(f"/liquidity/deals/bought/{deal_id}/import", json={"today": DURING_THE_REHAB})
        deposit_row = _rows(client, deal_id)[DEPOSIT]
        assert deposit_row["done_at"] is not None   # no overdue deposit appears


class TestTheBankReportsAChange:
    def test_the_refresh_lists_the_rows_it_moved_but_not_the_top_ups_daily_roll(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "draw-1", 70000)
        mercury.move("construction", "steal-at-the-bank", -40000, internal=True)
        refreshed = _refresh(client)
        assert refreshed["construction_accounts_changed"] is True
        (reported,) = refreshed["bank_reported_row_changes"]
        assert {change["item_key"] for change in reported["changes"]} >= {RETURN, TOP_UP}
        rolled = _refresh(client, today="2026-02-03")
        assert _rows(client, deal_id)[TOP_UP]["effective_date"] == "2026-02-03"
        assert rolled["bank_reported_row_changes"] == [] and rolled["construction_accounts_changed"] is False


class TestEveryNumberOnThePage:
    def test_the_bank_details_the_percentages_the_split_and_the_totals(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        _link(client, deal_id)
        mercury.move("construction", "deposit", 5000, internal=True)
        mercury.move("construction", "draw-1", 30000)
        mercury.move("construction", "gc-payment-1", -12000, counterparty_name="GC LLC")
        mercury.move("construction", "electrician-payment", -3000, counterparty_name="Sparks Electric")
        mercury.move("construction", "gc-payment-2", -6000, counterparty_name="GC LLC")
        mercury.move("construction", "pending-draw", 1000, status="pending")
        _refresh(client)
        status = _status(client, deal_id)
        assert (status["pending_money_in_dollars"], status["pending_money_out_dollars"]) == (1000, 0)
        assert status["primary_checking_available_balance_dollars"] == 80000
        assert status["rehab_paid_by_payee"] == [{"payee_name": "GC LLC", "amount_dollars": 18000},
                                                 {"payee_name": "Sparks Electric", "amount_dollars": 3000}]
        assert status["loan_draw_count"] == 2 and status["percent_of_the_construction_budget_pulled"] == 44.3   # 31,000 of 70,000
        assert status["percent_of_the_rehab_paid"] == 42.0                                                     # 21,000 of 50,000
        assert status["last_loan_draw"]["amount_dollars"] in (30000, 1000)
        assert status["transactions_counted_count"] == 6 and status["transactions_failed_or_cancelled_count"] == 0
        assert status["projected_return_at_rehab_end_dollars"] == 25000
        assert (status["own_money_back_at_rehab_end_dollars"], status["spread_at_rehab_end_dollars"]) == (5000, 20000)
        assert {row["item_key"] for row in status["timeline_rows"]} >= {DEPOSIT, RETURN, "appliances"}
        assert status["appliances_dollars"] == float(bought_deal["appliances"])

        page = client.get("/liquidity/construction-accounts").json()
        assert page["totals"]["linked_account_count"] == 1
        assert page["totals"]["projected_return_at_rehab_end_dollars"] == 25000
        assert page["totals"]["current_balance_dollars"] == status["current_balance_dollars"]

    def test_a_deal_with_a_deposit_due_needs_attention(self, client, mercury, bought_deal):
        _link(client, bought_deal["id"])
        page = client.get("/liquidity/construction-accounts").json()
        assert page["accounts"][0]["needs_attention_because"] == ["deposit_due"]   # the purchase closed, nothing deposited
        assert page["totals"]["accounts_needing_attention_count"] == 1


class TestTheMercuryConnectionStatus:
    def test_it_names_the_settings_it_reads_and_never_a_value(self, client, mercury, bought_deal, monkeypatch):
        monkeypatch.setenv("MERCURY_TRANSFER_API_TOKEN_AJYK", "fake-transfer-token-ajyk")
        body = client.get("/liquidity/mercury-connection-status").json()
        by_label = {workspace["mercury_workspace_label"]: workspace for workspace in body["workspaces"]}
        assert set(by_label) == {"AJYK", "OTHER"}
        assert (by_label["AJYK"]["has_read_token"], by_label["AJYK"]["has_transfer_token"]) == (True, True)
        assert (by_label["OTHER"]["has_transfer_token"], by_label["OTHER"]["transfer_token_environment_variable_name"]) == (
            False, "MERCURY_TRANSFER_API_TOKEN_OTHER")
        assert by_label["OTHER"]["read_token_environment_variable_name"] == "MERCURY_API_TOKEN_OTHER"
        assert by_label["AJYK"]["instant_updates_are_on"] is False and by_label["AJYK"]["last_valid_event_received_at"] is None
        assert body["transfer_token_environment_variable_name_pattern"] == "MERCURY_TRANSFER_API_TOKEN_<LABEL>"
        assert "fake-" not in str(body)


class TestTheSharedMercuryPace:
    """One Mercury read per workspace every 10 seconds, whoever asks; a 429 backs every reader off."""

    @pytest.fixture
    def paced(self, monkeypatch, mercury):
        monkeypatch.setattr(mercury_reads, "MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE", 10)
        return mercury

    def test_the_general_balance_and_the_refresh_share_one_read(self, client, paced, bought_deal):
        _link(client, bought_deal["id"])
        calls_before = dict(paced.accounts_call_count_by_workspace)
        client.get("/liquidity/mercury-balance", params={"fresh": True})
        _refresh(client)
        client.get("/liquidity/mercury-balance", params={"fresh": True})
        new_calls = {label: count - calls_before.get(label, 0) for label, count in paced.accounts_call_count_by_workspace.items()}
        assert new_calls == {"AJYK": 0, "OTHER": 0}   # the link just read both: every reader since got that snapshot

    def test_a_slow_down_answer_backs_off_every_reader(self, client, paced, bought_deal):
        import db as app_db
        from sqlalchemy import text
        with app_db.engine.begin() as conn:   # the floor has passed
            conn.execute(text("UPDATE liquidity_mercury_workspace_reads SET last_mercury_read_at = now() - interval '1 hour'"))
        assert client.get("/liquidity/mercury-balance", params={"fresh": True}).status_code == 200   # a first snapshot
        with app_db.engine.begin() as conn:
            conn.execute(text("UPDATE liquidity_mercury_workspace_reads SET last_mercury_read_at = now() - interval '1 hour'"))
        paced.answers_slow_down = True
        calls_before = sum(paced.accounts_call_count_by_workspace.values())
        refreshed = _refresh(client)
        assert refreshed["next_mercury_read_not_before"] is not None
        client.get("/liquidity/mercury-balance", params={"fresh": True})
        _refresh(client)
        assert sum(paced.accounts_call_count_by_workspace.values()) - calls_before == 2   # one per workspace, then the back-off holds
        assert client.get("/liquidity/mercury-balance").status_code == 200                # the last snapshot still answers

    def test_a_cash_balance_change_moves_the_last_change_with_no_account_linked(self, client, mercury, bought_deal):
        first = _refresh(client)
        assert first["cash_balance_changed"] is True   # the first read ever
        assert _refresh(client)["cash_balance_changed"] is False
        last_change = client.get("/liquidity/construction-accounts/last-change").json()
        mercury.balance_by_account_id["checking"] += 2500   # money lands in checking: no construction account involved
        refreshed = _refresh(client)
        assert refreshed["cash_balance_changed"] is True and refreshed["construction_accounts_changed"] is False
        moved = client.get("/liquidity/construction-accounts/last-change").json()
        assert moved["cash_balance_last_changed_at"] > last_change["cash_balance_last_changed_at"]
        assert client.get("/liquidity/mercury-balance").json()["counted_as_cash_balance_dollars"] == 80000 + 2500 + 9000


class TestAStaleBoughtDealFormCannotUndoACardEdit:
    def test_a_form_loaded_before_the_cards_edit_is_refused_and_a_save_without_the_time_still_works(self, client, mercury, bought_deal):
        deal_id = bought_deal["id"]
        form_loaded_at = bought_deal["updated_at"]
        client.put(f"/liquidity/construction-accounts/{deal_id}/rehab-figures", json={"actual_rehab_cost_dollars": 58000})

        stale = client.put(f"/bought-deals/{deal_id}", json={**bought_deal, "notes": "from an old tab"},
                           params={"updated_at_the_form_was_loaded_with": form_loaded_at})
        assert stale.status_code == 409 and "changed elsewhere" in stale.json()["detail"]
        assert _status(client, deal_id)["rehab_cost_dollars"] == 58000        # the card's edit survives

        fresh_deal = next(deal for deal in client.get("/bought-deals").json() if deal["id"] == deal_id)
        fresh = client.put(f"/bought-deals/{deal_id}", json={**fresh_deal, "notes": "from a fresh form"},
                           params={"updated_at_the_form_was_loaded_with": fresh_deal["updated_at"]})
        assert fresh.status_code == 200 and fresh.json()["notes"] == "from a fresh form"
        assert client.put(f"/bought-deals/{deal_id}", json={**bought_deal, "notes": "the connector"}).status_code == 200


class TestTheSettingsLiveInTheDatabase:
    def test_each_setting_is_saved_and_kept_within_its_bounds(self, client):
        defaults = client.get("/liquidity/settings").json()
        assert (defaults["construction_account_refresh_interval_seconds"], defaults["construction_account_refresh_when_window_regains_focus"],
                defaults["construction_account_in_app_transfers_enabled"], defaults["construction_account_transfers_per_hour_limit"],
                defaults["construction_account_maximum_single_transfer_dollars"]) == (30, True, True, 5, 100000)
        saved = client.put("/liquidity/settings", json={"construction_account_refresh_interval_seconds": 120,
                                                        "construction_account_in_app_transfers_enabled": False,
                                                        "construction_account_maximum_single_transfer_dollars": 25000}).json()
        assert (saved["construction_account_refresh_interval_seconds"], saved["construction_account_in_app_transfers_enabled"],
                saved["construction_account_maximum_single_transfer_dollars"]) == (120, False, 25000)
        assert client.put("/liquidity/settings", json={"reserve_dollars": 6000}).json()["construction_account_refresh_interval_seconds"] == 120
        for out_of_bounds in ({"construction_account_refresh_interval_seconds": 14}, {"construction_account_refresh_interval_seconds": 601},
                              {"construction_account_transfers_per_hour_limit": 0}, {"construction_account_maximum_single_transfer_dollars": 0}):
            assert client.put("/liquidity/settings", json=out_of_bounds).status_code == 422, out_of_bounds


class TestPollsAreAuditedOnlyWhenSomethingHappens:
    @staticmethod
    def _refresh_audit_rows() -> int:
        from sqlalchemy import select, func
        from DAL.data_models.audit.models import AuditLog
        from db import SessionLocal
        with SessionLocal() as session:
            return session.execute(select(func.count()).select_from(AuditLog).where(AuditLog.event == "liquidity_construction_accounts_refreshed")).scalar()

    def test_a_quiet_poll_leaves_no_row_and_a_manual_refresh_always_does(self, client, mercury, bought_deal):
        _link(client, bought_deal["id"])
        _refresh(client)
        rows_before = self._refresh_audit_rows()
        client.post("/liquidity/construction-accounts/refresh", json={"today": DURING_THE_REHAB, "is_a_background_poll": True})
        assert self._refresh_audit_rows() == rows_before
        mercury.balance_by_account_id["checking"] += 100
        client.post("/liquidity/construction-accounts/refresh", json={"today": DURING_THE_REHAB, "is_a_background_poll": True})
        assert self._refresh_audit_rows() == rows_before + 1
        _refresh(client)
        assert self._refresh_audit_rows() == rows_before + 2
