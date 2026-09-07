from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from PySide6.QtGui import QGuiApplication, QPalette

from app.settings import ApplicationPaths


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    name: str
    background: str
    surface: str
    surface_raised: str
    border: str
    border_strong: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    success: str
    warning: str
    error: str
    surface_secondary: str
    surface_elevated: str
    border_subtle: str
    difference: str
    hover: str
    selected: str
    scrollbar_thumb: str
    scrollbar_thumb_hover: str
    scrollbar_thumb_pressed: str
    hex_background: str
    hex_toolbar_background: str
    hex_text: str
    hex_secondary: str
    hex_offset: str
    hex_separator: str
    hex_selection: str
    hex_current: str
    timeline_document: str
    timeline_signature: str
    timeline_metadata: str
    timeline_filesystem: str
    timeline_structural: str
    timeline_fh: str
    timeline_certificate: str
    timeline_axis: str
    timeline_grid: str
    timeline_secondary: str
    radius_small: int = 2
    radius_panel: int = 2
    spacing: int = 8


DARK_THEME = ThemeTokens(
    name="dark",
    background="#0B0D0F",
    surface="#111417",
    surface_raised="#191E23",
    border="#2A3036",
    border_strong="#46515B",
    text_primary="#F0F1F2",
    text_secondary="#B8BDC2",
    text_muted="#9DA3A9",
    accent="#65A4E8",
    success="#62B989",
    warning="#D1A553",
    error="#E1767A",
    surface_secondary="#15191D",
    surface_elevated="#191E23",
    border_subtle="#20262B",
    difference="#65A4E8",
    hover="#20262B",
    selected="#172534",
    scrollbar_thumb="#68737E",
    scrollbar_thumb_hover="#85909B",
    scrollbar_thumb_pressed="#A2ABB4",
    hex_background="#111417",
    hex_toolbar_background="#15191D",
    hex_text="#E3E7EB",
    hex_secondary="#AAB2BA",
    hex_offset="#8F9AA5",
    hex_separator="#303840",
    hex_selection="#294B6D",
    hex_current="#75ADE8",
    timeline_document="#58A6A6",
    timeline_signature="#6E9FD2",
    timeline_metadata="#9A83C7",
    timeline_filesystem="#9099A2",
    timeline_structural="#C19A55",
    timeline_fh="#68A77F",
    timeline_certificate="#73A584",
    timeline_axis="#8B949E",
    timeline_grid="#30363D",
    timeline_secondary="#9DA3A9",
)

LIGHT_THEME = ThemeTokens(
    name="light",
    background="#F5F6F8",
    surface="#FFFFFF",
    surface_raised="#FFFFFF",
    border="#DDE1E6",
    border_strong="#CBD1D8",
    text_primary="#171A1F",
    text_secondary="#4F5965",
    text_muted="#737D8A",
    accent="#155AA8",
    success="#14733C",
    warning="#8A5A00",
    error="#A4262C",
    surface_secondary="#F7F8FA",
    surface_elevated="#FFFFFF",
    border_subtle="#E4E4E4",
    difference="#155AA8",
    hover="#EFEFEF",
    selected="#EAF2FA",
    scrollbar_thumb="#8A949F",
    scrollbar_thumb_hover="#6F7984",
    scrollbar_thumb_pressed="#59636E",
    hex_background="#FAFBFC",
    hex_toolbar_background="#F1F3F5",
    hex_text="#20252B",
    hex_secondary="#59636E",
    hex_offset="#66717D",
    hex_separator="#D6DBE1",
    hex_selection="#CFE2F5",
    hex_current="#155AA8",
    timeline_document="#267878",
    timeline_signature="#356C9F",
    timeline_metadata="#70559A",
    timeline_filesystem="#68737E",
    timeline_structural="#8A672A",
    timeline_fh="#34744B",
    timeline_certificate="#477A58",
    timeline_axis="#6F7984",
    timeline_grid="#D7DCE2",
    timeline_secondary="#68737E",
)


def brand_logo_path(
    tokens: ThemeTokens = DARK_THEME,
    *,
    paths: ApplicationPaths | None = None,
) -> Path | None:
    filename = (
        "forensihash_logo_branco.png"
        if tokens.name == "dark"
        else "forensihash_logo_preto.png"
    )
    candidate = (paths or ApplicationPaths.discover()).resource(
        f"app/ui/assets/{filename}"
    )
    return candidate if candidate.is_file() else None


def theme_tokens(mode: str) -> ThemeTokens:
    if mode == "dark":
        return DARK_THEME
    if mode == "system":
        app = QGuiApplication.instance()
        if app is not None:
            color = app.palette().color(QPalette.ColorRole.Window)
            return DARK_THEME if color.lightness() < 128 else LIGHT_THEME
    return LIGHT_THEME


