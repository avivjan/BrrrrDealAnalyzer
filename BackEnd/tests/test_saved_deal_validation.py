"""Saving a BRRRR deal is gated by the same range and sign rules as the calculator.

A saved deal is re-analyzed on every read with no validation of its own, so anything
`/analyze/brrr` would reject must be kept out of the row: otherwise the board shows numbers
the calculator never would (a lowest ARV above the ARV plans Cash Needed on the higher
appraisal) or, for a loan term of 0, fails to load at all. Unlike the calculator the board
accepts the blank new-deal zeros (ARV, price, rent) because that is how a deal starts.
"""

from __future__ import annotations

import pytest

BLANK_NEW_DEAL_ZEROS = {"arv_in_thousands": 0, "purchasePrice": 0, "rent": 0}

REJECTED_SAVED_INPUTS = [
    ("loanTermYears", 0, "Loan term must be at least 1 year"),
    ("lowestArv", 999, "Lowest ARV cannot exceed ARV"),
    ("down_payment", 150, "Down payment percentage must be between 0% and 100%"),
    ("ltv_as_precent", 120, "LTV must be between 0% and 100%"),
    ("interestRate", -1, "Interest rate must be between 0% and 100%"),
    ("appraisalFee", -1, "Appraisal fee cannot be negative"),
    ("vacancyPercent", 101, "Vacancy percentage must be between 0% and 100%"),
    ("daysUntilRefi", 0, "Days until refi must be a positive number"),
    ("constructionLoanBudget", -1, "Construction loan budget cannot be negative"),
]


def _post_active(client, payload):
    return client.post("/active-deals", json=payload)


class TestActiveDealSaveValidation:
    def test_a_blank_new_deal_saves_and_the_board_loads_it(self, client, brrrr_payload):
        response = _post_active(client, {**brrrr_payload, **BLANK_NEW_DEAL_ZEROS, "lowestArv": None})
        assert response.status_code == 200, response.text
        board = client.get("/active-deals")
        assert board.status_code == 200 and [deal["id"] for deal in board.json()] == [response.json()["id"]]

    @pytest.mark.parametrize("field, value, message", REJECTED_SAVED_INPUTS)
    def test_post_rejects_what_the_calculator_rejects(self, client, brrrr_payload, field, value, message):
        response = _post_active(client, {**brrrr_payload, field: value})
        assert response.status_code == 400, response.text
        assert message in response.json()["detail"]
        assert client.get("/active-deals").json() == []

    def test_put_rejects_and_keeps_the_saved_row_and_the_board(self, client, brrrr_payload):
        deal = _post_active(client, brrrr_payload).json()
        response = client.put(f"/active-deals/{deal['id']}", json={**brrrr_payload, "loanTermYears": 0})
        assert response.status_code == 400
        assert "Loan term must be at least 1 year" in response.json()["detail"]
        board = client.get("/active-deals")
        assert board.status_code == 200
        assert [saved["loanTermYears"] for saved in board.json()] == [brrrr_payload["loanTermYears"]]
        assert board.json()[0]["cash_flow"] == pytest.approx(deal["cash_flow"])

    def test_the_lowest_arv_is_only_checked_against_a_known_arv(self, client, brrrr_payload):
        """On a blank deal the ARV is still 0; a lowest ARV typed first must not be refused."""
        response = _post_active(client, {**brrrr_payload, **BLANK_NEW_DEAL_ZEROS, "lowestArv": 250})
        assert response.status_code == 200, response.text

    def test_the_messages_are_the_calculators(self, client, brrrr_payload):
        bad = {**brrrr_payload, "loanTermYears": 0, "hmlPoints": 101}
        saved_detail = _post_active(client, bad).json()["detail"]
        calculator_detail = client.post("/analyze/brrr", json=bad).json()["detail"]
        for message in ("HML points must be between 0% and 100%.", "Loan term must be at least 1 year."):
            assert message in saved_detail and message in calculator_detail


class TestBoughtDealSaveValidation:
    def test_post_rejects(self, client, brrrr_payload):
        response = client.post("/bought-deals", json={**brrrr_payload, "hmlPoints": 101})
        assert response.status_code == 400
        assert "HML points must be between 0% and 100%" in response.json()["detail"]
        assert client.get("/bought-deals").json() == []

    def test_put_rejects_and_the_board_keeps_loading(self, client, brrrr_payload):
        active = _post_active(client, brrrr_payload).json()
        bought = client.post(f"/bought-deals/from-active/{active['id']}", params={"deal_type": "BRRRR"}).json()
        response = client.put(f"/bought-deals/{bought['id']}", json={**brrrr_payload, "boughtStage": bought["boughtStage"], "lowestArv": 999})
        assert response.status_code == 400
        assert "Lowest ARV cannot exceed ARV" in response.json()["detail"]
        board = client.get("/bought-deals")
        assert board.status_code == 200 and [deal["id"] for deal in board.json()] == [bought["id"]]
        assert board.json()[0]["lowestArv"] == bought["lowestArv"]
