# Mapa da arquitetura atual

## Visão geral

O repositório contém uma aplicação desktop PySide6, um núcleo Rust/PyO3 para JSON e executáveis externos. A separação nominal por camadas existe, mas o contrato central e parte da orquestração ainda carregam escolhas da UI e do ambiente local.

```text
ForensiHashPro/
├── main.py                    entrada PySide6
├── app/
│   ├── ui/, pages/, widgets/  apresentação desktop
│   ├── workers/               execução em QThread
│   ├── factory/               composição concreta
│   ├── services/              orquestração e extrações
│   ├── engines/               hash, metadados, magic, PDF, assinatura, integridade
│   ├── binary/                leitor, scanner, strings, entropia e PdfRawParser V1
│   ├── biometric/             parsers Aware/Knomi e avaliação de constraints
│   ├── investigation/         contexto, correlação e regras especializadas
│   ├── integrations/ip/       IP2Location, modelos e provider
│   ├── models/                resultados e DTOs heterogêneos
│   ├── rules/, knowledge/     regras e textos técnicos
│   ├── presentation/          formatadores auxiliares
│   ├── repositories/          histórico em memória
│   └── settings/              configuração JSON local
├── rust/forensihash_core/     parser JSON via PyO3/maturin
├── tests/                     suíte Python automatizada (305 testes)
├── tools/                     ExifTool e instalador Tesseract
└── config/                    configuração local versionada
```

## Responsabilidades e dependências

| Componente | Responsabilidade atual | Dependências relevantes | Candidato para backend |
|---|---|---|---|
| `FileAnalyzer` | Executa motores sequencialmente e monta `AnalysisResult` | Engines concretos, services JSON/biometria | Sim, após receber EvidenceSource e políticas |
| `AnalysisService` | Texto, análise e correlação | `FileAnalyzer`, extração e correlação | Sim, como caso de uso sem `print()` |
| Engines | Fatos técnicos e, em integridade, score agregado | filesystem e bibliotecas diretamente | Parcial; separar portas de infraestrutura |
| Binary | Leitura por chunks/mmap e fatos estruturais | filesystem | Sim; é a fundação mais reutilizável |
| Investigation | Contexto e findings correlacionados | modelos e dicionários | Sim; requer contratos/IDs/severidade estáveis |
| OCR/metadata/signature/IP | Adaptadores de ferramentas externas | fitz, Tesseract, Poppler, ExifTool, pyHanko, requests | Infraestrutura isolável |
| Qt worker | Thread, progresso e cancelamento | QObject/Signal/QThread | Não; substituir por porta de progresso/cancelamento |
| Pages/widgets | Renderização e alguma normalização de dados | PySide6 e modelos | Não; adaptadores de apresentação |
| Rust JSON | Parsing incremental | extensão nativa PyO3 | Sim, com capability/error contract |

Não foi detectado ciclo de importação que impeça os testes/imports atuais. Há, porém, dependência conceitual reversa: páginas normalizam contratos incompletos, models contêm propriedades de exibição e `AnalysisService` imprime resultados.

## Fluxos principais

```text
Seleção de arquivos (Qt)
  -> MainWindow cria QThread/AnalysisWorker
  -> AnalysisService.analyze
  -> FileAnalyzer
       -> stat -> hashes -> ExifTool -> magic number -> pyHanko
       -> PDF heurístico -> integridade/score -> Rust JSON -> biometria
       -> findings -> BinaryStructureEngine
  -> extração nativa/OCR
  -> AnalysisResult mutável
  -> CorrelationService -> InvestigationContext -> regras -> CorrelationResult
  -> sinais Qt -> páginas/widgets
```

O arquivo é reaberto em cada etapa. Não existe uma unidade imutável de ingestão que garanta que todos os resultados pertençam aos mesmos bytes.

## Integrações externas e recursos

- ExifTool: processo local em `tools/exiftool/exiftool.exe`, caminho relativo e sem timeout.
- OCR: `pytesseract`; procura executável inexistente no bundle atual.
- PDF OCR: `pdf2image`, que requer Poppler externo não documentado.
- PDF nativo: PyMuPDF; assinatura: pyHanko.
- IP: HTTPS para IP2Location, chave persistida em JSON local.
- JSON: extensão Rust `forensihash_core`, construída com maturin.
- Persistência: `HistoryRepository` em memória; settings em JSON. Não há banco de dados operacional.

