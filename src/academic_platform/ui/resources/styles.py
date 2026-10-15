"""Application stylesheet builder.

The stylesheet is composed from three inputs:

- ``theme``: selects the color palette.
- ``font_scale``: multiplies base font sizes.
- ``density``: selects spacing and padding values.

The builder returns a single string suitable for ``setStyleSheet``. Object
names referenced here are set explicitly on the corresponding widgets; the
builder never depends on widget hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass

from academic_platform.app.settings.schema import ThemeMode

_BASE_FONT_PX = 13
_BASE_HEADING_PX = 22
_BASE_SUBHEADING_PX = 14
_BASE_BRAND_PX = 15


@dataclass(frozen=True, slots=True)
class _Palette:
    background: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    text_subtle: str
    accent: str
    accent_soft: str
    accent_border: str
    sidebar_bg: str
    sidebar_border: str
    sidebar_text: str
    sidebar_text_muted: str
    sidebar_item_selected: str
    sidebar_item_hover: str
    heading: str
    disabled_bg: str
    disabled_border: str
    disabled_text: str
    danger: str
    danger_soft: str
    danger_border: str
    warning: str
    warning_soft: str
    warning_border: str
    success: str
    success_soft: str
    success_border: str


_LIGHT = _Palette(
    background="#f6f7f9",
    surface="#ffffff",
    surface_alt="#fbfcfe",
    border="#e4e7eb",
    text="#1f2933",
    text_muted="#52606d",
    text_subtle="#7b8794",
    accent="#1c4f9c",
    accent_soft="#e6f0ff",
    accent_border="#b8d4ff",
    sidebar_bg="#1f2933",
    sidebar_border="#111827",
    sidebar_text="#cbd2d9",
    sidebar_text_muted="#9aa5b1",
    sidebar_item_selected="#3e4c59",
    sidebar_item_hover="#323f4b",
    heading="#102a43",
    disabled_bg="#f0f4f8",
    disabled_border="#e4e7eb",
    disabled_text="#9aa5b1",
    danger="#a4161a",
    danger_soft="#fdecea",
    danger_border="#f5c6c6",
    warning="#b45309",
    warning_soft="#fef3c7",
    warning_border="#fde68a",
    success="#166534",
    success_soft="#dcfce7",
    success_border="#bbf7d0",
)

_DARK = _Palette(
    background="#0f1720",
    surface="#17222e",
    surface_alt="#1b2836",
    border="#243445",
    text="#e6edf3",
    text_muted="#a5b4c3",
    text_subtle="#7d8fa1",
    accent="#8ab4ff",
    accent_soft="#1a2c46",
    accent_border="#2c476b",
    sidebar_bg="#0b1219",
    sidebar_border="#05090d",
    sidebar_text="#a5b4c3",
    sidebar_text_muted="#7d8fa1",
    sidebar_item_selected="#1f3145",
    sidebar_item_hover="#16222f",
    heading="#e6edf3",
    disabled_bg="#141e29",
    disabled_border="#1f2c3a",
    disabled_text="#5f7284",
    danger="#f87171",
    danger_soft="#2c1a1c",
    danger_border="#5b2a2e",
    warning="#fbbf24",
    warning_soft="#2c2410",
    warning_border="#5b4516",
    success="#4ade80",
    success_soft="#132a1a",
    success_border="#1f4a2c",
)


@dataclass(frozen=True, slots=True)
class _Spacing:
    list_item_padding_v: int
    list_item_padding_h: int
    card_padding_top: int
    card_padding_side: int
    card_padding_bottom: int
    empty_padding_v: int
    empty_padding_h: int
    header_padding_v: int
    header_padding_h: int
    control_padding_v: int
    control_padding_h: int
    control_radius: int
    card_radius: int
    chip_padding_v: int
    chip_padding_h: int
    chip_radius: int


_COMFORTABLE = _Spacing(
    list_item_padding_v=8,
    list_item_padding_h=10,
    card_padding_top=16,
    card_padding_side=20,
    card_padding_bottom=20,
    empty_padding_v=32,
    empty_padding_h=24,
    header_padding_v=20,
    header_padding_h=24,
    control_padding_v=6,
    control_padding_h=10,
    control_radius=6,
    card_radius=10,
    chip_padding_v=3,
    chip_padding_h=8,
    chip_radius=10,
)

_COMPACT = _Spacing(
    list_item_padding_v=6,
    list_item_padding_h=8,
    card_padding_top=12,
    card_padding_side=16,
    card_padding_bottom=14,
    empty_padding_v=22,
    empty_padding_h=18,
    header_padding_v=14,
    header_padding_h=18,
    control_padding_v=4,
    control_padding_h=8,
    control_radius=4,
    card_radius=8,
    chip_padding_v=2,
    chip_padding_h=6,
    chip_radius=8,
)

_SPACIOUS = _Spacing(
    list_item_padding_v=11,
    list_item_padding_h=14,
    card_padding_top=22,
    card_padding_side=26,
    card_padding_bottom=26,
    empty_padding_v=44,
    empty_padding_h=32,
    header_padding_v=26,
    header_padding_h=30,
    control_padding_v=8,
    control_padding_h=12,
    control_radius=8,
    card_radius=12,
    chip_padding_v=4,
    chip_padding_h=10,
    chip_radius=12,
)


def _resolve_palette(theme: ThemeMode) -> _Palette:
    if theme is ThemeMode.DARK:
        return _DARK
    return _LIGHT


def _resolve_spacing(density: str) -> _Spacing:
    if density == "compact":
        return _COMPACT
    if density == "spacious":
        return _SPACIOUS
    return _COMFORTABLE


def _scaled(base: int, scale: float) -> int:
    return max(1, int(round(base * scale)))


def build_application_stylesheet(
    theme: ThemeMode,
    font_scale: float,
    density: str,
) -> str:
    """Compose a complete application stylesheet.

    Parameters
    ----------
    theme:
        Selected theme mode. ``SYSTEM`` falls back to the light palette at
        this layer; callers that resolve the system theme pass ``LIGHT`` or
        ``DARK`` explicitly.
    font_scale:
        Multiplier applied to base font sizes. Values outside the range
        accepted by the settings schema are still accepted here and clamped
        by ``_scaled``.
    density:
        One of ``compact``, ``comfortable``, ``spacious``. Unknown values
        fall back to ``comfortable``.
    """
    palette = _resolve_palette(theme)
    spacing = _resolve_spacing(density)

    base_font = _scaled(_BASE_FONT_PX, font_scale)
    heading_font = _scaled(_BASE_HEADING_PX, font_scale)
    subheading_font = _scaled(_BASE_SUBHEADING_PX, font_scale)
    brand_font = _scaled(_BASE_BRAND_PX, font_scale)
    footer_font = max(10, base_font - 2)
    small_font = max(10, base_font - 1)
    tiny_font = max(9, base_font - 3)

    return f"""
