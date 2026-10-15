"""Development launcher.

Adds ``src`` to ``sys.path`` so the application can be started from the
repository root without installing the package, then dispatches to
``academic_platform.main``. All arguments are forwarded unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from academic_platform.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())