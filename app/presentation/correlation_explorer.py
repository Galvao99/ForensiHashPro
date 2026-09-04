from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
from typing import Iterable, Sequence

from app.correlation.v2.engine import EvidenceGraphCorrelationEngine
from app.correlation.v2.models import CorrelationEntity, EntityType
from app.correlation.v2.providers import AnalysisResultCorrelationProvider
from app.investigation.investigation_context import InvestigationContext
from app.investigation.investigation_context_builder import InvestigationContextBuilder
from app.investigation.correlation_result import CorrelationResult
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


@dataclass(frozen=True, slots=True)
class CrossSourceVerificationGroup:
    key: str
    label: str
    items: tuple[CrossSourceVerification, ...]

    @property
    def state_counts(self) -> tuple[tuple[str, int], ...]:
        order = ("CONVERGENTE", "DIVERGENTE", "INDETERMINADA", "NÃO APLICÁVEL")
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
}

_FIELD_LABELS = {
    "accessed_at": "Data de acesso", "created_at": "Data de criação",
    "modified_at": "Data de modificação", "createdate": "Data de criação",
    "modifydate": "Data de modificação", "producer": "Produtor",
    "creator": "Criador", "filename": "Nome do arquivo",
    "sourcefile": "Arquivo de origem", "native_text": "Corpo do documento",
}


def build_correlation_explorer_model(
    results: Sequence[AnalysisResult],
    *,
    context: InvestigationContext | None = None,
) -> CorrelationExplorerModel:
    """Project cached analysis facts into a neutral, read-only UI model."""
    materialized = tuple(results)
    investigation = context or InvestigationContextBuilder().build(materialized)
    report = EvidenceGraphCorrelationEngine().correlate(
        AnalysisResultCorrelationProvider().provide_many(materialized)
    )
    elements = [_from_graph_entity(entity) for entity in report.entities]
    elements.extend(_metadata_elements(investigation, materialized))
    elements.extend(_declared_hash_elements(investigation, materialized))
    ordered = tuple(sorted(elements, key=_element_key))
    return CorrelationExplorerModel(ordered, report.limitations)


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
    correlation_result: CorrelationResult | None,
) -> CaseCorrelationSummary:
    """Summarize distinct values spanning >=2 artifacts; never count file pairs."""
    qualifying = tuple(item for item in model.elements if item.artifact_count >= 2)
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
    groups = _verification_groups(correlation_result)
    artifacts = {str(Path(item.file_info.path).resolve()) for item in results}
    return CaseCorrelationSummary(
        frozenset(item.stable_id for item in qualifying), len(qualifying),
        len(artifacts), frozenset(participant_ids), categories, groups,
    )


def _verification_groups(
    result: CorrelationResult | None,
) -> tuple[CrossSourceVerificationGroup, ...]:
    grouped: dict[str, list[CrossSourceVerification]] = defaultdict(list)
    for index, finding in enumerate(getattr(result, "findings", ()) or ()):
        category = str(getattr(finding, "category", ""))
        rule_id = str(getattr(finding, "rule_id", ""))
        if rule_id == "metadata_contract_date":
            group_key, group_label = "document_metadata_date", "Data documental × Metadados"
            days = getattr(finding, "metadata", {}).get("diferenca_dias")
            state = "DIVERGENTE" if isinstance(days, int) and days > 0 else "CONVERGENTE"
            detail_keys = (
                ("Data documental", "data_pactuacao"),
                ("Data de criação", "data_criacao_metadados"),
                ("Diferença em dias", "diferenca_dias"),
            )
        elif category in {"embedded_hash_match", "declared_hash_mismatch", "embedded_hash_unmatched"}:
            group_key, group_label = "declared_calculated_hash", "Hash declarado × Hash calculado"
            state = {
                "embedded_hash_match": "CONVERGENTE",
                "declared_hash_mismatch": "DIVERGENTE",
                "embedded_hash_unmatched": "INDETERMINADA",
            }[category]
            detail_keys = (("Algoritmo", "algorithm"), ("Hash declarado", "hash"))
        else:
            continue
        metadata = getattr(finding, "metadata", {})
        details = tuple(
            (label, format_temporal_ptbr(str(metadata[key])) if "data_" in key else str(metadata[key]))
            for label, key in detail_keys if key in metadata
        )
        finding_id = getattr(finding, "finding_id", "") or _stable(
            "verification", rule_id, category, str(index), str(getattr(finding, "source_file", ""))
        )
        grouped[group_key].append(CrossSourceVerification(
            finding_id, group_key, group_label, state,
            str(getattr(finding, "title", "Verificação técnica")),
            str(getattr(finding, "description", "")),
            getattr(finding, "source_file", None), getattr(finding, "target_file", None), details,
        ))
    order = ("document_metadata_date", "declared_calculated_hash")
    return tuple(
        CrossSourceVerificationGroup(key, items[0].group_label, tuple(items))
        for key in order if (items := grouped.get(key))
    )


