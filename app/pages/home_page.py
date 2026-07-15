from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation.file_display import folder_display_origin


class HomePage(QWidget):
    """
    Área inicial do ForensiHash.

    É exibida enquanto nenhuma página de análise foi escolhida
    no menu lateral.
    """

    open_file_requested = Signal()
    open_folder_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("HomePage")

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 28, 28, 28)
        root_layout.setSpacing(22)

        root_layout.addWidget(
            self._build_welcome_card()
        )

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)

        content_layout.addWidget(
            self._build_quick_actions(),
            stretch=1,
        )

        content_layout.addWidget(
            self._build_workspace_summary(),
            stretch=1,
        )

        root_layout.addLayout(content_layout)
        root_layout.addStretch()

    def _build_welcome_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("HomeHeroCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)

        badge = QLabel("FORENSIHASH PRO")
        badge.setObjectName("HomeHeroBadge")

        title = QLabel(
            "Investigação técnica de arquivos"
        )
        title.setObjectName("HomeHeroTitle")

        subtitle = QLabel(
            "Abra um arquivo ou uma pasta para iniciar a análise. "
            "Os resultados serão organizados em hashes, metadados, "
            "vestígios, OCR, timeline, assinatura digital e contexto de rede."
        )
        subtitle.setObjectName("HomeHeroSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(760)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        open_file_button = QPushButton(
            "Abrir arquivo"
        )
        open_file_button.setObjectName(
            "HomePrimaryButton"
        )
        open_file_button.clicked.connect(
            self.open_file_requested.emit
        )

        open_folder_button = QPushButton(
            "Abrir pasta"
        )
        open_folder_button.setObjectName(
            "HomeSecondaryButton"
        )
        open_folder_button.clicked.connect(
            self.open_folder_requested.emit
        )

        actions_layout.addWidget(open_file_button)
        actions_layout.addWidget(open_folder_button)
        actions_layout.addStretch()

        layout.addWidget(badge)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addLayout(actions_layout)

        return card

    def _build_quick_actions(self) -> QWidget:
        card = QFrame()
        card.setObjectName("HomeInfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Como começar")
        title.setObjectName("HomeCardTitle")

        file_item = self._create_instruction(
            "1",
            "Arquivo individual",
            "Analise um PDF, imagem, JSON ou outro arquivo isoladamente.",
        )

        folder_item = self._create_instruction(
            "2",
            "Conjunto de evidências",
            "Abra uma pasta para correlacionar hashes, datas e informações entre arquivos.",
        )

        investigation_item = self._create_instruction(
            "3",
            "Navegação técnica",
            "Use o menu lateral para acessar cada camada da análise.",
        )

        layout.addWidget(title)
        layout.addWidget(file_item)
        layout.addWidget(folder_item)
        layout.addWidget(investigation_item)
        layout.addStretch()

        return card

    def _build_workspace_summary(self) -> QWidget:
        card = QFrame()
        card.setObjectName("HomeInfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Área de trabalho")
        title.setObjectName("HomeCardTitle")

        self.workspace_status = QLabel(
            "Nenhum arquivo ou pasta foi aberto."
        )
        self.workspace_status.setObjectName(
            "HomeWorkspaceStatus"
        )
        self.workspace_status.setWordWrap(True)

        self.workspace_details = QLabel(
            "Os arquivos analisados aparecerão no explorador lateral."
        )
        self.workspace_details.setObjectName(
            "HomeWorkspaceDetails"
        )
        self.workspace_details.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.workspace_status)
        layout.addWidget(self.workspace_details)
        layout.addStretch()

        return card

    def _create_instruction(
        self,
        number: str,
        title: str,
        description: str,
    ) -> QWidget:
        container = QWidget()
        container.setObjectName("HomeInstructionItem")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        number_label = QLabel(number)
        number_label.setObjectName(
            "HomeInstructionNumber"
        )
        number_label.setAlignment(Qt.AlignCenter)
        number_label.setFixedSize(30, 30)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName(
            "HomeInstructionTitle"
        )

        description_label = QLabel(description)
        description_label.setObjectName(
            "HomeInstructionDescription"
        )
        description_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)

        layout.addWidget(
            number_label,
            alignment=Qt.AlignTop,
        )
        layout.addLayout(text_layout, stretch=1)

        return container

    def update_workspace(
        self,
        *,
        file_name: str | None = None,
        file_count: int = 0,
        folder_path: str | None = None,
    ) -> None:
        if file_name:
            self.workspace_status.setText(
                f"Arquivo selecionado: {file_name}"
            )

            self.workspace_details.setText(
                "Selecione uma página no menu lateral "
                "para visualizar os resultados da análise."
            )

            return

        if folder_path:
            self.workspace_status.setText(
                f"Pasta aberta com {file_count} arquivo(s)."
            )

            self.workspace_details.setText(
                folder_display_origin(folder_path)
            )

            return

        self.workspace_status.setText(
            "Nenhum arquivo ou pasta foi aberto."
        )

        self.workspace_details.setText(
            "Os arquivos analisados aparecerão no explorador lateral."
        )
