"""A fake Mercury for the browser tests, inside the throwaway test server only (tasks/todo/ConstructionAccountPerRehab.md,
Step H). Production never imports this file.

Off by default: until a spec turns it on, no Mercury token is set, so every existing flow keeps its "Mercury not
configured" branch and its network golden. Turned on, it is one LLC labelled E2E with a read and a transfer token, and
three accounts, and it plays the four Mercury calls the app makes: the accounts read, an account's transactions, a
transfer, and the webhook registration. A spec drives it through test-only routes under /e2e/fake-mercury/ (each
request carries `x-e2e-seed: 1`, so the network recorder leaves it out):

    POST /e2e/fake-mercury/reset        {"on": true|false, "minimum_seconds_between_reads": 0}   fresh accounts, no
                                        calls, the app's Mercury rows cleared (the pace's floor, real seconds, 0 by default)
    POST /e2e/fake-mercury/balance      {"account_id", "balance_dollars"}
    POST /e2e/fake-mercury/transaction  {"account_id", "transaction_id", "signed_amount_dollars", "internal", "counterparty_name"}
    GET  /e2e/fake-mercury/calls        how many accounts reads, transfers and registrations Mercury got
    POST /e2e/fake-mercury/signed-event {"wrong_signature": bool} -> {"path", "body", "signature"} to POST as Mercury would
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import time
from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel

from BL.liquidity.common import mercury_client, mercury_reads
from BL.liquidity.common.mercury_transfers import MercuryTransferAnswer
from BL.liquidity.common.mercury_webhooks import MercuryWebhookRegistration
from BL.liquidity.constructionAccount import construction_account_transfers, construction_accounts, mercury_instant_updates
from db import SessionLocal
from DAL.data_models.liquidity.construction_account_models import LiquidityConstructionAccountTransfer
from DAL.data_models.liquidity.mercury_models import LiquidityMercuryWebhook, LiquidityMercuryWorkspaceRead

WORKSPACE_LABEL = "E2E"
ORIGINAL_MINIMUM_SECONDS_BETWEEN_READS = mercury_reads.MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE
WEBHOOK_SIGNING_SECRET = "e2e-fake-mercury-webhook-secret"
PUBLIC_ORIGIN_FOR_WEBHOOKS = "https://e2e.example"
STARTING_ACCOUNTS = {
    "e2e-checking": ("E2E Checking", 80000),
    "e2e-construction": ("Oak Rehab Construction", 0),
    "e2e-tax": ("E2E Tax Bucket", 4000),
}


class FakeMercury:
    def __init__(self):
        self.reset(on=False)

    def reset(self, on: bool) -> None:
        self.is_on = on
        self.balance_by_account_id = {account_id: Decimal(balance) for account_id, (_name, balance) in STARTING_ACCOUNTS.items()}
        self.transactions_by_account_id: dict[str, list[dict]] = {account_id: [] for account_id in STARTING_ACCOUNTS}
        self.accounts_read_count = 0
        self.transfer_count = 0
        self.registered_receiving_url: str | None = None
        for name in ("MERCURY_API_TOKEN_E2E", "MERCURY_TRANSFER_API_TOKEN_E2E"):
            if on:
                os.environ[name] = f"fake-{name.lower()}"
            else:
                os.environ.pop(name, None)
        os.environ["MERCURY_CACHE_SECONDS"] = "60"
        mercury_client.clear_cache()

    # --- the four Mercury calls ---

    def fetch_workspace_summary(self, workspace_label: str) -> dict:
        if not self.is_on or workspace_label != WORKSPACE_LABEL:
            raise mercury_client.MercuryApiError("HTTP 404")
        self.accounts_read_count += 1
        accounts = [{"id": account_id, "name": name, "account_number_last_four": "4242", "type": "checking", "status": "active",
                     "current_balance_dollars": float(self.balance_by_account_id[account_id]),
                     "available_balance_dollars": float(self.balance_by_account_id[account_id]), "workspace": WORKSPACE_LABEL}
                    for account_id, (name, _balance) in STARTING_ACCOUNTS.items()]
        total = round(sum(account["current_balance_dollars"] for account in accounts), 2)
        return {"workspace": WORKSPACE_LABEL, "total_balance_dollars": total, "total_available_dollars": total,
                "account_count": len(accounts), "accounts": accounts}

    def fetch_account_transactions(self, workspace_label: str, account_id: str, use_cache: bool = True) -> list[dict]:
        if not self.is_on:
            raise mercury_client.MercuryApiError("HTTP 404")
        return list(self.transactions_by_account_id.get(account_id, []))

    def add_transaction(self, account_id: str, transaction_id: str, signed_amount_dollars, internal: bool, counterparty_name: str) -> None:
        amount = Decimal(str(signed_amount_dollars))
        self.transactions_by_account_id[account_id].append({
            "id": transaction_id, "signed_amount_dollars": amount, "kind": "internalTransfer" if internal else "wire", "status": "sent",
            "counterparty_name": counterparty_name or transaction_id, "transaction_date": date.today(),
            "is_internal_transfer": internal, "is_failed_or_cancelled": False, "is_pending": False})
        self.balance_by_account_id[account_id] += amount

    def send_internal_transfer(self, workspace_label, source_account_id, destination_account_id, amount_dollars, idempotency_key, note):
        self.transfer_count += 1
        transfer_id = f"e2e-transfer-{self.transfer_count}"
        self.add_transaction(source_account_id, transfer_id, -Decimal(amount_dollars), True, "Internal transfer")
        self.add_transaction(destination_account_id, transfer_id, Decimal(amount_dollars), True, "Internal transfer")
        return MercuryTransferAnswer(transfer_id, "sent")

    def register_webhook(self, workspace_label: str, receiving_url: str) -> MercuryWebhookRegistration:
        self.registered_receiving_url = receiving_url
        return MercuryWebhookRegistration("e2e-webhook-endpoint", WEBHOOK_SIGNING_SECRET)

    def delete_webhook(self, workspace_label: str, endpoint_id: str) -> None:
        self.registered_receiving_url = None

    def signed_event(self, wrong_signature: bool) -> dict:
        body = json.dumps({"type": "transaction.created", "id": f"evt-{time.time_ns()}"})
        timestamp = int(time.time())
        secret = "not-the-secret" if wrong_signature else WEBHOOK_SIGNING_SECRET
        signature = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
        path = (self.registered_receiving_url or "").removeprefix(PUBLIC_ORIGIN_FOR_WEBHOOKS)
        return {"path": path, "body": body, "signature": f"t={timestamp},v1={signature}"}


class ResetReq(BaseModel):
    on: bool = True
    # The server's pace runs on real time while the browser's clock is paused: specs read Mercury whenever they ask.
    minimum_seconds_between_reads: int = 0


class BalanceReq(BaseModel):
    account_id: str
    balance_dollars: float


class TransactionReq(BaseModel):
    account_id: str
    transaction_id: str
    signed_amount_dollars: float
    internal: bool = False
    counterparty_name: str = ""


class SignedEventReq(BaseModel):
    wrong_signature: bool = False


def install(app: FastAPI) -> FakeMercury:
    fake = FakeMercury()
    mercury_client.fetch_workspace_summary = fake.fetch_workspace_summary
    construction_accounts.fetch_account_transactions = fake.fetch_account_transactions
    construction_account_transfers.send_internal_transfer = fake.send_internal_transfer
    mercury_instant_updates.register_webhook = fake.register_webhook
    mercury_instant_updates.delete_webhook = fake.delete_webhook
    # The test server runs on http://127.0.0.1: instant updates need an https address, so they get a stand-in one.
    importlib.import_module("routers.liquidity_construction_accounts")._public_https_origin_of = lambda request: PUBLIC_ORIGIN_FOR_WEBHOOKS

    @app.post("/e2e/fake-mercury/reset", include_in_schema=False)
    def reset_fake_mercury(data: ResetReq):
        fake.reset(on=data.on)
        mercury_reads.MINIMUM_SECONDS_BETWEEN_MERCURY_READS_OF_ONE_WORKSPACE = (
            data.minimum_seconds_between_reads if data.on else ORIGINAL_MINIMUM_SECONDS_BETWEEN_READS)
        with SessionLocal() as db:
            for model in (LiquidityConstructionAccountTransfer, LiquidityMercuryWorkspaceRead, LiquidityMercuryWebhook):
                db.query(model).delete(synchronize_session=False)
            db.commit()
        importlib.import_module("routers.mercury_webhooks").reset_mercury_webhook_rate_limits()
        return {"on": fake.is_on}

    @app.post("/e2e/fake-mercury/balance", include_in_schema=False)
    def set_fake_mercury_balance(data: BalanceReq):
        fake.balance_by_account_id[data.account_id] = Decimal(str(data.balance_dollars))
        return {"ok": True}

    @app.post("/e2e/fake-mercury/transaction", include_in_schema=False)
    def add_fake_mercury_transaction(data: TransactionReq):
        fake.add_transaction(data.account_id, data.transaction_id, data.signed_amount_dollars, data.internal, data.counterparty_name)
        return {"ok": True}

    @app.get("/e2e/fake-mercury/calls", include_in_schema=False)
    def fake_mercury_calls():
        return {"accounts_reads": fake.accounts_read_count, "transfers": fake.transfer_count,
                "transactions": sum(len(rows) for rows in fake.transactions_by_account_id.values()),
                "webhook_is_registered": fake.registered_receiving_url is not None}

    @app.post("/e2e/fake-mercury/signed-event", include_in_schema=False)
    def fake_mercury_signed_event(data: SignedEventReq):
        return fake.signed_event(data.wrong_signature)

    return fake
