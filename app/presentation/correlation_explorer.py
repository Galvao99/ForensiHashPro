from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable, Sequence
from app.correlation.v2.models import CorrelationEntity, EntityType
from app.correlation.v2.pipeline import CanonicalCasePipelineResult
from app.models import AnalysisResult


@dataclass(frozen=True, slots=True)
class ExplorerOccurrence:
    occurrence_id: str
    artifact_id: str
    artifact_name: str
    artifact_path: str | None
    raw_value: str
    normalized_value: str
    source_label: str
    provenance_label: str
    source_kind: str
    page: int | None = None
    context: str | None = None


@dataclass(frozen=True, slots=True)
class ExplorerElement:
    stable_id: str
    category: str
    type_label: str
    display_value: str
    normalized_value: str
    occurrences: tuple[ExplorerOccurrence, ...]
    relation_label: str
    deterministic_state: str | None = None

    @property
    def artifact_count(self) -> int:
        return len({item.artifact_id for item in self.occurrences})

    @property
    def occurrence_count(self) -> int:
        return len(self.occurrences)


@dataclass(frozen=True, slots=True)
class CorrelationExplorerModel:
    elements: tuple[ExplorerElement, ...]
    limitations: tuple[str, ...] = ()
    deterministic_element_ids: frozenset[str] = frozenset()
    verification_groups: tuple["CrossSourceVerificationGroup", ...] = ()


@dataclass(frozen=True, slots=True)
class CorrelationCategorySummary:
    key: str
    label: str
    element_count: int


@dataclass(frozen=True, slots=True)
class CrossSourceVerification:
    finding_id: str
    group_key: str
    group_label: str
    state: str
    title: str
    description: str
    source_file: str | None
    target_file: str | None
    details: tuple[tuple[str, str], ...]
    rule_id: str = ""
    rule_version: str = ""
    supporting_occurrences: tuple[ExplorerOccurrence, ...] = ()
    relation_id: str | None = None


@dataclass(frozen=True, slots=True)
class CrossSourceVerificationGroup:
    key: str
    label: str
    items: tuple[CrossSourceVerification, ...]

    @property
    def state_counts(self) -> tuple[tuple[str, int], ...]:
        order = ("OBSERVADA", "MATCH", "MISMATCH", "UNKNOWN", "NOT_APPLICABLE")
        return tuple((state, sum(item.state == state for item in self.items)) for state in order)


@dataclass(frozen=True, slots=True)
class CaseCorrelationSummary:
    correlated_element_ids: frozenset[str]
    correlated_element_count: int
    analyzed_artifact_count: int
    participating_artifact_ids: frozenset[str]
    categories: tuple[CorrelationCategorySummary, ...]
    verification_groups: tuple[CrossSourceVerificationGroup, ...]

    @property
    def participating_artifact_count(self) -> int:
        return len(self.participating_artifact_ids)

    @property
    def artifact_without_relation_count(self) -> int:
        return max(0, self.analyzed_artifact_count - self.participating_artifact_count)


_SUMMARY_CATEGORIES = {
    "identifiers": ("identities", "Identificadores e identidades"),
    "identities": ("identities", "Identificadores e identidades"),
    "temporal": ("temporal", "Temporal"),
    "metadata": ("metadata", "Metadados e origem"),
    "network": ("network", "Rede e ambiente"),
    "hashes": ("hashes", "Hashes e integridade"),
    "other": ("other", "Outros elementos técnicos"),
}


_TYPE_LABELS = {
    EntityType.CPF: "CPF",
    EntityType.CNPJ: "CNPJ",
    EntityType.DOCUMENT_IDENTIFIER: "Identificador documental",
    EntityType.EMAIL: "E-mail",
    EntityType.PHONE: "Telefone",
    EntityType.IP: "Endereço IP",
    EntityType.URL: "URL",
    EntityType.SHA256: "SHA-256",
    EntityType.MD5: "MD5",
    EntityType.TIMESTAMP: "Valor temporal",
    EntityType.FILENAME: "Nome de arquivo",
    EntityType.PRODUCER: "Produtor",
    EntityType.CREATOR: "Criador",
}

_FIELD_LABELS = {
    "accessed_at": "Data de acesso", "created_at": "Data de criação",
    "modified_at": "Data de modificação", "createdate": "Data de criação",
    "creationdate": "Data de criação", "modifydate": "Data de modificação",
    "moddate": "Data de modificação", "metadatadate": "Data de metadados",
    "producer": "Produtor",
    "creator": "Criador", "filename": "Nome do arquivo",
    "sourcefile": "Arquivo de origem", "native_text": "Corpo do documento",
}


