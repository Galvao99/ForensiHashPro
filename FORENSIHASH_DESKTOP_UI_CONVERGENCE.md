# Convergência visual ForensiHash Desktop/Web — Fase 1

## 1. Arquitetura anterior

O Desktop permanece uma aplicação nativa PySide6. `MainWindow` organiza um
`QSplitter` horizontal com `Sidebar` e `AnalysisWorkspace`; o workspace usa um
`QStackedWidget` e recebe `AnalysisResult` das rotinas existentes. A seleção do
artefato é propagada pela lista da sidebar e atualiza as páginas sem alterar o
pipeline forense.

A Visão Geral anterior (`AnalysisDashboard`) combinava um cabeçalho interno,
`SummaryCard`, `FileInfoCard` e `FindingsPreviewCard`. Nome e contexto do arquivo
eram repetidos em vários containers. A identidade da sidebar era texto
improvisado, os ícones misturavam emoji, caracteres Unicode e abreviações, e o
QSS usava muitas variações de azul e cards arredondados aninhados.

## 2. Referência visual Web

O Web apresenta o resultado com um `ArtifactHeader` factual, SHA-256 copiável,
estado discreto e seções semânticas de identificação, estrutura, metadados e
assinaturas. Seus tokens dark usam fundo `#111315`, superfícies `#191b1e` e
`#1e2124`, bordas cinza, texto de alto contraste e azul apenas como ação ou
informação. A navegação e os resumos privilegiam progressive disclosure, sem
score ou conclusão agregada.

## 3. Estratégia de convergência

A Fase 1 traduz esses princípios para widgets Qt; não copia CSS e não introduz
WebView, React ou outra camada Web. A convergência será feita por:

- tokens centrais para superfícies, bordas, texto, estados e espaçamento;
- header de resultado reutilizável, com nome único, estado e hash copiável;
- resumo forense composto por seções semânticas e dados já presentes no
  `AnalysisResult`;
- sidebar preservada conceitualmente, com logo oficial e sistema uniforme de
  marcadores técnicos;
- cards rasos, raios discretos, linhas finas e menor repetição;
- estados factuais (`CONCLUÍDO`, `PARCIAL`, `FALHOU`, `NÃO EXECUTADO` e
  `INDISPONÍVEL`) sem avaliação de autenticidade.

## 4. Componentes e tokens

Esta fase introduz `ResultHeader`, `StatusIndicator`, `TechnicalField`,
`SummarySection` e `ForensicSummary`. O tema passa a possuir tokens dark e light
em uma única estrutura; o tema dark continua sendo o padrão atual. A UI não
ganha um seletor de tema nesta fase.

## 5. Navegação

A navegação vertical permanece como autoridade, sem uma segunda faixa de tabs.
As chaves internas continuam estáveis para preservar o comportamento. Apenas a
nomenclatura apresentada e a hierarquia visual convergem para o Web.

## 6. Visão Geral

A Visão Geral passa a conter: header técnico, Resumo Forense, Identificação,
Estrutura, Metadados relevantes, Assinaturas e Principais Vestígios. Ela mostra
somente sínteses; os detalhes permanecem nas páginas específicas. Ausência de
assinatura é descrita como “Nenhuma assinatura incorporada reportada”.

## 7. Assets

O Desktop reutiliza os assets oficiais existentes
`web/frontend/public/assets/forensihash_logo_branco.png` e
`forensihash_logo_preto.png`, selecionados pelo tema. Não há redesenho nem
inversão artificial. A resolução possui fallback textual seguro para pacotes que
ainda não incluam os assets compartilhados.

## 8. Diferenças intencionais

O Web mantém navegação e responsividade próprias de SaaS. O Desktop preserva o
splitter, a lista local de artefatos, atalhos de abertura/exportação e a densidade
adequada a uma workstation. A convergência é conceitual e visual, não
pixel-perfect.

## 9. Roadmap

- Fase 2: Identificação, Estrutura, Metadados, Assinaturas, Entidades e Findings.
- Fase 3: Timeline interativa, OCR, Biometria, Correlação e visualizações
  avançadas.
- Fase 4: loading, processamento, fila, UX de pasta e exportações.

Nenhum item dessas fases é implementado nesta entrega.
