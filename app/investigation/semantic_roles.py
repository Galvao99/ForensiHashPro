from __future__ import annotations

import re
import unicodedata

from app.entities import EntitySource, EntityType


_ROLE_TERMS: dict[EntityType, tuple[tuple[str, tuple[str, ...]], ...]] = {
    EntityType.CPF: (
        ("customer", ("cpf cliente", "cpf contratante", "cpf titular", "cpf consumidor")),
        ("cpf", ("cpf",)),
    ),
    EntityType.PHONE: (
        ("customer", ("telefone cliente", "telefone do cliente", "celular cliente", "telefone contratante", "contato cliente")),
        ("institution", ("telefone empresa", "telefone da empresa", "telefone instituicao", "central atendimento", "sac")),
        ("primary_contact", ("telefone contato", "telefone", "celular")),
    ),
    EntityType.EMAIL: (
        ("customer", ("email cliente", "e-mail cliente", "email contratante")),
        ("institution", ("email empresa", "e-mail empresa", "email instituicao")),
        ("primary_contact", ("email", "e-mail")),
    ),
    EntityType.MONEY: (
        ("installment", ("valor parcela", "parcela",)),
        ("financed_amount", ("valor financiado", "montante financiado")),
        ("total_amount", ("valor total", "total contrato", "total")),
    ),
    EntityType.DATETIME: (
        ("signature_date", ("data assinatura", "assinado em", "assinatura")),
        ("contract_date", ("data contrato", "data contratacao", "pactuacao")),
        ("creation_date", ("creationdate", "createdate", "data criacao")),
    ),
    EntityType.IP: (
        ("origin_ip", ("ip origem", "origin ip")),
        ("access_ip", ("ip acesso", "endereco ip", "ip")),
    ),
}


def normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def semantic_role(entity_type: EntityType, source: EntitySource) -> str | None:
    text = normalized_text(
        " ".join(
            value
            for value in (source.field_path or "", source.context_before, source.context_after)
            if value
        )
    )
    if not text:
        return None
    for role, terms in _ROLE_TERMS.get(entity_type, ()):
        if any(normalized_text(term) in text for term in terms):
            return role
    return None


def comparable_role(entity_type: EntityType, sources: tuple[EntitySource, ...]) -> str | None:
    roles = {role for source in sources if (role := semantic_role(entity_type, source))}
    return next(iter(roles)) if len(roles) == 1 else None
