from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PdfStructureConcept:
    title: str
    description: str


PDF_STRUCTURE_CONCEPTS: dict[str, PdfStructureConcept] = {
    "pdf_version": PdfStructureConcept(
        "Versão do PDF",
        "Identifica a versão da especificação PDF declarada no cabeçalho do arquivo.",
    ),
    "objects": PdfStructureConcept(
        "Objetos PDF",
        "Unidades numeradas que representam elementos do documento, como dicionários, páginas, fontes e outros dados.",
    ),
    "streams": PdfStructureConcept(
        "Streams",
        "Sequências de bytes associadas a objetos PDF, usadas para armazenar conteúdo, imagens, fontes e outros dados.",
    ),
    "trailer": PdfStructureConcept(
        "Trailer",
        "Dicionário estrutural que referencia componentes essenciais do PDF, como o objeto raiz e informações da tabela de referências cruzadas.",
    ),
    "startxref": PdfStructureConcept(
        "startxref",
        "Marcador que declara a posição inicial da seção de referências cruzadas mais recente.",
    ),
    "eof": PdfStructureConcept(
        "Marcador %%EOF",
        "Marcador sintático usado para delimitar o final de uma revisão da estrutura PDF.",
    ),
    "javascript": PdfStructureConcept(
        "JavaScript",
        "Recurso do formato PDF que permite associar código JavaScript a elementos ou eventos do documento.",
    ),
    "encryption": PdfStructureConcept(
        "Criptografia",
        "Mecanismo do formato PDF para controlar o acesso e aplicar proteção criptográfica ao conteúdo.",
    ),
    "embedded_files": PdfStructureConcept(
        "Arquivos incorporados",
        "Recurso que permite armazenar arquivos como objetos anexados dentro da estrutura do PDF.",
    ),
    "open_action": PdfStructureConcept(
        "OpenAction",
        "Entrada do catálogo PDF que define uma ação ou destino a ser processado quando o documento é aberto.",
    ),
    "additional_actions": PdfStructureConcept(
        "Additional Actions",
        "Conjunto de entradas que associa ações adicionais a eventos definidos pelo formato PDF.",
    ),
    "acroform": PdfStructureConcept(
        "AcroForm",
        "Estrutura de formulários interativos do PDF, composta por campos, controles e propriedades relacionadas.",
    ),
    "xfa": PdfStructureConcept(
        "XFA",
        "Arquitetura de formulários baseada em XML que pode ser incorporada a um PDF para descrever campos e apresentação.",
    ),
}


def get_pdf_structure_concept(key: str) -> PdfStructureConcept:
    """Retorna o conceito associado a uma chave conhecida."""
    return PDF_STRUCTURE_CONCEPTS[key]
