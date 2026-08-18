# PDF Structural Engine V1

## Escopo

O módulo `app.deep_structure` é um backend local e independente para inventário estrutural de PDF. Ele não alimenta Findings, correlação, timeline, AnalysisContract, Web ou UI e não produz score, confiança ou conclusão pericial.

## Arquitetura

```text
DeepFileStructureEngine (Python)
  -> forensihash_core.analyze_pdf (PyO3/maturin)
    -> StructureParser (trait Rust)
      -> PdfStructureParser (lopdf + varredura física limitada)
        -> StructureReport próprio do ForensiHash
```

`StructureParser` é o ponto de extensão para JPEG, PNG, TIFF, ZIP e RIFF. Os tipos de `lopdf` permanecem dentro do crate e não fazem parte do contrato público.

## Estratégia de parsing

Foi adotado `lopdf 0.44`, biblioteca Rust dedicada à estrutura PDF, em vez da implementação de um parser completo da especificação. A biblioteca resolve objetos, referências, page tree, streams e object streams. Uma varredura física complementar coleta header, versão, `%%EOF`, `startxref` e offsets aproximados de objetos.

O grafo é representado por `objects` (nós) e `references` (arestas rotuladas). A geração das arestas percorre cada objeto uma vez e não segue referências recursivamente, portanto ciclos como `Parent`/`Kids` não causam recursão infinita.

## Contrato `StructureReport` 1.0

O relatório serializável contém:

- `format`, `contract_version` e `parser`;
- `physical`: tamanho, magic bytes, versão/header, EOFs, startxref e bytes após EOF;
- `summary`: objetos, páginas, streams, imagens, fontes, anotações, anexos, assinaturas e revisões observadas;
- `objects` e `references`;
- `xref`, `trailer`, `catalog` e `page_tree`;
- `resources`, `streams`, `images` e `embedded_items`;
- `previewable_assets`, `occurrences` e `parser_warnings`.

Warnings são técnicos e descritivos. Bytes após EOF e múltiplos EOF são contagens/observações, nunca indicadores de fraude.

Exemplo reduzido:

```json
{
  "format": "PDF",
  "contract_version": "1.0",
  "summary": {"object_count": 428, "stream_count": 94, "image_count": 18},
  "occurrences": [{"name": "/FlateDecode", "count": 47}],
  "parser_warnings": []
}
```

## Integração Python e acesso sob demanda

```python
from app.deep_structure import analyze_pdf

session = analyze_pdf("evidence.pdf")
report = session.report
raw = session.get_raw_stream("27_0")
decoded = session.get_decoded_stream("27_0")
preview = session.get_preview("27_0")
```

A sessão conserva o `Document` analisado em memória. Assim, cliques futuros não exigirão novo parse. O relatório não contém payloads pesados. `get_object` devolve atualmente a representação técnica do objeto; streams devolvem bytes.

## Segurança

- arquivo aberto somente para leitura e limite padrão de 512 MiB;
- descompressão individual limitada por padrão a 64 MiB;
- nenhum JavaScript ou anexo é executado/aberto;
- ausência de `unsafe` no código do módulo;
- offsets e comprimentos usam operações limitadas e `Result`/erros Python controlados;
- o original nunca é alterado.

## Preview V1

Image XObjects são inventariados com dimensões, filtros, cor e tamanhos. JPEG (`DCTDecode`) e JPEG 2000 (`JPXDecode`) podem ser devolvidos diretamente por `get_preview`. Imagens Flate/raw expõem dados decodificados, mas ainda exigem reconstrução de pixels pela futura camada de preview.

## Limitações reais

- offsets de objetos são obtidos por varredura lexical complementar e podem ser ausentes para objetos em object streams;
- xref V1 inventaria seções e campos principais, mas não expõe ainda cada entrada livre/em uso;
- `revision_count` é uma contagem inicial de marcadores EOF, não reconstrução de revisões;
- PDFs severamente corrompidos podem retornar erro controlado em vez de relatório parcial;
- herança completa de atributos da page tree e reconstrução visual de imagens não-JPEG ficam para versões posteriores;
- embedded files, forms, masks e assinaturas são inventariados de forma inicial, sem extração/renderização completa.

## Roadmap sugerido

V2: cadeia incremental por revisão, entradas xref completas, objetos redefinidos, embedded files, Form XObjects, masks e previews adicionais. V3: implementações do trait para JPEG, PNG, TIFF, WebP/RIFF e ZIP. A UI Deep File Explorer deve consumir este contrato somente após sua estabilização.
