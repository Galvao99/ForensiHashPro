from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

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
)

LIGHT_THEME = ThemeTokens(
    name="light",
    background="#FFFFFF",
    surface="#F7F7F7",
    surface_raised="#FFFFFF",
    border="#D2D2D2",
    border_strong="#8D8D8D",
    text_primary="#111111",
    text_secondary="#595959",
    text_muted="#6B6B6B",
    accent="#155AA8",
    success="#14733C",
    warning="#8A5A00",
    error="#A4262C",
    surface_secondary="#F7F7F7",
    surface_elevated="#FFFFFF",
    border_subtle="#E4E4E4",
    difference="#155AA8",
    hover="#EFEFEF",
    selected="#EAF2FA",
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
        f"web/frontend/public/assets/{filename}"
    )
    return candidate if candidate.is_file() else None


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
    }
    for legacy, replacement in replacements.items():
        base = base.replace(legacy, replacement)
    return base


def _phase_one_stylesheet(tokens: ThemeTokens) -> str:
    values = asdict(tokens)
    template = r"""
/* Phase 1: shared ForensiHash result language. */
QWidget#Content, QWidget#DashboardContent, QScrollArea#DashboardScroll,
QScrollArea#DashboardScroll > QWidget > QWidget {
    background: {background};
}
QLabel#PageTitle { color: {text_primary}; font-size: 22px; font-weight: 650; }
QLabel#SectionSubtitle, QLabel#ClockLabel { color: {text_muted}; }
QFrame#Sidebar { background: {surface_secondary}; border-right: 1px solid {border}; }
QLabel#SidebarLogoFallback { color: {text_primary}; font-size: 18px; font-weight: 700; }
QLabel#SidebarProductKind, QLabel#ResultEyebrow, QLabel#SummaryEyebrow,
QLabel#TechnicalFieldLabel, QLabel#SummarySectionTitle {
    color: {text_muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
QPushButton#SidebarActionButton, QPushButton#SidebarNavigationButton {
    background: transparent; border: 1px solid transparent; border-radius: {radius_small}px;
    color: {text_secondary};
}
QPushButton#SidebarActionButton { border-color: {border}; }
QPushButton#SidebarActionButton:hover, QPushButton#SidebarNavigationButton:hover {
    background: {hover}; border-color: {border_subtle}; color: {text_primary};
}
QPushButton#SidebarNavigationButton:checked {
    background: {selected}; border-color: {border}; color: {text_primary};
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
