import re

from app.enum.severity import Severity
from app.models import Finding, MetadataResult
from app.rules.base_rule import MetadataRule


class SuspiciousSoftwareRule(MetadataRule):
    """Identifica softwares/serviços que podem indicar reprocessamento, edição ou geração automatizada."""

    TERMS = {
        # Editores de imagem
        "photoshop": ("Adobe Photoshop", "Imagem", Severity.WARNING),
        "adobe photoshop": ("Adobe Photoshop", "Imagem", Severity.WARNING),
        "gimp": ("GIMP", "Imagem", Severity.WARNING),
        "paint.net": ("Paint.NET", "Imagem", Severity.INFO),
        "canva": ("Canva", "Imagem/Documento", Severity.WARNING),
        "imageio": ("Apple ImageIO", "Imagem", Severity.INFO),

        # Adobe / PDF
        "adobe acrobat": ("Adobe Acrobat", "PDF", Severity.WARNING),
        "acrobat distiller": ("Acrobat Distiller", "PDF", Severity.INFO),
        "adobe pdf library": ("Adobe PDF Library", "PDF", Severity.INFO),
        "illustrator": ("Adobe Illustrator", "Imagem/PDF", Severity.WARNING),
        "indesign": ("Adobe InDesign", "PDF", Severity.INFO),

        # Serviços online PDF
        "ilovepdf": ("iLovePDF", "PDF", Severity.WARNING),
        "smallpdf": ("Smallpdf", "PDF", Severity.WARNING),
        "sejda": ("Sejda", "PDF", Severity.WARNING),
        "pdf24": ("PDF24", "PDF", Severity.WARNING),
        "sodapdf": ("Soda PDF", "PDF", Severity.WARNING),

        # Impressoras virtuais / recriação
        "microsoft print to pdf": ("Microsoft Print to PDF", "PDF", Severity.WARNING),
        "pdfcreator": ("PDFCreator", "PDF", Severity.WARNING),
        "bullzip": ("Bullzip PDF Printer", "PDF", Severity.WARNING),
        "cutepdf": ("CutePDF", "PDF", Severity.WARNING),
        "dopdf": ("doPDF", "PDF", Severity.WARNING),

        # Bibliotecas PDF
        "itext": ("iText", "PDF", Severity.INFO),
        "itextsharp": ("iTextSharp", "PDF", Severity.INFO),
        "pdfbox": ("Apache PDFBox", "PDF", Severity.INFO),
        "pdfium": ("PDFium", "PDF", Severity.INFO),
        "skia": ("Skia/PDF", "PDF", Severity.INFO),
        "ghostscript": ("Ghostscript", "PDF", Severity.WARNING),
        "mupdf": ("MuPDF", "PDF", Severity.INFO),
        "cairo": ("Cairo", "PDF", Severity.INFO),
        "reportlab": ("ReportLab", "PDF", Severity.INFO),
        "tcpdf": ("TCPDF", "PDF", Severity.INFO),
        "fpdf": ("FPDF", "PDF", Severity.INFO),
        "dompdf": ("Dompdf", "PDF", Severity.INFO),
        "wkhtmltopdf": ("wkhtmltopdf", "PDF", Severity.INFO),
        "prince": ("PrinceXML", "PDF", Severity.INFO),

        # Navegadores / renderização
        "chrome": ("Google Chrome", "Navegador/PDF", Severity.INFO),
        "chromium": ("Chromium", "Navegador/PDF", Severity.INFO),
        "edge": ("Microsoft Edge", "Navegador/PDF", Severity.INFO),
        "firefox": ("Mozilla Firefox", "Navegador/PDF", Severity.INFO),

        # Office
        "microsoft word": ("Microsoft Word", "Documento", Severity.INFO),
        "microsoft office": ("Microsoft Office", "Documento", Severity.INFO),
        "libreoffice": ("LibreOffice", "Documento", Severity.INFO),
        "openoffice": ("OpenOffice", "Documento", Severity.INFO),

        # Plataformas assinatura
        "docusign": ("DocuSign", "Assinatura Eletrônica", Severity.INFO),
        "clicksign": ("Clicksign", "Assinatura Eletrônica", Severity.INFO),
        "autentique": ("Autentique", "Assinatura Eletrônica", Severity.INFO),
        "zapsign": ("ZapSign", "Assinatura Eletrônica", Severity.INFO),
        "d4sign": ("D4Sign", "Assinatura Eletrônica", Severity.INFO),

        # Mensageria
        "whatsapp": ("WhatsApp", "Mensageria", Severity.WARNING),
        "telegram": ("Telegram", "Mensageria", Severity.INFO),
    }

    VERSION_PATTERNS = [
        r"\b(?:version|versão|ver\.?|v)\s*[:=]?\s*([0-9]+(?:\.[0-9]+){0,4})",
        r"\b([0-9]+(?:\.[0-9]+){1,4})\b",
        r"\bm([0-9]{2,4})\b",  # exemplo: Skia/PDF m112
    ]

    def apply(self, metadata: MetadataResult) -> list[Finding]:
        findings: list[Finding] = []

        raw = metadata.raw if metadata else {}

        metadata_text = " ".join(
            f"{key} {value}"
            for key, value in raw.items()
        ).lower()

        for term, (name, category, severity) in self.TERMS.items():
            if term in metadata_text:
                source_value = self._find_source_value(raw, term)
                version = self._extract_version(source_value or metadata_text)

                observed = name
                if version:
                    observed = f"{name} | versão/identificador: {version}"

                findings.append(
                    Finding(
                        severity=severity,
                        category=category,
                        title=f"Vestígio técnico de {name}",
                        description=self._build_description(name, category, version, severity),
                        evidence_source="Metadados",
                        observed_value=observed,
                        recommendation=(
                            "Correlacionar este vestígio com datas de criação/modificação, assinatura digital, "
                            "estrutura interna do arquivo, magic number e eventual documento originário."
                        ),
                        score=0.85 if severity == Severity.WARNING else 0.70,
                    )
                )

        return findings

    def _find_source_value(self, raw: dict, term: str) -> str | None:
        term_lower = term.lower()

        for key, value in raw.items():
            combined = f"{key} {value}".lower()

            if term_lower in combined:
                return f"{key}: {value}"

        return None

    def _extract_version(self, text: str) -> str | None:
        if not text:
            return None

        for pattern in self.VERSION_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)

            if match:
                return match.group(1)

        return None

    def _build_description(
        self,
        name: str,
        category: str,
        version: str | None,
        severity: Severity,
    ) -> str:
        version_text = (
            f" Foi identificado também possível número de versão/identificador técnico ({version})."
            if version
            else ""
        )

        if severity == Severity.WARNING:
            return (
                f"Foram encontrados vestígios associados a {name}, classificado na categoria {category}. "
                "Esse elemento pode indicar edição, conversão, impressão virtual, compressão ou reprocessamento "
                "do arquivo analisado. Isoladamente, não permite concluir adulteração, mas recomenda cautela "
                "quanto à versão apresentada como originária."
                f"{version_text}"
            )

        return (
            f"Foram encontrados vestígios associados a {name}, classificado na categoria {category}. "
            "Esse elemento possui relevância interpretativa para compreender o ambiente de geração, renderização "
            "ou processamento do arquivo, devendo ser analisado em conjunto com os demais dados técnicos."
            f"{version_text}"
        )