QMainWindow, QWidget {{
    background-color: {palette.background};
    color: {palette.text};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: {base_font}px;
}}

#pageHeader {{
    background-color: {palette.background};
    border-bottom: 1px solid {palette.border};
}}

#pageBodyStack {{
    background-color: {palette.background};
    border: none;
}}

#navigationBar {{
    background-color: {palette.sidebar_bg};
    border-right: 1px solid {palette.sidebar_border};
}}

#navigationBrand {{
    color: #f9fafb;
    font-size: {brand_font}px;
    font-weight: 600;
    padding-bottom: 8px;
}}

#navigationList {{
    background-color: transparent;
    border: none;
    color: {palette.sidebar_text};
    outline: 0;
}}

#navigationList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
    margin: 1px 0;
}}

#navigationList::item:selected {{
    background-color: {palette.sidebar_item_selected};
    color: #ffffff;
}}

#navigationList::item:hover {{
    background-color: {palette.sidebar_item_hover};
    color: #ffffff;
}}

#navigationFooter {{
    color: {palette.sidebar_text_muted};
    font-size: {footer_font}px;
    padding-top: 8px;
}}

#pageHeading {{
    font-size: {heading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#pageSubtitle {{
    font-size: {base_font}px;
    color: {palette.text_muted};
}}

#sectionCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#sectionCardTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#emptyState {{
    background-color: {palette.surface_alt};
    border: 1px dashed {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#emptyStateGlyph {{
    font-size: {heading_font}px;
    color: {palette.text_subtle};
}}

#emptyStateTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#emptyStateMessage {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#emptyStateAction {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#emptyStateAction:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#errorState {{
    background-color: {palette.danger_soft};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.card_radius}px;
}}

#errorStateGlyph {{
    font-size: {subheading_font}px;
    color: {palette.danger};
}}

