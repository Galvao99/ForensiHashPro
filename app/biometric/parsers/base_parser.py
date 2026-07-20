from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from app.models.biometric_report import BiometricReport


class BaseBiometricReportParser(ABC):
    @abstractmethod
    def recognizes(self, payload: Mapping[str, Any]) -> bool:
        ...

    @abstractmethod
    def parse(self, payload: Mapping[str, Any]) -> BiometricReport:
        ...