## Acoplamento com PySide6

- `AnalysisWorker` define progresso, falha, conclusão e cancelamento como sinais Qt.
- `MainWindow` mantém resultados e lifecycle da thread.
- Páginas fazem adaptação de datas, severidades e objetos genéricos, lógica que deveria estar em presenters/serializers.
- Modelos contêm cores, ícones, badges e métodos de formatação.
- Consultas IP são iniciadas na apresentação, sem uma fila/caso de uso independente.

## Extração recomendada para o futuro backend

1. Definir `EvidenceSource` somente leitura, `AnalysisRequest`, `AnalysisEnvelope` e `ProcessingIssue` sem Qt.
2. Criar portas para filesystem, metadados, OCR, PDF, assinatura, rede, relógio e persistência.
3. Mover a sequência de motores para um `AnalyzeEvidenceUseCase`, com progresso e cancelamento por protocolos Python.
4. Adaptar o desktop aos novos protocolos, preservando sinais Qt apenas na borda.
5. Somente depois criar worker/fila e API; upload deve gerar ID isolado por análise, nunca usar nome do cliente como caminho.

## Atualização após a estabilização — Parte 5

O fluxo principal agora possui uma camada de aplicação e um envelope paralelo:

```text
PySide6 AnalysisWorker ─┐
                       ├─> AnalysisCoordinator (sem Qt)
execução headless ─────┘       -> AnalysisService -> EvidenceSource -> engines
                                      -> AnalysisResult legado
                                      -> LegacyAnalysisAdapter
                                      -> AnalysisContract 1.0.0
                                           ├─> JSON técnico
                                           └─> Signal desktop na borda
```

Novos limites arquiteturais:

| Camada | Componentes | Estado de reutilização |
|---|---|---|
| Contrato | `app/contracts` | independente de Qt e JSON-safe |
| Aplicação | `app/application/analysis_coordinator.py` | análise individual headless |
| Compatibilidade | `LegacyAnalysisAdapter` | transição, ainda conhece todos os DTOs legados |
| Infraestrutura | Evidence, OCR, ExifTool, PDF, IP | parcialmente isolada; engines ainda concretos |
| Desktop | worker/pages/widgets | worker adapta progresso/contrato; páginas seguem legadas |

O contrato central não elimina as duplicações históricas. Dois modelos de
timeline, findings comuns/correlacionados, badges no modelo investigativo e
enums divergentes continuam candidatos à migração posterior.

## Atualização — Entity Extraction V2

`app/entities` centraliza candidatos, validadores, resolução de conflito,
confidence e deduplicação para CPF, telefone, IP, moeda, data/hora e e-mail.
`AnalysisService` executa a resolução após texto/OCR e fontes estruturadas;
`AnalysisResult` preserva as entidades e `LegacyAnalysisAdapter` as converte em
facts versionados. `InvestigationContextBuilder` e `OcrContextRule` mantêm a
correlação legada por adapter, sem classificar novamente por regex.

## Atualização — Correlation Engine V2 e Analysis Sets

`app/investigation` agora contém comparabilidade semântica de
`NormalizedEntity`, source divergence e extração central de hash declarado. O
desktop mantém `CorrelationService`/`CorrelationResult`; a web converte
contratos concluídos em `AnalysisSetResult` separado. A tabela `analysis_sets`
persiste por tempo limitado somente resultado leve e referências a jobs, nunca
arquivos brutos.
# Atualização Sprint 4 — Timeline Web V2

A Timeline técnica passou a integrar o pipeline oficial após a produção do
`AnalysisResult`. `TimelineService` consome somente resultados existentes e publica
eventos temporais/estruturais no campo opcional `AnalysisContract.timeline` 1.0.0.
O Analysis Set agrega essas listas sem reabrir artefatos. Revisões PDF preservam
ordem estrutural e offsets sem atribuição de timestamp.
# Atualização Sprint 5 — Parser Registry e Archive Inspection

Após o MagicNumberEngine, `ArtifactIdentification` alimenta o `ParserRegistry`.
ZIP é inspecionado estaticamente por `ZipArtifactParser` e
`ArchiveInspectionEngine`; formatos sem parser usam `BinaryFallbackParser`. O
resultado normalizado entra em `AnalysisResult.parsed_artifact` e no
`technical_structure` do AnalysisContract 1.0.0. Entries são embedded artifacts,
não jobs, e nunca controlam paths no filesystem.
