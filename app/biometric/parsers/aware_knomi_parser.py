from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import PurePath
from typing import Any

from app.biometric.metric_normalization import normalize_aware_metric
from app.biometric.parsers.base_parser import BaseBiometricReportParser
from app.biometric.profile_parser import ProfileParseError, ProfileParser
from app.models.biometric_report import (
    BiometricAlgorithmResult,
    BiometricDecision,
    BiometricEvidence,
    BiometricMetric,
    BiometricReport,
)


class AwareKnomiReportParser(BaseBiometricReportParser):
    """Adaptador conservador para a estrutura Knomi suportada nesta versão."""

    def __init__(self, profile_parser: ProfileParser | None = None) -> None:
        self.profile_parser = profile_parser or ProfileParser(normalize_aware_metric)

    def recognizes(self, payload: Mapping[str, Any]) -> bool:
        transaction = payload.get("transaction")
        if not isinstance(transaction, Mapping):
            return False
        provider = str(transaction.get("provider", "")).strip().casefold()
        product = str(transaction.get("product", "")).strip().casefold()
        has_report_structure = any(
            key in payload for key in ("decisions", "algorithms", "profileXml")
        )
        return provider == "aware" and "knomi" in product and has_report_structure

    def parse(self, payload: Mapping[str, Any]) -> BiometricReport:
        transaction = self._mapping(payload.get("transaction"))
        report = BiometricReport(
            provider=self._text(transaction.get("provider")),
            product=self._text(transaction.get("product")),
            version=self._text(transaction.get("version")),
            workflow=self._text(transaction.get("workflow")),
            raw_payload=payload,
        )
        self._timestamps(transaction, report)
        report.decisions = self._decisions(payload.get("decisions"))
        report.algorithms = self._algorithms(payload.get("algorithms"))
        report.metrics = self._metrics(payload.get("metrics"), "$.metrics")
        report.metrics.extend(
            metric
            for algorithm in report.algorithms
            for metric in algorithm.metrics
        )
        report.evidences = self._evidences(payload.get("evidence"))

        profile_xml = payload.get("profileXml")
        report.has_profile = isinstance(profile_xml, str) and bool(profile_xml.strip())
        if report.has_profile:
            report.evidences.append(
                BiometricEvidence(
                    evidence_type="profile_xml",
                    original_reference="embedded:profileXml",
                    source_path="$.profileXml",
                    raw_data=profile_xml,
                )
            )
            try:
                report.constraints = self.profile_parser.parse(profile_xml)
            except ProfileParseError as error:
                report.warnings.append(str(error))
        return report

    def _timestamps(self, transaction: Mapping[str, Any], report: BiometricReport) -> None:
        for key, value in transaction.items():
            if key not in {"analysisDate", "createdAt", "completedAt"} or not isinstance(value, str):
                continue
            parsed = self._datetime(value)
            if parsed is None:
                report.timestamps[key] = value
                report.warnings.append(f"Timestamp inválido preservado em $.transaction.{key}.")
                continue
            report.timestamps[key] = parsed
            if key == "analysisDate":
                report.analysis_date = parsed

    def _decisions(self, value: Any) -> list[BiometricDecision]:
        decisions: list[BiometricDecision] = []
        for index, item in enumerate(self._list(value)):
            if not isinstance(item, Mapping):
                continue
            name = self._text(item.get("type") or item.get("name"))
            if not name:
                continue
            decisions.append(BiometricDecision(
                original_name=name,
                value=item.get("value", item.get("result")),
                category=self._text(item.get("category")),
                source_path=f"$.decisions[{index}]",
                raw_data=item,
            ))
        return decisions

    def _algorithms(self, value: Any) -> list[BiometricAlgorithmResult]:
        algorithms: list[BiometricAlgorithmResult] = []
        for index, item in enumerate(self._list(value)):
            if not isinstance(item, Mapping):
                continue
            name = self._text(item.get("name"))
            if not name:
                continue
            result = item.get("result", item.get("score"))
            algorithms.append(BiometricAlgorithmResult(
                original_name=name,
                value=result,
                version=self._text(item.get("version")),
                source_path=f"$.algorithms[{index}]",
                metrics=self._metrics(item.get("metrics"), f"$.algorithms[{index}].metrics"),
                raw_data=item,
            ))
        return algorithms

    def _metrics(self, value: Any, base_path: str) -> list[BiometricMetric]:
        if not isinstance(value, Mapping):
            return []
        metrics: list[BiometricMetric] = []
        for name, raw in value.items():
            details = raw if isinstance(raw, Mapping) else {"value": raw}
            canonical, default_unit = normalize_aware_metric(str(name))
            original_unit = self._text(details.get("unit"))
            metrics.append(BiometricMetric(
                original_name=str(name),
                canonical_name=canonical,
                value=details.get("value"),
                original_unit=original_unit,
                canonical_unit=default_unit if not original_unit or original_unit == default_unit else None,
                source_path=f"{base_path}.{name}",
                raw_data=raw,
            ))
        return metrics

    def _evidences(self, value: Any) -> list[BiometricEvidence]:
        evidences: list[BiometricEvidence] = []
        for index, item in enumerate(self._list(value)):
            if not isinstance(item, Mapping):
                continue
            reference = self._text(item.get("reference"))
            if not reference:
                continue
            evidences.append(BiometricEvidence(
                evidence_type=self._text(item.get("type")) or "unknown",
                original_reference=reference,
                file_name=PurePath(reference).name or None,
                mime_type=self._text(item.get("mimeType")),
                size_bytes=item.get("sizeBytes") if isinstance(item.get("sizeBytes"), int) else None,
                source_path=f"$.evidence[{index}]",
                raw_data=item,
            ))
        return evidences

    @staticmethod
    def _datetime(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _text(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None
