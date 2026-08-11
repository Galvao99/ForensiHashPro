from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeclaredHashOccurrence:
    value: str
    algorithm: str
    evidence_ref: str
    filename: str
    source_type: str
    page: int | None = None
    start: int | None = None
    end: int | None = None
    field_path: str | None = None
    context: str = ""
    extractor: str = "declared_hash_extractor_v2"
    artifact_hint: str | None = None
    declared: bool = False


class DeclaredHashExtractor:
    HASH_PATTERN = re.compile(
        r"(?<![a-fA-F0-9])([a-fA-F0-9]{32}|[a-fA-F0-9]{40}|"
        r"[a-fA-F0-9]{56}|[a-fA-F0-9]{64}|[a-fA-F0-9]{96}|"
        r"[a-fA-F0-9]{128})(?![a-fA-F0-9])"
    )
    ALGORITHM_BY_LENGTH = {
        32: "MD5", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256",
        96: "SHA-384", 128: "SHA-512",
    }
    DECLARATION_PATTERN = re.compile(
        r"(?i)\b(hash|checksum|digest|md5|sha[ -]?(?:1|224|256|384|512))\b"
    )
    ARTIFACT_PATTERN = re.compile(
        r"(?i)(?:hash|checksum|digest)\s+(?:do|da|de)\s+([\w .-]{1,80})"
    )

    def extract_text(
        self, text: str, *, evidence_ref: str, filename: str,
        source_type: str, page: int | None = None,
    ) -> list[DeclaredHashOccurrence]:
        occurrences: list[DeclaredHashOccurrence] = []
        for match in self.HASH_PATTERN.finditer(text or ""):
            start, end = match.span(1)
            before = text[max(0, start - 120):start]
            after = text[end:min(len(text), end + 120)]
            context = " ".join((before.strip(), match.group(1), after.strip())).strip()
            label_window = before[-100:]
            hint_match = self.ARTIFACT_PATTERN.search(label_window)
            hint = hint_match.group(1).strip(" .:-") if hint_match else None
            occurrences.append(DeclaredHashOccurrence(
                value=match.group(1).lower(),
                algorithm=self.ALGORITHM_BY_LENGTH[len(match.group(1))],
                evidence_ref=evidence_ref,
                filename=filename,
                source_type=source_type,
                page=page,
                start=start,
                end=end,
                context=context,
                artifact_hint=hint,
                declared=bool(self.DECLARATION_PATTERN.search(label_window)),
            ))
        return occurrences

    def extract_json_field(
        self, value: object, *, evidence_ref: str, filename: str, field_path: str,
    ) -> list[DeclaredHashOccurrence]:
        text = str(value)
        items = self.extract_text(
            text, evidence_ref=evidence_ref, filename=filename, source_type="json"
        )
        label_declared = bool(self.DECLARATION_PATTERN.search(field_path))
        return [
            DeclaredHashOccurrence(
                **{
                    **{field: getattr(item, field) for field in item.__dataclass_fields__},
                    "field_path": field_path,
                    "context": f"{field_path}: {text}",
                    "declared": item.declared or label_declared,
                }
            )
            for item in items
        ]
