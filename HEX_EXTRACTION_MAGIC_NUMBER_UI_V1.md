# Hex Extraction & Magic Number UI V1

## Estado anterior

`MagicNumberPage` era um alias sem comportamento próprio de `BinaryAnalyzerPage`. A página combinava vários cards, um preview fixo de 128 bytes e acesso ao `HexDialog`, que usava `Path.read_bytes()` e materializava o arquivo inteiro. Não havia seleção lógica de faixa, hash regional, detecção regional, extração ou proveniência.

## Arquitetura

`MagicNumberPage` agora é uma área de inspeção binária somente leitura. Ela consome o `AnalysisResult` existente e coordena operações assíncronas por `ExplorerTask`.

`ByteRangeExtractionService` concentra leitura, validação, hash, detecção e criação de artefatos. O serviço recebe `HashEngine` e `MagicNumberEngine` por injeção e não contém lista própria de assinaturas. Sua API foi desenhada para uso futuro pelo Deep File Explorer.

`ExtractedArtifact` é o modelo imutável de proveniência em memória. `HexViewerWidget` permanece um widget de apresentação e agora também solicita janelas incrementais ao consumidor.

## UI e UX

A página possui três seções discretas:

1. cabeçalho com formato, MIME, assinatura, arquivo, extensão, correspondência técnica e SHA-256 da origem;
2. Hex Inspector incremental com orientação curta;
3. Selected Range com Start/End inclusivos, contagem e ações.

Start e End aceitam decimal ou hexadecimal com prefixo `0x`. A seleção textual direta de bytes no `QPlainTextEdit` não foi transformada em seleção lógica nesta V1; os campos manuais são o mecanismo confiável. Botões permanecem desabilitados sem faixa válida e todo feedback ocorre inline.

## `read_range`

`read_range(path, offset, length)` usa `seek()` e `read(length)`, sem ler o arquivo inteiro. São verificados arquivo regular, offset não negativo, length positivo, overflow lógico, EOF e limite configurado. O padrão limita leitura a 128 MiB e extração a 512 MiB.

O Hex Inspector solicita inicialmente 64 KiB e dobra sob demanda até 2 MiB. Cada expansão relê somente a janela inicial ampliada; nenhum payload além do limite visual é carregado.

## Hash e type detection

`HashEngine.calculate_bytes_hash()` foi adicionado para regiões já limitadas. SHA-256 da origem vem do resultado oficial da análise; quando o serviço é usado isoladamente, ele calcula o hash da origem com o mesmo engine.

Detecção regional grava os bytes limitados em diretório temporário e chama `MagicNumberEngine.analyze()`. O temporário é removido automaticamente. A lista de signatures não é copiada para UI ou serviço.

## Extração e proveniência

A faixa é copiada em chunks de 1 MiB para arquivo temporário no diretório de destino. Somente após sucesso o temporário substitui o destino selecionado. A origem é aberta exclusivamente em modo `rb` e o serviço rejeita destino igual à origem.

`ExtractedArtifact` registra source/destination path, source SHA-256, offsets inclusivos, length, extracted SHA-256, formato, MIME, assinatura, método `hex_selection` e timestamp UTC.

Quando solicitado, `<arquivo>.forensihash.json` recebe os mesmos fatos técnicos. O sidecar não contém conclusão investigativa.

## Lifecycle e estados

Troca de arquivo incrementa uma geração, limpa seleção/artefato e invalida callbacks anteriores. Estados de carregamento, seleção vazia/válida/inválida, limite, hash, detecção, extração, cancelamento, sucesso e erro são apresentados inline.

A página expõe `artifact_extracted` e `analyze_artifact_requested`. O botão de nova análise emite o path, mas a conexão com o workflow da `MainWindow` foi deliberadamente adiada para evitar acoplamento página→janela e mudança implícita de caso.

## Segurança e performance diagnóstica

Medição local, não benchmark formal:

- construção da página: 60,28 ms;
- atualização e renderização inicial de 64 KiB: 37,45 ms;
- `read_range` 64 KiB cold: 13,65 ms;
- `read_range` 1 MiB: 1,09 ms;
- SHA-256 de 1 MiB: 1,46 ms;
- extração de 1 MiB: 29,19 ms;
- extração de 100 MiB: 513,58 ms.

Operações de I/O, hash, detecção e extração são executadas fora da thread da UI.

## Limitações e itens adiados

- seleção visual byte a byte por clique/drag;
- ir para offset e atalhos globais;
- seleção contextual automática de trailing JPEG/PDF, pois a página não recebe sessão Deep Structure;
- conexão do artefato ao workflow completo de nova análise;
- leitura paginada de regiões estruturais nativas que não possuam source offset;
- editor/patch hexadecimal, carving, recuperação, análise automática e cadeia de custódia formal.
