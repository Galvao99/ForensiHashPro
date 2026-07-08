from app.knowledge.findings.base import FindingDefinition, FindingSeverity


INTEGRITY_FINDINGS = {
    "missing_hash": FindingDefinition(
        code="INT_MISSING_HASH",
        title="Hash não calculado",
        category="Integridade",
        severity=FindingSeverity.WARNING,
        nature="Ausência de identificador técnico de integridade",
        explanation=(
            "Não foi identificado hash calculado para o arquivo analisado. "
            "O hash é um identificador técnico utilizado para demonstrar que "
            "o conteúdo examinado permaneceu inalterado durante a análise."
        ),
        forensic_impact=(
            "A ausência de hash dificulta a comprovação de integridade do arquivo "
            "analisado e limita a reprodutibilidade da perícia."
        ),
        recommendation=(
            "Calcular e registrar hash criptográfico, preferencialmente SHA-256, "
            "no início da análise pericial."
        ),
    ),
}