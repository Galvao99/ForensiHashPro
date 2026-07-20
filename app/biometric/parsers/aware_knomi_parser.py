from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any

from app.biometric.metric_normalization import (
    normalize_aware_metric,
    normalize_aware_profile_metric,
)
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
    """Adaptador para a estrutura observada no relatório Knomi real."""

    _VERSION = re.compile(
        r"^Aware (?P<product>.+?), version "
        r"(?P<version>\S+) (?P<revision>r\d+)$"
    )

    def __init__(self, profile_parser: ProfileParser | None = None) -> None:
        self.profile_parser = profile_parser or ProfileParser(
            normalize_aware_profile_metric
        )

    def recognizes(self, payload: Mapping[str, Any]) -> bool:
        input_data = self._mapping(payload.get("input"))
        workflow_data = self._mapping(input_data.get("workflow_data"))
        result = self._mapping(payload.get("result"))
        signals = (
            "KnomiFaceLiveness" in str(payload.get("faceliveness_version", "")),
            payload.get("server") == "face_liveness",
            payload.get("task") == "analyze_video",
            bool(workflow_data),
            isinstance(result.get("algorithm_results"), list),
            isinstance(result.get("liveness_result"), Mapping),
            isinstance(result.get("captured_frame_metrics_result"), list),
        )
        return sum(signals) >= 5 and all(signals[1:4])

    def parse(self, payload: Mapping[str, Any]) -> BiometricReport:
        input_data = self._mapping(payload.get("input"))
        workflow_data = self._mapping(input_data.get("workflow_data"))
        result = self._mapping(payload.get("result"))
        face_version = self._version(payload.get("faceliveness_version"))
        video_version = self._version(
            payload.get("video_version"),
            include_provider=True,
        )
        configured = self._configured_algorithms(workflow_data.get("algorithms"))
        thresholds = {
            algorithm.original_name: algorithm.threshold
            for algorithm in configured
        }
        returned = self._algorithm_results(
            result.get("algorithm_results"), thresholds
        )
        report = BiometricReport(
            provider="Aware",
            product=face_version.get("product"),
            version=face_version.get("version"),
            workflow=self._text(workflow_data.get("workflow")),
            algorithms=[*configured, *returned],
            metrics=self._metrics(result.get("captured_frame_metrics_result")),
            raw_payload=payload,
        )
        report.metadata = self._metadata(
            payload, workflow_data, result, face_version, video_version
        )
        self._timestamps(payload, workflow_data, report)
        report.decisions = self._liveness(result.get("liveness_result"))
        report.evidences = self._evidences(
            payload.get("images"), workflow_data.get("frames")
        )
        self._profile(workflow_data.get("profile"), report)
        return report

    def _metadata(
        self,
        payload: Mapping[str, Any],
        workflow: Mapping[str, Any],
        result: Mapping[str, Any],
        face_version: dict[str, str | None],
        video_version: dict[str, str | None],
    ) -> dict[str, Any]:
        excluded = {"algorithms", "frames", "profile"}
        return {
            "faceliveness_library": face_version,
            "video_library": video_version,
            "faceliveness_version_raw": payload.get("faceliveness_version"),
            "video_version_raw": payload.get("video_version"),
            "profile_name": self._mapping(workflow.get("profile")).get("name"),
            "workflow_parameters": {
                key: value for key, value in workflow.items() if key not in excluded
            },
            "images_count": self._mapping(payload.get("images")).get("count"),
            "autocapture": dict(self._mapping(result.get("autocapture_result"))),
        }

    def _configured_algorithms(self, value: Any) -> list[BiometricAlgorithmResult]:
        algorithms: list[BiometricAlgorithmResult] = []
        for index, item in enumerate(self._list(value)):
            if not isinstance(item, Mapping) or not self._text(item.get("name")):
                continue
            algorithms.append(
                BiometricAlgorithmResult(
                    original_name=str(item["name"]),
                    category="configured",
                    threshold=self._number(item.get("threshold")),
                    source_path=f"$.input.workflow_data.algorithms[{index}]",
                    raw_data=item,
                )
            )
        return algorithms

    def _algorithm_results(
        self,
        value: Any,
        thresholds: Mapping[str, float | None],
    ) -> list[BiometricAlgorithmResult]:
        algorithms: list[BiometricAlgorithmResult] = []
        for index, item in enumerate(self._list(value)):
            if not isinstance(item, Mapping) or not self._text(item.get("name")):
                continue
            name = str(item["name"])
            score = self._number(item.get("score"))
            algorithms.append(
                BiometricAlgorithmResult(
                    original_name=name,
                    value=item.get("score"),
                    score=score,
                    threshold=thresholds.get(name),
                    feedback=self._list(item.get("feedback")),
                    category="result",
                    source_path=f"$.result.algorithm_results[{index}]",
                    raw_data=item,
                )
            )
        return algorithms

    def _liveness(self, value: Any) -> list[BiometricDecision]:
        item = self._mapping(value)
        if not item or "decision" not in item:
            return []
        return [
            BiometricDecision(
                original_name="liveness_result",
                value=item.get("decision"),
                source_path="$.result.liveness_result",
                metadata={
                    "score": item.get("score"),
                    "score_frr": item.get("score_frr"),
                    "feedback": item.get("feedback"),
                },
                raw_data=item,
            )
        ]

    def _metrics(self, value: Any) -> list[BiometricMetric]:
        metrics: list[BiometricMetric] = []
        for index, item in enumerate(self._list(value)):
            if not isinstance(item, Mapping) or not self._text(item.get("name")):
                continue
            name = str(item["name"])
            canonical, unit = normalize_aware_metric(name)
            metrics.append(
                BiometricMetric(
                    original_name=name,
                    canonical_name=canonical,
                    value=item.get("score"),
                    canonical_unit=unit,
                    category=self._text(item.get("category")),
                    original_category=self._text(item.get("category")),
                    source_path=f"$.result.captured_frame_metrics_result[{index}]",
                    raw_data=item,
                )
            )
        return metrics

    def _evidences(self, images: Any, frames: Any) -> list[BiometricEvidence]:
        image_data = self._mapping(images)
        reference = self._text(image_data.get("path"))
        if reference is None:
            return []
        return [
            BiometricEvidence(
                evidence_type="face_image",
                original_reference=reference,
                file_name=PurePath(reference).name or None,
                metadata={
                    "count": image_data.get("count"),
                    "frames": self._list(frames),
                },
                source_path="$.images.path",
                raw_data=images,
            )
        ]

    def _profile(self, value: Any, report: BiometricReport) -> None:
        profile = self._mapping(value)
        xml = profile.get("xml")
        report.has_profile = isinstance(xml, str) and bool(xml.strip())
        if not report.has_profile:
            return
        report.evidences.append(
            BiometricEvidence(
                evidence_type="profile_xml",
                original_reference="embedded:input.workflow_data.profile.xml",
                source_path="$.input.workflow_data.profile.xml",
                raw_data=xml,
            )
        )
        try:
            report.constraints = self.profile_parser.parse(xml)
        except ProfileParseError as error:
            report.warnings.append(str(error))

    def _timestamps(
        self,
        payload: Mapping[str, Any],
        workflow: Mapping[str, Any],
        report: BiometricReport,
    ) -> None:
        analysis_date = self._timestamp(payload.get("date"), milliseconds=True)
        if analysis_date:
            report.analysis_date = analysis_date
            report.timestamps["date"] = analysis_date
        workflow_time = self._timestamp(workflow.get("timestamp"), milliseconds=True)
        if workflow_time:
            report.timestamps["workflow.timestamp"] = workflow_time
        for index, frame in enumerate(self._list(workflow.get("frames"))):
            if not isinstance(frame, Mapping):
                continue
            timestamp = self._timestamp(frame.get("timestamp"), milliseconds=False)
            if timestamp:
                report.timestamps[f"workflow.frames[{index}].timestamp"] = timestamp

    @classmethod
    def _version(
        cls,
        value: Any,
        *,
        include_provider: bool = False,
    ) -> dict[str, str | None]:
        raw = cls._text(value)
        match = cls._VERSION.fullmatch(raw or "")
        if match is None:
            return {"product": None, "version": None, "revision": None, "raw": raw}
        parts = match.groupdict()
        if include_provider:
            parts["product"] = f"Aware {parts['product']}"
        return {**parts, "raw": raw}

    @staticmethod
    def _timestamp(value: Any, *, milliseconds: bool) -> datetime | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        divisor = 1000 if milliseconds else 1
        return datetime.fromtimestamp(value / divisor, tz=timezone.utc)

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
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
