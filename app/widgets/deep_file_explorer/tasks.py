from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str, str)
    finished = Signal()


class ExplorerTask(QRunnable):
    """Small QThreadPool task whose results are delivered on the GUI thread."""

    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = TaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.operation()
        except Exception as error:  # boundary: native/parser errors reach the UI
            category = str(getattr(error, "category", "unavailable"))
            self.signals.failed.emit(category, str(error))
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
