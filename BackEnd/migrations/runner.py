"""Hand-rolled schema migrations, run once at import time by `bootstrap`.

`Base.metadata.create_all` only creates tables that do not exist yet, so every
column added after a table shipped is reconciled here. All migrations are
Postgres-only and idempotent; SQLite (the test harness) gets correct tables
straight from `create_all`.

The module-global `engine` that these functions used to close over is now passed
in explicitly -- that is the only change from the code that lived in `main.py`.
"""

from contextlib import contextmanager

from sqlalchemy import text, inspect as sa_inspect

from models import (
    DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT,
    DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT,
)
from migrations.steps.bought_stage_to_string import migrate_bought_stage_to_string
from migrations.steps.months_to_days import migrate_months_until_refi_to_days
from migrations.steps.widen_money_columns import widen_money_columns


def add_column_if_missing(
    engine,
    inspector,
    table_name: str,
    column_name: str,
    column_ddl: str,
    backfill_value: str,
) -> None:
    """Idempotently add a column to an existing table, backfilling old rows.

    `Base.metadata.create_all` only creates tables that do not exist yet, so
    every column added after a table shipped needs a call here. Keep
    `backfill_value` in step with the SQLAlchemy `default=` and the Pydantic
    default: `update_*_deal` dumps every field on each PUT, so a mismatch
    silently rewrites existing rows.
    """
    if table_name not in inspector.get_table_names():
        return
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    if column_name in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}"
        ))
        conn.execute(text(
            f"UPDATE {table_name} SET {column_name} = {backfill_value} "
            f"WHERE {column_name} IS NULL"
        ))


# Arbitrary but fixed key identifying "this app's schema migration".
MIGRATION_LOCK_KEY = 8_147_233_901


@contextmanager
def migration_lock(engine):
    """Serialise `run_migrations` across processes.

    Migrations run at *import* time, so every uvicorn worker runs them at once
    on boot. Two workers both seeing `days_until_refi` missing would both try
    to add it; one wins, the other dies on "column already exists" and takes
    the deploy with it. A Postgres advisory lock makes the second worker wait
    and then find the work already done.

    Held for the duration of the `with` block by its own transaction, and
    released when that commits. A no-op off Postgres -- SQLite in the tests is
    single-process by construction.
    """
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.begin() as lock_conn:
        lock_conn.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": MIGRATION_LOCK_KEY},
        )
        yield


def run_migrations(engine):
    with migration_lock(engine):
        _run_migrations_locked(engine)


def _run_migrations_locked(engine):
    inspector = sa_inspect(engine)
    table_names = inspector.get_table_names()

    # BRRRR-specific columns added after initial schema. New rows pick up the
    # default from the model; existing rows are backfilled here so all reads
    # are safe (no NULLs, no surprise KeyErrors in the response models).
    for brrr_table in ("active_deals", "bought_brrrr_deals"):
        add_column_if_missing(
            engine,
            inspector,
            brrr_table,
            "refi_points",
            "NUMERIC(5,2) DEFAULT 1.5",
            "1.5",
        )
        add_column_if_missing(
            engine,
            inspector,
            brrr_table,
            "cash_reserve_in_thousands",
            "NUMERIC(12,2) DEFAULT 0",
            "0",
        )

    if "liquidity_transactions" in table_names:
        columns = [col["name"] for col in inspector.get_columns("liquidity_transactions")]

        # Rename legacy columns to their current model names
        renames = {"date": "effective_date", "amount": "amount_k"}
        for old_name, new_name in renames.items():
            if old_name in columns and new_name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE liquidity_transactions RENAME COLUMN {old_name} TO {new_name}"
                    ))
                columns = [new_name if c == old_name else c for c in columns]
            elif old_name in columns and new_name in columns:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"UPDATE liquidity_transactions SET {new_name} = {old_name} WHERE {new_name} IS NULL"
                    ))
                    conn.execute(text(
                        f"ALTER TABLE liquidity_transactions DROP COLUMN {old_name}"
                    ))
                columns = [c for c in columns if c != old_name]

        # Drop any leftover columns not in the current model
        expected = {"id", "effective_date", "description", "amount_k", "created_at", "updated_at"}
        for col in columns:
            if col not in expected:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE liquidity_transactions DROP COLUMN {col}"
                    ))

    # `liquidity_recurring_transactions` is created by `Base.metadata.create_all`
    # on first boot; nothing else to migrate yet. If we later evolve the schema
    # (e.g. add `notes` or `category` columns) the per-column backfill goes
    # here, mirroring the pattern used for `liquidity_transactions` above.

    if "liquidity_settings" in table_names:
        columns = [col["name"] for col in inspector.get_columns("liquidity_settings")]
        if "opening_balance_date" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE liquidity_settings ADD COLUMN opening_balance_date DATE DEFAULT CURRENT_DATE NOT NULL"
                ))
        if "reserve_k" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE liquidity_settings ADD COLUMN reserve_k NUMERIC(14,4) DEFAULT 5 NOT NULL"
                ))
        if "opening_balance_k" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE liquidity_settings ADD COLUMN opening_balance_k NUMERIC(14,4) DEFAULT 0 NOT NULL"
                ))

    # Migrate `bought_stage` from INTEGER -> TEXT, mapping legacy numeric IDs
    # to the stable slug IDs used by the default pipeline template. Idempotent.
    migrate_bought_stage_to_string(engine, inspector, "bought_brrrr_deals", DEFAULT_BRRRR_STAGE_SLUGS_BY_LEGACY_INT)
    migrate_bought_stage_to_string(engine, inspector, "bought_flip_deals", DEFAULT_FLIP_STAGE_SLUGS_BY_LEGACY_INT)

    # Replace `Months_until_refi` with whole `days_until_refi`. Idempotent.
    for brrr_table in ("active_deals", "bought_brrrr_deals"):
        migrate_months_until_refi_to_days(engine, brrr_table)

    # Widen the money columns so a thousands value can hold an exact dollar.
    widen_money_columns(engine)
