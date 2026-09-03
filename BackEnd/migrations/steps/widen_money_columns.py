"""Bring every `*_in_thousands` column up to NUMERIC(14,4)."""

from sqlalchemy import text, inspect as sa_inspect

from migrations.money_columns import MONEY_COLUMNS_BY_TABLE


def widen_money_columns(engine) -> None:
    """Bring every `*_in_thousands` column up to NUMERIC(14,4). Idempotent.

    Reflects fresh, for the same reason as the days migration above.
    """
    if engine.dialect.name != "postgresql":
        return
    inspector = sa_inspect(engine)
    table_names = inspector.get_table_names()
    for table_name, column_names in MONEY_COLUMNS_BY_TABLE.items():
        if table_name not in table_names:
            continue
        existing = {c["name"]: c for c in inspector.get_columns(table_name)}
        for column_name in column_names:
            col = existing.get(column_name)
            if col is None:
                continue
            # `NUMERIC(14, 4)` -- already widened, skip.
            if getattr(col.get("type"), "scale", None) == 4:
                continue
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {table_name} "
                    f"ALTER COLUMN {column_name} TYPE NUMERIC(14,4)"
                ))
