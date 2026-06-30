class InsightService:
    """
    Serviço responsável por gerar interpretações técnicas simples
    a partir dos dados encontrados na análise.
    """

    def build_producer_insight(self, producer: str | None) -> str:
        if not producer:
            return (
                "Não foi identificado produtor do arquivo. "
                "A ausência dessa informação pode limitar a interpretação da origem do documento."
            )

        producer_lower = producer.lower()

        if "itext" in producer_lower:
            return (
                "Foi identificado o uso da biblioteca iText, normalmente utilizada para geração, "
                "manipulação ou processamento de arquivos PDF. Isoladamente, esse vestígio não indica "
                "adulteração, devendo ser correlacionado com datas de criação, modificação, assinatura "
                "digital e demais metadados do documento."
            )

        if "pdfium" in producer_lower:
            return (
                "Foi identificado vestígio relacionado ao PDFium, mecanismo utilizado para renderização "
                "e processamento de documentos PDF, inclusive em navegadores e aplicações baseadas em Chromium."
            )

        if "ghostscript" in producer_lower:
            return (
                "Foi identificado vestígio relacionado ao Ghostscript, ferramenta comumente utilizada para "
                "conversão, reprocessamento, otimização ou geração de arquivos PDF."
            )

        if "microsoft" in producer_lower or "word" in producer_lower:
            return (
                "O documento apresenta vestígios compatíveis com geração ou exportação a partir de ferramenta "
                "Microsoft, como Word ou outro componente do pacote Office."
            )

        if "libreoffice" in producer_lower:
            return (
                "O documento apresenta vestígios compatíveis com geração ou exportação por meio do LibreOffice."
            )

        if "ilovepdf" in producer_lower:
            return (
                "Foi identificado processamento por iLovePDF, serviço online utilizado para manipulação, união, "
                "compressão ou conversão de arquivos PDF. Esse elemento sugere que o documento analisado pode "
                "corresponder a versão processada posteriormente."
            )

        return (
            f"Foi identificado o produtor '{producer}'. Esse vestígio deve ser analisado em conjunto com os "
            "demais elementos técnicos do arquivo."
        )

    def build_signature_insight(self, has_signature: bool | None) -> str:
        if has_signature is True:
            return (
                "Foram identificados elementos de assinatura digital verificável no documento, permitindo "
                "análise técnica complementar quanto à integridade e autoria criptográfica."
            )

        if has_signature is False:
            return (
                "Não foram identificadas assinaturas digitais verificáveis. Tal circunstância não implica, "
                "por si só, invalidade do documento, mas reduz os elementos técnicos passíveis de validação "
                "independente quanto à autoria, integridade e temporalidade."
            )

        return (
            "Não foi possível determinar, a partir dos dados disponíveis, a existência de assinatura digital verificável."
        )

    def build_magic_number_insight(self, is_valid: bool | None) -> str:
        if is_valid is True:
            return (
                "O magic number identificado é compatível com a extensão declarada do arquivo, indicando "
                "coerência estrutural inicial entre o tipo real e o tipo informado."
            )

        if is_valid is False:
            return (
                "Foi identificada divergência entre o magic number e a extensão declarada do arquivo, "
                "circunstância que demanda análise técnica mais cautelosa."
            )

        return (
            "Não foi possível validar o magic number do arquivo com os dados atualmente disponíveis."
        )