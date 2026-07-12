import re

from app.investigation.correlation_finding import (
    CorrelationFinding,
)
from app.investigation.investigation_context import (
    InvestigationContext,
)
from app.investigation.rules.base_correlation_rule import (
    BaseCorrelationRule,
)
from app.models.badge import (
    info_badge,
    neutral_badge,
    success_badge,
    warning_badge,
)
from app.models.json_analysis_result import (
    JsonAnalysisResult,
    JsonField,
)


class JsonContextRule(BaseCorrelationRule):
    """
    Transforma os campos extraídos de JSON pelo núcleo Rust
    em informações técnicas visualmente organizadas.
    """

    rule_id = "json_context"
    name = "Contexto de arquivos JSON"

    ANDROID_PATTERN = re.compile(
        r"Android\s+([0-9.]+)",
        re.IGNORECASE,
    )

    DEVICE_MODEL_PATTERN = re.compile(
        r"\b(SM-[A-Z0-9-]+)\b",
        re.IGNORECASE,
    )

    SAMSUNG_BROWSER_PATTERN = re.compile(
        r"SamsungBrowser/([0-9.]+)",
        re.IGNORECASE,
    )

    CHROME_PATTERN = re.compile(
        r"Chrome/([0-9.]+)",
        re.IGNORECASE,
    )

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        for file_name, json_result in (
            context.json_results.items()
        ):
            if not json_result.is_valid:
                self._add_invalid_json(
                    findings=findings,
                    file_name=file_name,
                    json_result=json_result,
                )
                continue

            self._add_json_summary(
                findings=findings,
                file_name=file_name,
                json_result=json_result,
            )

            self._analyze_device(
                findings=findings,
                file_name=file_name,
                json_result=json_result,
            )

            self._analyze_browser(
                findings=findings,
                file_name=file_name,
                json_result=json_result,
            )

            self._analyze_location(
                findings=findings,
                file_name=file_name,
                json_result=json_result,
            )

            self._analyze_categories(
                findings=findings,
                file_name=file_name,
                json_result=json_result,
            )

        return findings

    def _add_invalid_json(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        json_result: JsonAnalysisResult,
    ) -> None:
        self.add_warning(
            findings,
            title="JSON inválido ou não processado",
            description=(
                "O arquivo não pôde ser interpretado "
                "como uma estrutura JSON válida."
            ),
            icon="json-warning",
            source_file=file_name,
            badges=[
                warning_badge("JSON inválido"),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "erro": json_result.error_message,
            },
        )

    def _add_json_summary(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        json_result: JsonAnalysisResult,
    ) -> None:
        badges = [
            success_badge("JSON válido"),
            info_badge(
                f"{json_result.total_fields} campo(s)"
            ),
            neutral_badge(
                json_result.root_type
                or "estrutura não identificada"
            ),
        ]

        if json_result.streaming_used:
            badges.append(
                info_badge("Parser Rust")
            )

        if json_result.truncated:
            badges.append(
                warning_badge("Exibição limitada")
            )

        self.add_ok(
            findings,
            title="Estrutura JSON processada",
            description=(
                "O conteúdo JSON foi processado pelo núcleo "
                "Rust e disponibilizado para interpretação."
            ),
            icon="json",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "tipo_raiz": json_result.root_type,
                "total_campos": (
                    json_result.total_fields
                ),
                "campos_disponiveis": (
                    json_result.displayed_fields
                ),
                "streaming": (
                    json_result.streaming_used
                ),
                "truncado": json_result.truncated,
            },
        )

    def _analyze_device(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        json_result: JsonAnalysisResult,
    ) -> None:
        device_fields = (
            json_result.get_category("device")
            + json_result.get_category(
                "technical"
            )
        )

        combined_text = " ".join(
            field.display_value
            for field in device_fields
        )

        if not combined_text.strip():
            return

        android_version = self._first_match(
            self.ANDROID_PATTERN,
            combined_text,
        )

        device_model = self._first_match(
            self.DEVICE_MODEL_PATTERN,
            combined_text,
        )

        version_name = self._first_field_value(
            json_result,
            (
                "versionName",
                "version_name",
            ),
        )

        memory_info = self._first_field_value(
            json_result,
            (
                "memoryInfo",
                "memory_info",
                "memory",
            ),
        )

        badges = []

        if device_model:
            badges.append(
                success_badge(
                    device_model.upper()
                )
            )

        if android_version:
            badges.append(
                info_badge(
                    f"Android {android_version}"
                )
            )

        if version_name:
            badges.append(
                neutral_badge(version_name)
            )

        if " wv" in combined_text.lower():
            badges.append(
                info_badge("WebView")
            )

        if not badges:
            badges.append(
                info_badge("Dados de dispositivo")
            )

        self.add_info(
            findings,
            title="Dispositivo identificado no JSON",
            description=(
                "Foram localizados dados técnicos relacionados "
                "ao dispositivo utilizado."
            ),
            icon="device",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "modelo": device_model,
                "android": android_version,
                "versao_plataforma": version_name,
                "memory_info": memory_info,
                "campos_origem": self._serialize_fields(
                    device_fields
                ),
            },
        )

    def _analyze_browser(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        json_result: JsonAnalysisResult,
    ) -> None:
        browser_fields = (
            json_result.get_category("browser")
        )

        if not browser_fields:
            return

        combined_text = " ".join(
            field.display_value
            for field in browser_fields
        )

        samsung_version = self._first_match(
            self.SAMSUNG_BROWSER_PATTERN,
            combined_text,
        )

        chrome_version = self._first_match(
            self.CHROME_PATTERN,
            combined_text,
        )

        badges = []

        if samsung_version:
            badges.append(
                success_badge(
                    f"SamsungBrowser {samsung_version}"
                )
            )

        if chrome_version:
            badges.append(
                info_badge(
                    f"Chrome {chrome_version}"
                )
            )

        if "mobile" in combined_text.lower():
            badges.append(
                neutral_badge("Mobile")
            )

        if " wv" in combined_text.lower():
            badges.append(
                info_badge("WebView")
            )

        if not badges:
            badges.append(
                info_badge("User-Agent")
            )

        self.add_info(
            findings,
            title="Navegador identificado no JSON",
            description=(
                "Foram localizadas informações de navegador "
                "e User-Agent no conteúdo analisado."
            ),
            icon="browser",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "samsung_browser": samsung_version,
                "chrome": chrome_version,
                "campos_origem": self._serialize_fields(
                    browser_fields
                ),
            },
        )

    def _analyze_location(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        json_result: JsonAnalysisResult,
    ) -> None:
        latitude = self._first_field_value(
            json_result,
            (
                "lat",
                "latitude",
            ),
        )

        longitude = self._first_field_value(
            json_result,
            (
                "lon",
                "lng",
                "longitude",
            ),
        )

        origin = self._first_field_value(
            json_result,
            (
                "originLocation",
                "origin_location",
                "locationSource",
            ),
        )

        if (
            latitude is None
            and longitude is None
            and origin is None
        ):
            return

        badges = []

        if origin is not None:
            badges.append(
                success_badge(str(origin))
            )

        if latitude is not None:
            badges.append(
                info_badge(
                    f"Lat: {latitude}"
                )
            )

        if longitude is not None:
            badges.append(
                info_badge(
                    f"Lon: {longitude}"
                )
            )

        self.add_info(
            findings,
            title="Geolocalização declarada no JSON",
            description=(
                "O arquivo contém coordenadas e informações "
                "sobre a origem da localização."
            ),
            icon="location",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "latitude": latitude,
                "longitude": longitude,
                "origem_localizacao": origin,
                "observacao": (
                    "As coordenadas representam dados declarados "
                    "no arquivo e devem ser avaliadas em conjunto "
                    "com sua origem e cadeia de custódia."
                ),
            },
        )

    def _analyze_categories(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        json_result: JsonAnalysisResult,
    ) -> None:
        handled_categories = {
            "device",
            "technical",
            "browser",
            "location",
            "other",
        }

        titles = {
            "network": "Dados de rede localizados no JSON",
            "document": "Documentos localizados no JSON",
            "date": "Datas localizadas no JSON",
            "hash": "Hashes localizados no JSON",
            "person": "Dados pessoais localizados no JSON",
        }

        for category, fields in (
            json_result.categories.items()
        ):
            if (
                category in handled_categories
                or not fields
            ):
                continue

            visible_fields = fields[:12]

            badges = [
                neutral_badge(
                    f"{field.key}: "
                    f"{self._shorten(field.display_value)}"
                )
                for field in visible_fields
            ]

            self.add_info(
                findings,
                title=titles.get(
                    category,
                    "Campos técnicos localizados no JSON",
                ),
                description=(
                    "O parser identificou campos pertencentes "
                    f"à categoria '{category}'."
                ),
                icon="json-fields",
                source_file=file_name,
                badges=badges,
                metadata={
                    "arquivo": file_name,
                    "categoria": category,
                    "total": len(fields),
                    "campos": self._serialize_fields(
                        fields
                    ),
                },
            )

    def _first_field_value(
        self,
        json_result: JsonAnalysisResult,
        keys: tuple[str, ...],
    ):
        normalized_keys = {
            key.lower()
            for key in keys
        }

        for field in json_result.fields:
            if (
                field.key.lower()
                in normalized_keys
            ):
                return field.value

        return None

    @staticmethod
    def _first_match(
        pattern: re.Pattern[str],
        text: str,
    ) -> str:
        match = pattern.search(text)

        if not match:
            return ""

        return match.group(1)

    @staticmethod
    def _serialize_fields(
        fields: list[JsonField],
    ) -> list[dict]:
        return [
            {
                "caminho": field.path,
                "chave": field.key,
                "valor": field.value,
                "tipo": field.value_type,
                "categoria": field.category,
            }
            for field in fields
        ]

    @staticmethod
    def _shorten(
        value: str,
        limit: int = 40,
    ) -> str:
        normalized = str(value)

        if len(normalized) <= limit:
            return normalized

        return f"{normalized[:limit - 3]}..."