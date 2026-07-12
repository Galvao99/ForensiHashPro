from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class JsonField:
    """
    Campo simples extraído do documento JSON.
    """

    path: str
    key: str
    value: Any
    value_type: str
    category: str = "other"

    @property
    def display_value(self) -> str:
        if self.value is None:
            return "null"

        if isinstance(self.value, bool):
            return "Sim" if self.value else "Não"

        return str(self.value)


@dataclass(slots=True)
class JsonAnalysisResult:
    """
    Resultado normalizado recebido do núcleo Rust.
    """

    is_valid: bool = False
    streaming_used: bool = False
    root_type: str = ""

    total_fields: int = 0
    displayed_fields: int = 0
    truncated: bool = False

    fields: list[JsonField] = field(
        default_factory=list
    )

    categories: dict[str, list[JsonField]] = field(
        default_factory=dict
    )

    error_message: str = ""

    def add_field(
        self,
        json_field: JsonField,
    ) -> None:
        self.fields.append(json_field)

        self.categories.setdefault(
            json_field.category,
            [],
        ).append(json_field)

    def get_category(
        self,
        category: str,
    ) -> list[JsonField]:
        return self.categories.get(
            category,
            [],
        )

    def find_by_key(
        self,
        key: str,
    ) -> list[JsonField]:
        normalized = key.strip().lower()

        return [
            field
            for field in self.fields
            if field.key.lower() == normalized
        ]