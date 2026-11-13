"""What the app remembers about its own reads of Mercury, per workspace (one LLC = one workspace = one token label)
(tasks/todo/ConstructionAccountPerRehab.md, "Requirement 4 -- live Mercury").

Kept in the database, not in memory, so every server process shares one pace: the general balance read, the
construction account refresh and the webhook never make a call another just made.
"""

from sqlalchemy import Column, DateTime, Integer, JSON, Numeric, String, func

from db import Base


class LiquidityMercuryWorkspaceRead(Base):
    """The last accounts snapshot of one workspace, and when Mercury may be read for it again."""
    __tablename__ = "liquidity_mercury_workspace_reads"

    mercury_workspace_label = Column(String(80), primary_key=True)
    # The workspace's summarised accounts as `mercury_client` returns them: names, balances, the last four digits of a
    # number. Never a token. NULL = never read, or discarded by a webhook so the next read is fresh.
    accounts_snapshot = Column(JSON, nullable=True)
    counted_as_cash_balance_dollars = Column(Numeric(16, 2), nullable=True)
    last_mercury_read_at = Column(DateTime(timezone=True), nullable=True)
    # Set while Mercury asked us to slow down (429): no read of this workspace before it.
    next_mercury_read_not_before = Column(DateTime(timezone=True), nullable=True)
    consecutive_slow_down_answers = Column(Integer, nullable=False, default=0, server_default="0")
    # A webhook arrived while a read was not allowed yet: the next allowed read is a fresh one, whoever asks.
    fresh_read_requested_at = Column(DateTime(timezone=True), nullable=True)
    cash_balance_last_changed_at = Column(DateTime(timezone=True), nullable=True)
    construction_accounts_last_changed_at = Column(DateTime(timezone=True), nullable=True)
    # The rows an instant update (a webhook) changed, so an open page can show "Timeline updated from the bank": a list
    # of DealCashRowChangesRes as JSON, and when. Rows and amounts of this app's own timeline only, never Mercury's text.
    last_instant_update_at = Column(DateTime(timezone=True), nullable=True)
    bank_reported_row_changes_of_last_instant_update = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiquidityMercuryWebhook(Base):
    """A workspace's "instant updates": the webhook endpoint registered at Mercury, and how it is doing.

    An event only ever means "look now": its contents are never trusted or stored. So the signing secret guards
    nothing but the trigger of a re-read; it is still never returned by any route and never logged."""
    __tablename__ = "liquidity_mercury_webhooks"

    mercury_workspace_label = Column(String(80), primary_key=True)
    mercury_webhook_endpoint_id = Column(String(120), nullable=True)
    signing_secret = Column(String(400), nullable=True)
    # The random last segment of the address Mercury calls: /webhooks/mercury/{receiving_path_token}.
    receiving_path_token = Column(String(80), nullable=False, unique=True, index=True)
    turned_on_at = Column(DateTime(timezone=True), nullable=True)
    last_valid_event_received_at = Column(DateTime(timezone=True), nullable=True)
    # In our own words, never Mercury's text: a refused registration, or an event that failed its checks.
    last_webhook_error_message = Column(String(300), nullable=True)
    last_webhook_error_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
