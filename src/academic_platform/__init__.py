"""Academic Research & Evidence Intelligence Platform.

This package hosts the desktop application, its domain logic, application
services, infrastructure adapters, and the optional external API layer.

Package boundaries are documented in ``docs/architecture.md``. No module in
this package may import from ``academic_platform.ui`` except modules inside
the ``ui`` subpackage itself.
"""

__version__ = "0.3.0"

__all__ = ["__version__"]