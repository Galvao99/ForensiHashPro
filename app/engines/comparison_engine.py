from app.models import AnalysisResult
from app.models.comparison_result import ComparisonResult
from app.models.comparison_section import ComparisonSection


class ComparisonEngine:
    """Responsável pela comparação entre duas análises forenses."""

    def compare(
        self,
        left: AnalysisResult,
        right: AnalysisResult,
    ) -> ComparisonResult:
        sections: list[ComparisonSection] = []

        same_sha256 = left.hashes.sha256 == right.hashes.sha256

        sections.append(
            ComparisonSection(
                title="SHA-256",
                status="success" if same_sha256 else "critical",
                description=(
                    "Os arquivos possuem o mesmo hash SHA-256."
                    if same_sha256
                    else "Os arquivos possuem hashes SHA-256 distintos, indicando diferença de conteúdo binário."
                ),
            )
        )

        same_magic = (
            left.magic_numbers.detected_type == right.magic_numbers.detected_type
            and left.magic_numbers.signature == right.magic_numbers.signature
        )

        sections.append(
            ComparisonSection(
                title="Magic Number",
                status="success" if same_magic else "warning",
                description=(
                    "Os arquivos apresentam a mesma assinatura binária."
                    if same_magic
                    else "Os arquivos apresentam divergência na assinatura binária ou no tipo detectado."
                ),
            )
        )

        same_signature = (
            left.digital_signature.has_signature == right.digital_signature.has_signature
            and left.digital_signature.signer == right.digital_signature.signer
            and left.digital_signature.serial_number
            == right.digital_signature.serial_number
        )

        sections.append(
            ComparisonSection(
                title="Assinatura Digital",
                status="success" if same_signature else "warning",
                description=(
                    "As informações de assinatura digital são compatíveis entre os arquivos."
                    if same_signature
                    else "Foram identificadas diferenças nas informações de assinatura digital."
                ),
            )
        )

        critical_count = sum(1 for section in sections if section.status == "critical")
        warning_count = sum(1 for section in sections if section.status == "warning")

        if critical_count:
            summary = "Foram identificadas divergências críticas entre os arquivos analisados."
        elif warning_count:
            summary = "Foram identificadas divergências técnicas que exigem análise complementar."
        else:
            summary = "Os principais elementos técnicos comparados apresentaram compatibilidade."

        return ComparisonResult(
            left_file=left.file_info.name,
            right_file=right.file_info.name,
            sections=sections,
            technical_summary=summary,
        )