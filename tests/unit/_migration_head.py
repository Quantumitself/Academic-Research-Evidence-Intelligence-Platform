"""Single source of truth for the migration head revision.

Every test that asserts on the current head imports ``EXPECTED_HEAD``
from this module. Adding a new migration requires no test changes: the
constant reads the head from the migrations directory at import time.
"""

from __future__ import annotations

from academic_platform.infrastructure.database.migrations import (
    declared_head_revision,
)

EXPECTED_HEAD: str = declared_head_revision()