def build_correlation_explorer_model(
    snapshot: CanonicalCasePipelineResult,
) -> CorrelationExplorerModel:
    """Project one canonical Case snapshot without executing analysis in the UI."""
    report = snapshot.graph
    case_findings = snapshot.case_result.findings
    states = {
        str(item.metadata.get("fact_id")): item.epistemic_state.value.upper()
        for item in case_findings
        if item.metadata.get("fact_id")
    }
    elements = [_from_graph_entity(entity, states.get(entity.stable_id)) for entity in report.entities]
    ordered = tuple(sorted(elements, key=_element_key))
    deterministic_ids: set[str] = set()
    for finding in case_findings:
        deterministic_ids.update(
            occurrence.entity_id for occurrence_id in finding.supporting_occurrence_ids
            if (occurrence := snapshot.index.occurrence(occurrence_id)) is not None
        )
        for key in ("fact_id", "declared_fact_id", "calculated_fact_id"):
            if value := finding.metadata.get(key):
                deterministic_ids.add(str(value))
    limitations = tuple(item.message for item in snapshot.case_result.limitations) + tuple(report.limitations)
    return CorrelationExplorerModel(
        ordered, limitations, frozenset(deterministic_ids),
        _verification_groups(snapshot),
    )


def filter_correlation_elements(
    elements: Iterable[ExplorerElement], search: str = "", category: str = "all",
    sort_by: str = "technical",
) -> tuple[ExplorerElement, ...]:
    needle = _search_key(search)
    filtered = (
        item for item in elements
        if (category == "all" or item.category == category)
        and (not needle or needle in _search_key(
            f"{item.type_label} {item.display_value} {item.normalized_value}"
        ))
    )
    if sort_by == "artifacts":
        key = lambda item: (-item.artifact_count, item.type_label.casefold(), item.normalized_value)
    elif sort_by == "occurrences":
        key = lambda item: (-item.occurrence_count, item.type_label.casefold(), item.normalized_value)
    else:
        key = _element_key
    return tuple(sorted(filtered, key=key))


def build_case_correlation_summary(
    model: CorrelationExplorerModel,
    results: Sequence[AnalysisResult],
) -> CaseCorrelationSummary:
    """Count distinct cross-artifact or deterministically verified canonical facts."""
    qualifying = tuple(
        item for item in model.elements
        if item.artifact_count >= 2 or item.stable_id in model.deterministic_element_ids
    )
    category_counts: dict[str, int] = defaultdict(int)
    category_labels: dict[str, str] = {}
    participant_ids: set[str] = set()
    for element in qualifying:
        key, label = _SUMMARY_CATEGORIES[element.category]
        category_counts[key] += 1
        category_labels[key] = label
        participant_ids.update(item.artifact_id for item in element.occurrences)
    category_order = ("identities", "temporal", "metadata", "network", "hashes", "other")
    categories = tuple(
        CorrelationCategorySummary(key, category_labels[key], category_counts[key])
        for key in category_order if category_counts[key]
    )
    artifacts = {str(Path(item.file_info.path).resolve()) for item in results}
    return CaseCorrelationSummary(
        frozenset(item.stable_id for item in qualifying), len(qualifying),
        len(artifacts), frozenset(participant_ids), categories, model.verification_groups,
    )


def _verification_groups(
    snapshot: CanonicalCasePipelineResult,
) -> tuple[CrossSourceVerificationGroup, ...]:
    grouped: dict[str, list[CrossSourceVerification]] = defaultdict(list)
    registry = {
        "case.identical_calculated_hash": ("identical_hash", "Hashes calculados idênticos"),
        "case.declared_hash_verification": ("declared_hash", "Hash declarado × hash calculado"),
        "case.signing_time_certificate_validity": (
            "signing_time_interval", "SigningTime × intervalo temporal do certificado",
        ),
        "case.document_date_metadata_temporal_relation": (
            "document_date_metadata", "Data documental × metadados",
        ),
    }
    for finding in snapshot.case_result.findings:
        definition = registry.get(finding.rule_id)
        if definition is None:
            continue
        group_key, group_label = definition
        supports = tuple(
            _from_occurrence(occurrence)
            for occurrence in snapshot.index.trace_occurrences(finding.supporting_occurrence_ids)
        )
        details = tuple(
            (_metadata_label(key), _metadata_value(key, value))
            for key, value in sorted(finding.metadata.items())
            if key in {
                "algorithm", "position", "delta_seconds", "metadata_field",
                "relation_type", "document_raw_value", "metadata_raw_value",
                "document_normalized_value", "metadata_normalized_value",
                "document_precision", "metadata_precision",
                "document_timezone_status", "metadata_timezone_status",
            }
        )
        grouped[group_key].append(CrossSourceVerification(
            finding.finding_id, group_key, group_label,
            _presentation_state(finding.epistemic_state.value), finding.title, finding.statement,
            supports[0].artifact_name if supports else None,
            supports[-1].artifact_name if len(supports) > 1 else None,
            details, finding.rule_id, finding.rule_version, supports, finding.relation_id,
        ))
    order = (
        "identical_hash", "declared_hash", "signing_time_interval",
        "document_date_metadata",
    )
    return tuple(
        CrossSourceVerificationGroup(key, items[0].group_label, tuple(items))
        for key in order if (items := grouped.get(key))
    )


