import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.factory.application_factory import ApplicationFactory
from app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    style_path = Path("app/ui/style.qss")
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    service = ApplicationFactory.create_analysis_service()
    window = MainWindow(service)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()