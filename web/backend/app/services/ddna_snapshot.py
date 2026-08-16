from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import fitz


SNAPSHOT_DISCLAIMER = (
    "Este ForensiHash - DDNA Snapshot é um registro técnico derivado de uma análise "
    "realizada pelo ForensiHash. Ele não representa cadeia de custódia original, não "
    "comprova eventos anteriores à ingestão do artefato na ferramenta e não constitui "
    "DDNA Manifest. Este documento não é assinado digitalmente; seus resultados são "
    "limitados ao material analisado, e a ausência de informação não significa a "
    "inexistência de um evento."
)

_PAGE = fitz.paper_rect("a4")
_MARGIN = 54.0
_BOTTOM = 55.0
_TEXT = (0.12, 0.14, 0.17)
_MUTED = (0.38, 0.42, 0.47)
_LINE = (0.78, 0.80, 0.82)
_OFF_WHITE = (0.975, 0.97, 0.955)
_BLOCKED_KEYS = (
    "path", "token", "secret", "password", "cookie", "staging", "authorization"
)
_MAX_VALUE = 2_000
_MAX_ROWS = 250


@dataclass(frozen=True, slots=True)
class SnapshotPackage:
    snapshot_id: str
    generated_at: datetime
    base_name: str
    pdf_bytes: bytes
    pdf_sha256: str
    checksum_bytes: bytes
    zip_bytes: bytes