def load_desktop_stylesheet(
    paths: ApplicationPaths,
    tokens: ThemeTokens = DARK_THEME,
) -> str:
    base_path = paths.resource("app/ui/style.qss")
    base = base_path.read_text(encoding="utf-8") if base_path.exists() else ""
    base = _normalize_legacy_surfaces(base, tokens)
    return f"{base}\n{_phase_one_stylesheet(tokens)}"


def _normalize_legacy_surfaces(base: str, tokens: ThemeTokens) -> str:
    """Converte superfícies azuis legadas para a paleta central ativa."""
    replacements = {
        "#0B1120": tokens.background,
        "#070D1D": tokens.surface_secondary,
        "#0E1728": tokens.surface,
        "#0F172A": tokens.surface,
        "#0B1220": tokens.background,
        "#0B1222": tokens.background,
        "#101827": tokens.surface,
        "#10192C": tokens.surface,
        "#111827": tokens.surface,
        "#111a2d": tokens.surface,
        "#151F31": tokens.surface_secondary,
        "#151f34": tokens.surface_secondary,
        "#162033": tokens.surface_secondary,
        "#17233A": tokens.surface_elevated,
        "#1b2942": tokens.hover,
        "#1E2A40": tokens.hover,
        "#1D2A42": tokens.border,
        "#1d2a42": tokens.border,
        "#1E293B": tokens.border,
        "#202E49": tokens.border,
        "#202d46": tokens.border,
        "#22314A": tokens.border,
        "#23324e": tokens.border,
        "#243244": tokens.border,
        "#25334D": tokens.border,
        "#26344D": tokens.border,
        "#293850": tokens.border,
        "#2A3D5D": tokens.border_strong,
        "#2a3a59": tokens.border_strong,
        "#334155": tokens.border_strong,
        "#F8FAFC": tokens.text_primary,
        "#f8fafc": tokens.text_primary,
        "#F1F5F9": tokens.text_primary,
        "#f1f5f9": tokens.text_primary,
        "#E5E7EB": tokens.text_primary,
        "#e5e7eb": tokens.text_primary,
        "#E2E8F0": tokens.text_primary,
        "#e2e8f0": tokens.text_primary,
        "#D7E2F5": tokens.text_primary,
        "#d8e3f6": tokens.text_primary,
        "#CBD5E1": tokens.text_secondary,
        "#cbd5e1": tokens.text_secondary,
        "#C4D0E4": tokens.text_secondary,
        "#A7B4C9": tokens.text_secondary,
        "#a9b5c2": tokens.text_secondary,
        "#94A3B8": tokens.text_muted,
        "#94a3b8": tokens.text_muted,
        "#91a0b8": tokens.text_muted,
        "#8495b3": tokens.text_muted,
        "#71839F": tokens.text_muted,
        "#71819c": tokens.text_muted,
        "#64748B": tokens.text_muted,
        "#64748b": tokens.text_muted,
        "#60A5FA": tokens.accent,
        "#60a5fa": tokens.accent,
        "#3B82F6": tokens.accent,
        "#3b82f6": tokens.accent,
    }
    for legacy, replacement in replacements.items():
        base = base.replace(legacy, replacement)
    return base


