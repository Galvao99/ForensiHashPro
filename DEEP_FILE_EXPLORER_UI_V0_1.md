# Deep File Explorer UI V0.1 — Desktop Prototype

## Objetivo e escopo

O protótipo adiciona ao ForensiHash Pro desktop uma área somente leitura que apresenta o PDF renderizado ao lado de uma organização navegável do `StructureReport 1.2`. A UI não lê a sintaxe PDF, não executa actions ou anexos e não produz interpretações investigativas.

O arquivo atual é recebido por `AnalysisWorkspace` a partir de `AnalysisResult.file_info.path`; portanto, o usuário não precisa selecioná-lo novamente. Arquivos que não sejam PDF recebem uma mensagem de compatibilidade técnica e não são enviados ao parser.

## Arquitetura

```text
MainWindow / Sidebar
        ↓
AnalysisWorkspace
        ↓
DeepFileExplorerPage
  ├── DocumentPageViewer (PyMuPDF, uma página por vez)
  ├── StructureTreeModel (QAbstractItemModel)
  └── ObjectInspector
        ├── Preview
        ├── Properties
        ├── Decoded
        └── Raw
                ↓
       DeepStructureSession pública
```

Componentes principais:

- `DeepFileExplorerPage`: ciclo de vida da sessão, resumo, busca, estados e splitters;
- `DocumentPageViewer`: navegação anterior/próxima, zoom, ajuste à largura/página e renderização de uma página;
- `StructureTreeModel`: modelo Qt semântico com identidade `object + generation` e nó `Objects` lazy;
- `ObjectInspector`: propriedades tipadas e carregamento sob demanda das quatro representações;
- `ExplorerTask`: execução em `QThreadPool`, com sinais que retornam à thread da interface.

O motor Rust e o contrato 1.2 não foram alterados.

## Organização da árvore

A raiz contém Header, Trailer, Catalog, Pages, Objects, Embedded Files, Metadata, Annotations, Signatures e Occurrences. Dentro de cada página, `visual_resources` é organizado por Images, Forms e Other.

Forms usam `container_object_id` para formar relações aninhadas:

```text
Page 1
└── Resources
    └── Forms
        └── /Fm1 → 58 0 R [invoked]
            ├── Properties
            ├── Content Stream
            └── Resources
                └── /Im2 → 47 0 R [declared]
```

`declared` e `invoked` reproduzem os fatos fornecidos pelo motor. `invoked` significa invocação por `Do`, não visibilidade. `/Mask` e `/SMask` referenciados por Image XObjects recebem nós selecionáveis próprios.

O modelo não expande referências gerais recursivamente. Isso impede loops `Parent/Kids`; a identidade do alvo permanece disponível para seleção/busca. O nó `Objects` somente materializa seus filhos quando expandido ou quando uma busca precisa consultá-los.

## Inspeção e proveniência

- **Preview:** chama `get_preview()` e `get_visual_asset()` somente ao abrir a aba. O tooltip registra objeto, filtro, transformação e se houve reconstrução. Assim, PNG derivado não é apresentado como bytes originais.
- **Properties:** chama `get_object()` para objetos navegáveis e preserva os tipos de `PdfValue` em uma tabela hierárquica.
- **Decoded:** usa `get_decoded_stream()`, `get_metadata_text()` ou `get_embedded_file()`, conforme o tipo selecionado.
- **Raw:** usa `get_raw_object()`.

Payload textual é mostrado em fonte adequada ao controle `QPlainTextEdit`. Payload binário recebe representação hexadecimal. A visualização textual/hexadecimal é limitada a 512 KiB; o tamanho total continua indicado e os bytes não são modificados pelo motor.

Embedded files são apenas recuperados em memória após solicitação explícita na aba Decoded. Não há execução, abertura externa, extração automática ou exportação. Signature dictionaries exibem a indicação “dados exclusivamente estruturais”; validação criptográfica permanece no `DigitalSignatureEngine`.

## Threading, lazy loading e estados

Parsing estrutural, renderização de página, preview, properties, decoded e raw são executados no pool global do Qt. Widgets são atualizados somente pelos sinais entregues à thread principal.

