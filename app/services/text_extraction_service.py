from pathlib import Path

import fitz
import pytesseract
from pdf2image import convert_from_path

ROOT = Path(__file__).resolve().parents[2]

TESSERACT = (
    ROOT
    / "tools"
    / "tesseract"
    / "tesseract.exe"
)

if TESSERACT.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT)

class TextExtractionService:
    def extract_text(self, file_path: str | Path) -> str:
        path = Path(file_path)

        if path.suffix.lower() == ".pdf":
            text = self._extract_pdf_text(path)

            if len(text.strip()) >= 80:
                return text

            return self._extract_pdf_ocr(path)

        if path.suffix.lower() in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
            return pytesseract.image_to_string(str(path), lang="por")

        return ""

    def _extract_pdf_text(self, path: Path) -> str:
        text = ""

        try:
            document = fitz.open(path)

            for page in document:
                text += page.get_text("text") + "\n"

            document.close()

        except Exception:
            return ""

        return text

    def _extract_pdf_ocr(self, path: Path) -> str:
        text = ""

        try:
            pages = convert_from_path(str(path), dpi=300)

            for page in pages:
                text += pytesseract.image_to_string(page, lang="por") + "\n"

        except Exception:
            return ""

        return text