def _from_graph_entity(entity: CorrelationEntity) -> ExplorerElement:
    occurrences = tuple(
        ExplorerOccurrence(
            occurrence_id=item.occurrence_id,
            artifact_id=item.source_file.stable_id,
            artifact_name=item.source_file.display_name,
            artifact_path=item.source_file.path,
            raw_value=item.raw_value,
            normalized_value=item.normalized_value,
            source_label=_source_label(item.provenance.engine),
            provenance_label=_provenance_label(item.provenance),
            source_kind=_source_kind(entity.entity_type, item.provenance.engine),
            page=item.provenance.page,
            context=item.context,
        )
        for item in entity.occurrences
    )
    kinds = {item.source_kind for item in occurrences}
    deterministic = (
        "MATCH" if entity.entity_type in {EntityType.SHA256, EntityType.MD5}
        and kinds == {"calculated_hash"} and entity.unique_file_count > 1 else None
    )
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
        _TYPE_LABELS.get(entity.entity_type, entity.entity_type.value),
        display_value, entity.normalized_value, occurrences, relation, deterministic,
    )


def _metadata_elements(
    context: InvestigationContext, results: Sequence[AnalysisResult],
) -> list[ExplorerElement]:
    paths = _paths_by_name(results)
    collected: dict[tuple[str, str], list[ExplorerOccurrence]] = defaultdict(list)
    for field, values in (("Produtor", context.producers), ("Criador", context.creators)):
        for artifact_name, value in sorted(values.items()):
            normalized = " ".join(value.casefold().split())
            display_name, path = _artifact_identity(context, artifact_name, paths)
            artifact_id = _stable("artifact", path or artifact_name)
            occurrence_id = _stable("metadata", artifact_id, field, normalized)
            collected[(field, normalized)].append(ExplorerOccurrence(
                occurrence_id, artifact_id, display_name, path, value, normalized,
                "Metadados", f"Campo de metadados · {field}", "metadata",
            ))
    return [
        ExplorerElement(
            _stable("metadata-entity", field, normalized), "metadata", field,
            items[0].raw_value, normalized, tuple(items),
            "Mesmo valor normalizado observado" if len({i.artifact_id for i in items}) > 1
            else "Valor de metadados observado",
        )
        for (field, normalized), items in collected.items()
    ]


def _declared_hash_elements(
    context: InvestigationContext, results: Sequence[AnalysisResult],
) -> list[ExplorerElement]:
    paths = _paths_by_name(results)
    collected: dict[tuple[str, str, str], list[ExplorerOccurrence]] = defaultdict(list)
    for artifact_name, values in sorted(context.declared_hashes.items()):
        for item in values:
            kind = "declared_hash" if item.declared else "hash_like"
            display_name, path = _artifact_identity(context, artifact_name, paths)
            artifact_id = _stable("artifact", path or artifact_name)
            occurrence_id = _stable("declared-hash", artifact_id, item.evidence_ref, item.value, str(item.start))
            collected[(item.algorithm, item.value, kind)].append(ExplorerOccurrence(
                occurrence_id, artifact_id, display_name, path, item.value, item.value,
                "Hash declarado" if item.declared else "String compatível com hash",
                _declared_hash_provenance(item), kind, item.page, item.context or None,
            ))
    return [
        ExplorerElement(
            _stable("declared-hash-entity", algorithm, value, kind), "hashes",
            f"{algorithm} declarado" if kind == "declared_hash" else f"String compatível com {algorithm}",
            value, value, tuple(items), "Valor observado; papel semântico não promovido", None,
        )
        for (algorithm, value, kind), items in collected.items()
    ]


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
    }.get(engine, engine.replace("_", " ").title())


def _provenance_label(provenance: object) -> str:
    parts = [_source_label(str(getattr(provenance, "engine", "fonte técnica")))]
    field = getattr(provenance, "field", None)
    path = getattr(provenance, "path", None)
    page = getattr(provenance, "page", None)
    if field:
        parts.append(presentation_field_label(str(field)))
    if path and path != field:
        parts.append(str(path))
    if page is not None:
        parts.append(f"Página {page}")
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


def _declared_hash_provenance(item: object) -> str:
    raw_source = str(getattr(item, "source_type", "fonte técnica"))
    parts = [{
        "native_text": "Corpo do documento",
        "legacy_text": "Texto extraído",
        "ocr": "OCR",
        "json": "Campo estruturado JSON",
    }.get(raw_source, raw_source)]
    field = getattr(item, "field_path", None)
    page = getattr(item, "page", None)
    if field:
        parts.append(str(field))
    if page is not None:
        parts.append(f"Página {page}")
    return " · ".join(parts)


def _paths_by_name(results: Sequence[AnalysisResult]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for result in results:
        raw = str(result.file_info.path)
        resolved = str(Path(result.file_info.path).resolve())
        paths[result.file_info.name] = raw
        paths[raw] = raw
        paths[resolved] = raw
    return paths


def _artifact_identity(
    context: InvestigationContext, key: str, paths: dict[str, str],
) -> tuple[str, str | None]:
    return context.display_name_for(key), paths.get(key)


def _stable(namespace: str, *values: str) -> str:
    payload = "\x1f".join((namespace, *values)).encode("utf-8")
    return sha256(payload).hexdigest()


def _search_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _element_key(item: ExplorerElement) -> tuple[str, str, str]:
    return item.category, item.type_label.casefold(), item.normalized_value
