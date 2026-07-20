from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from collections.abc import Callable

from app.models.biometric_report import BiometricConstraint


class ProfileParseError(ValueError):
    pass


class ProfileParser:
    _LIMIT_KEYS = {
        "minimum", "min", "preferred", "pref", "maximum", "max"
    }

    def __init__(
        self,
        name_normalizer: Callable[
            [str], tuple[str | None, str | None]
        ] | None = None,
    ) -> None:
        self._name_normalizer = (
            name_normalizer or self._without_normalization
        )

    def parse(self, xml_text: str | None) -> list[BiometricConstraint]:
        if not xml_text or not xml_text.strip():
            return []
        stripped = xml_text.strip()
        decoded = (
            html.unescape(stripped)
            if stripped.startswith("&lt;")
            else stripped
        )
        if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
            raise ProfileParseError("DTD e entidades não são permitidas no perfil XML.")
        try:
            root = ET.fromstring(decoded)
        except ET.ParseError as error:
            raise ProfileParseError(f"Perfil XML inválido: {error}") from error

        constraints: list[BiometricConstraint] = []
        self._walk(root, f"/{self._local(root.tag)}", constraints)
        return constraints

    def _walk(
        self,
        element: ET.Element,
        path: str,
        constraints: list[BiometricConstraint],
    ) -> None:
        attributes = {self._local(key): value for key, value in element.attrib.items()}
        lowered = {key.lower(): value for key, value in attributes.items()}
        if self._LIMIT_KEYS.intersection(lowered):
            name = attributes.get("name") or self._local(element.tag)
            canonical, canonical_unit = self._name_normalizer(name)
            minimum = self._number(
                lowered.get("minimum", lowered.get("min")), name
            )
            preferred = self._number(
                lowered.get("preferred", lowered.get("pref")),
                name,
            )
            maximum = self._number(
                lowered.get("maximum", lowered.get("max")), name
            )
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ProfileParseError(
                    f"Limites inconsistentes para a restrição '{name}'."
                )
            constraints.append(
                BiometricConstraint(
                    original_name=name,
                    canonical_name=canonical,
                    minimum=minimum,
                    preferred=preferred,
                    maximum=maximum,
                    original_unit=attributes.get("unit"),
                    canonical_unit=canonical_unit,
                    source_path=path,
                    raw_data=dict(element.attrib),
                )
            )
        for index, child in enumerate(element, start=1):
            child_name = self._local(child.tag)
            self._walk(child, f"{path}/{child_name}[{index}]", constraints)

    @staticmethod
    def _number(value: str | None, name: str) -> float | None:
        if value is None or not value.strip():
            return None
        try:
            return float(value)
        except ValueError as error:
            raise ProfileParseError(
                f"Limite numérico inválido para a restrição '{name}'."
            ) from error

    @staticmethod
    def _local(tag: str) -> str:
        return tag.rsplit("}", maxsplit=1)[-1]

    @staticmethod
    def _without_normalization(
        _name: str,
    ) -> tuple[str | None, str | None]:
        return None, None
