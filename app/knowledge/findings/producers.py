from app.knowledge.findings.base import FindingDefinition, FindingSeverity


PRODUCER_FINDINGS = {
    "ghostscript": FindingDefinition(
        code="PROD_GHOSTSCRIPT",
        title="Documento processado por Ghostscript",
        category="Produtor PDF",
        severity=FindingSeverity.WARNING,
        nature="Reprocessamento ou conversão documental",
        explanation=(
            "Foi identificado vestígio compatível com Ghostscript, ferramenta "
            "frequentemente utilizada para conversão, impressão virtual, compressão "
            "ou reprocessamento de arquivos PDF."
        ),
        forensic_impact=(
            "Esse elemento, isoladamente, não comprova adulteração documental, "
            "mas indica que o arquivo pode não corresponder diretamente ao documento "
            "originalmente gerado no fluxo de contratação."
        ),
        recommendation=(
            "Recomenda-se confrontar esse vestígio com datas de criação/modificação, "
            "assinatura digital, logs de contratação e cadeia de custódia do arquivo."
        ),
    ),

    "aspose": FindingDefinition(
        code="PROD_ASPOSE",
        title="Documento processado por Aspose",
        category="Produtor PDF",
        severity=FindingSeverity.WARNING,
        nature="Geração ou reconstrução programática de PDF",
        explanation=(
            "Foi identificado vestígio compatível com Aspose, biblioteca utilizada "
            "para criação, conversão ou manipulação automatizada de documentos PDF."
        ),
        forensic_impact=(
            "A presença desse produtor pode indicar que o arquivo foi gerado ou "
            "reconstruído por sistema automatizado, não sendo possível afirmar, "
            "apenas por esse dado, que se trata do arquivo original da contratação."
        ),
        recommendation=(
            "Recomenda-se solicitar o arquivo original, logs técnicos do fluxo, "
            "hashes de origem e trilha de eventos vinculada à contratação."
        ),
    ),

    "ilovepdf": FindingDefinition(
        code="PROD_ILOVEPDF",
        title="Documento processado por iLovePDF",
        category="Produtor PDF",
        severity=FindingSeverity.WARNING,
        nature="Processamento por ferramenta online de PDF",
        explanation=(
            "Foi identificado vestígio compatível com iLovePDF, serviço online "
            "utilizado para compressão, união, divisão, conversão ou edição de PDFs."
        ),
        forensic_impact=(
            "Esse vestígio sugere processamento posterior por ferramenta externa "
            "ao fluxo original de contratação eletrônica."
        ),
        recommendation=(
            "Recomenda-se avaliar se há coerência entre esse processamento, "
            "as datas do documento e a origem declarada pela parte responsável."
        ),
    ),

    "microsoft word": FindingDefinition(
        code="PROD_WORD",
        title="Documento gerado ou exportado pelo Microsoft Word",
        category="Produtor PDF",
        severity=FindingSeverity.INFO,
        nature="Exportação convencional de documento",
        explanation=(
            "Foi identificado vestígio compatível com Microsoft Word, software "
            "amplamente utilizado para elaboração e exportação de documentos."
        ),
        forensic_impact=(
            "Esse elemento pode ser compatível com a geração comum de documentos, "
            "mas deve ser analisado em conjunto com os demais metadados e eventos."
        ),
        recommendation=(
            "Recomenda-se confrontar esse dado com datas, autoria, assinatura "
            "digital e demais vestígios técnicos do arquivo."
        ),
    ),

    "libreoffice": FindingDefinition(
        code="PROD_LIBREOFFICE",
        title="Documento gerado ou exportado pelo LibreOffice",
        category="Produtor PDF",
        severity=FindingSeverity.INFO,
        nature="Exportação convencional de documento",
        explanation=(
            "Foi identificado vestígio compatível com LibreOffice, suíte utilizada "
            "para criação e exportação de documentos em PDF."
        ),
        forensic_impact=(
            "A presença desse produtor não indica, por si só, adulteração, mas "
            "ajuda a compreender o ambiente de geração ou exportação do arquivo."
        ),
        recommendation=(
            "Recomenda-se verificar coerência com o fluxo informado, datas de "
            "criação/modificação e demais evidências documentais."
        ),
    ),

    "pdfium": FindingDefinition(
        code="PROD_PDFIUM",
        title="Documento processado por PDFium",
        category="Produtor PDF",
        severity=FindingSeverity.INFO,
        nature="Renderização ou geração por mecanismo PDF",
        explanation=(
            "Foi identificado vestígio compatível com PDFium, mecanismo de "
            "renderização/manipulação de PDF utilizado por diversos softwares."
        ),
        forensic_impact=(
            "Esse vestígio indica processamento por ferramenta baseada nesse "
            "motor, mas não permite concluir, isoladamente, alteração indevida."
        ),
        recommendation=(
            "Recomenda-se analisar esse dado em conjunto com produtores, datas, "
            "estrutura do PDF e assinatura digital."
        ),
    ),

    "skia": FindingDefinition(
        code="PROD_SKIA",
        title="Documento processado por Skia/PDF",
        category="Produtor PDF",
        severity=FindingSeverity.INFO,
        nature="Geração por mecanismo gráfico",
        explanation=(
            "Foi identificado vestígio compatível com Skia/PDF, biblioteca gráfica "
            "utilizada em ambientes como navegadores e aplicações modernas."
        ),
        forensic_impact=(
            "Esse vestígio pode indicar geração, impressão ou renderização do "
            "documento por aplicação baseada nesse mecanismo."
        ),
        recommendation=(
            "Recomenda-se verificar se tal origem é compatível com o sistema "
            "de contratação declarado."
        ),
    ),
}