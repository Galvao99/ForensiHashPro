import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.biometric.constraint_evaluator import BiometricConstraintEvaluator
from app.biometric.parsers.registry import BiometricParserRegistry
from app.models.biometric_report import (
    BiometricConstraintEvaluation,
    BiometricReport,
)
from app.services.biometric_report_exceptions import (
    AmbiguousBiometricReportError,
    BiometricReportParsingError,
    InvalidBiometricJsonError,
    UnsupportedBiometricExtensionError,
    UnrecognizedBiometricReportError,
)


class BiometricReportService:
    def __init__(
        self,
        registry: BiometricParserRegistry,
        evaluator: BiometricConstraintEvaluator | None = None,
    ) -> None:
        self.registry = registry
        self.evaluator = evaluator or BiometricConstraintEvaluator()

    def parse(self, file_path: str | Path) -> BiometricReport:
        path = Path(file_path)
        if not path.is_file():
            raise BiometricReportParsingError(f"Arquivo não encontrado: {path}")
        if path.suffix.lower() != ".json":
            raise UnsupportedBiometricExtensionError("Somente relatórios .json são suportados.")
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise InvalidBiometricJsonError(f"JSON biométrico inválido: {error}") from error
        if not isinstance(payload, Mapping):
            raise InvalidBiometricJsonError("A raiz do relatório JSON deve ser um objeto.")
        parsers = self.registry.find_all(payload)
        if not parsers:
            raise UnrecognizedBiometricReportError("Formato biométrico não reconhecido.")
        if len(parsers) > 1:
            raise AmbiguousBiometricReportError("Mais de um parser reconheceu o relatório.")
        try:
            report = parsers[0].parse(payload)
        except Exception as error:
            raise BiometricReportParsingError(f"Falha ao interpretar relatório: {error}") from error
        report.constraint_evaluations = self._evaluate(report)
        return report

    def _evaluate(
        self,
        report: BiometricReport,
    ) -> list[BiometricConstraintEvaluation]:
        evaluations: list[BiometricConstraintEvaluation] = []
        for metric in report.metrics:
            for constraint in report.constraints:
                metric_name = metric.canonical_name or metric.original_name
                constraint_name = (
                    constraint.canonical_name or constraint.original_name
                )
                names_match = metric_name == constraint_name
                if names_match:
                    evaluations.append(self.evaluator.evaluate(metric, constraint))
        return evaluations
