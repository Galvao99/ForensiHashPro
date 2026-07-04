from dataclasses import dataclass, field


@dataclass
class MagicNumberFinding:
    offset: int
    hex_value: str
    ascii_value: str
    description: str
    confidence: int
    status: str = "Válido"


@dataclass
class MagicNumberResult:
    detected_type: str
    signature: str
    extension_matches: bool

    detected_format: str = "UNKNOWN"
    ascii_signature: str = ""
    extension: str = ""
    confidence: int = 0
    mime_type: str = "application/octet-stream"
    offset: int = 0
    header_preview_hex: str = ""
    header_preview_ascii: str = ""
    is_corrupted: bool = False
    findings: list[MagicNumberFinding] = field(default_factory=list)
    forensic_interpretation: list[str] = field(default_factory=list)
    conclusion: str = ""