"""Package execution entry point.

Running ``python -m academic_platform`` dispatches to
``academic_platform.main``. This module exists so that the package can be
executed directly without requiring the console script to be installed.
"""

from __future__ import annotations

import sys

from academic_platform.main import main

if __name__ == "__main__":
    sys.exit(main())