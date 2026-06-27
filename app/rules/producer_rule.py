from app.enum.severity import Severity
from app.models import Finding, MetadataResult
from app.rules.base_rule import MetadataRule


class ProducerRule(MetadataRule):
    """Identifica vestígios técnicos relacionados a Producer/Creator."""

    def apply(self, metadata: MetadataResult) -> list[Finding]:
        findings: list[Finding] = []

        metadata_text = " ".join(str(value) for value in metadata.raw.values()).lower()

        if "itext" in metadata_text:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="PDF",
                    title="Vestígio de processamento por iText",
                    description=(
                        "Foram encontrados metadados relacionados ao iText, "
                        "biblioteca comumente utilizada para geração, edição ou processamento de PDFs."
                    ),
                    evidence_source="Metadados",
                    observed_value="iText",
                    recommendation="Verificar se o arquivo corresponde ao documento originalmente produzido.",
                    score=0.85,
                )
            )

        if "libreoffice" in metadata_text:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="Documento",
                    title="Vestígio de geração por LibreOffice",
                    description="Foram encontrados metadados compatíveis com documento gerado ou exportado pelo LibreOffice.",
                    evidence_source="Metadados",
                    observed_value="LibreOffice",
                    score=0.80,
                )
            )

        if "photoshop" in metadata_text:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="Imagem",
                    title="Vestígio de Adobe Photoshop",
                    description=(
                        "Foram encontrados metadados associados ao Adobe Photoshop, "
                        "o que pode indicar edição ou processamento de imagem."
                    ),
                    evidence_source="Metadados",
                    observed_value="Photoshop",
                    recommendation="Verificar o arquivo original e demais metadados de edição.",
                    score=0.85,
                )
            )

        return findings