class DdnaSnapshotService:
    """Gera um registro derivado de um contrato individual já apresentado pelo Web."""

    def __init__(self, *, assets_root: Path | None = None) -> None:
        default_assets = (
            Path(__file__).resolve().parents[3] / "frontend" / "public" / "assets"
        )
        self.assets_root = Path(assets_root or default_assets)

    def generate(
        self,
        contract: dict[str, Any],
        *,
        generated_at: datetime | None = None,
        snapshot_id: str | None = None,
    ) -> SnapshotPackage:
        generated_at = generated_at or datetime.now(timezone.utc)
        if generated_at.tzinfo is None:
            raise ValueError("generated_at deve conter timezone.")
        snapshot_id = snapshot_id or str(uuid4())
        analysis_id = self._text(contract.get("analysis_id"), 120) or "analysis"
        safe_id = "".join(character for character in analysis_id if character.isalnum() or character in "-_")[:80] or "analysis"
        base_name = f"forensihash_ddna_snapshot_{safe_id}"
        pdf_bytes = self._build_pdf(contract, snapshot_id, generated_at)
        digest = sha256(pdf_bytes).hexdigest()
        checksum = f"SHA256({base_name}.pdf)={digest}\n".encode("ascii")
        archive = self._zip(base_name, pdf_bytes, checksum, generated_at)
        return SnapshotPackage(
            snapshot_id,
            generated_at,
            base_name,
            pdf_bytes,
            digest,
            checksum,
            archive,
        )

    def _build_pdf(
        self, contract: dict[str, Any], snapshot_id: str, generated_at: datetime
    ) -> bytes:
        document = fitz.open()
        document.set_metadata({
            "title": "ForensiHash - DDNA Snapshot",
            "author": "ForensiHash / ARQEN",
            "subject": "Registro técnico derivado de análise",
            "creator": f"ForensiHash {self._application_version()}",
            "producer": "ForensiHash Web / PyMuPDF",
            "creationDate": generated_at.strftime("D:%Y%m%d%H%M%S+00'00'"),
            "modDate": generated_at.strftime("D:%Y%m%d%H%M%S+00'00'"),
        })
        writer = _SnapshotWriter(document)
        self._cover(writer, contract, snapshot_id, generated_at)
        writer.new_page()
        writer.heading("1. IDENTIFICAÇÃO DO SNAPSHOT", level=1)
        writer.key_values([
            ("Snapshot ID", snapshot_id),
            ("Analysis ID", contract.get("analysis_id")),
            ("Gerado em", generated_at.isoformat()),
            ("Versão ForensiHash", self._application_version()),
            ("Analysis profile", self._profile(contract)),
            ("AnalysisContract schema", contract.get("schema_version")),
        ])
        writer.callout(SNAPSHOT_DISCLAIMER)

        file_data = self._mapping(contract.get("file"))
        hashes = self._mapping(contract.get("hashes"))
        artifact_rows = [
            ("Filename", file_data.get("name")),
            ("Tamanho", self._size(file_data.get("size_bytes"))),
            ("Extensão declarada", contract.get("declared_type")),
            ("MIME", file_data.get("mime_type") or self._find(contract.get("metadata"), ("mime",))),
            ("Tipo detectado", contract.get("detected_type")),
            ("Magic number", self._find(contract.get("technical_structure"), ("magic", "signature"))),
            ("Número de páginas", self._find(contract.get("technical_structure"), ("page_count", "pages"))),
            ("SHA-256 DO ARTEFATO", hashes.get("sha256")),
        ]
        writer.section("2. ARTEFATO ANALISADO", artifact_rows)

        writer.section("3. IDENTIFICAÇÃO TÉCNICA", [
            ("Formato detectado", contract.get("detected_type")),
            ("Versão", self._find(contract.get("technical_structure"), ("pdf_version", "version"))),
            ("MIME", file_data.get("mime_type") or self._find(contract.get("metadata"), ("mime",))),
            ("Magic", self._find(contract.get("technical_structure"), ("magic", "signature"))),
        ])
        writer.section(
            "4. HASHES DO ARTEFATO",
            [(key.upper(), value) for key, value in sorted(hashes.items())],
            mono=True,
        )
        self._metadata(writer, self._mapping(contract.get("metadata")))
        self._structure(writer, self._mapping(contract.get("technical_structure")))
        self._signatures(writer, contract.get("signatures"))
        self._findings(writer, contract.get("findings"))
        self._limitations(writer, contract)
        self._processing(writer, contract)
        self._provenance(writer, contract)

        writer.heading("12. INTEGRIDADE DO SNAPSHOT", level=1)
        writer.paragraph(
            "O hash SHA-256 dos bytes finais deste PDF está no arquivo .sha256 que "
            "acompanha o Snapshot. O hash não é inserido neste PDF porque isso alteraria "
            "os próprios bytes verificados e criaria uma recursão inválida."
        )
        writer.key_values([
            ("Hash do artefato analisado", hashes.get("sha256")),
            ("Hash do Snapshot PDF", "Consulte o arquivo .sha256 acompanhante."),
            ("Assinatura digital do Snapshot", "Não aplicada nesta versão."),
        ], mono=True)
        writer.finish()
        return document.tobytes(garbage=4, deflate=True, clean=True)

    def _cover(
        self,
        writer: _SnapshotWriter,
        contract: dict[str, Any],
        snapshot_id: str,
        generated_at: datetime,
    ) -> None:
        writer.new_page(cover=True)
        arqen = self.assets_root / "arqen_logo_preta.png"
        forensihash = self.assets_root / "forensihash_logo_preto.png"
        if arqen.is_file():
            writer.image(arqen, fitz.Rect(_MARGIN, 45, 125, 68))
        writer.text_at("ARQEN", 78, 6.5, _MUTED)
        if forensihash.is_file():
            writer.image(forensihash, fitz.Rect(_MARGIN, 120, 360, 166))
        else:
            writer.text_at("FORENSIHASH", 124, 24, _TEXT)
        writer.text_at("DDNA SNAPSHOT", 202, 27, _TEXT)
        writer.text_at("Registro técnico derivado de análise", 239, 12, _MUTED)
        writer.rule(285)
        file_data = self._mapping(contract.get("file"))
        cover_rows = [
            ("Artefato", file_data.get("name")),
            ("Analysis ID", contract.get("analysis_id")),
            ("Snapshot ID", snapshot_id),
            ("Gerado em", generated_at.isoformat()),
            ("Versão ForensiHash", self._application_version()),
        ]
        y = 320.0
        for label, value in cover_rows:
            writer.text_at(label.upper(), y, 7, _MUTED)
            y += 17
            writer.text_at(self._text(value), y, 11, _TEXT, mono=label.endswith("ID"))
            y += 31
        writer.rule(y + 5)
        writer.y = y + 36
        writer.paragraph(
            "Este documento registra resultados técnicos observados durante uma análise ForensiHash.",
            size=12,
        )
        writer.y += 12
        writer.paragraph(SNAPSHOT_DISCLAIMER, size=8.5, color=_MUTED)

    def _metadata(self, writer: _SnapshotWriter, metadata: dict[str, Any]) -> None:
        if not metadata:
            return
        writer.heading("5. METADADOS", level=1)
        priority_names = ("createdate", "modifydate", "metadatadate", "producer", "creator", "author")
        normalized = {self._normalized(key): (key, value) for key, value in metadata.items()}
        priority: list[tuple[str, Any]] = []
        consumed: set[str] = set()
        for name in priority_names:
            match = next((item for key, item in normalized.items() if key.endswith(name)), None)
            if match:
                priority.append(match)
                consumed.add(match[0])
        writer.key_values(priority)
        remaining = [(key, metadata[key]) for key in sorted(metadata) if key not in consumed]
        if remaining:
            writer.heading("Demais metadados", level=2)
            writer.key_values(remaining[:_MAX_ROWS])

    def _structure(self, writer: _SnapshotWriter, structure: dict[str, Any]) -> None:
        rows = list(self._flatten(structure))[:_MAX_ROWS]
        if rows:
            writer.section("6. ESTRUTURA", rows)

    def _signatures(self, writer: _SnapshotWriter, value: Any) -> None:
        signatures = value if isinstance(value, list) else []
        writer.heading("7. ASSINATURAS INCORPORADAS", level=1)
        if not signatures:
            writer.paragraph("Não foi reportada assinatura incorporada.")
            return
        for index, signature in enumerate(signatures, 1):
            writer.heading(f"Assinatura reportada #{index}", level=2)
            writer.key_values(list(self._flatten(signature))[:80])

    def _findings(self, writer: _SnapshotWriter, value: Any) -> None:
        findings = value if isinstance(value, list) else []
        if not findings:
            return
        writer.heading("8. FINDINGS", level=1)
        allowed = ("title", "statement", "rule_id", "severity", "source", "evidence_refs", "confidence", "limitation")
        for index, finding in enumerate(findings[:100], 1):
            item = self._mapping(finding)
            writer.heading(f"{index}. {self._text(item.get('title') or 'Finding técnico')}", level=2)
            writer.key_values([(key, item.get(key)) for key in allowed if item.get(key) is not None])

    def _limitations(self, writer: _SnapshotWriter, contract: dict[str, Any]) -> None:
        limitations = contract.get("limitations") if isinstance(contract.get("limitations"), list) else []
        errors = contract.get("errors") if isinstance(contract.get("errors"), list) else []
        skipped = [
            step for step in contract.get("processing_steps", [])
            if isinstance(step, dict) and step.get("status") == "skipped"
        ]
        if not limitations and not errors and not skipped:
            return
        writer.heading("9. LIMITACOES", level=1)
        for item in limitations[:100]:
            data = self._mapping(item)
            writer.bullet(data.get("message") or data.get("code") or "Limitação reportada.")
        for item in errors[:100]:
            data = self._mapping(item)
            writer.bullet(data.get("message") or data.get("code") or "Erro parcial reportado.")
        for step in skipped[:100]:
            details = self._mapping(step.get("safe_details"))
            if details.get("reason") == "capability_not_enabled":
                capability = details.get("capability") or step.get("component")
                writer.bullet(f"{capability}: análise não executada neste perfil.")
            else:
                writer.bullet(step.get("user_message") or step.get("technical_message") or "Etapa não executada.")

    def _processing(self, writer: _SnapshotWriter, contract: dict[str, Any]) -> None:
        execution = self._mapping(contract.get("execution"))
        steps = contract.get("processing_steps") if isinstance(contract.get("processing_steps"), list) else []
        writer.heading("10. PROCESSAMENTO FORENSIHASH", level=1)
        writer.paragraph(
            "Eventos desta seção descrevem a operação da ferramenta e não a história documental do artefato.",
            color=_MUTED,
        )
        writer.key_values([
            ("Análise iniciada", execution.get("started_at")),
            ("Análise concluída", execution.get("finished_at")),
            ("Profile", self._profile(contract)),
            ("Runtime", execution.get("runtime")),
        ])
        for step in steps[:150]:
            if not isinstance(step, dict):
                continue
            writer.bullet(
                f"{self._text(step.get('code') or step.get('component'))} - "
                f"{self._text(step.get('status'))} - "
                f"{self._text(step.get('finished_at') or step.get('user_message'))}"
            )

    def _provenance(self, writer: _SnapshotWriter, contract: dict[str, Any]) -> None:
        writer.heading("11. PROVENANCE / REFERENCES", level=1)
        writer.key_values([
            ("Evidence ref", contract.get("evidence_id")),
            ("Analysis ref", contract.get("analysis_id")),
        ], mono=True)
        sources = sorted({
            self._text(fact.get("source"))
            for fact in contract.get("facts", [])
            if isinstance(fact, dict) and fact.get("source")
        })
        if sources:
            writer.key_values([("Sources reportadas", ", ".join(sources))])

    @staticmethod
    def _zip(base_name: str, pdf: bytes, checksum: bytes, generated_at: datetime) -> bytes:
        target = BytesIO()
        timestamp = generated_at.astimezone(timezone.utc)
        date_time = (max(1980, timestamp.year), timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second)
        with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for suffix, content in (("pdf", pdf), ("sha256", checksum)):
                info = ZipInfo(f"{base_name}.{suffix}", date_time=date_time)
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, content)
        return target.getvalue()

    @staticmethod
    def _application_version() -> str:
        try:
            return version("forensihash-pro")
        except PackageNotFoundError:
            return "0.1.0"

    @staticmethod
    def _profile(contract: dict[str, Any]) -> str:
        execution = DdnaSnapshotService._mapping(contract.get("execution"))
        return DdnaSnapshotService._text(execution.get("analysis_profile") or "unspecified").upper()

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _normalized(value: Any) -> str:
        return "".join(character for character in str(value).lower() if character.isalnum())

    @classmethod
    def _text(cls, value: Any, maximum: int = _MAX_VALUE) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            text = ", ".join(cls._text(item, 300) for item in value)
        elif isinstance(value, dict):
            text = "; ".join(
                f"{cls._text(key, 80)}={cls._text(value[key], 300)}" for key in sorted(value)
            )
        else:
            text = str(value)
        text = " ".join(text.replace("\x00", "").split())
        return text[:maximum] + ("..." if len(text) > maximum else "")

    @classmethod
    def _flatten(cls, value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
        if isinstance(value, dict):
            for key in sorted(value):
                normalized = cls._normalized(key)
                if any(blocked in normalized for blocked in _BLOCKED_KEYS):
                    continue
                label = f"{prefix}.{key}" if prefix else str(key)
                child = value[key]
                if isinstance(child, (dict, list)):
                    yield from cls._flatten(child, label)
                elif child is not None:
                    yield label, child
        elif isinstance(value, list):
            for index, child in enumerate(value[:100]):
                yield from cls._flatten(child, f"{prefix}[{index}]")

    @classmethod
    def _find(cls, value: Any, names: tuple[str, ...]) -> Any:
        normalized_names = tuple(cls._normalized(name) for name in names)
        for key, item in cls._flatten(value):
            normalized = cls._normalized(key.rsplit(".", 1)[-1])
            if any(name in normalized for name in normalized_names):
                return item
        return None

    @staticmethod
    def _size(value: Any) -> str:
        return f"{value} bytes" if isinstance(value, int) else ""


class _SnapshotWriter:
    def __init__(self, document: fitz.Document) -> None:
        self.document = document
        self.page: fitz.Page | None = None
        self.y = _MARGIN

    def new_page(self, *, cover: bool = False) -> None:
        self.page = self.document.new_page(width=_PAGE.width, height=_PAGE.height)
        self.page.draw_rect(self.page.rect, color=_OFF_WHITE, fill=_OFF_WHITE, overlay=False)
        self.y = 45 if cover else _MARGIN

    def image(self, path: Path, rect: fitz.Rect) -> None:
        assert self.page is not None
        self.page.insert_image(rect, filename=str(path), keep_proportion=True)

    def text_at(
        self, text: Any, y: float, size: float, color: tuple[float, float, float], *, mono: bool = False
    ) -> None:
        assert self.page is not None
        self.page.insert_text(
            fitz.Point(_MARGIN, y),
            DdnaSnapshotService._text(text),
            fontsize=size,
            fontname="cour" if mono else "helv",
            color=color,
        )

    def rule(self, y: float) -> None:
        assert self.page is not None
        self.page.draw_line(fitz.Point(_MARGIN, y), fitz.Point(_PAGE.width - _MARGIN, y), color=_LINE, width=0.6)

    def heading(self, text: str, *, level: int) -> None:
        size = 15 if level == 1 else 10
        before = 24 if level == 1 else 14
        self._ensure(before + size + 12)
        self.y += before
        self._lines(text, size=size, color=_TEXT, bold=True)
        if level == 1:
            self.rule(self.y + 4)
            self.y += 12
        else:
            self.y += 5

    def section(self, title: str, rows: list[tuple[str, Any]], *, mono: bool = False) -> None:
        present = [(label, value) for label, value in rows if DdnaSnapshotService._text(value)]
        if not present:
            return
        self.heading(title, level=1)
        self.key_values(present, mono=mono)

    def key_values(self, rows: list[tuple[str, Any]], *, mono: bool = False) -> None:
        for label, value in rows:
            text = DdnaSnapshotService._text(value)
            if not text:
                continue
            self._ensure(40)
            self._lines(DdnaSnapshotService._text(label, 180).upper(), size=6.7, color=_MUTED, bold=True)
            self._lines(text, size=8.4, color=_TEXT, mono=mono or "hash" in label.lower())
            self.y += 8

    def paragraph(
        self, text: Any, *, size: float = 9, color: tuple[float, float, float] = _TEXT
    ) -> None:
        self._lines(DdnaSnapshotService._text(text), size=size, color=color)
        self.y += 8

    def callout(self, text: Any) -> None:
        self._ensure(120)
        start = self.y
        self.y += 12
        self._lines(DdnaSnapshotService._text(text), size=8.2, color=_TEXT, left=_MARGIN + 14, right=_PAGE.width - _MARGIN - 14)
        self.y += 12
        assert self.page is not None
        self.page.draw_rect(fitz.Rect(_MARGIN, start, _PAGE.width - _MARGIN, self.y), color=_LINE, width=0.6)

    def bullet(self, text: Any) -> None:
        self._ensure(30)
        assert self.page is not None
        self.page.draw_circle(fitz.Point(_MARGIN + 3, self.y + 4), 1.4, color=_MUTED, fill=_MUTED)
        self._lines(DdnaSnapshotService._text(text), size=8.2, color=_TEXT, left=_MARGIN + 12)
        self.y += 5

    def _lines(
        self,
        text: str,
        *,
        size: float,
        color: tuple[float, float, float],
        bold: bool = False,
        mono: bool = False,
        left: float = _MARGIN,
        right: float = _PAGE.width - _MARGIN,
    ) -> None:
        font = "cour" if mono else "hebo" if bold else "helv"
        for line in self._wrap(text, right - left, size, font):
            self._ensure(size * 1.55)
            assert self.page is not None
            self.page.insert_text(fitz.Point(left, self.y + size), line, fontsize=size, fontname=font, color=color)
            self.y += size * 1.4

    @staticmethod
    def _wrap(text: str, width: float, size: float, font: str) -> list[str]:
        words = text.split() or [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and fitz.get_text_length(candidate, fontname=font, fontsize=size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def _ensure(self, height: float) -> None:
        if self.page is None or self.y + height > _PAGE.height - _BOTTOM:
            self.new_page()

    def finish(self) -> None:
        count = len(self.document)
        for index, page in enumerate(self.document, 1):
            page.draw_line(
                fitz.Point(_MARGIN, _PAGE.height - 38),
                fitz.Point(_PAGE.width - _MARGIN, _PAGE.height - 38),
                color=_LINE,
                width=0.5,
            )
            page.insert_text(
                fitz.Point(_MARGIN, _PAGE.height - 22),
                "FORENSIHASH - DDNA SNAPSHOT",
                fontsize=6.5,
                fontname="helv",
                color=_MUTED,
            )
            page.insert_text(
                fitz.Point(_PAGE.width - _MARGIN - 42, _PAGE.height - 22),
                f"{index} / {count}",
                fontsize=6.5,
                fontname="cour",
                color=_MUTED,
            )
