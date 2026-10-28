"""Let an inspection link to a My Deals deal too (tasks/todo/InspectionLinkToMyDeals.md).

`property_inspections` shipped with two deal links (the Bought Deal tables).
This adds the two My Deals links (`active_deals`, `flip_deals`), each a
nullable foreign key with ON DELETE SET NULL and an index, and widens the
check so at most one of the four links is set. Existing rows keep their link;
the new columns start NULL. Idempotent: each column is added only if missing,
and the check is replaced only while it still has the old two-column form.
Fresh databases get all of it from `create_all`, and this is a no-op.
"""

from sqlalchemy import text

from DAL.data_models.inspection.models import (
    INSPECTION_LINKED_TO_AT_MOST_ONE_DEAL_CONSTRAINT_NAME,
    INSPECTION_LINKED_TO_AT_MOST_ONE_DEAL_SQL,
)
from migrations.add_column import add_column_if_missing

INSPECTIONS_TABLE = "property_inspections"

# (column, the My Deals table it points at)
ACTIVE_DEAL_LINK_COLUMNS = (
    ("linked_active_brrrr_deal_id", "active_deals"),
    ("linked_active_flip_deal_id", "flip_deals"),
)


def add_inspection_links_to_active_deals(engine, inspector) -> None:
    if INSPECTIONS_TABLE not in inspector.get_table_names():
        return
    for column_name, deal_table in ACTIVE_DEAL_LINK_COLUMNS:
        add_column_if_missing(
            engine, inspector, INSPECTIONS_TABLE, column_name,
            f"UUID REFERENCES {deal_table}(id) ON DELETE SET NULL", None,
        )
    with engine.begin() as connection:
        for column_name, _ in ACTIVE_DEAL_LINK_COLUMNS:
            connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{INSPECTIONS_TABLE}_{column_name} ON {INSPECTIONS_TABLE} ({column_name})"))
        current_check = connection.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
            {"name": INSPECTION_LINKED_TO_AT_MOST_ONE_DEAL_CONSTRAINT_NAME},
        ).scalar()
        if current_check is None or "linked_active_brrrr_deal_id" not in current_check:
            connection.execute(text(f"ALTER TABLE {INSPECTIONS_TABLE} DROP CONSTRAINT IF EXISTS {INSPECTION_LINKED_TO_AT_MOST_ONE_DEAL_CONSTRAINT_NAME}"))
            connection.execute(text(
                f"ALTER TABLE {INSPECTIONS_TABLE} ADD CONSTRAINT {INSPECTION_LINKED_TO_AT_MOST_ONE_DEAL_CONSTRAINT_NAME} "
                f"CHECK ({INSPECTION_LINKED_TO_AT_MOST_ONE_DEAL_SQL})"
            ))
