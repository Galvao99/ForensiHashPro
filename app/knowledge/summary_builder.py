from app.models.analysis_result import AnalysisResult
from app.models.digital_signature_result import (
    SignatureAnalysisStatus,
)


class SummaryBuilder:
    """Monta um resumo factual sem avaliação agregada."""

    def build(
        self,
        analysis_result: AnalysisResult,
        correlation_count: int | None = None,
    ) -> dict:
        file_info = analysis_result.file_info
        magic = analysis_result.magic_numbers
        integrity = analysis_result.integrity
        signature = analysis_result.digital_signature

        hashes = analysis_result.hashes
        hash_count = sum(
            bool(getattr(hashes, attribute, ""))
            for attribute in (
                "md5",
                "sha1",
                "sha224",
                "sha256",
                "sha384",
                "sha512",
            )
        )

        facts = [
            ("Arquivo", file_info.name),
            (
                "Tipo técnico",
                magic.detected_format
                or magic.detected_type
                or "Não identificado",
            ),
            ("Hashes calculados", str(hash_count)),
            (
                "Magic number",
                "Compatível com a extensão"
                if magic.extension_matches
                else "Incompatível ou não identificado",
            ),
            (
                "Estrutura PDF",
                self._pdf_structure_status(
                    integrity.is_structurally_valid
                ),
            ),
            (
                "Assinatura digital",
                self._signature_status(
                    signature.analysis_status
                ),
            ),
            (
                "Vestígios técnicos",
                str(len(analysis_result.findings or [])),
            ),
            (
                "Texto extraído",
                "Disponível"
                if analysis_result.has_extracted_text
                else "Não disponível",
            ),
        ]

        if correlation_count is not None:
            facts.append(
                ("Correlações", str(correlation_count))
            )

        return {
            "title": "Resumo técnico factual",
            "facts": facts,
            "note": (
                "Os itens são apresentados separadamente e não constituem "
                "avaliação agregada ou conclusão de autenticidade."
            ),
        }

    @staticmethod
    def _pdf_structure_status(value: bool | None) -> str:
        if value is True:
            return "Válida nos critérios verificados"
        if value is False:
            return "Inválida nos critérios verificados"
        return "Não aplicável"

    @staticmethod
    def _signature_status(
        status: SignatureAnalysisStatus | None,
    ) -> str:
        labels = {
            SignatureAnalysisStatus.PRESENT: "Presente",
            SignatureAnalysisStatus.ABSENT: "Ausente",
            SignatureAnalysisStatus.NOT_APPLICABLE: "Não aplicável",
            SignatureAnalysisStatus.UNSUPPORTED: "Formato não suportado",
            SignatureAnalysisStatus.ERROR: "Não foi possível analisar",
        }
        return labels.get(status, "Não analisada")