Fluxo normal:

```text
selecionar resultado → abrir Deep File Explorer → analyze_pdf
expandir Objects → materializar inventário
selecionar objeto → carregar propriedades
abrir Preview/Decoded/Raw → solicitar somente esse payload
```

Estados objetivos incluem “Carregando estrutura”, “Renderizando página”, “Gerando preview” e “Decodificando stream”. Erros preservam as categorias `unsupported`, `malformed`, `limit_exceeded` ou a categoria técnica retornada pelo método sob demanda.

## Busca e sincronização

A busca textual encontra rótulo, tipo e `object_id`, incluindo `42 0 R`, nomes de recursos e tipos. “Localizar página na estrutura” seleciona a página atualmente renderizada. Não há expansão automática agressiva ao trocar de página.

## Testes

O corpus de UI usa um `StructureReport 1.2` determinístico com página, content stream, imagem invocada, Form, imagem aninhada declarada, embedded file, XMP, annotation, signature, occurrences e ciclo Pages/Page. A sessão fake comprova chamadas lazy de preview/decoded/raw/metadata. Um teste adicional gera um PDF real com PyMuPDF, analisa-o pelo binding Rust/PyO3 instalado e entrega a sessão real à página.

São cobertos:

- árvore e identidade com generation number;
- Page → Contents → Stream;
- Page → Form → Image;
- declared versus invoked;
- materialização lazy de Objects;
- ausência de expansão infinita em ciclo;
- preview, decoded, raw e metadata sob demanda;
- representação binária limitada;
- embedded, annotation e signature;
- arquivo não PDF;
- erros `malformed` e `limit_exceeded`;
- integração real com o engine.

## Limitações V0.1

- não há renderer próprio nem análise de z-order/visibilidade;
- a árvore mostra recursos visuais conhecidos pelo mapa do contrato; Fonts e recursos não visuais continuam acessíveis em Objects, mas ainda não possuem uma navegação semântica completa por página;
- o preview composto de SMask existe no motor, mas V0.1 não oferece alternador Original/Mask/Composite; cada máscara pode ser inspecionada separadamente;
- embedded files não podem ser salvos/exportados;
- busca seleciona a primeira correspondência;
- não há visualizador hexadecimal virtualizado; a saída é deliberadamente limitada;
- não há cancelamento de uma tarefa já iniciada ao trocar rapidamente de arquivo;
- screenshots não foram incorporados ao repositório nesta sprint.

# UX Validation

1. **Relação página → recurso:** sim; páginas, grupos, Forms e recursos aninhados têm hierarquia e caminho coerentes.
2. **Localizar imagem interna:** sim, pela página/Resources ou busca por nome/objeto.
3. **Original/raw versus preview derivado:** sim; são abas distintas e a proveniência do preview informa transformação/reconstrução.
4. **Properties/Decoded/Raw:** funcionam em controles separados e são carregados apenas quando solicitados.
5. **Forms aninhados:** permanecem hierárquicos; ciclos não geram expansão infinita.
6. **1366×768:** o layout usa splitters redimensionáveis, mínimos compactos e árvore de linhas uniformes; é funcional, embora a área de inspeção exija ajuste do splitter para payloads longos.
7. **1920×1080:** há espaço para documento, árvore e inspeção simultâneos.
8. **Antes da UI V1:** adicionar alternador Original/Mask/Composite, navegação “ir para objeto” entre todas as referências, busca com múltiplos resultados, cancelamento/gerações de tarefas, hex viewer virtualizado e testes visuais automatizados em mais escalas/DPI.

## Roadmap sugerido

- navegação bidirecional por edges e histórico voltar/avançar;
- alternador de SMask/composite e painel explícito de proveniência;
- mapa semântico completo de Fonts e outros Resources;
- filtro de ocorrências e múltiplos resultados de busca;
- cancelamento de jobs obsoletos e cache visual controlado na UI;
- exportação explícita e segura de embedded content em sprint própria;
- refinamento visual e acessibilidade para a UI V1.
