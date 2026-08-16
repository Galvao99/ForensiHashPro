# ForensiHash Desktop — Comparison Workspace (Fase 1.5)

## Limite conceitual

Comparação é a ação explícita de colocar os artefatos A e B lado a lado. O conector representa somente o par selecionado. Correlação continua sendo produzida pelas engines investigativas, considerando evidência, contexto, fontes e relações; o canvas não cria correlações.

## Arquitetura

`MainWindow.analysis_results` continua sendo a fonte do workspace. `AnalysisWorkspace` entrega esses resultados já analisados à `ComparisonWorkspace`. A identidade usa, em ordem, `evidence_id`, `analysis_id` ou o caminho absoluto normalizado; filename é apenas apresentação.

O usuário escolhe no máximo dois `ArtifactNode`s por clique. A e B não implicam ordem temporal. A seleção apenas habilita **Executar comparação**; não dispara análise ou OCR. O retorno ao workspace preserva artefatos e par.

Na execução, `ComparisonService` chama `ComparisonEngine.compare(A, B)` exatamente uma vez e cria o modelo de apresentação determinístico. Nenhuma comparação todos-contra-todos é executada. O engine legado encontrado cobre SHA-256, magic number e assinatura digital básica. O serviço de apresentação preenche o gap de visualização com valores que já existem em `AnalysisResult`: resumo, hashes, metadata, estrutura PDF, assinatura, texto extraído, entidades normalizadas e timeline. Nenhuma engine individual é recalculada e nenhuma inferência nova é produzida.

## Apresentação

O resultado mantém um header A ↔ B, bloco de Correspondências Técnicas e diff detalhado. Correspondência significa igualdade determinística de valores. SHA-256 integral igual recebe texto específico sobre os bytes analisados, sem inferir origem, autoria ou cadeia de custódia. Diferenças usam A/B e estados `ALTERADO`, `SOMENTE A` e `SOMENTE B`, nunca before/after.

Comparabilidade é informada por dimensão, sem score. Dimensão indisponível não é erro. O diff oferece filtros Tudo, Alterações e Correspondências. A grade tem scroll e busca para conjuntos maiores.

## Limitações

- O diff textual é baseado em linhas e utiliza somente texto já extraído.
- Timeline compara chaves factuais de eventos já existentes; não cria ordenação entre artefatos.
- Metadados complexos são apresentados pela representação textual já fornecida pelo resultado.
- O conector é uma representação textual responsiva, não um editor de grafos.

## Fase 1.5.1 — refinamento de UX

A linguagem visual foi aproximada do ForensiHash Web: superfícies neutras, radius de 2 px, bordas finas, labels técnicos monoespaçados, tabs compactas e hierarquia baseada em tabelas. Os valores permanecem fornecidos pelo mesmo `ComparisonView`; nenhuma regra técnica mudou.

A sidebar agora é recolhível durante a sessão. O estado compacto mantém ações essenciais, navegação e tooltips, enquanto libera largura no `QSplitter` principal. O modo **Expandir comparação** recolhe a sidebar e oculta o contexto auxiliar da janela sem destruir o workspace; ao sair, restaura o estado anterior da sidebar e preserva A, B, resultado e filtro.

O `ComparisonPairHeader` utiliza duas células A/B, filename protagonista, detalhes secundários e SHA-256 monoespaçado. Nomes extensos são elididos no centro e preservados integralmente no tooltip.

As Correspondências Técnicas usam uma tabela compacta. Por padrão são exibidos os quatro primeiros itens na ordem determinística já produzida pelo serviço — não existe ranking forense. O contador sempre representa o total e o usuário pode expandir ou recolher a lista sem executar nova comparação.

O diff é a única região técnica com scroll vertical principal. Cada campo usa um `QSplitter` horizontal não colapsável, com largura mínima para A e B. Filtros, redimensionamento, progressive disclosure e focus mode operam exclusivamente sobre o modelo já calculado e não chamam o `ComparisonEngine` novamente.
