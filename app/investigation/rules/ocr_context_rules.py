import re
from datetime import datetime

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import (
    info_badge,
    neutral_badge,
    success_badge,
    warning_badge,
)


class OcrContextRule(BaseCorrelationRule):
    """
    Produz evidências visuais a partir dos textos extraídos
    de cada arquivo.

    A regra não realiza OCR diretamente. Ela interpreta os textos
    previamente extraídos e adicionados ao InvestigationContext.
    """

    rule_id = "ocr_context"
    name = "Contexto textual e OCR"

    HASH_PATTERN = re.compile(
        r"(?<![a-fA-F0-9])"
        r"("
        r"[a-fA-F0-9]{32}"
        r"|[a-fA-F0-9]{40}"
        r"|[a-fA-F0-9]{56}"
        r"|[a-fA-F0-9]{64}"
        r"|[a-fA-F0-9]{96}"
        r"|[a-fA-F0-9]{128}"
        r")"
        r"(?![a-fA-F0-9])"
    )

    CPF_PATTERN = re.compile(
        r"(?<!\d)"
        r"(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})"
        r"(?!\d)"
    )

    DATE_PATTERN = re.compile(
        r"(?<!\d)"
        r"("
        r"(?:0[1-9]|[12]\d|3[01])"
        r"[/-]"
        r"(?:0[1-9]|1[0-2])"
        r"[/-]"
        r"(?:19|20)\d{2}"
        r")"
        r"(?!\d)"
    )

    EMAIL_PATTERN = re.compile(
        r"\b"
        r"[A-Za-z0-9._%+-]+"
        r"@"
        r"[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}"
        r"\b"
    )

    PHONE_PATTERN = re.compile(
        r"(?<!\d)"
        r"("
        r"(?:\+?55[\s.-]?)?"
        r"(?:\(?\d{2}\)?[\s.-]?)?"
        r"(?:9\d{4}|\d{4})"
        r"[\s.-]?"
        r"\d{4}"
        r")"
        r"(?!\d)"
    )

    HASH_ALGORITHM_BY_LENGTH = {
        32: "MD5",
        40: "SHA-1",
        56: "SHA-224",
        64: "SHA-256",
        96: "SHA-384",
        128: "SHA-512",
    }

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        for file_name, text in context.extracted_texts.items():
            normalized_text = text.strip()

            if not normalized_text:
                continue

            self._add_text_extraction_finding(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

            self._analyze_contract_date(
                findings=findings,
                context=context,
                file_name=file_name,
            )

            self._analyze_hashes(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

            self._analyze_document_numbers(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

            self._analyze_emails(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

            self._analyze_phones(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

            self._analyze_dates(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

        return findings

    def _add_text_extraction_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        character_count = len(text)
        word_count = len(text.split())

        self.add_ok(
            findings,
            title="Conteúdo textual extraído",
            description=(
                "O arquivo apresentou conteúdo textual disponível "
                "para pesquisa e correlação."
            ),
            icon="ocr",
            source_file=file_name,
            badges=[
                success_badge("Texto extraído"),
                info_badge(f"{word_count} palavras"),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "quantidade_caracteres": character_count,
                "quantidade_palavras": word_count,
            },
        )

    def _analyze_contract_date(
        self,
        *,
        findings: list[CorrelationFinding],
        context: InvestigationContext,
        file_name: str,
    ) -> None:
        contract_date = context.contract_dates.get(file_name)

        if contract_date is None:
            return

        self.add_info(
            findings,
            title="Data de pactuação localizada",
            description=(
                "Foi identificada uma data contratual no conteúdo "
                "textual do documento."
            ),
            icon="calendar",
            source_file=file_name,
            badges=[
                info_badge("Data contratual"),
                success_badge(
                    contract_date.strftime("%d/%m/%Y")
                ),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "data_pactuacao": contract_date.isoformat(),
            },
        )

    def _analyze_hashes(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        hashes = self._extract_unique_matches(
            pattern=self.HASH_PATTERN,
            text=text,
        )

        if not hashes:
            return

        for hash_value in hashes:
            algorithm = self.HASH_ALGORITHM_BY_LENGTH.get(
                len(hash_value),
                "Hash",
            )

            self.add_info(
                findings,
                title="Hash localizado no conteúdo",
                description=(
                    "Foi identificado no corpo do documento um valor "
                    "com formato compatível com algoritmo de hash."
                ),
                icon="hash",
                source_file=file_name,
                badges=[
                    info_badge(algorithm),
                    success_badge("Localizado no texto"),
                    neutral_badge(file_name),
                ],
                metadata={
                    "arquivo": file_name,
                    "algoritmo_provavel": algorithm,
                    "hash": hash_value.lower(),
                },
            )

    def _analyze_document_numbers(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        cpfs = self._extract_unique_matches(
            pattern=self.CPF_PATTERN,
            text=text,
        )

        for cpf in cpfs:
            normalized_cpf = self._only_digits(cpf)
            is_valid = self._is_valid_cpf(normalized_cpf)

            if is_valid:
                self.add_ok(
                    findings,
                    title="CPF localizado no conteúdo",
                    description=(
                        "Foi identificado um CPF com estrutura "
                        "matematicamente válida."
                    ),
                    icon="document-number",
                    source_file=file_name,
                    badges=[
                        success_badge("CPF válido"),
                        info_badge(self._format_cpf(normalized_cpf)),
                        neutral_badge(file_name),
                    ],
                    metadata={
                        "arquivo": file_name,
                        "cpf": normalized_cpf,
                        "valido": True,
                    },
                )

                continue

            self.add_warning(
                findings,
                title="CPF com estrutura inválida",
                description=(
                    "Foi localizado um número semelhante a CPF, "
                    "mas os dígitos verificadores não são válidos."
                ),
                icon="document-warning",
                source_file=file_name,
                badges=[
                    warning_badge("CPF inválido"),
                    info_badge(cpf),
                    neutral_badge(file_name),
                ],
                metadata={
                    "arquivo": file_name,
                    "cpf": normalized_cpf,
                    "valido": False,
                },
            )

    def _analyze_emails(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        emails = self._extract_unique_matches(
            pattern=self.EMAIL_PATTERN,
            text=text,
        )

        if not emails:
            return

        self.add_info(
            findings,
            title="E-mail localizado no conteúdo",
            description=(
                "Foram identificados endereços de e-mail no texto "
                "extraído do documento."
            ),
            icon="email",
            source_file=file_name,
            badges=[
                info_badge("E-mail"),
                neutral_badge(f"{len(emails)} encontrado(s)"),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "emails": emails,
            },
        )

    def _analyze_phones(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        phones = self._extract_unique_matches(
            pattern=self.PHONE_PATTERN,
            text=text,
        )

        normalized_phones = [
            self._only_digits(phone)
            for phone in phones
            if len(self._only_digits(phone)) >= 10
        ]

        normalized_phones = list(dict.fromkeys(normalized_phones))

        if not normalized_phones:
            return

        self.add_info(
            findings,
            title="Telefone localizado no conteúdo",
            description=(
                "Foram identificados números com formato compatível "
                "com telefone no texto extraído."
            ),
            icon="phone",
            source_file=file_name,
            badges=[
                info_badge("Telefone"),
                neutral_badge(
                    f"{len(normalized_phones)} encontrado(s)"
                ),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "telefones": normalized_phones,
            },
        )

    def _analyze_dates(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        date_values = self._extract_unique_matches(
            pattern=self.DATE_PATTERN,
            text=text,
        )

        parsed_dates: list[datetime] = []

        for date_value in date_values:
            parsed_date = self._parse_document_date(date_value)

            if parsed_date is not None:
                parsed_dates.append(parsed_date)

        if not parsed_dates:
            return

        formatted_dates = list(
            dict.fromkeys(
                date.strftime("%d/%m/%Y")
                for date in parsed_dates
            )
        )

        self.add_info(
            findings,
            title="Datas localizadas no conteúdo",
            description=(
                "Foram encontradas datas no texto extraído, "
                "disponíveis para correlação cronológica."
            ),
            icon="calendar-search",
            source_file=file_name,
            badges=[
                info_badge("Datas"),
                neutral_badge(
                    f"{len(formatted_dates)} encontrada(s)"
                ),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "datas": formatted_dates,
            },
        )

    def _extract_unique_matches(
        self,
        *,
        pattern: re.Pattern[str],
        text: str,
    ) -> list[str]:
        matches: list[str] = []

        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            normalized = value.strip()

            if normalized and normalized not in matches:
                matches.append(normalized)

        return matches

    def _parse_document_date(
        self,
        value: str,
    ) -> datetime | None:
        for date_format in (
            "%d/%m/%Y",
            "%d-%m-%Y",
        ):
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue

        return None

    def _is_valid_cpf(
        self,
        cpf: str,
    ) -> bool:
        if len(cpf) != 11:
            return False

        if cpf == cpf[0] * 11:
            return False

        first_total = sum(
            int(cpf[index]) * (10 - index)
            for index in range(9)
        )

        first_digit = (first_total * 10) % 11

        if first_digit == 10:
            first_digit = 0

        if first_digit != int(cpf[9]):
            return False

        second_total = sum(
            int(cpf[index]) * (11 - index)
            for index in range(10)
        )

        second_digit = (second_total * 10) % 11

        if second_digit == 10:
            second_digit = 0

        return second_digit == int(cpf[10])

    def _only_digits(
        self,
        value: str,
    ) -> str:
        return "".join(
            character
            for character in value
            if character.isdigit()
        )

    def _format_cpf(
        self,
        cpf: str,
    ) -> str:
        if len(cpf) != 11:
            return cpf

        return (
            f"{cpf[:3]}."
            f"{cpf[3:6]}."
            f"{cpf[6:9]}-"
            f"{cpf[9:]}"
        )