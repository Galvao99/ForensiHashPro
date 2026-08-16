import sys

from PySide6.QtWidgets import QApplication

from app.factory.application_factory import ApplicationFactory
from app.ui.main_window import MainWindow
from app.ui.theme import load_desktop_stylesheet
from app.ui.application_identity import (
    APPLICATION_NAME,
    application_icon,
    configure_windows_app_user_model_id,
)
from app.settings import ApplicationPaths


def main() -> None:
    configure_windows_app_user_model_id()
    app = QApplication(sys.argv)

    paths = ApplicationPaths.discover()
    app.setApplicationName(APPLICATION_NAME)
    app.setOrganizationName("ForensiHash")
    app.setWindowIcon(application_icon(paths))
    app.setStyleSheet(load_desktop_stylesheet(paths))

    service = ApplicationFactory.create_analysis_service()
    window = MainWindow(service)
    window.setWindowIcon(app.windowIcon())
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
