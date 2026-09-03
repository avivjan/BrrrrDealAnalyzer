"""Schema bootstrap: create missing tables, then reconcile existing ones.

Pure module -- importing it has no side effects. `bootstrap_schema(engine)` is
called once, at import time, by `bootstrap.run`.
"""

from db import Base
from migrations.runner import run_migrations


def bootstrap_schema(engine) -> None:
    """Create any missing tables, then run the idempotent column migrations."""
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
