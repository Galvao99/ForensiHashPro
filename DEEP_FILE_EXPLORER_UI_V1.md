# Deep File Explorer UI V1

## Arquitetura

O Explorer continua sendo uma página Desktop somente leitura. `DeepFileExplorerPage` controla arquivo, sessão, carregamento assíncrono e preview; `StructureTreeModel` adapta os contratos PDF 1.2 e JPEG 1.0 para nós de navegação; `ObjectInspector` resolve capacidades lazy; `DocumentPageViewer` reutiliza PyMuPDF para páginas PDF e também apresenta bytes de assets retornados pelas sessões; `HexViewerWidget` apresenta bytes já solicitados com limites visuais.

Nenhum parsing estrutural foi movido para Python/Qt. A árvore mantém somente registros pequenos do relatório e identificadores necessários para chamar a sessão.

## Layout

Um `QSplitter` horizontal contém:

1. árvore estrutural à esquerda;
2. arquivo ou preview no centro;
3. Inspector à direita.

O cabeçalho conserva arquivo, hash, busca e localização de página. A sidebar não foi alterada.

## Modelo de nós

`StructureTreeNode` preserva `id`, `label`, `kind`, `object_id`, `segment_index`, `path`, `preview_asset_id`, `payload` estrutural pequeno e `capabilities`. Capacidades possíveis são `summary`, `preview`, `raw`, `decoded`, `text` e `hex`. IDs são estáveis dentro do relatório atual; payloads raw/decoded não são armazenados no modelo.

Objetos PDF permanecem lazy no grupo Objects. Relações de recursos preservam object id, generation e path semântico. Referências `PdfValue` podem navegar ao objeto correspondente por duplo clique.

## PDF

A árvore apresenta Physical Structure, Trailer, Catalog, Pages, Contents, Resources/XObjects, Forms aninhados, Visual Assets, Embedded Files, Metadata, Annotations, Signatures, Occurrences e Objects. Usos de um objeto aparecem no contexto sem substituir sua identidade única no grupo Objects.

O painel central mantém o renderer PDF existente. Selecionar uma página navega no documento; selecionar Image XObject solicita preview pela sessão. Raw object/stream, decoded stream, metadata e embedded content são consultados somente quando a aba correspondente é aberta.

## JPEG

A árvore apresenta estrutura física, SOI/EOI/trailing, sequência de segmentos, scan associado ao SOS, DQT/DHT/SOF, Frames, Scans, EXIF/TIFF/IFDs/entries, XMP, ICC, Visual Assets, Comments e Warnings. APP1/APP2 possuem links leves para as estruturas aprofundadas, evitando duplicação de conteúdo.

O original e thumbnails são exibidos sem recompressão usando `get_preview`. Segmentos, scans, XMP, ICC e trailing usam as APIs lazy da sessão. EXIF mostra valor tipado, tag id hexadecimal, tipo TIFF, IFD, path, segmento e offset absoluto sem interpretar autenticidade.

## Inspector e proveniência

As abas Preview, Properties/Summary, Decoded, Raw, Text e Hex são mostradas conforme capacidades do nó. Summary inclui source, structural path, object/segment e offsets disponíveis. Text é reservado a XMP, comentários e metadata/conteúdo textual já suportado. JPEG não recebe decoder genérico de pixels.

## Hex viewer

`HexViewerWidget` usa fonte monoespaçada e linhas com offset, dezesseis bytes hex e ASCII. A apresentação inicial é limitada a 64 KiB; “Carregar mais” dobra a janela até 2 MiB. O limite é visual: a API atual da sessão ainda retorna o payload solicitado inteiro antes da apresentação, limitação registrada abaixo.

## Threading, lifecycle e cache

Todas as operações de sessão passam por `ExplorerTask`. Callbacks do Inspector carregam token de seleção e identidade da sessão; previews centrais usam token próprio. Resultado antigo não substitui seleção, arquivo ou sessão novos. Troca de arquivo e retorno à Home removem referências, modelo e estado visual.

Não foi adicionado cache UI de bytes. O cache nativo limitado de preview continua sendo reutilizado.

## Performance diagnóstica

A montagem da árvore processa somente inventários do relatório. Objects PDF continuam lazy; raw, decoded, text, ICC e previews não são materializados na construção. Diagnóstico local com build PyO3 de desenvolvimento: PDF de 1/25/200 páginas montou a árvore em 0,34/0,49/3,70 ms; JPEG pequeno, 12 MP e progressive montaram em 0,67/0,31/0,34 ms; JPEG com 8 MiB de trailing montou em 0,26 ms. Acesso raw a objeto PDF levou 0,07 ms, previews JPEG entre 0,02 e 0,16 ms e leitura lazy dos 8 MiB trailing 6,14 ms. Parsing ficou fora da responsabilidade da UI, mas foi observado entre 11,93 e 1.176,01 ms nesses arquivos. São medições diagnósticas, não benchmark formal, e variam conforme Qt, PyMuPDF, compressibilidade dos arquivos e ambiente.

## Limitações

- As APIs raw atuais retornam uma região completa; o Hex Viewer limita renderização e memória textual, mas não implementa leitura nativa paginada.
- Links internos cobrem referências PDF tipadas e links estruturais JPEG conhecidos, não um grafo universal.
- Preview de embedded file não executa nem renderiza o conteúdo.
- Busca avançada, filtros, bookmarks, export, edição, comparação e grafo ficam adiados.
- PNG, Office/ZIP e outros formatos continuam sem Deep Structure.
- Não há score, heurística investigativa ou conclusão automática.
