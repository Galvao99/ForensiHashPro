from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult


class CaseOverview(QFrame):
    """Síntese factual do Caso, sem produzir novas interpretações."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("CaseOverview")
        self.title = QLabel("VISÃO GERAL DO CASO")
        self.title.setObjectName("SummaryEyebrow")
        self.case_name = QLabel("Nenhum Caso aberto")
        self.case_name.setObjectName("ForensicSummaryTitle")
        self.progress = QLabel("0 / 0 arquivos analisados")
        self.progress.setObjectName("ForensicSummaryDescription")
        self.counts = QLabel("0 pendentes · 0 em análise · 0 falhas")
        self.formats = QLabel("Formatos: —")
        self.formats.setWordWrap(True)
        self.correlation_title = QLabel("CORRELAÇÕES DO CASO")
        self.correlation_title.setObjectName("SummaryEyebrow")
        self.correlation_summary = QLabel("Nenhuma correlação disponível.")
        self.correlation_summary.setWordWrap(True)
        self.correlation_details = QLabel("")
        self.correlation_details.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(7)
        for widget in (
            self.title, self.case_name, self.progress, self.counts, self.formats,
            self.correlation_title, self.correlation_summary, self.correlation_details,
        ):
            layout.addWidget(widget)

    def update_case(
        self,
        state: dict[str, object],
        results: list[AnalysisResult],
        correlation: CorrelationResult | None,
    ) -> None:
        self.setVisible(bool(state.get("is_case", True)))
        total = int(state.get("total", 0))
        analyzed = int(state.get("analyzed", 0))
        pending = int(state.get("pending", 0))
        analyzing = int(state.get("analyzing", 0))
        failed = int(state.get("failed", 0))
        current = str(state.get("current_file", "") or "")
        self.case_name.setText(str(state.get("case_name", "Caso")))
        percentage = int((analyzed + failed) * 100 / total) if total else 0
        self.progress.setText(
            f"{analyzed} / {total} arquivos analisados · {percentage}%"
            + (f" · Analisando: {current}" if current else "")
        )
        self.counts.setText(
            f"{pending} pendentes · {analyzing} em análise · {failed} falhas"
        )
        registered_paths = state.get("file_paths")
        paths = (
            [Path(str(path)) for path in registered_paths]
            if isinstance(registered_paths, list)
            else [Path(result.file_info.path) for result in results]
        )
        distribution = Counter(
            (path.suffix.removeprefix(".").upper() or "SEM EXTENSÃO")
            for path in paths
        )
        self.formats.setText(
            "Formatos: " + (
                " · ".join(f"{kind} {count}" for kind, count in sorted(distribution.items()))
                if distribution else "—"
            )
        )
        findings = list(correlation.findings) if correlation is not None else []
        severities = Counter(str(item.severity).lower() for item in findings)
        self.correlation_summary.setText(
            f"{len(findings)} correlações · "
            f"{severities.get('warning', 0) + severities.get('critical', 0)} alertas · "
            f"{severities.get('ok', 0)} compatibilidades"
        )
        hash_matches = [
            item for item in findings if item.category == "embedded_hash_match"
        ]
        self.correlation_details.setText("\n\n".join(
            f"HASH CORRELACIONADO · {item.source_file} → {item.target_file}\n"
            f"Algoritmo: {item.metadata.get('algorithm', 'Hash')}\n"
            f"Hash declarado: {item.metadata.get('hash', '—')}\n"
            f"Hash calculado: {item.metadata.get('calculated_hash', '—')}\n"
            "Correspondência: criptográfica exata"
            for item in hash_matches
        ))
