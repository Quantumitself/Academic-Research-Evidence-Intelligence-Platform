"""Application services.

The application layer coordinates domain logic and infrastructure
adapters. It is the layer the presentation layer talks to. It never
imports Qt, HTTP clients, or the ORM's session type directly; it depends
on the abstractions the infrastructure layer exposes.
"""

from academic_platform.application.settings_persistence import (
    SettingsPersistenceBridge,
    SettingsPersistenceError,
)

__all__ = [
    "SettingsPersistenceBridge",
    "SettingsPersistenceError",
]