"""Bring every percent-rate column up to NUMERIC(6,3)."""

from sqlalchemy import text, inspect as sa_inspect

from migrations.rate_columns import RATE_COLUMNS_BY_TABLE, RATE_COLUMN_SCALE


def widen_rate_columns(engine) -> None:
    """Bring every percent-rate column up to NUMERIC(6,3). Idempotent.

    Lossless in Postgres: 7.13 stays 7.13, and a 7.125 typed afterwards is kept. Reflects
    fresh, for the same reason as the money-column step. SQLAlchemy created `HML_points` and
    `HML_interest_rate` as quoted mixed-case identifiers, so every column name is quoted.
    """
    if engine.dialect.name != "postgresql":
        return
    inspector = sa_inspect(engine)
    table_names = inspector.get_table_names()
    for table_name, column_names in RATE_COLUMNS_BY_TABLE.items():
        if table_name not in table_names:
            continue
        existing = {c["name"]: c for c in inspector.get_columns(table_name)}
        for column_name in column_names:
            col = existing.get(column_name)
            if col is None:
                continue
            if getattr(col.get("type"), "scale", None) == RATE_COLUMN_SCALE:
                continue
            with engine.begin() as conn:
                conn.execute(text(
                    f'ALTER TABLE {table_name} '
                    f'ALTER COLUMN "{column_name}" TYPE NUMERIC(6,{RATE_COLUMN_SCALE})'
                ))
