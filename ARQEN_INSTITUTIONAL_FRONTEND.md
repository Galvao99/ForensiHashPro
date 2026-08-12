# ARQEN — frontend institucional

## 1. Arquitetura anterior

O frontend React/TypeScript já separava as rotas públicas, agrupadas por
`PublicLayout`, da plataforma autenticada, agrupada por `AppShell`. A homepage e
o shell público usavam ForensiHash como marca principal. DDNA já possuía uma
página técnica extensa, com diagramas React/CSS, referências primárias e
ressalvas editoriais próprias.

## 2. Componentes reutilizados

- `PublicLayout`, `Section`, `Container` e componentes de UI existentes;
- `DdnaDiagram` e todo o conteúdo de `DdnaPage`;
- conteúdos estáticos de tecnologias, referências e camadas de análise;
- `Brand` permanece exclusivo da plataforma ForensiHash autenticada.

## 3. Componentes criados

- `ArqenBrand`: usa os PNGs oficiais sem alterar os assets; a composição
  `arqen_logo_preta.png` contém fundo preto/lettering branco e é usada no shell
  escuro, conforme verificação visual do conteúdo real;
- `ArtifactGraph`: grafo técnico leve em React, CSS e SVG;
- `EvidenceExplorer`: exemplo didático acessível com categorias de informação.

## 4. Design system

Foram adicionados tokens `--arqen-*` para preto, branco, superfícies, bordas,
texto, espaçamento e raios. A linguagem é monocromática, com linhas de 1 px,
raios baixos, sombras mínimas e Montserrat/JetBrains Mono já instaladas. O CSS
institucional é compartilhado, sem dependência de animação ou 3D adicional.

## 5. Homepage

A homepage agora apresenta ARQEN como empresa e organiza a narrativa em: hero,
princípios de arquitetura, soluções DDNA e ForensiHash, ciclo da evidência,
fragmentação de contexto, exemplo didático, aplicações e fundamentos. Não são
exibidos clientes, certificações, parceiros ou estatísticas não verificadas.

## 6. Artifact Graph

O Digital Artifact Graph relaciona um artefato central a hash, metadata,
context, events, timeline e custody. Mouse, foco e clique destacam nó e conexão.
O deslocamento por cursor é deliberadamente pequeno; em movimento reduzido ele
é removido. O SVG possui título e descrição acessíveis.

## 7. Navegação

O header ARQEN é compartilhado pelas rotas públicas, fixo, transparente nos
heros escuros e opaco após rolagem ou nas páginas claras. O menu mobile informa
estado por `aria-expanded` e aponta apenas para rotas existentes. O footer agrupa
somente soluções, recursos e páginas legais existentes.

## 8. Páginas migradas visualmente

As rotas `/`, `/forensihash`, `/ddna`, `/technology`, `/references`, `/login`,
`/register`, `/terms` e `/privacy` recebem o shell ARQEN. A área `/app` e suas
funcionalidades permanecem no shell ForensiHash existente.

## 9. Responsividade

Os layouts usam breakpoints fluidos para desktop, tablet e mobile. Grids de seis
colunas passam a três e duas; produtos e blocos editoriais viram coluna; o grafo
mantém proporção e os controles didáticos reorganizam-se em duas colunas. O
container e as tipografias usam medidas fluidas para cobrir de 375 a 1920 px.

## 10. Acessibilidade

Foram preservados headings semânticos e links nativos. Grafo, ciclo e mapa têm
nomes acessíveis; nós são botões; o explorador usa `tablist`, `tab` e `tabpanel`;
foco visível e contraste permanecem explícitos. `prefers-reduced-motion` elimina
animações e deslocamento ambiental.

## 11. SEO

O documento-base e a homepage usam ARQEN como marca, com título
`ARQEN | Infraestrutura para Evidências Digitais` e descrição institucional. O
SEO específico de DDNA foi preservado.

## 12. Performance

Não foram adicionadas dependências, vídeo, WebGL ou bibliotecas de animação. O
elemento principal utiliza apenas DOM, CSS e SVG. Os logos são assets locais.

## 13. Testes

`arqen-institutional.test.tsx` cobre marca, logo, hero, produtos, CTAs, rotas,
menu, interações acessíveis, linguagem de aplicações e alegações proibidas.
Testes anteriores de navegação e fronteira de tema foram atualizados para a nova
marca pública. DDNA continua coberta por sua suíte específica.

## 14. Arquivos criados

- `ARQEN_INSTITUTIONAL_FRONTEND.md`;
- `src/components/ArqenBrand.tsx`;
- `src/components/ArtifactGraph.tsx`;
- `src/components/EvidenceExplorer.tsx`;
- `src/test/arqen-institutional.test.tsx`.

## 15. Arquivos modificados

- `index.html`;
- `src/components/PublicHeader.tsx`;
- `src/components/PublicLayout.tsx`;
- `src/pages/HomePage.tsx`;
- `src/styles/tokens.css` e `src/styles/global.css`;
- testes de navegação e arquitetura de tema.

## 16. Limitações

- Não há estatísticas de mercado suficientemente sustentadas no conteúdo atual;
  por isso a homepage não apresenta números. Pesquisa e validação editorial são
  um próximo passo explícito.
- A referência visual mencionada não estava disponível como arquivo no workspace;
  a implementação seguiu os requisitos textuais de composição e linguagem.
- A validação automatizada cobre estrutura e comportamento, mas a homologação
  visual final ainda requer revisão humana em navegadores e dispositivos reais.

## 17. Próximos passos

Realizar revisão visual com a equipe em 375, 430, 768, 1024, 1440 e 1920 px;
validar recortes reais dos logos; pesquisar estatísticas apenas em fontes
primárias; e, após aprovação institucional, produzir imagem Open Graph própria.