def _metadata_label(key: str) -> str:
    return {
        "algorithm": "Algoritmo", "position": "Posição temporal",
        "delta_seconds": "Distância do intervalo (segundos)",
        "source_artifact_id": "Artefato da declaração",
        "target_artifact_id": "Artefato verificado",
        "signature_id": "Assinatura", "certificate_id": "Certificado",
        "signing_time_relation_id": "Relação SigningTime",
        "certificate_interval_relation_id": "Relação do intervalo",
        "metadata_field": "Campo de metadado",
        "relation_type": "Relação temporal observada",
        "document_raw_value": "Data documental · valor bruto",
        "metadata_raw_value": "Metadado · valor bruto",
        "document_normalized_value": "Data documental · valor normalizado",
        "metadata_normalized_value": "Metadado · valor normalizado",
        "document_precision": "Data documental · precisão",
        "metadata_precision": "Metadado · precisão",
        "document_timezone_status": "Data documental · timezone",
        "metadata_timezone_status": "Metadado · timezone",
    }.get(key, key.replace("_", " ").capitalize())


def _metadata_value(key: str, value: object) -> str:
    if key == "position":
        return {"inside": "dentro", "before": "antes", "after": "depois"}.get(str(value), str(value))
    if key == "relation_type":
        return {
            "document_date_before_metadata": "metadado posterior à data documental",
            "document_date_after_metadata": "metadado anterior à data documental",
            "temporal_overlap": "sobreposição temporal",
        }.get(str(value), str(value))
    if key in {"document_normalized_value", "metadata_normalized_value"}:
        return format_temporal_ptbr(str(value))
    if key in {"document_precision", "metadata_precision"}:
        return {
            "year": "ano", "month": "mês", "day": "dia", "minute": "minuto",
            "second": "segundo", "millisecond": "milissegundo",
            "microsecond": "microssegundo",
        }.get(str(value), str(value))
    if key in {"document_timezone_status", "metadata_timezone_status"}:
        return {"explicit": "explícito", "unknown": "não especificado"}.get(
            str(value), str(value),
        )
    return str(value)


def _presentation_state(value: str) -> str:
    return "OBSERVADA" if value == "observed" else value.upper()


def _from_graph_entity(
    entity: CorrelationEntity, deterministic: str | None = None,
) -> ExplorerElement:
    occurrences = tuple(_from_occurrence(item) for item in entity.occurrences)
    relation = (
        "Mesmo digest calculado a partir dos bytes"
        if deterministic == "MATCH"
        else "Mesmo valor normalizado observado"
        if entity.unique_file_count > 1
        else "Valor técnico observado"
    )
    display_value = (
        format_temporal_ptbr(entity.display_value)
        if entity.entity_type is EntityType.TIMESTAMP else entity.display_value
    )
    return ExplorerElement(
        entity.stable_id, _category(entity.entity_type),
        _entity_type_label(entity),
        display_value, entity.normalized_value, occurrences, relation, deterministic,
    )


def _from_occurrence(item: object) -> ExplorerOccurrence:
    entity_type = getattr(item, "entity_type")
    provenance = getattr(item, "provenance")
    source_file = getattr(item, "source_file")
    return ExplorerOccurrence(
        occurrence_id=str(getattr(item, "occurrence_id")),
        artifact_id=str(source_file.stable_id),
        artifact_name=str(source_file.display_name),
        artifact_path=source_file.path,
        raw_value=str(getattr(item, "raw_value")),
        normalized_value=str(getattr(item, "normalized_value")),
        source_label=_source_label(provenance.engine),
        provenance_label=_provenance_label(provenance),
        source_kind=getattr(item, "semantic_role") or _source_kind(entity_type, provenance.engine),
        page=provenance.page,
        context=getattr(item, "context"),
    )
