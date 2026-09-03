"""Migrate `bought_stage` from INTEGER -> TEXT.

Legacy numeric stage IDs are mapped to the stable slug IDs used by the default
pipeline template. Idempotent, Postgres-only (SQLite tables come out of
`create_all` already correct).
"""

from sqlalchemy import text


def migrate_bought_stage_to_string(
    engine,
    inspector,
    table_name: str,
    slug_by_int: dict[int, str],
) -> None:
    if table_name not in inspector.get_table_names():
        return
    cols = {c["name"]: c for c in inspector.get_columns(table_name)}
    col = cols.get("bought_stage")
    if col is None:
        return

    col_type = str(col.get("type") or "").upper()
    # Already text-like? Nothing to do.
    if any(token in col_type for token in ("CHAR", "TEXT", "STRING", "VARCHAR")):
        return

    default_slug = slug_by_int.get(1, "purchase")
    with engine.begin() as conn:
        # 1) Add a temp text column with a safe default.
        conn.execute(text(
            f"ALTER TABLE {table_name} ADD COLUMN bought_stage_new TEXT"
        ))
        # 2) Translate each legacy int to its canonical slug; anything unknown
        #    clamps to the first default stage so the board never breaks.
        for legacy_int, slug in slug_by_int.items():
            conn.execute(
                text(
                    f"UPDATE {table_name} SET bought_stage_new = :slug "
                    f"WHERE bought_stage = :legacy_int"
                ),
                {"slug": slug, "legacy_int": legacy_int},
            )
        conn.execute(
            text(
                f"UPDATE {table_name} SET bought_stage_new = :default_slug "
                f"WHERE bought_stage_new IS NULL"
            ),
            {"default_slug": default_slug},
        )
        # 3) Drop the old int column and rename the new one into place.
        conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN bought_stage"))
        conn.execute(text(
            f"ALTER TABLE {table_name} RENAME COLUMN bought_stage_new TO bought_stage"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} ALTER COLUMN bought_stage SET NOT NULL"
        ))
        conn.execute(text(
            f"ALTER TABLE {table_name} ALTER COLUMN bought_stage SET DEFAULT 'purchase'"
        ))
