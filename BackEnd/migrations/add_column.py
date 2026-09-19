"""`add_column_if_missing` -- the one primitive every additive column migration is built on."""

from sqlalchemy import text


def add_column_if_missing(
    engine,
    inspector,
    table_name: str,
    column_name: str,
    column_ddl: str,
    backfill_value: str | None,
) -> None:
    """Idempotently add a column to an existing table, backfilling old rows.

    `Base.metadata.create_all` only creates tables that do not exist yet, so
    every column added after a table shipped needs a call here. Keep
    `backfill_value` in step with the SQLAlchemy `default=` and the Pydantic
    default: `update_*_deal` dumps every field on each PUT, so a mismatch
    silently rewrites existing rows. `backfill_value` is a SQL expression
    (a literal, or a CASE over the row's other columns); `None` leaves the new
    column NULL, for fields where NULL means "use the formula default".
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
        if backfill_value is not None:
            conn.execute(text(
                f"UPDATE {table_name} SET {column_name} = {backfill_value} "
                f"WHERE {column_name} IS NULL"
            ))