#errorStateMessage {{
    font-size: {small_font}px;
    color: {palette.danger};
}}

#errorStateRetry {{
    background-color: {palette.surface};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.danger};
}}

#errorStateRetry:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#loadingIndicator {{
    background-color: transparent;
}}

#loadingIndicatorMessage {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#loadingIndicatorBar {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    height: 8px;
}}

#loadingIndicatorBar::chunk {{
    background-color: {palette.accent};
    border-radius: {spacing.control_radius}px;
}}

#progressBar {{
    background-color: transparent;
}}

#progressBarLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#progressBarTrack {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    height: 10px;
}}

#progressBarTrack::chunk {{
    background-color: {palette.accent};
    border-radius: {spacing.control_radius}px;
}}

#progressBarCancel {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#searchBar {{
    background-color: transparent;
}}

#searchBarInput {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#searchBarInput:focus {{
    border-color: {palette.accent};
}}

#searchBarSubmit {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#searchBarClear {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#searchBarScope {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#filterPanel {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#filterPanelTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#filterPanelToggle {{
    border: none;
    background-color: transparent;
    color: {palette.text_muted};
}}

#filterPanelReset {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#filterPanelFieldLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#filterPanelRangeTo {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
}}

#statBadge {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.chip_radius}px;
}}

#statBadge[tone="positive"] {{
    background-color: {palette.success_soft};
    border-color: {palette.success_border};
}}

#statBadge[tone="warning"] {{
    background-color: {palette.warning_soft};
    border-color: {palette.warning_border};
}}

#statBadge[tone="danger"] {{
    background-color: {palette.danger_soft};
    border-color: {palette.danger_border};
}}

#statBadgeLabel {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
    text-transform: uppercase;
    letter-spacing: 1px;
}}

#statBadgeValue {{
    font-size: {small_font}px;
    color: {palette.text};
    font-weight: 600;
}}

#statBadge[tone="positive"] #statBadgeValue {{
    color: {palette.success};
}}

#statBadge[tone="warning"] #statBadgeValue {{
    color: {palette.warning};
}}

#statBadge[tone="danger"] #statBadgeValue {{
    color: {palette.danger};
}}

#tagList {{
    background-color: transparent;
}}

#tagChip {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.chip_radius}px;
}}

#tagChipLabel, #tagChipButton {{
    font-size: {small_font}px;
    color: {palette.accent};
    background-color: transparent;
    border: none;
    padding: 0;
}}

#tagChipButton:hover {{
    text-decoration: underline;
}}

#tagChipRemove {{
    background-color: transparent;
    border: none;
    color: {palette.accent};
    font-size: {subheading_font}px;
    padding: 0 2px;
}}

#tagChipRemove:hover {{
    color: {palette.danger};
}}

#metadataGrid {{
    background-color: transparent;
}}

#metadataGridLabel {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
    text-transform: uppercase;
    letter-spacing: 1px;
    min-width: 90px;
}}

#metadataGridValue {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#metadataGridLink {{
    font-size: {small_font}px;
    color: {palette.accent};
    background-color: transparent;
    border: none;
    padding: 0;
    text-align: left;
}}

#metadataGridLink:hover {{
    text-decoration: underline;
}}

#articleCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#articleCard:hover {{
    border-color: {palette.accent_border};
}}

#articleCardTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#articleCardAuthors {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#articleCardVenue {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
    font-style: italic;
}}

#articleCardAbstract {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#articleCardOpen, #articleCardSave, #articleCardDetails {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#articleCardOpen:disabled, #articleCardSave:disabled, #articleCardDetails:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#researchProjectCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#researchProjectCardTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#researchProjectCardQuestion {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#researchProjectCardOpen, #researchProjectCardEdit, #researchProjectCardArchive {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#researchProjectCardOpen:disabled, #researchProjectCardEdit:disabled, #researchProjectCardArchive:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#collectionCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#collectionCardTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#collectionCardDescription {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#collectionCardPreview {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
}}

#collectionCardOpen, #collectionCardEdit, #collectionCardExport {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#collectionCardOpen:disabled, #collectionCardEdit:disabled, #collectionCardExport:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#aiProviderCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#aiProviderCardName {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#aiProviderCardDetails {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#aiProviderCardTest, #aiProviderCardEdit {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#aiProviderCardRemove {{
    background-color: {palette.danger_soft};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.danger};
}}

