"""Settings page.

The Settings page is organized into six tabs:

- General
- Appearance
- Search
- AI Providers
- Privacy
- Advanced

Each tab is a self-contained widget that reads its initial state from the
settings service and writes changes back through the service. Changes are
persisted atomically; tabs never mutate the configuration file directly.

The page exposes a ``reset_to_defaults`` action that restores the schema
defaults. The action is guarded by a confirmation dialog.

Design decisions
----------------
- Each tab owns its own widgets and observes only the sections of the
  settings schema that are relevant to it. Cross-tab coordination goes
  through the settings service, not through direct tab-to-tab references.
- Changes are applied on control change (no global Apply button) because
  every control has a well-defined, immediately persistable value.
- Multi-step edits that could leave the configuration inconsistent (for
  example, choosing a default model before choosing a default provider)
  are validated by the settings schema before being saved. The tab
  surfaces validation errors through the notification service.
"""

from academic_platform.ui.pages.settings.advanced_tab import AdvancedSettingsTab
from academic_platform.ui.pages.settings.ai_providers_tab import (
    AIProvidersSettingsTab,
)
from academic_platform.ui.pages.settings.appearance_tab import (
    AppearanceSettingsTab,
)
from academic_platform.ui.pages.settings.general_tab import GeneralSettingsTab
from academic_platform.ui.pages.settings.privacy_tab import PrivacySettingsTab
from academic_platform.ui.pages.settings.search_tab import SearchSettingsTab
from academic_platform.ui.pages.settings.settings_page import SettingsPage

__all__ = [
    "AIProvidersSettingsTab",
    "AdvancedSettingsTab",
    "AppearanceSettingsTab",
    "GeneralSettingsTab",
    "PrivacySettingsTab",
    "SearchSettingsTab",
    "SettingsPage",
]