import pytest
from PySide6.QtWidgets import QApplication

from app.widgets.technical_timeline import TimelineSidePanel


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_timeline_side_panel_accepts_mixed_naive_and_aware_datetimes(qt_app) -> None:
    panel = TimelineSidePanel()
    events = [
        {"timestamp": "2023-01-26T15:50:00", "category": "Criação"},
        {"timestamp": "2023-01-26T15:50:00Z", "category": "Modificação"},
        {"timestamp": "2023-01-26T16:50:00-03:00", "category": "Sistema"},
        {"timestamp": "invalid", "category": "Sistema"},
    ]

    panel.update_summary(events)

    assert "Primeiro evento" in panel.period.content.text()
    assert "Último evento" in panel.period.content.text()
