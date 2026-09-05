# Canonical Evidence Pipeline V1

## Fluxo canônico

```text
Specialized deterministic parser
  -> CorrelationCandidate (observação adaptada)
  -> CanonicalFact / CanonicalOccurrence + CanonicalProvenance
  -> EvidenceGraphCorrelationEngine
  -> CaseEvidenceIndex
  -> DeterministicCaseRule
  -> versioned CaseResult
  -> presenter / UI
```

O núcleo está em `app/correlation/v2`. Os nomes `CorrelationEntity`,
`CorrelationOccurrence` e `CorrelationProvenance` permanecem por compatibilidade;
`CanonicalFact`, `CanonicalOccurrence` e `CanonicalProvenance` são aliases do
mesmo modelo, não uma segunda implementação.

## Fact, Occurrence e Provenance

Um Fact representa `(tipo, valor normalizado, versão de normalização)`.
Qualificadores que alteram o significado técnico, hoje especialmente
`declared_hash` e `hash_like`, também participam da identidade. A identidade V2
anterior de fatos ordinários e hashes calculados foi preservada.

Occurrence representa uma aparição concreta do Fact. Duas páginas, um campo JSON
e uma região OCR nunca são fundidos apenas por terem o mesmo valor. A identidade
da ocorrência usa artefato, Fact e coordenadas primárias de Provenance. Anotações
de uma view derivada, como Timeline, não criam uma segunda ocorrência.

Provenance é opcional por campo e nunca é fabricada. O modelo suporta página,
faixa textual, offsets, objeto/stream, metadata/XMP, JSONPath, CSV, SQL, região
OCR, método de parsing, valor bruto, precisão temporal e estado de timezone.

## Igualdade, coocorrência e relação

`SAME_ENTITY_ACROSS_FILES` significa somente que o mesmo Fact normalizado foi
observado em artefatos distintos. Não significa identidade de pessoa, contrato,
autenticidade ou fraude. Coocorrência não promove associação. Uma
`STRUCTURED_ASSOCIATION` só pode ser fornecida explicitamente por parser que
possua contexto estrutural e inclui sua própria Provenance.

Hashes calculados, hashes declarados e strings compatíveis com hash são papéis
distintos e não são mesclados. OCR é uma fonte de extração, assim como texto
nativo, metadata e JSON; todos entram no mesmo índice, mantendo sua origem.

## Índice e regras

`CaseEvidenceIndex` materializa lookups por tipo+valor, artefato, tipo, natureza
da fonte e papel semântico. Consultas não percorrem `AnalysisResult` bruto.
Também resolve Fact, Occurrence e Relation por ID, permitindo a trilha:

```text
CaseFinding -> Relation -> Fact -> Occurrence -> Artifact / source locator
```

Regras implementam `DeterministicCaseRule`, declaram ID, versão e tipos exigidos,
e consomem apenas o índice. `CaseResult` mantém estado epistêmico separado de
severidade. Falha de execução é limitação operacional; ausência de entrada não é
MISMATCH.

## Parcialidade e fronteiras

Providers são independentes. Falha de OCR não invalida Facts de metadata já
produzidos. Estados futuros de módulo desabilitado, não encontrado e falha devem
permanecer em registros operacionais, não na evidência. O domínio não importa
PySide6 e todos os objetos são serializáveis.

`AnalysisResultCorrelationProvider` e
`InvestigationContextCorrelationProvider` são adaptadores legados. Novos parsers
devem emitir `CorrelationCandidate` (ou uma interface nativa equivalente) com
proveniência e papel semântico explícitos. CSV e SQL ainda não possuem producers.

## Migração

- **Canonical now:** correlation/v2, Evidence Graph, CaseEvidenceIndex,
  DeterministicCaseRule e CaseResult.
- **Adapter required:** AnalysisResult, AnalysisContract, TimelineEvent,
  NormalizedEntity e InvestigationContext.
- **Legacy, deprecate after parity:** CaseCorrelationIndex antigo e derivações
  analíticas do InvestigationContext.
- **Legacy, still required:** CorrelationService/CorrelationEngine,
  AnalysisSetCorrelator e seus consumidores de findings.
- **Follow-up:** migrar cada regra legada com testes de paridade e depois apontar
  Timeline/Technical Findings para read models canônicos.

Presenters podem traduzir e formatar, mas não criar relações, estados epistêmicos
ou significado forense. Se a evidência não suporta uma relação, o Fact e sua
Provenance permanecem e nenhuma conclusão é criada.
