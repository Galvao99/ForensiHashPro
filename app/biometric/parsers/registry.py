from collections.abc import Mapping
from typing import Any

from app.biometric.parsers.base_parser import BaseBiometricReportParser


class BiometricParserRegistry:
    def __init__(
        self,
        parsers: list[BaseBiometricReportParser] | None = None,
    ) -> None:
        self._parsers = list(parsers or [])

    def register(self, parser: BaseBiometricReportParser) -> None:
        self._parsers.append(parser)

    def find_all(
        self, payload: Mapping[str, Any]
    ) -> list[BaseBiometricReportParser]:
        return [parser for parser in self._parsers if parser.recognizes(payload)]

