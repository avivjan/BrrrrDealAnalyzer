"""Replace the legacy `Months_until_refi` column with `days_until_refi`."""

from sqlalchemy import text, inspect as sa_inspect


def migrate_months_until_refi_to_days(engine, table_name: str) -> None:
    """Replace the legacy `Months_until_refi` column with `days_until_refi`.

    The conversion is `months * 30`, and the calc moved to a 360-day banking
    year at the same time, which makes the whole migration value-preserving:

        HML interest  old: (rate/12/100)  * amount * months
                      new: (rate/360/100) * amount * (months * 30)   -- equal
        holding costs old: (taxes/12 + ins/12 + hoa)      * months
                      new: (taxes/360 + ins/360 + hoa/30) * (months*30) -- equal

    So every existing deal re-analyzes to exactly the figures it showed before.
    The old default of 6 months lands on the new default of 180 days.

    Idempotent, and a no-op on SQLite (the test harness) which cannot
    `ALTER COLUMN` -- its tables come out of `create_all` already correct.

    Takes a *fresh* Inspector rather than sharing the caller's: an Inspector
    memoises `get_columns`, so one reused across DDL hands back a stale picture
    of the table. This is the migration that drops a column -- it reads the
    truth.
    """
    if engine.dialect.name != "postgresql":
        return
    inspector = sa_inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    if "days_until_refi" in columns:
        return
    # SQLAlchemy created this one with a quoted mixed-case identifier, so match
    # case-insensitively and then quote back whatever is actually there.
    legacy_column = next(
        (c for c in columns if c.lower() == "months_until_refi"), None
    )
    if legacy_column is None:
        return
    legacy = f'"{legacy_column}"'

    # `IF NOT EXISTS` / `IF EXISTS` so a second process that got this far
    # anyway (see `_migration_lock`) degrades to a no-op instead of crashing
    # the boot on "column already exists".
    with engine.begin() as conn:
        conn.execute(text(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS days_until_refi INTEGER"
        ))
        conn.execute(text(
            f"UPDATE {table_name} "
            f"SET days_until_refi = ROUND({legacy} * 30) "
            f"WHERE {legacy} IS NOT NULL"
        ))
        conn.execute(text(
            f"UPDATE {table_name} SET days_until_refi = 180 "
            f"WHERE days_until_refi IS NULL"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} ALTER COLUMN days_until_refi SET NOT NULL"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} ALTER COLUMN days_until_refi SET DEFAULT 180"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {legacy}"
        ))
