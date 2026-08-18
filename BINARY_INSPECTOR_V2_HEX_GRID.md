# Binary Inspector V2 — Virtualized Interactive Hex Grid

## Objetivo

O Binary Inspector usa uma grade hexadecimal interativa, somente leitura, com Offset, 16 células Hex e 16 células ASCII sincronizadas. O componente não interpreta nem modifica bytes e não conhece regras de hash, detecção ou extração.

## Arquitetura

`HexGridWidget` é um `QAbstractScrollArea` pintado diretamente. Ele mantém cursor, seleção, posição virtual e cache LRU. Quando faltam bytes para o viewport, emite `window_requested(offset, length, request_id)`. `MagicNumberPage` atende o pedido com o `ByteRangeExtractionService` e devolve somente a janela solicitada por `accept_window`.

O `HexViewerWidget` textual permanece no Deep File Explorer. Essa separação evita regressão e mantém o novo comportamento restrito ao Binary Inspector.

## Virtualização

- 16 bytes por linha.
- Somente linhas visíveis e duas linhas de margem são pintadas.
- Nenhuma linha física do arquivo cria widget ou item Qt.
- A scrollbar representa todas as linhas do arquivo e usa escala proporcional quando necessário.
- Janelas são alinhadas em 64 KiB.
- Cache LRU limitado a seis janelas (máximo nominal de 384 KiB).
- O cache é descartado a cada troca de arquivo.
- A última linha exibe somente bytes existentes.

## Cursor e seleção

Clique posiciona o cursor e seleciona um byte. Arraste seleciona um intervalo. `Shift+click` e `Shift` com navegação por teclado estendem a seleção. A mesma posição recebe destaque nas zonas Hex e ASCII.

O modelo expõe `current_offset`, `selection_start`, `selection_end` e `selection_length`. A página sincroniza esses campos bidirecionalmente com Start/End. As ações Detectar, SHA-256 e Extrair continuam sendo executadas pela infraestrutura existente.

## Teclado e cópia

- Setas esquerda/direita: um byte.
- Setas acima/abaixo: 16 bytes.
- PageUp/PageDown: uma tela.
- Home/End: início/fim da linha.
- Ctrl+Home/Ctrl+End: início/fim do arquivo.
- Shift com movimento: estende seleção.
- Ctrl+G: foco em Go to Offset.
- Ctrl+C: copia Hex; o menu contextual também oferece ASCII e offset.

A cópia direta pelo grid é limitada a uma janela. Seleções não residentes usam a leitura regional da página, respeitando o limite existente.

## Lifecycle e concorrência

Pedidos mantêm geração e caminho do arquivo. Callbacks de análises anteriores são descartados. Respostas ainda válidas do arquivo atual podem alimentar apenas o cache LRU; o viewport sempre pinta a janela correspondente à sua posição virtual.

## UX

O título principal é `Binary Inspector`. O arquivo, tipo, MIME, tamanho, magic e SHA-256 permanecem no cabeçalho compacto. A grade ocupa a área central e possui cabeçalho fixo. Um Byte Inspector lateral mostra offset, Hex, decimal, binário e ASCII. A barra inferior informa seleção, tamanho, janela carregada e posição percentual.

## Segurança

O grid é estritamente read-only. Não existem comandos de edição, inserção, remoção ou patch. Toda leitura continua validada pelo serviço de faixa existente.

## Limitações e itens adiados

- Minimap/file map foi adiado para V2.1.
- Não há busca binária, bookmarks, templates ou interpretação multibyte.
- O inspector mostra somente valor de 8 bits.
- O cache não faz prefetch agressivo; prioriza memória limitada e navegação direta.
