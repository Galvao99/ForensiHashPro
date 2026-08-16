import sys

from PySide6.QtWidgets import QApplication

from app.factory.application_factory import ApplicationFactory
from app.ui.main_window import MainWindow
from app.ui.theme import load_desktop_stylesheet
from app.settings import ApplicationPaths


def main() -> None:
    app = QApplication(sys.argv)

    paths = ApplicationPaths.discover()
    app.setStyleSheet(load_desktop_stylesheet(paths))

    service = ApplicationFactory.create_analysis_service()
    window = MainWindow(service)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