def _phase_one_stylesheet(tokens: ThemeTokens) -> str:
    values = asdict(tokens)
    template = r"""
/* Phase 1: shared ForensiHash result language. */
QWidget { background-color: {background}; color: {text_primary}; }
QLabel { color: {text_primary}; }
QWidget#Content, QWidget#DashboardContent, QScrollArea#DashboardScroll,
QScrollArea#DashboardScroll > QWidget > QWidget {
    background: {background};
}
QWidget#MainArea, QWidget#WorkspaceContainer, QWidget#HomeContent, QScrollArea#HomeScroll { background: {background}; }
QStackedWidget#AnalysisWorkspace, QStackedWidget#AnalysisWorkspace > QWidget,
QScrollArea#DashboardScroll > QWidget > QWidget { background: {surface_elevated}; }
QFrame#TopBar, QFrame#StatusBar { background: {surface_elevated}; border: 0; }
QFrame#TopBar { border-bottom: 1px solid {border_subtle}; }
QFrame#StatusBar { border-top: 1px solid {border_subtle}; }
QLabel#TopBarBrand { color: {text_primary}; font-size: 13px; font-weight: 700; letter-spacing: 1px; }
QLabel#TopBarContext, QLabel#StatusBarText, QLabel#StatusBarVersion { color: {text_secondary}; }
QLabel#StatusCurrentFile { color: {text_primary}; font-size: 11px; }
QProgressBar#AnalysisProgressBar { background: {surface_secondary}; color: {text_primary}; border: 1px solid {border}; border-radius: 3px; height: 16px; text-align: center; font-size: 10px; }
QProgressBar#AnalysisProgressBar::chunk { background: {accent}; border-radius: 2px; }
QLabel#HomeTitle { color: {text_primary}; font-size: 26px; font-weight: 650; }
QLabel#HomeSubtitle, QLabel#HomeDropHint, QLabel#HomeRecentEmpty, QLabel#SettingsDescription { color: {text_secondary}; }
QLabel#SectionLabel, QLabel#SidebarSectionTitle { color: {text_muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QFrame#HomeDropArea { background: {surface_elevated}; border: 1px solid {border}; border-radius: 6px; min-height: 150px; }
QFrame#HomeDropArea[dropActive="true"] { background: {selected}; border: 2px solid {accent}; }
QPushButton#HomeNewCaseButton { color: white; background: {accent}; border: 0; border-radius: 4px; min-height: 38px; padding: 0 18px; font-weight: 650; }
QPushButton#HomeOpenCaseButton { color: {accent}; background: transparent; border: 0; min-height: 30px; }
QFrame#HomeRecentCaseCard { background: {surface_elevated}; border: 0; border-bottom: 1px solid {border_subtle}; }
QPushButton#HomeRecentCase, QPushButton#HomeExploreRow { color: {text_primary}; background: {surface_elevated}; border: 0; border-bottom: 1px solid {border_subtle}; padding: 12px; text-align: left; }
QFrame#HomeRecentCaseCard QPushButton#HomeRecentCase { border-bottom: 0; }
QPushButton#HomeRecentCase:hover, QPushButton#HomeExploreRow:hover { background: {hover}; }
QPushButton#HomeRecentCaseDelete { color: {text_muted}; background: transparent; border: 0; border-radius: 3px; font-size: 17px; padding: 0; }
QPushButton#HomeRecentCaseDelete:hover { color: #b42318; background: rgba(180, 35, 24, 0.07); }
QPushButton#HomeRecentCaseDelete:pressed, QPushButton#HomeRecentCaseDelete:focus { color: #b42318; border: 1px solid {accent}; }
QPushButton#HomeExploreRow:disabled { color: {text_muted}; }
QFrame#HomeTips { background: {surface_elevated}; border: 1px solid {border_subtle}; border-radius: 5px; }
QLabel#HomeTip { color: {text_secondary}; border-bottom: 1px solid {border_subtle}; padding: 10px 2px; }
QLabel#SidebarCaseName { color: {text_primary}; font-weight: 650; }
QLabel#SidebarCaseDetails { color: {text_muted}; font-size: 11px; }
QPushButton#SidebarNavigationButton { text-align: left; min-height: 34px; padding: 0 8px; }
QPushButton#SidebarNavigationButton:checked { border-left: 3px solid {accent}; }
QLabel#SidebarNavigationText { color: {text_secondary}; background: transparent; }
QLabel#SidebarNavigationText { font-weight: 400; }
QPushButton#SidebarNavigationButton:checked QLabel#SidebarNavigationText { color: {text_primary}; }
QPushButton#SidebarGroupButton { min-height: 22px; background: transparent; border: 0; border-radius: 0; text-align: left; }
QPushButton#SidebarGroupButton:hover { background: {hover}; border: 0; }
QPushButton#SidebarGroupButton:focus { background: transparent; border: 0; border-bottom: 1px solid {accent}; }
QLabel#SidebarGroupIndicator { color: {text_muted}; background: transparent; }
QWidget#LineIcon, QWidget#HomeIllustration { background: transparent; }
QPushButton#SidebarCollapseButton { background: transparent; color: {text_secondary}; border: 1px solid transparent; border-radius: 3px; }
QPushButton#SidebarCollapseButton:hover, QPushButton#SidebarCollapseButton:focus { background: {hover}; border-color: {border}; color: {text_primary}; }
QFrame#SidebarSeparator { color: {border_subtle}; }
QDialog#NewCaseDialog { background: {background}; color: {text_primary}; }
QLabel#DialogTitle, QLabel#SettingsSectionTitle { color: {text_primary}; font-size: 18px; font-weight: 650; }
QLabel#CaseDropHint { color: {text_secondary}; background: {surface_secondary}; border: 1px dashed {border}; padding: 18px; }
QLineEdit, QListWidget { background: {surface_elevated}; color: {text_primary}; border: 1px solid {border}; selection-background-color: {selected}; selection-color: {text_primary}; }
QPushButton:disabled { color: {text_muted}; background: {surface_secondary}; }
QPushButton:focus, QLineEdit:focus, QListWidget:focus { border: 1px solid {accent}; }
QFrame#FileStrip { background: {surface_elevated}; border-top: 1px solid {border}; }
QListView#FileStripView { background: {surface_elevated}; color: {text_primary}; border: 0; outline: 0; }
QListView#FileStripView::item { border: 0; border-radius: 0; }
QPushButton#FileStripScrollButton { background: {surface_secondary}; border: 0; border-radius: 0; color: {text_secondary}; }
QPushButton#FileStripScrollButton:hover { background: {hover}; color: {text_primary}; }
QScrollBar:horizontal { background: transparent; height: 5px; margin: 0; }
QScrollBar::handle:horizontal { background: {border_strong}; min-width: 28px; border-radius: 2px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QFrame#TimelineModeControl { background: {surface_secondary}; border: 1px solid {border_subtle}; border-radius: 3px; }
QPushButton#TimelineModeButton { min-width: 76px; min-height: 28px; max-height: 28px; padding: 0 10px; background: transparent; color: {text_secondary}; border: 1px solid transparent; border-radius: 2px; text-align: center; }
QPushButton#TimelineModeButton:hover { background: {hover}; color: {text_primary}; }
QPushButton#TimelineModeButton:checked { color: {text_primary}; background: {surface_elevated}; border: 0; border-bottom: 2px solid {border_strong}; font-weight: 600; }
QPushButton#TimelineModeButton:focus, QPushButton#TimelineSourceButton:focus, QPushButton#TimelineDetailsButton:focus, QPushButton#TimelineReferencesButton:focus, QPushButton#TimelineMoreButton:focus, QPushButton#TimelinePopoverEvent:focus, QPushButton#TimelinePopoverClose:focus { border: 1px dashed {border_strong}; }
QLabel#TimelineArtifactContext { color: {text_muted}; font-size: 11px; }
QScrollArea#DetailedTimelineScroll, QScrollArea#DetailedTimelineScroll > QWidget > QWidget, QWidget#DetailedTimelineContainer { background: transparent; border: 0; }
QFrame#TimelineV2EventRow { background: transparent; border: 0; border-bottom: 1px solid {border_subtle}; }
QFrame#TimelineV2EventRow:hover { background: {hover}; }
QFrame#TimelineV2EventRow[selected="true"] { background: {selected}; border-left: 2px solid {border_strong}; }
QFrame#TimelineV2EventRow:focus { border-left: 2px solid {border_strong}; }
QWidget#TimelineVerticalRail { background: transparent; }
QFrame#TimelineVerticalLineV2 { background: {timeline_grid}; border: 0; min-width: 1px; max-width: 1px; }
QLabel#TimelineV2Marker { color: {timeline_axis}; background: transparent; font-size: 12px; min-width: 18px; min-height: 18px; }
QLabel#TimelineV2Category, QLabel#TimelinePopoverCategory { color: {timeline_secondary}; background: transparent; font-size: 9px; font-weight: 700; letter-spacing: 0.8px; }
QLabel#TimelineV2Marker[timelineCategory="document"], QLabel#TimelineV2Category[timelineCategory="document"], QLabel#TimelinePopoverCategory[timelineCategory="document"] { color: {timeline_document}; }
QLabel#TimelineV2Marker[timelineCategory="signature"], QLabel#TimelineV2Category[timelineCategory="signature"], QLabel#TimelinePopoverCategory[timelineCategory="signature"] { color: {timeline_signature}; }
QLabel#TimelineV2Marker[timelineCategory="metadata"], QLabel#TimelineV2Category[timelineCategory="metadata"], QLabel#TimelinePopoverCategory[timelineCategory="metadata"] { color: {timeline_metadata}; }
QLabel#TimelineV2Marker[timelineCategory="filesystem"], QLabel#TimelineV2Category[timelineCategory="filesystem"], QLabel#TimelinePopoverCategory[timelineCategory="filesystem"] { color: {timeline_filesystem}; }
QLabel#TimelineV2Marker[timelineCategory="structural"], QLabel#TimelineV2Category[timelineCategory="structural"], QLabel#TimelinePopoverCategory[timelineCategory="structural"] { color: {timeline_structural}; }
QLabel#TimelineV2Marker[timelineCategory="fh"], QLabel#TimelineV2Category[timelineCategory="fh"], QLabel#TimelinePopoverCategory[timelineCategory="fh"] { color: {timeline_fh}; }
QLabel#TimelineV2Marker[timelineCategory="certificate"], QLabel#TimelineV2Category[timelineCategory="certificate"], QLabel#TimelinePopoverCategory[timelineCategory="certificate"] { color: {timeline_certificate}; }
QLabel#TimelineV2EventTitle, QLabel#TimelinePopoverTitle { color: {text_primary}; font-weight: 600; }
QLabel#TimelineV2EventTime, QLabel#TimelinePopoverTime { color: {text_primary}; font-family: "Consolas", monospace; }
QLabel#TimelineV2Secondary, QLabel#TimelineV2Description, QLabel#TimelineV2Empty, QLabel#TimelineV2Technical, QLabel#TimelinePopoverDetail { color: {text_secondary}; }
QWidget#TimelineTechnicalPanel { background: {surface_secondary}; border: 1px solid {border_subtle}; border-radius: 2px; }
QPushButton#TimelineSourceButton, QPushButton#TimelineDetailsButton, QPushButton#TimelineReferencesButton, QPushButton#TimelineMoreButton, QPushButton#TimelinePopoverClose { color: {text_secondary}; background: transparent; border: 1px solid {border}; border-radius: {radius_small}px; min-height: 27px; padding: 0 9px; }
QPushButton#TimelineSourceButton:hover, QPushButton#TimelineDetailsButton:hover, QPushButton#TimelineReferencesButton:hover, QPushButton#TimelineMoreButton:hover, QPushButton#TimelinePopoverClose:hover { background: {hover}; color: {text_primary}; }
QPushButton#TimelineDetailsButton:checked { background: {surface_secondary}; color: {text_primary}; border-color: {border_strong}; }
QPushButton#TimelineReferencesButton, QPushButton#TimelineMoreButton { text-align: left; margin-top: 6px; }
QWidget#VisualTimeline { background: {surface_elevated}; border: 1px solid {border}; border-radius: 3px; }
QFrame#TimelinePopover { background: {surface_elevated}; border: 1px solid {border_strong}; border-radius: 4px; }
QPushButton#TimelinePopoverEvent { color: {text_primary}; background: transparent; border: 0; border-left: 3px solid {timeline_axis}; border-bottom: 1px solid {border_subtle}; border-radius: 0; text-align: left; min-height: 32px; padding: 4px 7px; }
QPushButton#TimelinePopoverEvent:hover { background: {hover}; }
QPushButton#TimelinePopoverEvent[timelineCategory="document"] { border-left-color: {timeline_document}; }
QPushButton#TimelinePopoverEvent[timelineCategory="signature"] { border-left-color: {timeline_signature}; }
QPushButton#TimelinePopoverEvent[timelineCategory="metadata"] { border-left-color: {timeline_metadata}; }
QPushButton#TimelinePopoverEvent[timelineCategory="filesystem"] { border-left-color: {timeline_filesystem}; }
QPushButton#TimelinePopoverEvent[timelineCategory="structural"] { border-left-color: {timeline_structural}; }
QPushButton#TimelinePopoverEvent[timelineCategory="fh"] { border-left-color: {timeline_fh}; }

/* V3: instrument-like internal page language. */
QFrame#BaseCard, QFrame#CardContent, QFrame#InfoCard, QFrame#metadataCard,
QFrame#summaryCard, QFrame#CaseOverview, QFrame#ResultHeader,
QFrame#SummarySection, QFrame#AnalyzedFileCard, QFrame#BinaryCard,
QFrame#DetectedIpCard, QFrame#TimelineEventCard, QFrame#TimelineInfoCard,
QFrame#ProportionalTimelineCard, QFrame#ContractDateConfirmationCard {
    background: {surface_elevated}; border: 1px solid {border}; border-radius: {radius_panel}px;
}
QLabel#CardTitle, QLabel#SectionTitle, QLabel#StructureSectionTitle,
QLabel#TimelinePageTitle, QLabel#DashboardTitle { color: {text_primary}; }
QLabel#MutedText, QLabel#SectionSubtitle, QLabel#StructureMutedText,
QLabel#TimelinePageSubtitle, QLabel#ForensicSummaryDescription,
QLabel#AnalyzedFileFieldTitle, QLabel#metadataInsightText,
QLabel#findingItemMuted, QLabel#findingsPreviewMuted { color: {text_secondary}; }
QTableView, QTreeView, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit {
    background: {surface_elevated}; color: {text_primary}; alternate-background-color: {surface_secondary};
    border: 1px solid {border}; gridline-color: {border}; selection-background-color: {selected};
    selection-color: {text_primary};
}
QHeaderView::section { background: {surface_secondary}; color: {text_secondary}; border: 0; border-bottom: 1px solid {border}; padding: 6px; }
QGroupBox { background: {surface_elevated}; color: {text_primary}; border: 1px solid {border}; border-radius: {radius_small}px; margin-top: 10px; }
QLabel#TechnicalMetricBadge, QLabel#StatusBadge, QLabel#EvidenceBadge,
QLabel#ConfidenceBadge, QLabel#TimelineBadge, QLabel#TimelineHourBadge,
QLabel#DiagnosticsStatusBadge { border-radius: {radius_small}px; background: {surface_secondary}; color: {text_secondary}; }
QFrame#DiagnosticsMetricCard, QFrame#DiagnosticsFact, QFrame#DiagnosticsChart {
    background: {surface_elevated}; border: 1px solid {border}; border-radius: {radius_panel}px;
}
QLabel#DiagnosticsCardTitle, QLabel#DiagnosticsFactTitle { color: {text_secondary}; }
QLabel#DiagnosticsCardValue, QLabel#DiagnosticsFactValue { color: {text_primary}; }
QLabel#DiagnosticsDetails { color: {text_secondary}; background: {surface_secondary}; border: 1px solid {border}; border-radius: {radius_small}px; }
QFrame#MagicCompactHeader, QFrame#SelectionBar, QFrame#BinaryStatusBar {
    background: {surface_elevated}; border: 0; border-bottom: 1px solid {border};
}
QFrame#MagicCompactHeader QLabel, QFrame#SelectionBar QLabel,
QFrame#BinaryStatusBar QLabel { background: transparent; }
QFrame#HexWorkspace {
    background: {hex_background}; border: 1px solid {hex_separator}; border-radius: {radius_small}px;
}
QFrame#HexToolbar, QFrame#ByteInspector {
    background: {hex_toolbar_background}; border: 0;
}
QFrame#ByteInspector { border-left: 1px solid {hex_separator}; }
QAbstractScrollArea#HexGrid { background: {hex_background}; border: 0; }
QFrame#HexWorkspace QLabel { color: {hex_text}; }
QFrame#HexWorkspace QLabel#TechnicalCaption,
QFrame#HexWorkspace QLabel#InspectorCaption { color: {hex_secondary}; }
QFrame#HexWorkspace QLabel#InspectorValue { color: {hex_text}; }
QLabel#CurrentFileName, QLabel#MagicDetectedType, QLabel#InspectorValue { color: {text_primary}; }
QLabel#CurrentFileMeta, QLabel#TechnicalCaption, QLabel#InspectorCaption,
QLabel#MagicFeedback { color: {text_secondary}; }
QPushButton#ThemeOptionButton { text-align: left; max-width: 360px; min-height: 34px; }
QPushButton#ThemeOptionButton:checked { border: 1px solid {accent}; background: {selected}; }
QLabel#PageTitle { color: {text_primary}; font-size: 22px; font-weight: 650; }
QLabel#PageSubtitle, QLabel#CorrelationDisclaimer, QLabel#CorrelationElementCounts,
QLabel#CorrelationRelationLabel, QLabel#CorrelationProvenance,
QLabel#CorrelationFileExtension, QLabel#CorrelationRawValue { color: {text_secondary}; }
QLabel#CorrelationDetailValue { color: {text_primary}; font-size: 18px; font-weight: 600; }
QLabel#CorrelationElementTitle { color: {text_primary}; font-weight: 400; font-size: 14px; }
QLabel#CorrelationElementCategory {
    color: {text_muted}; font-size: 10px; font-weight: 500; letter-spacing: 0.7px;
}
QFrame#CorrelationSummaryMetrics {
    background: transparent; border: 0; border-top: 1px solid {border_subtle};
    border-bottom: 1px solid {border_subtle};
}
QLabel#CorrelationMetricValue { color: {text_primary}; font-size: 22px; font-weight: 600; }
QLabel#CorrelationMetricLabel, QLabel#CorrelationCoverageNote { color: {text_secondary}; }
QPushButton#CorrelationMetricButton {
    background: transparent; color: {text_primary}; border: 0;
    border-right: 1px solid {border_subtle}; border-radius: 0; text-align: left;
    padding: 0 14px; font-size: 13px;
}
QPushButton#CorrelationMetricButton:hover { background: {hover}; }
QPushButton#CorrelationSummaryRow, QPushButton#CorrelationVerificationRow {
    background: transparent; color: {text_primary}; border: 0;
    border-bottom: 1px solid {border_subtle}; border-radius: 0;
    text-align: left; padding: 9px 8px;
}
QPushButton#CorrelationSummaryRow:hover, QPushButton#CorrelationVerificationRow:hover {
    background: {hover};
}
QLabel#CorrelationCategoryLabel, QLabel#CorrelationCategoryCount {
    color: {text_primary}; background: transparent;
}
QLabel#CorrelationCategoryCount { min-width: 28px; font-weight: 600; }
QProgressBar#CorrelationCategoryBar {
    background: {surface_secondary}; border: 0; border-radius: 2px;
    min-height: 6px; max-height: 6px;
}
QProgressBar#CorrelationCategoryBar::chunk { background: {text_muted}; border-radius: 2px; }
QPushButton#CorrelationBackButton {
    background: transparent; color: {text_secondary}; border: 0;
    border-radius: 0; padding: 3px 2px; text-align: left;
}
QPushButton#CorrelationBackButton:hover { color: {text_primary}; text-decoration: underline; }
QLabel#CorrelationVerificationTitle { color: {text_primary}; font-size: 16px; font-weight: 600; }
QLabel#CorrelationVerificationState { color: {text_primary}; font-weight: 600; }
QFrame#CorrelationVerificationBlock {
    background: transparent; border: 0; border-bottom: 1px solid {border_subtle};
}
QLabel#CorrelationDeterministicState { color: {text_primary}; font-weight: 600; }
QPushButton#CorrelationElementRow {
    background: transparent; color: {text_primary}; text-align: left;
    border: 0; border-bottom: 1px solid {border_subtle}; border-radius: 0;
}
QPushButton#CorrelationElementRow QLabel { background: transparent; }
QPushButton#CorrelationElementRow:hover { background: {hover}; }
QPushButton#CorrelationElementRow:checked {
    background: {selected}; border-left: 2px solid {accent};
}
QFrame#CorrelationArtifactBlock {
    background: transparent; border: 0; border-top: 1px solid {border_subtle};
}
QPushButton#CorrelationArtifactLink, QPushButton#InlineActionButton {
    background: transparent; color: {text_primary}; border: 0; text-align: left;
    padding: 2px 0; font-weight: 500;
}
QPushButton#CorrelationArtifactLink:hover, QPushButton#InlineActionButton:hover {
    color: {accent}; text-decoration: underline;
}
QPushButton#CorrelationArtifactLink:focus, QPushButton#InlineActionButton:focus {
    border-bottom: 1px solid {accent};
}
QLabel#SectionSubtitle, QLabel#ClockLabel { color: {text_muted}; }
QFrame#Sidebar { background: {surface_secondary}; border: 0; }
QScrollArea#SidebarCaseScroll, QScrollArea#SidebarCaseScroll > QWidget > QWidget {
    background: {surface_secondary}; border: 0;
}
QScrollBar:vertical {
    background: transparent; border: 0; width: 9px; margin: 0;
}
QScrollBar:horizontal {
    background: transparent; border: 0; height: 9px; margin: 0;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: {scrollbar_thumb}; border: 0; border-radius: 3px;
}
QScrollBar::handle:vertical { min-height: 28px; }
QScrollBar::handle:horizontal { min-width: 28px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: {scrollbar_thumb_hover};
}
QScrollBar::handle:vertical:pressed, QScrollBar::handle:horizontal:pressed {
    background: {scrollbar_thumb_pressed};
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background: transparent; border: 0; width: 0; height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent; border: 0;
}
QLabel#SidebarLogoFallback { color: {text_primary}; font-size: 18px; font-weight: 700; }
QLabel#SidebarProductKind, QLabel#ResultEyebrow, QLabel#SummaryEyebrow,
QLabel#TechnicalFieldLabel, QLabel#SummarySectionTitle {
    color: {text_muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
QPushButton#SidebarActionButton, QPushButton#SidebarNavigationButton {
    background: transparent; border: 1px solid transparent; border-radius: {radius_small}px;
    color: {text_secondary};
}
QPushButton#SidebarNavigationButton {
    border: 0; border-left: 2px solid transparent; border-radius: 0; font-weight: 400;
}
QPushButton#SidebarNavigationButton:checked {
    background: {selected}; border: 0; border-left: 2px solid {accent};
    color: {text_primary}; font-weight: 500;
}
QPushButton#SidebarNavigationButton:checked QLabel#SidebarNavigationText { font-weight: 500; }
QPushButton#SidebarActionButton { border-color: {border}; }
QPushButton#SidebarActionButton:hover, QPushButton#SidebarNavigationButton:hover {
    background: {hover}; border-color: {border_subtle}; color: {text_primary};
}
QPushButton#SidebarNavigationButton:checked {
    background: {selected}; border-color: {border}; color: {text_primary};
}
QPushButton#SidebarNavigationButton:hover {
    background: {hover}; border: 0; border-left: 2px solid transparent;
}
QPushButton#SidebarNavigationButton:checked,
QPushButton#SidebarNavigationButton:checked:hover {
    background: {selected}; border: 0; border-left: 2px solid {accent};
}
QPushButton#SidebarGroupButton {
    min-height: 22px; background: transparent; border: 0; border-radius: 0;
}
QPushButton#SidebarGroupButton:hover { background: {hover}; border: 0; }
QPushButton#SidebarGroupButton:focus {
    background: transparent; border: 0; border-bottom: 1px solid {accent};
}
QLabel#SidebarNavigationIcon, QLabel#SidebarFileTypeIcon {
    color: {accent}; font-family: "Consolas", monospace; font-size: 9px; font-weight: 700;
}
QFrame#ResultHeader, QFrame#SummarySection, QFrame#findingsPreviewCard {
    background: {surface_elevated}; border: 1px solid {border}; border-radius: {radius_panel}px;
}
QLabel#ResultFileName { color: {text_primary}; font-size: 22px; font-weight: 650; }
QLabel#ResultHash, QLabel#TechnicalFieldMono {
    color: {text_primary}; font-family: "Consolas", monospace; font-size: 12px;
}
QPushButton#CopyHashButton {
    background: transparent; border: 1px solid {border}; border-radius: 3px;
    color: {accent}; min-height: 28px; padding: 0 10px; font-size: 10px; font-weight: 700;
}
QPushButton#CopyHashButton:hover { border-color: {accent}; }
QLabel#StatusIndicator { border: 1px solid {border}; border-radius: 3px; padding: 3px 7px;
    font-size: 10px; font-weight: 700; color: {text_secondary}; }
QLabel#StatusIndicator[status="completed"] { color: {success}; }
QLabel#StatusIndicator[status="partial"] { color: {warning}; }
QLabel#StatusIndicator[status="failed"] { color: {error}; }
QLabel#ForensicSummaryTitle { color: {text_primary}; font-size: 17px; font-weight: 650; }
QLabel#ForensicSummaryDescription, QLabel#TechnicalFieldValue,
QLabel#findingsPreviewSubtitle, QLabel#findingsPreviewText { color: {text_secondary}; }
QFrame#SummaryDivider { background: {border}; min-height: 1px; max-height: 1px; border: none; }
QPushButton#ArtifactNode {
    background: {surface_elevated}; border: 1px solid {border}; border-radius: {radius_panel}px;
    color: {text_secondary}; padding: 10px; text-align: left;
}
QPushButton#ArtifactNode:hover { border-color: {border_strong}; color: {text_primary}; background: {hover}; }
QPushButton#ArtifactNode:checked { border: 1px solid {accent}; color: {text_primary}; background: {selected}; }
QFrame#ComparisonPairHeader, QFrame#ComparisonDiffSection {
    background: {surface_elevated}; border: 1px solid {border}; border-radius: {radius_panel}px;
}
QFrame#ComparisonArtifactPanel { border: none; background: transparent; }
QLabel#ComparisonConnector { min-width: 54px; max-width: 54px; color: {accent}; border-left: 1px solid {border}; border-right: 1px solid {border}; font: 700 9px "Consolas"; }
QLabel#ComparisonArtifactSlot, QLabel#TechnicalMatchesTitle { color: {text_muted}; font: 700 10px "Consolas"; letter-spacing: 1px; }
QLabel#ComparisonArtifactName { color: {text_primary}; font-size: 17px; font-weight: 650; }
QLabel#ComparisonArtifactDetails { color: {text_secondary}; font-size: 11px; }
QLabel#ComparisonArtifactHash { color: {text_muted}; font: 10px "Consolas"; }
QLabel#ComparisonPairStatus { color: {accent}; font-weight: 700; }
QPushButton#ComparisonExecuteButton { min-height: 36px; font-weight: 700; }
QFrame#TechnicalMatches { border: 1px solid {border}; background: {surface_elevated}; }
QLabel#TechnicalMatchesTitle { padding: 8px 10px; }
QLabel#TechnicalMatchesCount { color: {accent}; font: 700 13px "Consolas"; padding: 8px 10px; }
QFrame#TechnicalMatchRow { border-top: 1px solid {border_subtle}; }
QLabel#TechnicalMatchKey { color: {text_muted}; font: 10px "Consolas"; }
QLabel#TechnicalMatchValue { color: {text_primary}; font-size: 11px; }
QPushButton#TechnicalMatchesToggle { border: 0; border-top: 1px solid {border}; border-radius: 0; background: transparent; color: {accent}; min-height: 28px; font: 10px "Consolas"; text-align: left; padding-left: 10px; }
QPushButton#TechnicalMatchesToggle:hover { background: {hover}; }
QLabel#ComparisonDiffTitle { color: {text_primary}; font-size: 14px; font-weight: 650; }
QPushButton#ComparisonFilterButton, QPushButton#ComparisonBackButton, QPushButton#ComparisonFocusButton, QPushButton#SidebarCollapseButton { border: 1px solid {border}; border-radius: {radius_small}px; background: transparent; color: {text_secondary}; min-height: 28px; padding: 0 10px; }
QPushButton#ComparisonFilterButton:hover, QPushButton#ComparisonBackButton:hover, QPushButton#ComparisonFocusButton:hover, QPushButton#SidebarCollapseButton:hover { background: {hover}; color: {text_primary}; }
QPushButton#ComparisonFilterButton:checked { color: {text_primary}; background: {selected}; border-bottom: 2px solid {accent}; }
QFrame#ComparisonDiffSection { margin: 0; }
QFrame#DiffField { border-top: 1px solid {border_subtle}; }
QFrame#DiffField[state="match"] { border-left: 3px solid {success}; }
QFrame#DiffField[state="changed"], QFrame#DiffField[state="left_only"], QFrame#DiffField[state="right_only"] { border-left: 3px solid {difference}; }
QLabel#DiffValueA, QLabel#DiffValueB { color: {text_primary}; font-family: "Consolas", monospace; padding: 5px 8px; }
QSplitter#ComparisonDiffSplitter::handle { background: {border}; width: 1px; }
QScrollArea#ComparisonDiffScroll, QScrollArea#ComparisonCanvas { border: 0; background: transparent; }
QWidget#SidebarFileItemWidget { border-radius: {radius_small}px; }
"""
    for name, value in values.items():
        template = template.replace(f"{{{name}}}", str(value))
    return template
