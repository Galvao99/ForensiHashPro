# Auditoria do pipeline de resultados do ForensiHash Web

## Escopo

Fluxo auditado: engine e serviços → `AnalysisResult` → `LegacyAnalysisAdapter` → `AnalysisContract` → serialização/presenter Web → componentes React. A auditoria não define contrato DDNA e não cria fatos ausentes.

## Entidades

`EntityExtractionService` coleta candidatos de texto nativo, OCR, metadados e JSON. `EntityResolver` produz `NormalizedEntity` com `entity_type`, `normalized_value`, confiança, valores brutos, atributos, hipóteses e fontes.

O adapter preserva cada entidade como `Fact`: `kind=entity` representa a classe geral; `data.type` guarda o tipo semântico original (`cpf`, `phone`, `ip`, `money`, `datetime`, `email`, `unknown_numeric_identifier` ou `ambiguous`). `data` também pode conter `normalized_value`, `raw_values`, confiança, atributos, hipóteses e provenance com fonte, `evidence_ref`, página, offsets, contexto, extractor e field path.

O presenter remove paths internos, mas mantém tipo e provenance pública. A causa do label genérico era exclusivamente o frontend: ele mostrava `Fact.kind` e ignorava `Fact.data.type`. A UI agora traduz o tipo para português, preserva o valor original nos detalhes e mascara apenas o resumo de identificadores pessoais/rede.

## Metadata e Timeline

`MetadataEngine` executa ExifTool com grupos (`-G`) e entrega o mapa original em `MetadataResult.raw`. `TimelineService` reconhece `CreationDate`, `CreateDate`, `ModifyDate`, `ModDate`, `MetadataDate`, `FileModifyDate`, `FileCreateDate`, `DateTimeOriginal` e `DateTimeCreated`, inclusive com prefixo de grupo.

O serviço também consome datas textuais selecionadas conservadoramente; signing time, timestamp técnico e validade de certificado; campos temporais JSON; timestamps do filesystem; revisões PDF estruturais sem timestamp; e início/fim operacionais da análise.

`AnalysisService` constrói a Timeline antes da conversão. O adapter serializa eventos, warnings e limitações em `AnalysisContract.timeline`; o presenter mantém timestamp, precisão, timezone, fonte, engine, evidência e nome público.

A perda observada era no frontend: `TimelineResultView` preferia `AnalysisSet.timeline_result.events`. Um agregado vazio substituía um contrato individual não vazio; um agregado preenchido podia misturar outros artefatos. A página do artefato agora usa exclusivamente `AnalysisContract.timeline`. Correlação continua consumindo o Analysis Set em sua seção própria.

Eventos `category=operational` aparecem em **Execução ForensiHash**, separados da **Timeline do artefato**. Eventos `structural_only` ou sem timestamp parseável ficam em **Eventos sem data determinável**.

## Assinaturas

`DigitalSignatureEngine` produz um resultado de estado mesmo quando nenhuma assinatura existe ou a análise é inaplicável. O adapter colocava esse objeto sempre em `signatures`, fazendo uma coleção de tamanho um parecer uma assinatura encontrada. Agora `AnalysisContract.signatures` contém item somente quando `has_signature is True`. Indisponibilidade e erro permanecem nas etapas/limitações. `signing_time` continua autodeclarado e recebe limitação explícita; validade do certificado não é descrita como momento da assinatura.

## Wiring das seções

| Seção | Fonte | Situação |
|---|---|---|
| Identificação | `file`, `declared_type`, `detected_type` | direta |
| Hashes | `hashes` | direta |
| Estrutura | `technical_structure` | direta; mapa varia por parser |
| Metadados | `metadata` | direta |
| Assinaturas | `signatures` | coleção semântica corrigida |
| Entidades | fatos `kind=entity`, `data.type`; `ip_addresses` legado | leitura corrigida |
| Timeline | `timeline` individual | fonte corrigida |
| Texto/OCR | `native_text`, `ocr` | direta e separada |
| Biometria | `biometrics` | direta |
| Evidências/findings | `facts`, `findings` | direta |
| Correlações | `AnalysisSet.correlation_result` | resultado separado |
| Limitações | `limitations` e registros da Timeline | direta |
| Execução | `processing_steps`, `execution`, eventos operacionais | visualmente separada |

## Gaps relevantes para DDNA

- Entidades são fatos tipados dentro de coleção genérica; não existe coleção `entities` dedicada no contrato individual.
- `technical_structure` e `metadata` são mapas heterogêneos dependentes do parser/engine.
- Provenance pública usa `evidence_ref`; paths internos são corretamente removidos.
- Timestamps sem timezone permanecem com timezone desconhecido e não devem virar instantes UTC implicitamente.
- Eventos operacionais e do artefato compartilham o contrato, diferenciados por categoria/fonte.
- Correlação pertence ao Analysis Set e não deve ser incorporada implicitamente ao contrato individual.
- Indisponibilidade de ferramenta aparece nas etapas/limitações; a UI não sintetiza o dado ausente.
