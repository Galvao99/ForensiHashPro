from app.widgets.file_list import FileList
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QFrame,
    QVBoxLayout,
)


class Sidebar(QFrame):
    """
    Barra lateral principal.
    """

    def __init__(self):

        super().__init__()

        files_title = QLabel("Arquivos")
        files_title.setObjectName("SidebarSectionTitle")

        self.file_list = FileList()

        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout()

        layout.setContentsMargins(16, 20, 16, 20)

        layout.setSpacing(12)

        title = QLabel("ForensiHash")
        title.setObjectName("SidebarTitle")

        subtitle = QLabel("PRO")
        subtitle.setObjectName("SidebarSubtitle")

        self.open_file_button = QPushButton("📄 Abrir Arquivo")
        self.open_folder_button = QPushButton("📁 Abrir Pasta")
        self.compare_button = QPushButton("⚖ Comparar")
        self.snapshot_button = QPushButton("📸 Snapshot")
        self.export_button = QPushButton("📤 Exportar")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addSpacing(25)

        layout.addWidget(self.open_file_button)
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.compare_button)
        layout.addWidget(self.snapshot_button)
        layout.addWidget(self.export_button)
        layout.addSpacing(20)
        layout.addWidget(files_title)
        layout.addWidget(self.file_list)

        layout.addStretch()

        self.setLayout(layout)