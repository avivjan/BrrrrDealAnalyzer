"""Backwards-compatible shim.

The ORM models moved to ``DAL/data_models/`` (grouped by endpoint division).
This module re-exports them so ``from models import X`` keeps working during the
re-architecture. Removed once every importer points at ``DAL.data_models``.
"""

from DAL.data_models import *  # noqa: F401,F403
from DAL.data_models import __all__  # noqa: F401
