# Desktop IA + Timeline V2 — nota de implementação

Auditoria realizada em 4 de setembro de 2026, antes de alterações funcionais.

- O shell é `MainWindow`, com `Sidebar`, `AnalysisWorkspace` (`QStackedWidget`) e o `FileStrip` horizontal. A navegação usa chaves estáveis emitidas por `Sidebar.navigation_requested` e resolvidas por `AnalysisWorkspace.pages`.
- O estado canônico do arquivo selecionado é `MainWindow.current_selection` (`CurrentCaseSelection`). Na implementação revisada, o File Strip encaminha o caminho a `select_file_from_strip()`, que chama o handler canônico sem analisar novamente; a antiga lista lateral foi removida.
- O File Strip recebe arquivos/status do Caso e permanece sincronizado por `set_selected_path()` e `_on_file_state_changed()`.
- Existe uma única rota Desktop `timeline`. Ela é de arquivo: `AnalysisWorkspace.update_analysis()` entrega somente o `AnalysisResult` selecionado. Há agregação temporal de Caso em `AnalysisSetCorrelator`, mas não existe página Desktop canônica separada para ela; portanto não será criada uma rota duplicada.
- `TimelineService` constrói `TimelineEvent` imutáveis exclusivamente de resultados já produzidos. Fontes atuais: metadados internos/filesystem, texto extraído, assinatura e validade do certificado, JSON, timestamps do filesystem, eventos operacionais registrados e revisões estruturais PDF sem timestamp.
- Datas de texto nativo/OCR chegam por `AnalysisResult.extracted_text`; a etapa de extração registra a origem (`native`, `ocr` ou variante) e o serviço cria `contract_date` somente para a candidata contextual selecionada, mantendo as demais como `text_date` com offset/contexto.
- A ordenação canônica usa `TemporalParser.order_key`: instantes com timezone são normalizados para comparação UTC; valores sem timezone ficam em domínio civil separado, sem timezone inventado; precisão e valor bruto são preservados. Desempates usam sequência estrutural e `event_id` estável.
- A página atual converte eventos em dicionários e contém um fallback que recria eventos a partir de metadados/assinatura. Isso duplica semântica de apresentação e será substituído por uma transformação somente de leitura sobre os eventos canônicos já existentes.
- Navegar apenas troca o widget no stack. `show_workspace_page()` não chama análise; alternar a futura visualização Detailed/Visual também permanecerá estado exclusivamente visual.
- Testes existentes cobrem parser/ordenação/precisão/timezone/proveniência, fontes temporais, seleção canônica, sincronização do File Strip, navegação sem análise, colapso geral da sidebar e temas Light/Dark/System.
- Tokens semânticos residem em `app.ui.theme.ThemeTokens`; Light é o padrão e System resolve para Light/Dark pela paleta. A stylesheet base ainda contém cores legadas, mas a camada final sobrescreve componentes tocados com tokens semânticos.

Direção adotada: reorganizar as rotas existentes em HOME, CASE, FILE e TOOLS; manter uma única Timeline de arquivo; introduzir DTOs de apresentação imutáveis para pontos, referências não classificadas e intervalos; e fazer as duas visualizações consumirem exatamente a mesma coleção transformada, sem leitura de arquivo ou chamada de engine.

## Timeline UX V2 — fechamento de apresentação

Auditoria de apresentação realizada em 6 de setembro de 2026:

- A fonte única permanece `AnalysisResult.timeline_events`. `TimelinePage` cria um
  único `TimelinePresentation` imutável e entrega a mesma instância às visões
  Visual e Detalhada. Alternar o `QStackedWidget`, selecionar, abrir detalhes e
  agrupar markers não chama `TimelineService`, providers, engines ou regras.
- Eventos disponíveis continuam sendo os já produzidos para metadata/XMP,
  ContractDate selecionada e referências textuais, assinatura/timestamp,
  validade de certificado, JSON, filesystem, processamento FH e estrutura PDF.
  Nenhum evento foi adicionado ou reclassificado no dataset canônico.
- Precisão e timezone já chegavam em cada `TimelineEvent`. Valores aware são
  comparáveis no domínio UTC; naive permanecem no domínio civil. Para posição
  visual de `YEAR`, `MONTH` e `DAY`, o presenter usa o centro neutro do intervalo
  de precisão produzido pelo `TemporalParser`, sem exibir ou afirmar um horário.
- O intervalo do certificado continua sendo formado apenas por NotBefore e
  NotAfter canônicos no mesmo domínio. A apresentação só constrói o intervalo
  quando há exatamente um par; não escolhe endpoints ambíguos por ordem.
- Relações SigningTime × certificado e data documental × metadata são apenas
  projetadas de `CanonicalCasePipelineResult`. O presenter liga um finding a um
  evento somente quando artifact, semantic role, valor normalizado e campo
  permitem correspondência única. Ausência ou ambiguidade não gera label.
- Categorias e cores são exclusivamente apresentação: documental, assinatura,
  metadata, filesystem, estrutural, processamento FH, certificado e referência.
  Texto e forma acompanham toda cor; nenhuma delas representa risco, severidade
  ou relevância.
- A escala horizontal é linear no domínio temporal real e usa ticks adaptativos.
  Clustering ocorre depois da ordenação por posição em `O(n log n)` e preserva
  todos os pontos. A Timeline Visual é um único widget pintado, sem widget por
  evento; a Detalhada materializa lotes de até 200 linhas e oferece progressão.
- Filtros por categoria e zoom temporal foram deliberadamente adiados. Ambos
  exigem decisões adicionais sobre viewport, preservação de scroll e clipping
  de intervalos; não foi implementado espalhamento visual que falsifique escala.
- Limitação canônica preservada: a Timeline atual projeta para a coleção legada
  apenas a primeira assinatura de `DigitalSignatureResult.signatures`. A UX não
  cria eventos para as demais assinaturas. Uma evolução desse dataset pertence
  a patch próprio de TimelineService, com bindings explícitos por certificado.

Semântica preservada: ordem não prova causalidade; ModDate não prova alteração;
CreationDate não prova criação jurídica; SigningTime não prova validade
criptográfica; intervalo de certificado não prova confiança; data documental
não prova data contratual; cor e frequência não indicam relevância.

## Revisão da Sidebar

A especificação revisada removeu a função de navegador de arquivos da Sidebar. A lista e a pesquisa laterais foram eliminadas; o File Strip passou a encaminhar o `Path` diretamente ao mesmo handler que atualiza `CurrentCaseSelection`. A identidade do Caso e sua contagem factual permanecem na Sidebar, mas nenhum nome ou linha de artefato é renderizado ali. O logo do Home e o logo duplicado da Top Bar foram removidos, mantendo o logo oficial ampliado da Sidebar como única âncora de marca do shell.
