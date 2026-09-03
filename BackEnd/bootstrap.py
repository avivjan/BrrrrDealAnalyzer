"""Import-time application bootstrap: schema migrations + seed data.

`main` calls `run(engine, SessionLocal)` once at import, at the same point the
old inline block in `main.py` ran (after `create_all`, before the CORS
middleware). Kept as its own module so `main` stays a thin wiring file.
"""

import logging

import models  # noqa: F401  -- registers every ORM table on Base.metadata
import migrations
from crud_pipeline_template import ensure_defaults as ensure_pipeline_defaults
import crud_reps

logger = logging.getLogger(__name__)


def run(engine, SessionLocal) -> None:
    migrations.bootstrap_schema(engine)

    # Seed pipeline template rows (BRRRR + FLIP) on first boot. Safe to call often.
    with SessionLocal() as _seed_db:
        ensure_pipeline_defaults(_seed_db)
        # Seed REPS activity categories so the dropdown is never empty on first run.
        try:
            crud_reps.ensure_activity_category_defaults(_seed_db)
        except Exception as _exc:  # pragma: no cover
            logger.warning("Failed to seed REPS activity categories: %s", _exc)
