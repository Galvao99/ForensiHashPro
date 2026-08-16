from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.presentation.file_display import FileDisplay, build_file_displays


class FileListItemWidget(QWidget):
    """
    Widget visual utilizado em cada item da lista de arquivos.
    """

    def __init__(
        self,
        file_path: Path,
        display: FileDisplay | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.file_path = file_path
        self.display = display or build_file_displays(
            [file_path]
        )[str(file_path)]

        self.setObjectName("SidebarFileItemWidget")
        self.setAttribute(
            Qt.WA_StyledBackground,
            True,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(
            10,
            8,
            10,
            8,
        )
        root_layout.setSpacing(10)

        self.type_label = QLabel(
            self._file_type_icon()
        )
        self.type_label.setObjectName(
            "SidebarFileTypeIcon"
        )
        self.type_label.setFixedSize(
            32,
            32,
        )
        self.type_label.setAlignment(
            Qt.AlignCenter
        )

        information_layout = QVBoxLayout()
        information_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        information_layout.setSpacing(3)

        self.name_label = QLabel(
            self.display.display_name
        )
        self.name_label.setObjectName(
            "SidebarFileName"
        )
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(38)

        self.details_label = QLabel(
            f"{self.display.display_origin}  •  {self._build_details()}"
        )
        self.details_label.setObjectName(
            "SidebarFileDetails"
        )

        information_layout.addWidget(
            self.name_label
        )
        information_layout.addWidget(
            self.details_label
        )

        root_layout.addWidget(
            self.type_label,
            alignment=Qt.AlignTop,
        )

        root_layout.addLayout(
            information_layout,
            stretch=1,
        )

        tooltip = (
            f"{self.display.display_name} — "
            f"{self.display.display_origin}"
        )

        self.setToolTip(tooltip)
        self.name_label.setToolTip(tooltip)
        self.details_label.setToolTip(tooltip)

    def _build_details(self) -> str:
        extension = (
            self.file_path.suffix
            .replace(".", "")
            .upper()
        )

        if not extension:
            extension = "SEM EXTENSÃO"

        try:
            size = self.file_path.stat().st_size
            formatted_size = self._format_size(size)
        except OSError:
            formatted_size = "Tamanho indisponível"

        return (
            f"{extension}  •  {formatted_size}"
        )

    def _file_type_icon(self) -> str:
        extension = (
            self.file_path.suffix.lower()
        )

        text_extensions = {".txt", ".csv", ".xml", ".log"}

        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".tif",
            ".tiff",
        }

        archive_extensions = {
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
        }

        if extension == ".pdf":
            return "PDF"

        if extension in image_extensions:
            return extension.removeprefix(".").upper()[:4]

        if extension in archive_extensions:
            return "ZIP"

        if extension in text_extensions:
            return "TXT"

        if extension == ".json":
            return "JSON"

        if extension in {".html", ".htm"}:
            return "HTML"

        if extension in {".doc", ".docx"}:
            return "DOC"

        if extension in {".xls", ".xlsx"}:
            return "XLS"

        if extension in {".ppt", ".pptx"}:
            return "PPT"

        return "FILE"

    @staticmethod
    def _format_size(size: int) -> str:
        units = (
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        )

        value = float(size)

        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"

                return (
                    f"{value:.2f} {unit}"
                    .replace(".", ",")
                )

            value /= 1024

        return f"{size} B"


class FileList(QListWidget):
    """
    Lista de arquivos carregados na análise.
    """

    file_count_changed = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName(
            "SidebarFileList"
        )

        self.setSpacing(4)
        self.setUniformItemSizes(False)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.setSelectionMode(
            QListWidget.SingleSelection
        )

    def add_file(
        self,
        file_path: Path,
        display: FileDisplay | None = None,
    ) -> None:
        normalized_path = Path(file_path)

        item = QListWidgetItem()

        item.setData(
            Qt.UserRole,
            str(normalized_path),
        )

        safe_display = display or build_file_displays(
            [normalized_path]
        )[str(normalized_path)]
        item.setToolTip(
            f"{safe_display.display_name} — "
            f"{safe_display.display_origin}"
        )

        item_widget = FileListItemWidget(
            normalized_path,
            display=safe_display,
        )

        item.setSizeHint(
            QSize(
                0,
                max(
                    64,
                    item_widget.sizeHint().height(),
                ),
            )
        )

        self.addItem(item)
        self.setItemWidget(
            item,
            item_widget,
        )

    def add_files(
        self,
        files: list[Path],
    ) -> None:
        self.clear()

        displays = build_file_displays(files)

        for file_path in files:
            self.add_file(
                file_path,
                display=displays[str(Path(file_path))],
            )

        self.file_count_changed.emit(
            self.count()
        )

        if self.count() > 0:
            self.setCurrentRow(0)

    def filter_files(
        self,
        search_text: str,
    ) -> None:
        normalized_search = (
            search_text.strip().lower()
        )

        for index in range(self.count()):
            item = self.item(index)

            raw_path = item.data(
                Qt.UserRole
            )

            if raw_path is None:
                item.setHidden(False)
                continue

            file_path = Path(str(raw_path))

            searchable_text = (
                f"{file_path.name} "
                f"{file_path.suffix} "
                f"{file_path}"
            ).lower()

            should_show = (
                not normalized_search
                or normalized_search
                in searchable_text
            )

            item.setHidden(
                not should_show
            )

    def selected_file_path(
        self,
    ) -> Path | None:
        item = self.currentItem()

        if item is None:
            return None

        raw_path = item.data(
            Qt.UserRole
        )

        if raw_path is None:
            return None

        return Path(str(raw_path))
