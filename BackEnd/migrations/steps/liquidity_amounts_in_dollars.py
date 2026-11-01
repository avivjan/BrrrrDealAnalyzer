"""Move the liquidity amounts from thousands of dollars ($k) to exact dollars.

Each `_k` column is renamed to its `_dollars` name, multiplied by 1000 and retyped to
NUMERIC(16,2), in one transaction per table. Idempotent: a table whose `_k` column is gone
(already migrated, or created fresh by `create_all` with the `_dollars` names) is skipped.
The SQL names only the constant tables and columns below, never user data.
"""

from sqlalchemy import text

DOLLARS_PER_THOUSAND = 1000

# (table, old $k column, new dollars column)
LIQUIDITY_AMOUNT_COLUMNS_IN_THOUSANDS = (
    ("liquidity_transactions", "amount_k", "amount_dollars"),
    ("liquidity_recurring_transactions", "amount_k", "amount_dollars"),
    ("liquidity_settings", "opening_balance_k", "opening_balance_dollars"),
    ("liquidity_settings", "reserve_k", "reserve_dollars"),
)


def convert_liquidity_amounts_to_dollars(engine, inspector) -> None:
    table_names = inspector.get_table_names()
    for table_name, column_in_thousands, column_in_dollars in LIQUIDITY_AMOUNT_COLUMNS_IN_THOUSANDS:
        if table_name not in table_names:
            continue
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        if column_in_thousands not in column_names or column_in_dollars in column_names:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {column_in_thousands} TO {column_in_dollars}"))
            conn.execute(text(
                f"ALTER TABLE {table_name} ALTER COLUMN {column_in_dollars} TYPE NUMERIC(16,2) "
                f"USING ROUND({column_in_dollars} * {DOLLARS_PER_THOUSAND}, 2)"
            ))
            if column_in_dollars == "reserve_dollars":
                conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN reserve_dollars SET DEFAULT 5000"))
