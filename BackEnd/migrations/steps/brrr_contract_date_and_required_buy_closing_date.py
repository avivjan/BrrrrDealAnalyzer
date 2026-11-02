"""Make the two BRRRR deal dates mandatory: add `contract_date` and fill every missing `buy_closing_date`.

The engine has no "no buy closing date" mode any more: every figure and the Cash Needed schedule is
dated, so both columns become NOT NULL on the two BRRRR deal tables. Owner's decision for the rows
already saved:

* a NULL `buy_closing_date` becomes the day the deal was created + 7 days (the new-deal default);
* `contract_date` becomes the day the deal was created, or the buy closing date when that is earlier
  (a deal entered after it closed), so contract <= buy closing holds on every migrated row.

The closing date is filled first, because the contract date reads it. Idempotent: the UPDATE only
touches NULLs, `add_column_if_missing` skips an existing column and SET NOT NULL on a NOT NULL column
is a no-op. Runs under the runner's advisory lock, after `add_brrr_lifecycle_columns`.
"""

from sqlalchemy import text

from migrations.add_column import add_column_if_missing

BRRR_TABLES = ("active_deals", "bought_brrrr_deals")
BUY_CLOSING_DATE_DAYS_AFTER_CREATION = 7
# `created_at` has a server default, but a row written before it existed may hold NULL: that one counts as created today.
DEAL_CREATION_DATE_SQL = "COALESCE(created_at::date, CURRENT_DATE)"


def require_brrr_contract_date_and_buy_closing_date(engine, inspector) -> None:
    for table_name in BRRR_TABLES:
        if table_name not in inspector.get_table_names():
            continue
        with engine.begin() as conn:
            conn.execute(text(
                f"UPDATE {table_name} SET buy_closing_date = ({DEAL_CREATION_DATE_SQL} + {BUY_CLOSING_DATE_DAYS_AFTER_CREATION}) "
                f"WHERE buy_closing_date IS NULL"
            ))
        add_column_if_missing(engine, inspector, table_name, "contract_date", "DATE",
                              f"LEAST({DEAL_CREATION_DATE_SQL}, buy_closing_date)")
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN buy_closing_date SET NOT NULL"))
            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN contract_date SET NOT NULL"))