#aiProviderCardTest:disabled, #aiProviderCardEdit:disabled, #aiProviderCardRemove:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#searchSourceRow {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
}}

#searchSourceRowName {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.text};
}}

#searchSourceRowFilters {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#searchSourceRowError {{
    font-size: {tiny_font}px;
    color: {palette.danger};
}}

#searchSourceRowTest, #searchSourceRowEdit {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#searchSourceRowRemove {{
    background-color: {palette.danger_soft};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.danger};
}}

#searchSourceRowTest:disabled, #searchSourceRowEdit:disabled, #searchSourceRowRemove:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#quickActionButton {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: 12px 14px;
    text-align: left;
    color: {palette.accent};
}}

#quickActionButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#statusBarVersionLabel {{
    color: {palette.text_subtle};
    padding-right: 8px;
}}

QDialog {{
    background-color: {palette.surface};
    color: {palette.text};
}}

#messageDialog, #confirmDialog, #promptDialog, #formDialog, #progressDialog {{
    background-color: {palette.surface};
}}

#messageDialogKind {{
    font-size: {tiny_font}px;
    font-weight: 700;
    color: {palette.text_subtle};
    letter-spacing: 1px;
}}

#messageDialog[kind="warning"] #messageDialogKind {{
    color: {palette.warning};
}}

#messageDialog[kind="error"] #messageDialogKind {{
    color: {palette.danger};
}}

#messageDialogMessage, #confirmDialogQuestion {{
    font-size: {base_font}px;
    color: {palette.text};
}}

#messageDialogDetailsToggle, #confirmDialogDetailsToggle {{
    background-color: transparent;
    border: none;
    color: {palette.text_muted};
    padding: 2px 4px;
}}

#messageDialogDetails, #confirmDialogDetails {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text_muted};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {small_font}px;
}}

#messageDialogButtonBox QPushButton, #confirmDialogButtonBox QPushButton,
#promptDialogButtonBox QPushButton, #formDialogButtonBox QPushButton {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
    min-width: 80px;
}}

#confirmDialogConfirm {{
    background-color: {palette.accent_soft};
    border-color: {palette.accent_border};
    color: {palette.accent};
}}

#confirmDialogConfirmDestructive {{
    background-color: {palette.danger_soft};
    border-color: {palette.danger_border};
    color: {palette.danger};
}}

#promptDialogLabel, #formDialogFieldLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#promptDialogInput {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#promptDialogInput:focus {{
    border-color: {palette.accent};
}}

#promptDialogError {{
    font-size: {tiny_font}px;
    color: {palette.danger};
}}

#formDialogFieldHelp {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#progressDialogMessage {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#notificationHost {{
    background-color: transparent;
}}

#notificationCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#notificationCard[severity="success"] {{
    border-left: 4px solid {palette.success};
}}

#notificationCard[severity="warning"] {{
    border-left: 4px solid {palette.warning};
}}

#notificationCard[severity="error"] {{
    border-left: 4px solid {palette.danger};
}}

#notificationCard[severity="info"] {{
    border-left: 4px solid {palette.accent};
}}

#notificationTitle {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#notificationMessage {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#notificationClose {{
    background-color: transparent;
    border: none;
    color: {palette.text_subtle};
    font-size: {subheading_font}px;
}}

#notificationClose:hover {{
    color: {palette.text};
}}


#dashboardRefresh {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#dashboardQuickActionsCard, #dashboardRecentProjectsCard,
#dashboardRecentArticlesCard, #dashboardSavedSearchesCard,
#dashboardResearchTasksCard, #dashboardPendingEvidenceCard,
#dashboardRecentReportsCard, #dashboardRecentActivityCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#dashboardSavedSearchLabel {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#dashboardSavedSearchOpen {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#dashboardTaskLabel, #dashboardPendingEvidenceLabel,
#dashboardRecentReportLabel, #dashboardActivityLabel {{
    font-size: {small_font}px;
    color: {palette.text};
}}


#searchTabs::pane {{
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    background-color: {palette.surface};
}}

#searchTabs::tab-bar {{
    alignment: left;
}}

#searchTabs QTabBar::tab {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-bottom: none;
    border-top-left-radius: {spacing.control_radius}px;
    border-top-right-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
    margin-right: 2px;
}}

#searchTabs QTabBar::tab:selected {{
    background-color: {palette.surface};
    color: {palette.text};
    border-color: {palette.accent_border};
}}

