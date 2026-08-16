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


DARK_THEME = ThemeTokens(
    name="dark",
    background="#111315",
    surface="#191B1E",
    surface_raised="#1E2124",
    border="#393E43",
    border_strong="#5A6168",
    text_primary="#F0F1F2",
    text_secondary="#B8BDC2",
    text_muted="#9DA3A9",
    accent="#65A4E8",
    success="#62B989",
    warning="#D1A553",
    error="#E1767A",
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
    return f"{base}\n{_phase_one_stylesheet(tokens)}"


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
QFrame#Sidebar { background: {surface}; border-right: 1px solid {border}; }
QLabel#SidebarLogoFallback { color: {text_primary}; font-size: 18px; font-weight: 700; }
QLabel#SidebarProductKind, QLabel#ResultEyebrow, QLabel#SummaryEyebrow,
QLabel#TechnicalFieldLabel, QLabel#SummarySectionTitle {
    color: {text_muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
QPushButton#SidebarActionButton, QPushButton#SidebarNavigationButton {
    background: transparent; border: 1px solid transparent; border-radius: 4px;
    color: {text_secondary};
}
QPushButton#SidebarActionButton { border-color: {border}; }
QPushButton#SidebarActionButton:hover, QPushButton#SidebarNavigationButton:hover {
    background: {surface_raised}; border-color: {border}; color: {text_primary};
}
QPushButton#SidebarNavigationButton:checked {
    background: {surface_raised}; border-color: {border_strong}; color: {text_primary};
}
QLabel#SidebarNavigationIcon, QLabel#SidebarFileTypeIcon {
    color: {accent}; font-family: "Consolas", monospace; font-size: 9px; font-weight: 700;
}
QFrame#ResultHeader, QFrame#SummarySection, QFrame#findingsPreviewCard {
    background: {surface}; border: 1px solid {border}; border-radius: 6px;
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
"""
    for name, value in values.items():
        template = template.replace(f"{{{name}}}", str(value))
    return template
