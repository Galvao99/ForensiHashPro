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

## Declared Hash Verification V1

`case.declared_hash_verification`, versão `1`, verifica somente relações
`DECLARED_HASH_TARGET`. O sujeito da relação é o ID de uma Occurrence com role
`declared_hash`; o objeto é um único artifact ID. A relação é criada upstream a
partir de suporte estrutural e nunca por igualdade do digest.

O adapter JSON atual cria esse binding somente quando `filename`/`file_name` e
`sha256`/`sha_256`/`md5` são campos irmãos do mesmo objeto e o filename resolve,
por igualdade exata normalizada, para exatamente um artefato diferente da fonte.
Nomes parecidos, proximidade textual, OCR, ordem, diretório e igualdade do hash
não resolvem alvo. Alvos ausentes ou ambíguos não geram binding.

Com binding, a regra procura exatamente uma Occurrence `calculated_hash` do
mesmo algoritmo no artefato-alvo. Igualdade normalizada produz `MATCH`; diferença
produz `MISMATCH`. Ambas referenciam a declaração, o hash calculado e a relação.
Sem binding, sem algoritmo calculado compatível ou com input ambíguo, a regra não
produz Finding. Isso representa ausência de comparação aplicável; não promove
ausência a `UNKNOWN`, `NOT_APPLICABLE` ou `MISMATCH` artificialmente.

O caminho legado difere intencionalmente: ele aceita igualdade global de digest
como match e pode usar correspondência parcial de filename para mismatch. Esses
comportamentos permanecem somente por compatibilidade e não integram a regra
canônica.

## SigningTime × Certificate Validity V1

`case.signing_time_certificate_validity`, versão `1`, consome somente as relações
estruturais `SIGNATURE_HAS_SIGNING_TIME`, `SIGNATURE_USES_CERTIFICATE` e
`CERTIFICATE_VALIDITY_INTERVAL`. Os Facts temporais usam roles distintos:

- `signer_declared_signing_time`;
- `trusted_timestamp_time`;
- `certificate_not_before`;
- `certificate_not_after`.

O trusted timestamp não substitui SigningTime. O provider cria um binding por
`SignatureRecord` completo. A projeção agregada anterior continua aceita somente
como compatibilidade para resultados antigos e só é vinculada quando representa
exatamente uma assinatura.

O intervalo é inclusivo: `NotBefore <= SigningTime <= NotAfter`. Valores aware
são comparados pelo instante UTC. Valores naive nunca recebem timezone; só são
comparáveis a um intervalo também naive da mesma estrutura. Mistura de domínios
não produz Finding. A V1 exige precisão de minuto ou melhor; precisão de dia,
mês ou ano não é completada artificialmente.

`MATCH` significa somente que o SigningTime observado está dentro do intervalo
declarado pelo certificado associado. `MISMATCH` significa somente que está
fora. Nenhum estado afirma validade criptográfica, confiança, cadeia, revogação,
autenticidade, autoria ou validade jurídica. Intervalos com NotAfter anterior a
NotBefore geram `RuleExecutionLimitation`; inputs ausentes, ambíguos ou
temporalmente incompatíveis não geram MISMATCH.

## Signature Evidence Model V1

`DigitalSignatureResult.signatures` é a coleção canônica. Cada
`SignatureRecord` é independente e serializável, com `signature_id`, locator,
certificado signatário, SigningTime declarado, eventual trusted timestamp e os
campos técnicos já extraídos. Os campos agregados são uma projeção do primeiro
record para consumidores legados; eles não reconstroem a coleção.

O parser percorre todas as entradas de `PdfFileReader.embedded_signatures`. A
ordenação é determinística por revisão assinada e locator. O locator preserva,
conforme disponível, nome do campo, referência indireta do objeto de assinatura,
revisão assinada e ByteRange; o índice embedded é somente fallback. O
`signature_id` deriva do artefato e desse locator, nunca de nome de signatário,
horário ou representação Python do objeto.

O certificado vinculado é especificamente `EmbeddedPdfSignature.signer_cert`,
não um certificado escolhido da cadeia. Quando DER está disponível, seu ID é
`certificate:sha256:<fingerprint>`, calculado por SHA-256 sobre o DER. A
fingerprint identifica o certificado; não é hash de artefato, prova de confiança
ou estado de validade e não entra na correlação genérica de hashes de arquivos.

O grafo emite, por assinatura, relações determinísticas:

```text
Artifact --ARTIFACT_CONTAINS_SIGNATURE--> Signature
Signature --SIGNATURE_USES_CERTIFICATE--> Certificate
Signature --SIGNATURE_HAS_SIGNING_TIME--> SigningTime occurrence
Certificate --CERTIFICATE_VALIDITY_INTERVAL--> NotBefore/NotAfter occurrences
```

Assinaturas que reutilizam um certificado compartilham a identidade do
certificado, mas preservam records, ocorrências e bindings distintos. O índice
permite consultas por artifact, signature ID, certificate ID, papel semântico,
Fact ID e Occurrence ID. A regra temporal avalia cada binding separadamente.

Falha em uma entrada gera `SignatureParseIssue` sanitizada sem remover records
irmãos válidos. É limitação operacional, nunca Finding ou MISMATCH. O modelo não
retém objetos pyHanko vivos. SigningTime declarado e trusted timestamp permanecem
papéis diferentes; V1 não amplia a análise CMS para extrair RFC 3161.

O modelo não executa validação criptográfica, cadeia, revogação ou confiança e
não conclui autenticidade, autoria, fraude ou validade jurídica.

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