#searchResultList {{
    background-color: transparent;
}}

#searchResultRow {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
}}

#searchResultRow:hover {{
    border-color: {palette.accent_border};
}}

#searchResultRowTitle {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#searchResultRowSubtitle {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#searchResultRowSnippet {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#searchResultRowDetails {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#searchStatusLine {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#settingsContent {{
    background-color: transparent;
}}

#settingsTabs::pane {{
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    background-color: {palette.surface};
}}

#settingsTabs QTabBar::tab {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-bottom: none;
    border-top-left-radius: {spacing.control_radius}px;
    border-top-right-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
    margin-right: 2px;
}}

#settingsTabs QTabBar::tab:selected {{
    background-color: {palette.surface};
    color: {palette.text};
    border-color: {palette.accent_border};
}}

#settingsTabGeneral, #settingsTabAppearance, #settingsTabSearch,
#settingsTabAIProviders, #settingsTabPrivacy, #settingsTabAdvanced {{
    background-color: {palette.surface};
}}

#settingsAIIntro {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#settingsAdvancedPathsHeading {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#settingsAdvancedPathLine {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
    font-family: "Cascadia Mono", "Consolas", monospace;
}}

#settingsAdvancedOpenConfigFolder, #settingsAdvancedOpenLogFolder {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#settingsAdvancedReset {{
    background-color: {palette.danger_soft};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.danger};
}}

#settingsGeneralActiveUser {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#settingsGeneralActiveUserLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#settingsGeneralActiveUserValue {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.text};
}}

#settingsGeneralActiveUserRefresh {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}
#sourcesDialogHeading {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#sourcesDialogPlaceholder {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
    padding: 12px 0;
}}

#sourcesDialogAdd, #sourcesDialogRefresh {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#settingsSearchSourcesManage {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#settingsSearchSourcesHeading {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#settingsSearchSourceName {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#settingsSearchSourceStatus {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
    text-transform: uppercase;
    letter-spacing: 1px;
}}

#settingsSearchSourcesHint {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#searchSourcesHint {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#searchManageSources {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#importDialogHeader {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#importDialogModeLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#importDialogMode, #importDialogDuplicates {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#importDialogSelectAll, #importDialogClearSelection {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#importDialogPlaceholder {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
    padding: 12px 0;
}}

#importDialogSummary {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#importRow {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
}}

#importRowTitle {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#importRowDetail {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#importRowState {{
    font-size: {tiny_font}px;
    color: {palette.text_muted};
    text-transform: uppercase;
    letter-spacing: 1px;
}}

#importRowState[state="ready"] {{
    color: {palette.success};
}}

#importRowState[state="duplicate"] {{
    color: {palette.warning};
}}

#importRowState[state="unsupported"], #importRowState[state="oversize"],
#importRowState[state="missing"], #importRowState[state="unreadable"],
#importRowState[state="error"] {{
    color: {palette.danger};
}}

#librarySearchInput {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#librarySearchInput:focus {{
    border-color: {palette.accent};
}}

#librarySearchButton {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#librarySearchClear {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#libraryFilterState {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#libraryFilterReset {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#libraryTable {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    color: {palette.text};
    gridline-color: {palette.border};
}}

#libraryTable::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#libraryDetailTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#libraryDetailAuthors {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#libraryDetailMetadata {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#libraryDetailPath {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#libraryDetailError {{
    font-size: {tiny_font}px;
    color: {palette.danger};
}}

#libraryImportButton, #libraryRefreshButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#readerNavigationBar {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
}}

#readerFirstButton, #readerPreviousButton, #readerNextButton, #readerLastButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#readerFirstButton:disabled, #readerPreviousButton:disabled,
#readerNextButton:disabled, #readerLastButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#readerPageLabel, #readerZoomLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#readerZoomCombo {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#readerCloseButton, #readerHeaderClose {{
    background-color: {palette.danger_soft};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.danger};
}}

#readerOutlineList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#readerOutlineList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#readerOutlineList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#readerPageScroll {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#readerPageView {{
    background-color: {palette.surface};
    color: {palette.text_muted};
    padding: 12px;
}}

#readerProgressBar {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    height: 6px;
}}

#readerProgressBar::chunk {{
    background-color: {palette.accent};
    border-radius: {spacing.control_radius}px;
}}

#annotationPanel {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
}}

