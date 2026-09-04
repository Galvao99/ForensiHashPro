# Case Correlation Explorer V1 — auditoria pré-implementação

## Superfícies existentes

- A rota `comparison` abre `ComparisonWorkspace`: é o comparador arquivo-a-arquivo existente. A Sidebar o rotulava como “Correlações”, embora o título interno já fosse “Comparação”.
- `CaseCorrelationIndex` conserva `AnalysisResult` por caminho resolvido e cria `InvestigationContext` sem executar novamente OCR, parsers ou análise de arquivos.
- `CorrelationService` aplica regras explícitas ao contexto do Caso. Seus achados e limitações são independentes das observações factuais.
- Evidence Graph V2 (`app/correlation/v2`) normaliza candidatos tipados, preserva ocorrências/proveniência, conta arquivos/fontes e cria relações factuais determinísticas.
- `CaseFinding` separa estado epistêmico (`MATCH`, `MISMATCH`, `UNKNOWN`, `NOT_APPLICABLE`) de severidade e de limitações operacionais.

## Dados e semântica disponíveis

- Entidades V2: CPF, CNPJ, IP, e-mail, telefone, URL, SHA-256, MD5, timestamp, nome de arquivo e identificador documental.
- Fontes: texto nativo, OCR, entidades resolvidas, JSON estruturado, metadados, Timeline, IP e hashes calculados.
- A proveniência pode conter engine, source engine, campo/caminho, página, bloco/região, offsets, contexto e método de extração.
- Producer/Creator já entram no `InvestigationContext` a partir de chaves explícitas de metadados, mas não são entidades do Evidence Graph V2.
- Hashes calculados e declarados já são separados no contexto. Strings apenas parecidas com hash retêm `declared=False`; somente regras explícitas promovem comparação determinística.
- Datas de contrato, metadados, Timeline e assinaturas já chegam ao contexto; precisão e origem permanecem nos objetos canônicos. O Explorer não substitui Timeline V2.
- Igualdade normalizada no Evidence Graph significa apenas o mesmo valor técnico observado. `SAME_ENTITY_ACROSS_FILES` não estabelece identidade jurídica, mesmo documento ou importância.

## Estado, navegação e limites

- `MainWindow.current_selection` é o estado canônico do artefato; o `FileStrip` é o único navegador visual de arquivos.
- `AnalysisWorkspace.show_page()` apenas troca widgets. A atualização do Caso ocorre quando o cache/progresso muda, não ao navegar.
- `FindingPage` recebe o resultado do artefato selecionado e os achados do Caso, mas não oferece hoje uma API de foco por occurrence ID.
- O novo Explorer poderá selecionar explicitamente o artefato via o mesmo fluxo do File Strip e abrir Vestígios técnicos; preservará a referência da ocorrência na fronteira de navegação, sem fingir foco ainda inexistente.
- Os ícones locais incluem um SVG genérico de arquivo, mas não uma família completa por extensão. V1 usará esse SVG e texto explícito da extensão.

## Decisão de implementação

O Explorer será uma projeção somente leitura construída de `AnalysisResult` já armazenados, do Evidence Graph V2 e do `InvestigationContext`. Producer/Creator e hashes declarados serão adaptados como observações de apresentação, sem alterar entidades, regras ou estados epistêmicos do Core. Busca, filtro, ordenação e painel de detalhe atuarão somente sobre essa projeção imutável. Relações mais fortes serão exibidas apenas quando a fonte estiver tipada e uma regra determinística existente as sustentar.
