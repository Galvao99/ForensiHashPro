import re
from dataclasses import dataclass
from datetime import datetime

from app.config.contract_date_rules import DATE_CLASSIFICATION_RULES


@dataclass
class ContractDateFinding:
    date: datetime
    label: str
    context: str
    score: int


class ContractDateExtractor:
    DATE_PATTERN = re.compile(
        r"\b("
        r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}"
        r")\b"
    )

    def extract_contract_dates(self, text: str) -> list[ContractDateFinding]:
        findings: list[ContractDateFinding] = []

        if not text:
            return findings

        normalized_text = self._normalize_text(text)

        for match in self.DATE_PATTERN.finditer(normalized_text):
            raw_date = match.group(1)
            parsed_date = self._parse_date(raw_date)

            if not parsed_date:
                continue

            context = self._get_context(
                normalized_text,
                match.start(),
                match.end(),
            )

            label, score = self._classify_context(context)

            if label == "Ignorar":
                continue

            if score <= 0:
                continue

            findings.append(
                ContractDateFinding(
                    date=parsed_date,
                    label=label,
                    context=context.strip(),
                    score=score,
                )
            )

        return findings

    def get_best_contract_date(self, text: str) -> ContractDateFinding | None:
        findings = self.extract_contract_dates(text)

        if not findings:
            return None

        findings.sort(
            key=lambda finding: (
                finding.score,
                self._priority_score(finding.label),
            ),
            reverse=True,
        )

        return findings[0]

    def _classify_context(self, context: str) -> tuple[str, int]:
        best_label = "Data contratual"
        best_score = 10

        for label, rule in DATE_CLASSIFICATION_RULES.items():
            base_score = rule["score"]

            for pattern in rule["patterns"]:
                if re.search(pattern, context, flags=re.IGNORECASE):
                    if base_score > best_score:
                        best_label = label
                        best_score = base_score

        return best_label, best_score

    def _priority_score(self, label: str) -> int:
        priority = {
            "Pactuação": 5,
            "Assinatura textual": 4,
            "Aceite": 3,
            "Emissão": 2,
            "Data contratual": 1,
        }

        return priority.get(label, 0)

    def _parse_date(self, raw_date: str) -> datetime | None:
        raw_date = raw_date.replace("-", "/").replace(".", "/")

        formats = [
            "%d/%m/%Y",
            "%d/%m/%y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(raw_date, fmt)
            except ValueError:
                continue

        return None

    def _get_context(self, text: str, start: int, end: int) -> str:
        left = max(0, start - 150)
        right = min(len(text), end + 150)

        return text[left:right].replace("\n", " ")

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r", " ").replace("\n", " ")
        text = re.sub(r"\s+", " ", text)

        return text.strip()