#annotationPanelHeading {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#annotationPanelSummary {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#annotationAddNote, #annotationAddHighlight, #annotationAddBookmark {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#annotationColorCombo {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#annotationList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#annotationList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#annotationList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#annotationEditorLabel {{
    font-size: {tiny_font}px;
    color: {palette.text_muted};
}}

#annotationEditor {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#annotationSave {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#annotationSave:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#annotationDelete {{
    background-color: {palette.danger_soft};
    border: 1px solid {palette.danger_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.danger};
}}

#annotationDelete:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#annotationExportJson, #annotationExportMarkdown {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#documentSearchPanel {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
}}

#documentSearchHeading {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#documentSearchInput {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#documentSearchInput:focus {{
    border-color: {palette.accent};
}}

#documentSearchButton {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#documentSearchClear {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#documentSearchCaseSensitive, #documentSearchRegex {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#documentSearchSummary {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#documentSearchResults {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#documentSearchResults::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#documentSearchResults::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#linkDialogHeading {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#linkDialogTabs::pane {{
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    background-color: {palette.surface};
}}

#linkDialogTabs QTabBar::tab {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-bottom: none;
    border-top-left-radius: {spacing.control_radius}px;
    border-top-right-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
    margin-right: 2px;
}}

#linkDialogTabs QTabBar::tab:selected {{
    background-color: {palette.surface};
    color: {palette.text};
    border-color: {palette.accent_border};
}}

#linkDialogEmpty {{
    font-size: {small_font}px;
    color: {palette.text_subtle};
    padding: 12px 0;
}}

#linkDialogCheckbox_ {{
    /* placeholder selector; specific selectors are generated per key */
}}

#linkDialogApply {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#linkDialogCancel {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#readerLinkButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#readerLinkButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#assistantHandoffDialog {{
    background-color: {palette.surface};
}}

#handoffDialogHeading {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#handoffIncludeMetadata, #handoffIncludeExcerpt, #handoffIncludeAnnotations {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#handoffDialogSummary {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#handoffDialogPreview {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {small_font}px;
}}

#handoffDialogSend {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#handoffDialogCancel {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#readerHandoffButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#readerHandoffButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#projectsContent {{
    background-color: transparent;
}}

#projectsFilterLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#projectsStageFilter {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectsTable {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    color: {palette.text};
    gridline-color: {palette.border};
}}

#projectsTable::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#projectsDetailTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#projectsDetailTopic {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#projectsDetailStageLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#projectsDetailStage {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectsDetailSummary {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#projectsDetailTabs::pane {{
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    background-color: {palette.surface};
}}

#projectsDetailTabs QTabBar::tab {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-bottom: none;
    border-top-left-radius: {spacing.control_radius}px;
    border-top-right-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
    margin-right: 2px;
}}

#projectsDetailTabs QTabBar::tab:selected {{
    background-color: {palette.surface};
    color: {palette.text};
    border-color: {palette.accent_border};
}}

#projectsQuestionsList, #projectsTasksList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#projectsQuestionsList::item, #projectsTasksList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#projectsQuestionsList::item:selected, #projectsTasksList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#projectsCreateButton, #projectsEditButton, #projectsRefreshButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectsEditButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#projectsAddQuestion, #projectsSetPrimaryQuestion, #projectsRemoveQuestion,
#projectsAddTask, #projectsToggleTask, #projectsRemoveTask {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectsAddQuestion:disabled, #projectsSetPrimaryQuestion:disabled,
#projectsRemoveQuestion:disabled, #projectsAddTask:disabled,
#projectsToggleTask:disabled, #projectsRemoveTask:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#collectionsContent {{
    background-color: transparent;
}}

#collectionsFilterLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#collectionsKindFilter {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#collectionsTable {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    color: {palette.text};
    gridline-color: {palette.border};
}}

#collectionsTable::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#collectionsDetailTitle {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#collectionsDetailDescription {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#collectionsDetailSummary {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#collectionsDetailTabs::pane {{
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    background-color: {palette.surface};
}}

#collectionsDetailTabs QTabBar::tab {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-bottom: none;
    border-top-left-radius: {spacing.control_radius}px;
    border-top-right-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
    margin-right: 2px;
}}

#collectionsDetailTabs QTabBar::tab:selected {{
    background-color: {palette.surface};
    color: {palette.text};
    border-color: {palette.accent_border};
}}

