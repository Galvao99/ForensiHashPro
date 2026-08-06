# Contrato central de análise do ForensiHash

## Objetivo

O `AnalysisContract` é o envelope técnico, versionado e independente de Qt para
transportar uma análise entre núcleo, desktop, exportação JSON e testes. Ele não
é uma API web e não substitui imediatamente o `app.models.AnalysisResult`
legado. A conversão gradual é feita por `LegacyAnalysisAdapter`.

Versão inicial do schema: **1.0.0**.

## Estrutura

```text
AnalysisContract
├── schema_version, analysis_id, evidence_id, state
├── file, hashes, declared_type, detected_type
├── metadata, technical_structure
├── native_text, ocr, signatures, ip_addresses, timeline
├── comparison, biometrics
├── facts[]
├── findings[]
├── limitations[]
├── errors[]
├── external_results[]
├── processing_steps[]
└── execution
    ├── started_at, finished_at
    ├── engine_versions, rule_versions
    ├── integrations
    └── runtime
```

Campos de módulos não executados podem ser `null`, lista vazia ou objeto vazio,
conforme a cardinalidade. Uma lista vazia significa que a coleção está presente
e não possui itens; indisponibilidade, limite e falha devem aparecer em
`limitations`, `errors` e `processing_steps`, nunca ser inferidos apenas do
vazio.

## Separação semântica

### Fatos

`Fact` registra observação direta com `fact_id`, `kind`, `source` e `data`.
Fatos não possuem severidade ou conclusão investigativa. Exemplos: hashes,
magic number, metadados retornados e presença de objeto de assinatura.

### Findings

`FindingContract` contém interpretação de regra interna: `finding_id`,
`rule_id`, `severity`, título, statement, referências à evidência,
recomendação e confiança opcional. Severidade não representa score de fraude.

### Limitações

`Limitation` registra indisponibilidade, formato não aplicável, análise parcial
ou limite de segurança. Possui código estável, componente, mensagem e impacto.

### Erros

`ContractError` registra falha técnica com mensagem segura, instante com
timezone e detalhes controlados. A exceção original e stack trace não entram no
contrato.

### Resultados externos

`ExternalResult` atribui cada retorno a provedor, espécie, instante da consulta,
dados retornados e limitações. Métricas de terceiros não se tornam finding nem
severidade interna automaticamente.

### Execução

`execution` registra início, término, runtime, versões de motores/regras e
integrações efetivamente utilizadas. O adaptador inicial declara versão própria
e versão do conjunto de regras; versões detalhadas de cada parser deverão ser
preenchidas conforme os motores forem migrados nativamente.

## Estados e progresso

`AnalysisState`:

- `completed`;
- `partial`;
- `failed`;
- `cancelled`;
- `compromised`.

`ProgressEvent` é independente de UI e contém `event_id`, `analysis_id`, etapa,
status, mensagem, instante e percentual opcional. `ProgressStatus` aceita
`started`, `running`, `completed`, `failed` e `cancelled`. O worker Qt converte
esse evento em `Signal`, mas o coordenador não importa PySide6.

## IDs e rastreabilidade

- `analysis_id`: UUID aleatório criado uma vez pelo coordenador/caso de uso;
- `evidence_id`: UUID da aquisição imutável;
- IDs filhos: UUIDv5 sobre `analysis_id`, categoria, código técnico e posição;
- códigos e `rule_id`: identificadores técnicos estáveis, nunca texto traduzido;
- resultados legados sem `analysis_id` recebem UUIDv5 derivado do SHA-256 para
  conversão reprodutível.

Alterar descrição traduzida não altera IDs. A posição ainda participa de IDs de
coleções legadas porque elas não possuem identidade própria; isso é limitação
documentada até cada engine emitir IDs nativos.

## Regras de serialização JSON

- JSON UTF-8, `ensure_ascii=False`, chaves ordenadas e `allow_nan=False`;
- `Path` vira string quando permitido no contrato interno;
- caminhos originais, de trabalho e `source_path` são omitidos da exportação;
- datetime deve possuir timezone e usa ISO 8601;
- enums usam valores estáveis;
- bytes usam `{ "encoding": "hex", "value": "..." }`;
- `NaN` e infinitos são rejeitados;
- sets são ordenados antes da serialização;
- chaves sensíveis (`api_key`, `password`, `secret`, `token`) são omitidas;
- Qt, callbacks, handlers, exceções e objetos não controlados são rejeitados;
- conteúdo binário integral não é incluído.

Exemplo reduzido:

```json
{
  "analysis_id": "0d50b8a8-8db4-4e52-97ef-32ef20c55341",
  "evidence_id": "24c49d88-4187-4b12-8157-c762896b27ca",
  "schema_version": "1.0.0",
  "state": "completed",
  "facts": [
    {
      "fact_id": "da42b0e6-a895-58b6-a185-acb392633623",
      "kind": "hashes",
      "source": "hash_engine",
      "data": {"sha256": "..."}
    }
  ],
  "findings": [],
  "limitations": [],
  "errors": [],
  "external_results": []
}
```

## Versionamento

O schema segue SemVer independentemente da versão do aplicativo:

- PATCH: documentação, restrição mais clara ou campo opcional sem alterar
  interpretação de campos existentes;
- MINOR: novos campos opcionais, enums ou seções compatíveis;
- MAJOR: remoção, renomeação, mudança de tipo/semântica ou requisito novo.

Leitores devem verificar `schema_version`. Migrações futuras serão funções
explícitas `vN -> vN+1`; não haverá conversão silenciosa. A versão das regras e
motores permanece no bloco `execution`, separada da versão do schema.

## Compatibilidade e fluxo

```text
EvidenceSource
  -> AnalysisCoordinator (sem Qt)
  -> AnalysisService / engines legados
  -> AnalysisResult legado
  -> LegacyAnalysisAdapter
  -> AnalysisContract v1
       ├── ExportService -> JSON UTF-8
       └── AnalysisWorker -> contract_analyzed (Signal na borda)
```

O desktop continua consumindo `AnalysisResult` legado. Engines podem migrar
individualmente para fatos nativos sem alterar widgets. Exportadores novos
recebem o contrato e apenas o transformam.

## Extensibilidade futura

O contrato permite futura API, fila ou persistência, mas não implementa nenhum
desses recursos. Antes de exposição remota ainda são necessários contratos de
requisição, autorização, retenção, isolamento, quotas, storage, idempotência e
sandbox de parsers.

