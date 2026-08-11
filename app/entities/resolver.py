from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

from app.entities.models import (
    ConfidenceComponent,
    EntityCandidate,
    EntityHypothesis,
    EntityResolutionResult,
    EntitySource,
    EntitySourceType,
    EntityType,
    NormalizedEntity,
    ValidationResult,
)
from app.entities.validators import DEFAULT_VALIDATORS, EntityValidator


class EntityResolver:
    AMBIGUITY_MARGIN = 0.12
    MINIMUM_CONFIDENCE = 0.50
    CONTEXT_TERMS = {
        EntityType.CPF: ("cpf", "cadastro de pessoa fisica"),
        EntityType.PHONE: ("telefone", "fone", "celular", "whatsapp", "contato"),
        EntityType.IP: ("endereco ip", "ip", "ipv4", "ipv6"),
        EntityType.MONEY: ("valor", "parcela", "preco", "total", "pagamento", "saldo", "r$"),
        EntityType.DATETIME: ("data", "datetime", "emitido", "assinado", "vencimento"),
        EntityType.EMAIL: ("email", "e-mail", "correio eletronico"),
    }
    SOURCE_COMPONENT = {
        EntitySourceType.STRUCTURED: 0.10,
        EntitySourceType.JSON: 0.08,
        EntitySourceType.METADATA: 0.08,
        EntitySourceType.NATIVE_TEXT: 0.05,
        EntitySourceType.OCR: 0.00,
        EntitySourceType.LEGACY_TEXT: 0.00,
    }

    def __init__(self, validators: tuple[EntityValidator, ...] = DEFAULT_VALIDATORS) -> None:
        self.validators = validators

    def resolve(self, candidates: list[EntityCandidate]) -> EntityResolutionResult:
        resolved = [self._resolve_candidate(candidate) for candidate in candidates]
        entities = [entity for entity in resolved if entity is not None]
        return EntityResolutionResult(tuple(candidates), tuple(self._deduplicate(entities)))

    def _resolve_candidate(self, candidate: EntityCandidate) -> NormalizedEntity | None:
        evaluations: list[tuple[ValidationResult, float, tuple[ConfidenceComponent, ...]]] = []
        for validator in self.validators:
            validation = validator.validate(candidate)
            if not validation.valid or validation.normalized_value is None:
                continue
            confidence, components = self._confidence(candidate, validation)
            if confidence >= self.MINIMUM_CONFIDENCE:
                evaluations.append((validation, confidence, components))

        evaluations.sort(key=lambda item: (-item[1], item[0].entity_type.value))
        if evaluations:
            top = evaluations[0]
            competing = evaluations[1] if len(evaluations) > 1 else None
            if competing is not None and top[1] - competing[1] < self.AMBIGUITY_MARGIN:
                hypotheses = tuple(
                    EntityHypothesis(item[0].entity_type, item[0].normalized_value or "", item[1], item[0].reasons)
                    for item in evaluations
                )
                return NormalizedEntity(
                    EntityType.AMBIGUOUS,
                    candidate.normalized_candidate,
                    round(top[1], 2),
                    (candidate.raw_value,),
                    (candidate.source,),
                    top[2],
                    {"candidate_types": [item.entity_type.value for item, _, _ in evaluations]},
                    hypotheses,
                )
            validation, confidence, components = top
            return NormalizedEntity(
                validation.entity_type,
                validation.normalized_value or candidate.normalized_candidate,
                round(confidence, 2),
                (candidate.raw_value,),
                (candidate.source,),
                components,
                validation.attributes,
            )

        digits = "".join(character for character in candidate.raw_value if character.isdigit())
        if len(digits) >= 5:
            components = (
                ConfidenceComponent("fallback", 0.0, "Sequência numérica preservada sem classificação específica."),
            )
            return NormalizedEntity(
                EntityType.UNKNOWN_NUMERIC_IDENTIFIER,
                digits,
                0.0,
                (candidate.raw_value,),
                (candidate.source,),
                components,
                {"reason": "no_validator_confirmed"},
            )
        return None

    def _confidence(
        self, candidate: EntityCandidate, validation: ValidationResult
    ) -> tuple[float, tuple[ConfidenceComponent, ...]]:
        components = [
            ConfidenceComponent("structural_validation", validation.structural_confidence, validation.reasons[0] if validation.reasons else "Validação estrutural."),
        ]
        if validation.formatting_confidence:
            components.append(ConfidenceComponent("formatting", validation.formatting_confidence, "Formatação explícita compatível."))

        context = self._normalize(candidate.source.context)
        field_hint = " ".join(candidate.initial_hints)
        terms = self.CONTEXT_TERMS.get(validation.entity_type, ())
        own_distance = self._nearest_context_distance(candidate, terms)
        if any(term.replace("-", "_") in field_hint for term in terms):
            own_distance = 0
        if own_distance is not None:
            components.append(ConfidenceComponent("context", 0.20, "Rótulo contextual compatível próximo ao valor."))

        conflicting_terms = (
            self.CONTEXT_TERMS[EntityType.PHONE]
            if validation.entity_type is EntityType.CPF
            else self.CONTEXT_TERMS[EntityType.CPF]
            if validation.entity_type is EntityType.PHONE
            else ()
        )
        conflict_distance = self._nearest_context_distance(candidate, conflicting_terms)
        if conflict_distance is not None and (
            own_distance is None or conflict_distance < own_distance
        ):
            components.append(
                ConfidenceComponent(
                    "conflicting_context",
                    -0.25,
                    "Rótulo concorrente está mais próximo do valor.",
                )
            )

        source_value = self.SOURCE_COMPONENT[candidate.source.source_type]
        if source_value:
            components.append(ConfidenceComponent("source_reliability", source_value, f"Origem {candidate.source.source_type.value} preservada."))

        unformatted_numeric = candidate.raw_value.isdigit()
        if unformatted_numeric and validation.entity_type in {EntityType.CPF, EntityType.PHONE} and any(
            term in context for term in ("contrato", "proposta", "identificador", "numero do documento")
        ):
            components.append(ConfidenceComponent("conflicting_context", -0.35, "Contexto indica identificador genérico/contratual."))

        return max(0.0, min(1.0, sum(component.value for component in components))), tuple(components)

    def _deduplicate(self, entities: list[NormalizedEntity]) -> list[NormalizedEntity]:
        unique: dict[tuple[EntityType, str], NormalizedEntity] = {}
        for entity in entities:
            key = (entity.entity_type, entity.normalized_value)
            current = unique.get(key)
            if current is None:
                unique[key] = entity
                continue
            raw_values = tuple(dict.fromkeys((*current.raw_values, *entity.raw_values)))
            sources = self._unique_sources((*current.sources, *entity.sources))
            preferred = entity if entity.confidence > current.confidence else current
            unique[key] = replace(preferred, raw_values=raw_values, sources=sources)
        return sorted(unique.values(), key=lambda item: (item.entity_type.value, item.normalized_value))

    @staticmethod
    def _unique_sources(sources: tuple[EntitySource, ...]) -> tuple[EntitySource, ...]:
        return tuple(dict.fromkeys(sources))

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        plain = "".join(character for character in decomposed if not unicodedata.combining(character))
        return re.sub(r"\s+", " ", plain.lower()).strip()

    @classmethod
    def _nearest_context_distance(
        cls, candidate: EntityCandidate, terms: tuple[str, ...]
    ) -> int | None:
        if not terms:
            return None
        before = cls._normalize(candidate.source.context_before)
        after = cls._normalize(candidate.source.context_after)
        distances: list[int] = []
        for term in terms:
            for match in re.finditer(rf"\b{re.escape(term)}\b", before):
                distances.append(len(before) - match.end())
            for match in re.finditer(rf"\b{re.escape(term)}\b", after):
                distances.append(match.start())
        return min(distances) if distances else None
