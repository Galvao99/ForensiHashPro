# Sprint 3.5 — Correlation Engine V2 e Analysis Sets

## Arquitetura final

A correlação continua separada da análise individual. O desktop fornece
`AnalysisResult[]`; a web fornece `AnalysisContract[]` já concluídos. Ambos são
convertidos em `InvestigationContext` e avaliados por regras técnicas. Nenhuma
regra reabre arquivos, executa OCR, valida entidades ou recalcula hashes.

```text
Análises individuais
  -> NormalizedEntity / Fact(kind=entity)
  -> hashes calculados + ocorrências de hash declarado
  -> InvestigationContext
  -> CorrelationEngine V2
  -> CorrelationResult separado
```

## CorrelationFinding V2

O modelo legado foi estendido com defaults compatíveis: `finding_id`,
`category`, `evidence`, `entities`, `source_engine`, confidence técnica e
`limitations`. Título, descrição, severidade, arquivos, badges e metadata foram
preservados para `FindingPage` e `FindingCard`. IDs são UUIDv5 derivados da
regra, categoria, participantes e ocorrências.

Confidence representa somente a confiança determinística das entidades ou a
igualdade exata de hashes. Nunca representa fraude, autenticidade ou autoria.

## Comparabilidade semântica e entidades

`EntityCorrelationRule` consome somente entidades resolvidas. Um papel é
derivado conservadoramente de contexto ou `field_path`, para conceitos como
cliente, instituição, parcela, valor financiado, assinatura, contrato e IP de
origem/acesso. Match ou mismatch exige mesmo tipo e mesmo papel não nulo.
Papéis diferentes ou desconhecidos não produzem mismatch.

São suportados CPF, telefone, IP, dinheiro, data/hora e e-mail. `ambiguous` e
`unknown_numeric_identifier` não participam de mismatch forte.

## Source divergence

Entidades de texto nativo e OCR, na mesma evidência, com tipo e papel iguais e
valores diferentes produzem `source_divergence`. As duas ocorrências, contexts,
páginas e confidences são preservadas. A regra não escolhe uma fonte correta.

## Hash declarado e correlação

`DeclaredHashExtractor` centraliza o único regex e a normalização de MD5,
SHA-1, SHA-224, SHA-256, SHA-384 e SHA-512. Ele lê `TextSegment` nativo/OCR e
campos do JSON já analisado. Cada ocorrência contém algoritmo, valor, fonte,
evidence ref, página, offsets, contexto, field path e hint de artefato.

Hexadecimal sem label de hash é preservado como ocorrência, mas não gera
warning. O `HashEngine` continua sendo a única fonte dos hashes calculados.

- `embedded_hash_match`: valor declarado igual ao hash calculado de outro artefato;
- `embedded_hash_unmatched`: valor declarado sem correspondente no conjunto;
- `declared_hash_mismatch`: somente quando o contexto nomeia explicitamente um
  único artefato e o valor difere do hash calculado;
- `cross_file_match`: dois artefatos têm o mesmo SHA-256 calculado.

Unmatched registra que o artefato correspondente pode simplesmente não ter
sido incluído. Nenhuma regra infere ausência, intenção, autoria ou alteração.

## Analysis Set e API

`AnalysisSetResult` é independente do `AnalysisContract 1.0.0`. Ele contém ID,
estado, membros, timestamps, limitações e `CorrelationResult`. Membro falho vira
limitação; os contratos válidos continuam correlacionados. O estado é
`completed`, `partial` ou `failed` conforme contratos utilizáveis.

Na web, `POST /api/v1/analysis-sets` recebe de 1 a 50 `job_ids` terminais do
usuário autenticado. O backend lê apenas `result_json`, correlaciona e persiste
o resultado leve por uma hora. `GET /api/v1/analysis-sets/{set_id}` recupera o
resultado. Jobs, fila, concorrência e timeout da Sprint 1 não foram alterados.

## Frontend, desktop e segurança

O workspace web cria o set depois que todos os jobs ficam terminais. A seção
“Correlações do Analysis Set” apresenta resumo, severidade e “Ver detalhes”. No
desktop, `AnalysisWorker`, `CorrelationService`, `FindingPage` e `FindingCard`
permanecem compatíveis; o card inclui os campos V2 nos detalhes técnicos.

Respostas do set usam nomes públicos e UUIDs, nunca paths de staging. Exceções
de regra viram limitação segura. A taxonomia de papéis é pequena e
determinística. O resultado expira em uma hora e não constitui armazenamento
de caso. Não há Redis, Celery, storage distribuído, parser novo ou timeline.