#collectionsItemsList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#collectionsItemsList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#collectionsItemsList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#collectionsFilterHint {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#collectionsFilterEditor {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {small_font}px;
}}

#collectionsFilterEditor:disabled {{
    background-color: {palette.disabled_bg};
    color: {palette.disabled_text};
}}

#collectionsCreateButton, #collectionsEditButton, #collectionsRefreshButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#collectionsEditButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#collectionsAddItem, #collectionsEditItemNote, #collectionsMoveUp,
#collectionsMoveDown, #collectionsRemoveItem, #collectionsSaveFilter {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#collectionsAddItem:disabled, #collectionsEditItemNote:disabled,
#collectionsMoveUp:disabled, #collectionsMoveDown:disabled,
#collectionsRemoveItem:disabled, #collectionsSaveFilter:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#collectionsItemsHint {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
    padding: 4px 0;
}}

#milestonesPanel {{
    background-color: transparent;
}}

#milestonesSummary {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
}}

#milestonesSummaryTotal, #milestonesSummaryActive,
#milestonesSummaryDone, #milestonesSummaryMilestones {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#milestonesSummaryOverdue {{
    font-size: {small_font}px;
    color: {palette.danger};
    font-weight: 600;
}}

#milestonesFilterLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#milestonesStatusFilter, #milestonesOnlyFilter {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#milestonesList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#milestonesList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#milestonesList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#milestonesAddTask, #milestonesEditTask, #milestonesRemoveTask {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#milestonesAddTask:disabled, #milestonesEditTask:disabled,
#milestonesRemoveTask:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#projectExportDialog {{
    background-color: {palette.surface};
}}

#projectExportHeading {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#projectExportFormatLabel, #projectExportSectionsLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#projectExportFormat {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectExportPath {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectExportBrowse {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectExportOverwrite {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#projectExportAccept {{
    background-color: {palette.accent_soft};
    border: 1px solid {palette.accent_border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.accent};
}}

#projectExportCancel {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#projectsExportButton {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#projectsExportButton:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#researchAssistantContent {{
    background-color: transparent;
}}

#assistantSidebar {{
    background-color: {palette.surface_alt};
    border-right: 1px solid {palette.border};
}}

#assistantSidebarHeading {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#assistantSectionList {{
    background-color: transparent;
    border: none;
    color: {palette.text};
    outline: 0;
}}

#assistantSectionList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
    margin: 1px 0;
}}

#assistantSectionList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#assistantSectionList::item:hover {{
    background-color: {palette.surface};
}}

#assistantRefreshSummaries, #assistantRefresh, #assistantOpenProjects {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#assistantStack {{
    background-color: {palette.background};
    border: none;
}}

#sectionScroll {{
    background-color: {palette.background};
    border: none;
}}

#sectionFooter {{
    background-color: {palette.surface_alt};
    border-top: 1px solid {palette.border};
}}

#sectionFooterSummary {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#sectionFooterClear {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
}}

#reviewIntro {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#reviewSummary {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    color: {palette.text};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {small_font}px;
}}

#reviewRefresh, #reviewExport {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}


#titleWorkingTitleLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#titleWorkingTitle {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#titleGenerateCandidates, #titleRefreshCandidates {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#titleGenerateCandidates:disabled, #titleRefreshCandidates:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#titleCandidateList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
}}

#titleCandidateList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#titleCandidateList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#titleAcceptCandidate, #titleRejectCandidate, #titleUseCandidate {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#titleAcceptCandidate:disabled, #titleRejectCandidate:disabled,
#titleUseCandidate:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#titleCandidateDetails {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: {small_font}px;
}}

#titleComparisonPanel {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-radius: {spacing.card_radius}px;
    padding: 10px 12px;
}}

#titleComparisonHeading {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#titleComparisonList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
    min-height: 220px;
}}

#titleComparisonList::item {{
    padding: 2px;
    border-radius: {spacing.control_radius}px;
}}

#titleComparisonList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#titleCandidateCard {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
}}

#titleCandidateCard[state="accepted"] {{
    border-left: 4px solid {palette.success};
}}

#titleCandidateCard[state="proposed"] {{
    border-left: 4px solid {palette.accent};
}}

#titleCandidateCard[state="rejected"] {{
    border-left: 4px solid {palette.danger};
}}

