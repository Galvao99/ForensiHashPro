from abc import ABC, abstractmethod
from pathlib import Path

from app.models import DigitalSignatureResult


class BaseSignatureParser(ABC):
    """Classe base para todos os parsers de assinatura digital."""

    @abstractmethod
    def analyze(
        self,
        file_path: Path,
    ) -> DigitalSignatureResult:
        ...