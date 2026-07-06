from app.knowledge.producer_database import ProducerDatabase


class InsightService:
    """
    Serviço responsável por gerar interpretações técnicas simples
    a partir dos dados encontrados na análise.
    """

    def build_producer_insight(self, producer: str | None) -> str:
        if not producer:
            return (
                "Não foi identificado produtor do arquivo. "
                "A ausência dessa informação pode limitar a interpretação técnica "
                "quanto à origem, geração ou processamento do documento."
            )

        producer_info = ProducerDatabase.find_all(producer)

        if not producer_info:
            return (
                f"Foi identificado o produtor '{producer}'. "
                "Este vestígio deve ser analisado em conjunto com os demais "
                "elementos técnicos do arquivo, como datas de criação, modificação, "
                "estrutura documental, assinatura digital e metadados complementares."
            )

        common_uses = ", ".join(producer_info.common_uses)
        correlate_with = ", ".join(producer_info.correlate_with)

        return (
            f"{producer_info.interpretation} "
            f"Uso comum: {common_uses}. "
            f"Recomenda-se correlacionar este vestígio com: {correlate_with}."
        )

    def build_signature_insight(self, has_signature: bool | None) -> str:
        if has_signature is True:
            return (
                "Foram identificados elementos de assinatura digital verificável no documento, "
                "permitindo análise técnica complementar quanto à integridade e autoria criptográfica."
            )

        if has_signature is False:
            return (
                "Não foram identificadas assinaturas digitais verificáveis. Tal circunstância não implica, "
                "por si só, invalidade do documento, mas reduz os elementos técnicos passíveis de validação "
                "independente quanto à autoria, integridade e temporalidade."
            )

        return (
            "Não foi possível determinar, a partir dos dados disponíveis, "
            "a existência de assinatura digital verificável."
        )

    def build_magic_number_insight(self, is_valid: bool | None) -> str:
        if is_valid is True:
            return (
                "O magic number identificado é compatível com a extensão declarada do arquivo, "
                "indicando coerência estrutural inicial entre o tipo real e o tipo informado."
            )

        if is_valid is False:
            return (
                "Foi identificada divergência entre o magic number e a extensão declarada do arquivo, "
                "circunstância que demanda análise técnica mais cautelosa."
            )

        return (
            "Não foi possível validar o magic number do arquivo com os dados atualmente disponíveis."
        )