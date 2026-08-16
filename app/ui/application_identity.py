from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from app.settings import ApplicationPaths


APPLICATION_NAME = "ForensiHash Pro"
WINDOWS_APP_USER_MODEL_ID = "ForensiHash.Pro.Desktop"
APPLICATION_ICON_RESOURCE = "web/frontend/public/assets/forensihash_icon.png"


def application_icon_path(paths: ApplicationPaths | None = None) -> Path | None:
    """Resolve o ícone oficial sem depender do current working directory."""
    candidate = (paths or ApplicationPaths.discover()).resource(
        APPLICATION_ICON_RESOURCE
    )
    return candidate if candidate.is_file() else None


def application_icon(paths: ApplicationPaths | None = None) -> QIcon:
    icon_path = application_icon_path(paths)
    return QIcon(str(icon_path)) if icon_path is not None else QIcon()


def configure_windows_app_user_model_id() -> bool:
    """Associa taskbar/Alt+Tab à aplicação quando executada no Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            WINDOWS_APP_USER_MODEL_ID
        )
    except (AttributeError, OSError):
        return False
    return True