#titleCandidateCard[state="archived"] {{
    border-left: 4px solid {palette.text_subtle};
}}

#titleCandidateCardTitle {{
    font-size: {small_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#titleCandidateCardState {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
    text-transform: uppercase;
    letter-spacing: 1px;
}}

#titleCandidateCardState[state="accepted"] {{
    color: {palette.success};
}}

#titleCandidateCardState[state="rejected"] {{
    color: {palette.danger};
}}

#titleCandidateCardMeta {{
    font-size: {tiny_font}px;
    color: {palette.text_subtle};
}}

#titleCandidateCardRationale {{
    font-size: {small_font}px;
    color: {palette.text};
}}

#titleCandidateCardStrengths, #titleCandidateCardProblems,
#titleCandidateCardAssumptions {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#titleComparisonRefresh, #titleComparisonAccept, #titleComparisonReject,
#titleComparisonArchive, #titleComparisonRestore, #titleComparisonEdit,
#titleComparisonUse {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#titleComparisonAccept:disabled, #titleComparisonReject:disabled,
#titleComparisonArchive:disabled, #titleComparisonRestore:disabled,
#titleComparisonEdit:disabled, #titleComparisonUse:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#questionsValidation {{
    font-size: {small_font}px;
    color: {palette.text_muted};
    padding: 6px 0;
}}

#questionsValidation[severity="ok"] {{
    color: {palette.success};
}}

#questionsValidation[severity="warning"] {{
    color: {palette.warning};
}}

#questionsValidation[severity="error"] {{
    color: {palette.danger};
}}

#questionsSecondaryHeading {{
    font-size: {subheading_font}px;
    font-weight: 600;
    color: {palette.heading};
}}

#questionsEntryList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
    min-height: 160px;
}}

#questionsEntryList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#questionsEntryList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#questionsKind {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#questionsAddEntry, #questionsPromoteEntry, #questionsEditEntry,
#questionsRemoveEntry {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#questionsAddEntry:disabled, #questionsPromoteEntry:disabled,
#questionsEditEntry:disabled, #questionsRemoveEntry:disabled {{
    background-color: {palette.disabled_bg};
    border-color: {palette.disabled_border};
    color: {palette.disabled_text};
}}

#historyTopicLabel {{
    font-size: {small_font}px;
    color: {palette.text_muted};
}}

#historyTopicInput, #historySynonymInput, #historyQueryInput {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}

#historyTopicInput:focus, #historySynonymInput:focus, #historyQueryInput:focus {{
    border-color: {palette.accent};
}}

#historySynonymsList, #historyQueriesList, #historyRunsList,
#historyTimelineList, #historyThemesList, #historyResultsList {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    color: {palette.text};
    outline: 0;
    min-height: 160px;
}}

#historySynonymsList::item, #historyQueriesList::item, #historyRunsList::item,
#historyTimelineList::item, #historyThemesList::item, #historyResultsList::item {{
    padding: {spacing.list_item_padding_v}px {spacing.list_item_padding_h}px;
    border-radius: {spacing.control_radius}px;
}}

#historySynonymsList::item:selected, #historyQueriesList::item:selected,
#historyRunsList::item:selected, #historyTimelineList::item:selected,
#historyThemesList::item:selected, #historyResultsList::item:selected {{
    background-color: {palette.accent_soft};
    color: {palette.accent};
}}

#historyTabs::pane {{
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    background-color: {palette.surface};
}}

#historyTabs QTabBar::tab {{
    background-color: {palette.surface_alt};
    border: 1px solid {palette.border};
    border-bottom: none;
    border-top-left-radius: {spacing.control_radius}px;
    border-top-right-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text_muted};
    margin-right: 2px;
}}

#historyTabs QTabBar::tab:selected {{
    background-color: {palette.surface};
    color: {palette.text};
    border-color: {palette.accent_border};
}}

#historyAddSynonym, #historyRemoveSynonym, #historyAddQuery,
#historyRemoveQuery, #historyRunAll, #historyRunSelected, #historyClear {{
    background-color: {palette.surface};
    border: 1px solid {palette.border};
    border-radius: {spacing.control_radius}px;
    padding: {spacing.control_padding_v}px {spacing.control_padding_h}px;
    color: {palette.text};
}}
""".strip()


APPLICATION_STYLESHEET = build_application_stylesheet(
    theme=ThemeMode.LIGHT,
    font_scale=1.0,
    density="comfortable",
)