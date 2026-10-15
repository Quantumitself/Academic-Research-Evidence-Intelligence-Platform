"""Appearance settings tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

from academic_platform.app.settings import SettingsService, ThemeMode
from academic_platform.ui.notifications import NotificationService
from academic_platform.ui.pages.settings._base_tab import SettingsTab


_THEME_OPTIONS: tuple[tuple[ThemeMode, str], ...] = (
    (ThemeMode.SYSTEM, "Follow system"),
    (ThemeMode.LIGHT, "Light"),
    (ThemeMode.DARK, "Dark"),
)

_DENSITY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("compact", "Compact"),
    ("comfortable", "Comfortable"),
    ("spacious", "Spacious"),
)


class AppearanceSettingsTab(SettingsTab):
    """Visual preferences."""

    def __init__(
        self,
        settings_service: SettingsService,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(settings_service, notification_service, parent)
        self.setObjectName("settingsTabAppearance")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._theme_combo = QComboBox(self)
        self._theme_combo.setObjectName("settingsAppearanceTheme")
        for theme, label in _THEME_OPTIONS:
            self._theme_combo.addItem(label, theme.value)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("Theme", self._theme_combo)

        self._font_scale = QDoubleSpinBox(self)
        self._font_scale.setObjectName("settingsAppearanceFontScale")
        self._font_scale.setRange(0.75, 2.0)
        self._font_scale.setSingleStep(0.05)
        self._font_scale.setDecimals(2)
        self._font_scale.setSuffix(" ×")
        self._font_scale.valueChanged.connect(self._on_font_scale_changed)
        form.addRow("Font scale", self._font_scale)

        self._density_combo = QComboBox(self)
        self._density_combo.setObjectName("settingsAppearanceDensity")
        for identifier, label in _DENSITY_OPTIONS:
            self._density_combo.addItem(label, identifier)
        self._density_combo.currentIndexChanged.connect(self._on_density_changed)
        form.addRow("Density", self._density_combo)

        self._show_labels = QCheckBox("Show navigation labels", self)
        self._show_labels.setObjectName("settingsAppearanceShowLabels")
        self._show_labels.toggled.connect(self._on_show_labels_changed)
        form.addRow("", self._show_labels)

        layout.addLayout(form)
        layout.addStretch(1)

        self._populate()

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._loading = True
        try:
            appearance = self.settings.appearance
            self._select_combo_value(self._theme_combo, appearance.theme.value)
            self._font_scale.setValue(appearance.font_scale)
            self._select_combo_value(self._density_combo, appearance.density)
            self._show_labels.setChecked(appearance.show_sidebar_labels)
        finally:
            self._loading = False

    def reload(self) -> None:
        self._populate()

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_theme_changed(self, _index: int) -> None:
        value = self._theme_combo.currentData()
        if not isinstance(value, str):
            return
        if not self._update_section("appearance", theme=value):
            self._populate()

    def _on_font_scale_changed(self, value: float) -> None:
        if not self._update_section("appearance", font_scale=float(value)):
            self._populate()

    def _on_density_changed(self, _index: int) -> None:
        value = self._density_combo.currentData()
        if not isinstance(value, str):
            return
        if not self._update_section("appearance", density=value):
            self._populate()

    def _on_show_labels_changed(self, checked: bool) -> None:
        if not self._update_section("appearance", show_sidebar_labels=checked):
            self._populate()