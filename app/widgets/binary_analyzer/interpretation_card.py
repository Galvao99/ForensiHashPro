from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.models import MagicNumberResult


class InterpretationCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BinaryCard")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Interpretação Forense")
        title.setObjectName("CardTitle")

        self.text = QLabel("Nenhuma análise disponível.")
        self.text.setObjectName("CardContent")
        self.text.setWordWrap(True)

        self.conclusion = QLabel("")
        self.conclusion.setObjectName("ConclusionBox")
        self.conclusion.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.text)
        layout.addWidget(self.conclusion)

    def update_result(self, result: MagicNumberResult) -> None:
        lines = []

        for item in result.forensic_interpretation:
            lines.append(f"✅ {item}")

        if not lines:
            lines.append("Nenhuma interpretação adicional foi gerada.")

        self.text.setText("\n".join(lines))
        self.conclusion.setText(f"Conclusão:\n{result.conclusion}")