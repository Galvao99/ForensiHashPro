# ForensiHash Web — perfis de análise

## Fronteira de produto

O perfil **Free** inspeciona tecnicamente um artefato. O perfil **Pro** acrescenta análise de conteúdo, contexto, tempo enriquecido e relações entre artefatos. O entitlement comercial é persistido no usuário; as engines recebem somente um `AnalysisProfile` com capabilities técnicas.

Esta implementação é exclusiva do Web. O desktop continua usando o perfil completo padrão e nenhuma engine teve sua semântica forense alterada.

## Auditoria do pipeline anterior

O fluxo anterior era `POST /analysis-jobs → AnalysisJobExecutor → WebAnalysisService → AnalysisCoordinator → AnalysisService → FileAnalyzer → LegacyAnalysisAdapter`. Todo job individual executava extração textual/OCR, Entity Resolver V2 e Timeline V2. O `FileAnalyzer` também tentava parser JSON especializado e biometria. Ao terminar todos os jobs do workspace, o frontend chamava `createAnalysisSet`, que executava Correlation V2 e a timeline agregada.

| Engine/serviço | Custo/complexidade aproximada | Dependências | Saída | Consumidores |
| --- | --- | --- | --- | --- |
| Hash/Magic Number | baixo, leitura sequencial | biblioteca padrão | hashes e tipo detectado | contrato, integridade, findings |
| Metadata | baixo a médio | ExifTool quando disponível | campos estruturados | resultado, findings, timeline Pro |
| PDF/Binary Structure | médio, limitado | parsers internos | objetos, streams, xref, EOF, regiões | contrato e findings básicos |
| Digital Signature | baixo a médio | parser interno | presença e estado estrutural | contrato, findings, timeline Pro |
| Archive Inspection | médio, limitado | `zipfile`/parser interno | inventário estrutural | resultado técnico |
| Text Extraction/OCR | alto para PDF/imagem | Tesseract e Poppler | texto/segmentos | entidades e regras de contexto |
| Entity Resolver V2 | médio | texto, metadata e JSON | entidades normalizadas | fatos, correlação e contexto |
| IP investigativo | médio/variável | conteúdo e eventual provider | IPs contextualizados | regras e correlação |
| Timeline V2 | médio | metadata, conteúdo, entidades e assinatura | eventos/warnings | EvidenceTimeline e Analysis Set |
| JSON especializado/biometria | médio | Rust JSON e parsers biométricos | estrutura interpretada | findings e resultado Pro |
| Analysis Set/Correlation V2 | cresce com o conjunto | contratos individuais | relações e timeline agregada | resultado multi-artefato |

## Modelo de capabilities

`app/analysis_profiles.py` define capabilities independentes de pagamento. Existem `FORENSIHASH_FREE` e `FORENSIHASH_PRO`; o modelo admite novos perfis por composição, sem condicionais de plano dentro das regras.

### Free

Executa identificação, hashes, metadata, estrutura PDF/binária, assinaturas básicas, findings básicos e Archive Inspection estrutural. Trabalha com um artefato por seleção. Timestamps permanecem nos metadados, mas não são agregados na Timeline V2.

Não inicializa nem executa extração investigativa de conteúdo, Tesseract/Poppler, Entity Resolver V2, IP investigativo, Timeline V2, JSON especializado, biometria, Analysis Sets ou Correlation V2. Cada etapa individual excluída é registrada como `skipped` com `reason=capability_not_enabled`; isso não significa falha, indisponibilidade nem ausência de vestígio.

### Pro

Habilita todas as capabilities atuais: conteúdo nativo, OCR quando aplicável, entidades, IP contextual, timeline avançada, parsers especializados, biometria, múltiplos artefatos, Analysis Sets e correlação.

## Entitlement e API

`users.analysis_profile` é a fonte server-side (`FREE` por padrão). Ao criar `POST /analysis-jobs`, o backend resolve o profile e grava um snapshot em `analysis_jobs.analysis_profile`; o cliente não envia nem escolhe `PRO`. O worker repassa esse snapshot ao processo isolado. `POST /analysis-sets` valida novamente a capability no endpoint e no serviço.

Administradores podem alterar o profile pela API administrativa existente. Isso é configuração técnica para testes e operação; não há checkout, cobrança, assinatura ou integração de pagamento.

## UX Web

O processamento Free apresenta somente identificação, hashes, metadados, estrutura e assinatura. O resultado omite seções avançadas não executadas e mantém identificação, hashes, metadados, estrutura, assinaturas, fatos e findings básicos. Ao final há um bloco único, técnico e não agressivo, descrevendo o que o Pro **pode analisar**, sem alegar resultados não produzidos.

Seleções Free com múltiplos arquivos ou pasta não iniciam jobs. Os nomes permanecem visíveis e o usuário pode escolher um arquivo ou seguir para a página institucional do Pro. O frontend Pro preserva a fila serial e o workflow multi-arquivo existente.

## Impacto funcional

O pipeline Free remove sete grupos avançados da execução: conteúdo, OCR, entidades, IP investigativo, timeline avançada, parser especializado/biometria e correlação multi-artefato. Testes verificam call paths/serviços não inicializados; não há alegação percentual de desempenho porque não foi realizado benchmark controlado de tempo/CPU.

## Limitações e futuro billing

- A concessão Pro ainda é administrativa, não comercial.
- Não há preview de achados Pro nem migração automática de um job Free para Pro.
- Archive Inspection Free é somente estrutural; interpretação interna profunda depende das futuras capabilities específicas.
- Billing futuro deve atualizar o entitlement server-side após confirmação idempotente do provedor, sem alterar engines ou aceitar profile fornecido pelo navegador.

