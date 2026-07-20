import math

from app.models.biometric_report import (
    BiometricConstraint,
    BiometricConstraintEvaluation,
    BiometricMetric,
    ConstraintEvaluationStatus,
)


class BiometricConstraintEvaluator:
    def __init__(self, *, relative_tolerance: float = 1e-9, absolute_tolerance: float = 1e-9) -> None:
        if relative_tolerance < 0 or absolute_tolerance < 0:
            raise ValueError("As tolerâncias não podem ser negativas.")
        self.relative_tolerance = relative_tolerance
        self.absolute_tolerance = absolute_tolerance

    def evaluate(
        self, metric: BiometricMetric, constraint: BiometricConstraint
    ) -> BiometricConstraintEvaluation:
        value = self._number(metric.value)
        tolerance = max(self.relative_tolerance, self.absolute_tolerance)
        if value is None:
            return self._result(metric, constraint, ConstraintEvaluationStatus.NOT_EVALUATED, "Valor observado ausente ou não numérico.", tolerance)
        metric_unit = metric.canonical_unit or metric.original_unit
        constraint_unit = constraint.canonical_unit or constraint.original_unit
        if metric_unit and constraint_unit and metric_unit != constraint_unit:
            return self._result(metric, constraint, ConstraintEvaluationStatus.NOT_EVALUATED, "Unidades incompatíveis.", tolerance)
        if constraint.minimum is not None and value < constraint.minimum and not self._close(value, constraint.minimum):
            return self._result(metric, constraint, ConstraintEvaluationStatus.BELOW_MINIMUM, "Valor observado abaixo do mínimo configurado.", tolerance)
        if constraint.maximum is not None and value > constraint.maximum and not self._close(value, constraint.maximum):
            return self._result(metric, constraint, ConstraintEvaluationStatus.ABOVE_MAXIMUM, "Valor observado acima do máximo configurado.", tolerance)
        if constraint.preferred is not None and self._close(value, constraint.preferred):
            return self._result(metric, constraint, ConstraintEvaluationStatus.PREFERRED, "Valor observado compatível com o preferencial.", tolerance)
        if constraint.minimum is None and constraint.maximum is None and constraint.preferred is None:
            return self._result(metric, constraint, ConstraintEvaluationStatus.NOT_EVALUATED, "Restrição sem limites numéricos utilizáveis.", tolerance)
        return self._result(metric, constraint, ConstraintEvaluationStatus.WITHIN_RANGE, "Valor observado dentro dos limites configurados.", tolerance)

    def _close(self, left: float, right: float) -> bool:
        return math.isclose(left, right, rel_tol=self.relative_tolerance, abs_tol=self.absolute_tolerance)

    @staticmethod
    def _number(value):
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result(metric, constraint, status, justification, tolerance):
        return BiometricConstraintEvaluation(
            metric=metric,
            constraint=constraint,
            observed_value=metric.value,
            unit=metric.canonical_unit or metric.original_unit,
            status=status,
            justification=justification,
            tolerance=tolerance,
        )
