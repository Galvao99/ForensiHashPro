import math
from collections.abc import Mapping

import pytest

from app.biometric.constraint_evaluator import BiometricConstraintEvaluator
from app.biometric.parsers.base_parser import BaseBiometricReportParser
from app.biometric.parsers.registry import BiometricParserRegistry
from app.biometric.profile_parser import ProfileParseError, ProfileParser
from app.models.biometric_report import (
    BiometricConstraint,
    BiometricMetric,
    BiometricReport,
    ConstraintEvaluationStatus,
)


class _Parser(BaseBiometricReportParser):
    def __init__(self, recognized: bool = True) -> None:
        self.recognized = recognized

    def recognizes(self, payload: Mapping) -> bool:
        return self.recognized

    def parse(self, payload: Mapping) -> BiometricReport:
        return BiometricReport(raw_payload=payload)


def test_model_defaults_are_independent_and_payload_is_preserved() -> None:
    payload = {"original": [1]}
    first = BiometricReport(raw_payload=payload)
    second = BiometricReport()
    first.warnings.append("warning")
    assert second.warnings == []
    assert first.raw_payload is payload


def test_registry_registration_order_none_one_and_two() -> None:
    payload = {"value": 1}
    registry = BiometricParserRegistry()
    assert registry.find_all(payload) == []
    first = _Parser()
    second = _Parser()
    registry.register(first)
    assert registry.find_all(payload) == [first]
    registry.register(second)
    assert registry.find_all(payload) == [first, second]


def test_profile_absent_empty_valid_escaped_and_malformed() -> None:
    parser = ProfileParser(lambda name: ("image.width_pixels", "pixels"))
    assert parser.parse(None) == []
    assert parser.parse(" ") == []
    xml = '<profile><metric name="imageWidth" min="1" preferred="2" max="3" unit="pixels"/></profile>'
    for value in (xml, xml.replace("<", "&lt;").replace(">", "&gt;")):
        constraint = parser.parse(value)[0]
        assert (constraint.minimum, constraint.preferred, constraint.maximum) == (1, 2, 3)
        assert constraint.raw_data["name"] == "imageWidth"
    with pytest.raises(ProfileParseError):
        parser.parse("<profile>")
    with pytest.raises(ProfileParseError):
        parser.parse('<!DOCTYPE x [<!ENTITY e SYSTEM "file:///x">]><x/>')
    with pytest.raises(ProfileParseError):
        parser.parse('<profile><metric name="x" min="bad"/></profile>')
    with pytest.raises(ProfileParseError):
        parser.parse('<profile><metric name="x" min="2" max="1"/></profile>')


@pytest.mark.parametrize(
    ("value", "unit", "minimum", "preferred", "maximum", "status"),
    [
        (0, "pixels", 1, 2, 3, ConstraintEvaluationStatus.BELOW_MINIMUM),
        (1.5, "pixels", 1, 2, 3, ConstraintEvaluationStatus.WITHIN_RANGE),
        (2, "pixels", 1, 2, 3, ConstraintEvaluationStatus.PREFERRED),
        (4, "pixels", 1, 2, 3, ConstraintEvaluationStatus.ABOVE_MAXIMUM),
        (None, "pixels", 1, 2, 3, ConstraintEvaluationStatus.NOT_EVALUATED),
        (2, "bytes", 1, 2, 3, ConstraintEvaluationStatus.NOT_EVALUATED),
    ],
)
def test_constraint_states(value, unit, minimum, preferred, maximum, status) -> None:
    metric = BiometricMetric("width", value, original_unit=unit)
    constraint = BiometricConstraint(
        "width", minimum=minimum, preferred=preferred, maximum=maximum,
        original_unit="pixels",
    )
    assert BiometricConstraintEvaluator().evaluate(metric, constraint).status is status


def test_float_tolerance_is_explicit() -> None:
    evaluator = BiometricConstraintEvaluator(absolute_tolerance=1e-8)
    result = evaluator.evaluate(
        BiometricMetric("metric", 0.1 + 0.2),
        BiometricConstraint("metric", preferred=0.3),
    )
    assert result.status is ConstraintEvaluationStatus.PREFERRED
    assert math.isclose(result.tolerance or 0, 1e-8)