def _entity_type_label(entity: CorrelationEntity) -> str:
    base = _TYPE_LABELS.get(entity.entity_type, entity.entity_type.value)
    if entity.semantic_role == "declared_hash":
        return f"{base} declarado"
    if entity.semantic_role == "hash_like":
        return f"String compatível com {base}"
    return base


def _category(entity_type: EntityType) -> str:
    if entity_type in {EntityType.CPF, EntityType.CNPJ, EntityType.DOCUMENT_IDENTIFIER}:
        return "identifiers"
    if entity_type in {EntityType.EMAIL, EntityType.PHONE}:
        return "identities"
    if entity_type in {EntityType.IP, EntityType.URL}:
        return "network"
    if entity_type in {EntityType.SHA256, EntityType.MD5}:
        return "hashes"
    if entity_type is EntityType.TIMESTAMP:
        return "temporal"
    if entity_type in {EntityType.PRODUCER, EntityType.CREATOR}:
        return "metadata"
    return "other"


def _source_kind(entity_type: EntityType, engine: str) -> str:
    if entity_type in {EntityType.SHA256, EntityType.MD5}:
        return "calculated_hash" if engine == "hash_engine" else "declared_hash"
    return engine


def _source_label(engine: str) -> str:
    return {
        "hash_engine": "Hash calculado",
        "metadata_engine": "Metadados",
        "ocr": "OCR",
        "text_extraction": "Texto nativo",
        "json_engine": "JSON estruturado",
        "ip_extraction": "Análise de IP",
        "evidence_manager": "Gerenciador de evidências",
        "filesystem": "Sistema de arquivos",
        "signature_engine": "Assinatura digital",
        "timeline": "Linha temporal",
        "contract_date_extractor": "Data documental no texto",
    }.get(engine, engine.replace("_", " ").title())


def _provenance_label(provenance: object) -> str:
    parts = [_source_label(str(getattr(provenance, "engine", "fonte técnica")))]
    field = getattr(provenance, "field", None) or getattr(provenance, "metadata_key", None)
    path = getattr(provenance, "json_path", None) or getattr(provenance, "path", None)
    page = getattr(provenance, "page", None)
    if field:
        parts.append(presentation_field_label(str(field)))
    if path and path != field:
        parts.append(str(path))
    if page is not None:
        parts.append(f"Página {page}")
    coordinates = (
        ("Bloco", getattr(provenance, "block", None)),
        ("Objeto PDF", getattr(provenance, "object_number", None)),
        ("Geração", getattr(provenance, "object_generation", None)),
        ("Stream", getattr(provenance, "stream_id", None)),
        ("Segmento", getattr(provenance, "segment", None)),
        ("Marcador", getattr(provenance, "marker", None)),
        ("Offset", getattr(provenance, "absolute_offset", None)),
        ("Início", getattr(provenance, "offset_start", None)),
        ("Fim", getattr(provenance, "offset_end", None)),
        ("Linha CSV", getattr(provenance, "csv_row", None)),
        ("Coluna CSV", getattr(provenance, "csv_column", None)),
        ("XMP", getattr(provenance, "xmp_key", None)),
    )
    parts.extend(f"{label} {value}" for label, value in coordinates if value is not None)
    precision = getattr(provenance, "timestamp_precision", None)
    timezone = getattr(provenance, "timezone_status", None)
    if precision:
        parts.append(f"Precisão {precision}")
    if timezone:
        parts.append(f"Fuso {timezone}")
    return " · ".join(parts)


def presentation_field_label(field: str) -> str:
    """Translate known internal keys without changing their canonical value."""
    leaf = field.rsplit(":", 1)[-1]
    return _FIELD_LABELS.get(leaf.casefold(), field)


def format_temporal_ptbr(value: str) -> str:
    """Format ISO observations without assigning a timezone to naive values."""
    raw = value.strip()
    if re.fullmatch(r"\d{4}", raw):
        return raw
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        year, month = raw.split("-")
        return f"{month}/{year}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return value
    shown = parsed.strftime("%d/%m/%Y · %H:%M:%S")
    if parsed.tzinfo is None:
        return shown
    offset = parsed.utcoffset()
    if offset is not None and offset.total_seconds() == 0:
        return f"{shown} UTC"
    suffix = parsed.strftime("%z")
    return f"{shown} UTC{suffix[:3]}:{suffix[3:]}" if suffix else shown


def compact_hash(value: str, edge: int = 6) -> str:
    if len(value) <= edge * 2 + 1:
        return value
    return f"{value[:edge]}…{value[-edge:]}"


def _search_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _element_key(item: ExplorerElement) -> tuple[str, str, str]:
    return item.category, item.type_label.casefold(), item.normalized_value
