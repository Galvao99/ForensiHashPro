# Sprint 4 — Timeline Web V2

## Objetivo

A Timeline V2 consolida fatos temporais e eventos estruturais já produzidos pela
análise. Ela não reabre a evidência, não reexecuta engines e não transforma ordem,
offset ou divergência em conclusão sobre fraude, alteração ou causalidade.

## Arquitetura anterior

`TimelineService`, `TimelinePage` e widgets interpretavam datas separadamente.
Havia dois modelos `TimelineEvent`, o serviço não participava do pipeline oficial
e `AnalysisContract.timeline` normalmente permanecia nulo.

## Arquitetura final

```text
engines e parsers existentes
        -> AnalysisResult
        -> TimelineService
        -> TimelineResult(events, warnings, limitations)
        -> AnalysisResult.timeline_events
        -> LegacyAnalysisAdapter
        -> AnalysisContract 1.0.0.timeline
        -> desktop / web / Analysis Set
```

`TimelineService` trabalha somente com dados em memória já obtidos. Falha na
Timeline produz etapa parcial segura e não invalida o restante da análise.

## TimelineEvent

O modelo central fica em `app/models/timeline_event.py` e contém ID determinístico,
tipo, categoria, descrição factual, timestamp normalizado, valor bruto, timezone,
status de timezone, precisão, origem, engine, `evidence_ref`, nome público, página,
offset, caminho de campo, contexto, revisão, ordem estrutural, atributos, confiança
técnica e limitações. As propriedades `date`, `source` e `formatted_date` mantêm a
compatibilidade de leitura do desktop legado.

`temporal_status` usa:

- `timestamped`: data e horário identificados;
- `date_only`: precisão de ano, mês ou dia;
- `structural_only`: evento cuja ordem estrutural é conhecida, sem data;
- `time_unknown` permanece reservado para fontes futuras que declarem evento sem
  componente temporal utilizável.

## Parser temporal

`TemporalParser` reconhece formatos ISO, ExifTool, PDF (`D:`), brasileiros e
valores `datetime` já estruturados. O parser:

- preserva `raw_timestamp`;
- preserva `Z` e offsets explícitos;
- não assume timezone para valores sem offset;
- só armazena normalização UTC separada quando existe offset explícito;
- preserva precisão `year`, `month`, `day`, `minute`, `second`, `millisecond` ou
  `microsecond`;
- rejeita datas impossíveis e números Unix-like sem semântica suficiente.

## Fontes temporais

### Metadados

Campos reconhecidos incluem CreationDate, CreateDate, ModifyDate, ModDate,
MetadataDate, FileModifyDate, FileCreateDate, DateTimeOriginal e DateTimeCreated.
O grupo ExifTool e o nome original do campo são preservados. Datas internas e de
filesystem são categorias distintas.

### Contrato e texto

`ContractDateExtractor` e `ContractDateSelector` são reutilizados sobre o texto já
capturado. Somente a candidata selecionada pelo contexto recebe o tipo
`contract_date`; outras datas válidas são eventos textuais genéricos.

### Assinatura

Signing Time declarado, timestamp técnico e limites de validade do certificado
são eventos distintos. Certificate NotBefore/NotAfter nunca são apresentados como
momento de assinatura. O signing time autodeclarado recebe limitação explícita.

### JSON/logs

Somente campos já parseados com nome/categoria temporal e valor textual válido são
usados. O `field_path` é preservado. Números semelhantes a epoch são ignorados na
ausência de regra contextual determinística.

### Filesystem e processamento

Datas de filesystem são identificadas explicitamente e recebem limitação sobre a
diferença para metadados internos. Início e fim da análise são eventos da categoria
`operational`, separados da história documental. ProcessingSteps individuais não
são promovidos a eventos documentais.

## PDF revisions e incremental updates

A Timeline usa exclusivamente `PdfRawAnalysisResult` e `PDFStructureResult` já
produzidos. Ela representa, quando disponível:

- PDF Revision #1;
- Incremental Update #1, #2, ...;
- xref tradicional ou xref stream;
- marcador e valor startxref;
- `/Prev`;
- trailer e EOF;
- offsets e `structural_sequence`.

Esses eventos usam `timestamp=null`, `timezone_status=not_applicable` e
`temporal_status=structural_only`. Offset e sequência nunca são convertidos em
tempo. A associação incompleta de objetos/trailers às revisões é registrada como
limitação.

## Warnings temporais

A primeira regra é `metadata_modify_before_creation`. Ela só compara CreationDate
e ModifyDate do mesmo grupo de metadados, com precisão suficiente e compatibilidade
de timezone. A mensagem é factual: “ModifyDate é anterior a CreationDate segundo
os valores registrados nos metadados.” Eventos e warnings permanecem separados.

## AnalysisContract e Analysis Set

O contrato individual continua na versão 1.0.0. A lista `timeline` contém registros
com `record_type=event` ou `record_type=warning`; nenhum campo público anterior foi
removido. O apresentador web remove paths internos e reinsere apenas o nome público
do upload.

O Analysis Set agrega somente `AnalysisContract.timeline` dos membros terminados.
Ele preserva `evidence_ref`, tolera membros falhos e os registra como limitações.
Não acessa staging, arquivos brutos ou engines.

## Frontend

A página de resultado possui seção Timeline vertical com:

- eventos temporais e estruturais;
- “Data não determinada” para eventos estruturais;
- detalhes expansíveis;
- warnings separados;
- filtros por arquivo, categoria e tipo;
- layout responsivo sem biblioteca adicional.

## Compatibilidade desktop

`TimelinePage` consome prioritariamente os eventos centrais. A reconstrução anterior
permanece apenas como fallback para resultados legados. Os componentes visuais
existentes continuam utilizáveis pelas propriedades de compatibilidade do modelo.

## Limitações conhecidas

- o parser PDF atual não associa com segurança todos os objetos a cada revisão;
- timestamp token dedicado depende de a engine de assinatura fornecê-lo;
- timestamps JSON numéricos não são inferidos automaticamente;
- valores sem timezone não podem ser comparados com valores timezone-aware;
- a persistência do Analysis Set continua sujeita às limitações locais da Sprint 3.5.

## Configuração e performance

Não há configuração adicional. A Timeline é uma etapa leve dentro do job existente
e continua sujeita aos limites de concorrência e timeout da Sprint 1. Nenhum hash,
OCR, metadado, assinatura ou estrutura é recalculado.
