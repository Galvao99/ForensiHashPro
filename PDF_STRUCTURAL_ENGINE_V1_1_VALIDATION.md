# PDF Structural Engine V1.1 — Validation & Contract Hardening

## Objetivo e resultado

A sprint validou o contrato necessário para navegação estrutural futura, sem UI e sem interpretação pericial. A auditoria encontrou perda de caminhos aninhados, valores PDF convertidos prematuramente em texto, conteúdos de página não normalizados, preview ambíguo, contagens de recursos duplicáveis e descompressão no inventário. Esses pontos foram corrigidos no contrato 1.1.

## Alterações do contrato 1.0 → 1.1

- `ReferenceEdge.path` preserva caminhos como `/Resources/XObject/Im1`; `relation` foi mantido para compatibilidade conceitual.
- `ObjectRecord.dictionary` passou de `string` para `PdfValue` tipado: `null`, `boolean`, `integer`, `real`, `name`, `string`, `hex_string`, `array`, `dictionary`, `reference` e `stream`.
- Referências tipadas carregam tanto a forma normalizada `object_generation` quanto a apresentação `n g R`.
- `PageRecord.content_object_ids` normaliza stream único e arrays de streams.
- `PreviewableAsset` ganhou `previewable`, `direct_preview` e `preview_available`.
- `StructureSummary` ganhou `unique_image_objects`, `image_references`, `unique_font_objects` e `font_references`.
- `get_object()` agora devolve JSON estável do objeto normalizado; `get_raw_object()` recupera seus bytes físicos quando há offset.
- `decoded_length` permanece `null` no inventário. Nenhum stream é descomprimido apenas para montar o relatório.

Identificadores continuam no formato `<object_number>_<generation_number>` em objetos, edges, streams, imagens, páginas, recursos, assets e APIs sob demanda.

## Corpus sintético

Os PDFs são construídos durante os testes; nenhum documento real ou judicial é versionado.

| Categoria | Cobertura | Resultado |
|---|---|---|
| PDF mínimo, uma página, multipágina e texto | Rust e integração PyMuPDF | Validado |
| Xref tradicional | saída padrão `lopdf` | Validado |
| Xref stream e object streams | `SaveOptions` do `lopdf` | Validado |
| Flate stream | imagem sintética comprimida | Validado |
| JPEG incorporado | PyMuPDF + Pillow | Raw e preview direto validados |
| JPEG2000 | Sem fixture determinística disponível | Não validado |
| Form XObject | fixture sintética | Encontrado, tipado e relacionado |
| `/Mask` e `/SMask` | referências sintéticas | Paths e missing references validados |
| Annotation | `/Annots` com objeto indireto | Encontrado e relacionado |
| AcroForm | referência no Catalog | Encontrado e relacionado |
| Metadata/XMP | metadata stream | Encontrado e relacionado |
| Embedded file | stream `/Type /EmbeddedFile` | Inventário e contagem validados |
| Signature dictionary | `/Type /Sig` | Inventário e contagem validados |
| Parent/Kids e ciclos | pages ↔ page | Sem recursão ou duplicação infinita |
| Objeto/referência ausente | Mask/SMask inexistentes | Warning `missing_reference` |
| Conteúdo único e array de contents | referências indiretas | IDs normalizados validados |
| Reuso de imagem | uma imagem em três páginas | 1 objeto único, 3 referências |
| Múltiplos EOF e bytes finais | fixture sintética | Contagem neutra validada |
| Incremental update | somente marcadores/revisão observada | Reconstrução não validada |
| PDF truncado, stream incompleto, xref inválido | bytes mínimos malformados | Sem panic; erro controlado |

Não foram instalados Office, LibreOffice, Acrobat, iText, PDFium, Ghostscript ou scanners. A diversidade validada é estrutural, não por marca de produtor.

## Grafo e navegação

Cada objeto indireto é um nó único. Cada referência é uma aresta com `source`, `target`, `relation` e `path`. A coleta percorre o valor contido no objeto, mas nunca segue o objeto alvo; por isso ciclos não recursam.

Com apenas o relatório é possível:

1. localizar uma página em `page_tree.pages`;
2. filtrar `resources` por `page_object_id`;
3. obter `category`, nome local e `object_id`, por exemplo `XObject`, `Im1`, `42_0`;
4. localizar `42_0` em `objects`, `streams`, `images` e `previewable_assets`;
5. observar a edge `/Resources/XObject/Im1`;
6. solicitar properties, raw stream, decoded stream ou preview pela mesma identidade.

Contents únicos e múltiplos são expostos em ordem por `content_object_ids`.

## Contagens

- `object_count`, `stream_count` e contagens `unique_*` contam entidades indiretas únicas.
- `page_count` é a quantidade efetivamente resolvida por `get_pages()`.
- `image_references` e `font_references` contam usos em dicionários de recursos de páginas.
- `image_count` e `font_count` mantêm a semântica V1 de entidade apresentada, agora alinhada aos objetos únicos.
- `occurrences` conta chaves e nomes encontrados nos dicionários de objetos. É frequência lexical estrutural, não quantidade de entidades.
- `annotation_count` ainda conta páginas com `/Annots`, não objetos individuais; permanece uma lacuna documentada.

## Golden tests

O golden test fixa campos essenciais do JSON 1.1: versão, formato, page count, imagens únicas e normalização de contents. Ele evita caminhos, timestamps e IDs aleatórios. Mudanças futuras nesses campos exigirão alteração explícita do teste e decisão de versionamento.

## Performance observada

Medição simples em build de desenvolvimento, Windows, CPython 3.14, uma execução por caso:

| Caso | Tamanho | Páginas | Objetos | Streams | Parse |
|---|---:|---:|---:|---:|---:|
| pequeno | 792 B | 1 | 6 | 1 | 39,07 ms |
| médio | 8.718 B | 25 | 78 | 25 | 58,13 ms |
| muitas páginas | 67.857 B | 200 | 603 | 200 | 1.038,78 ms |
| imagem grande | 35.782 B | 5 | 22 | 8 | 110,68 ms |

São medições diagnósticas, não benchmark. O `lopdf::Document` e os bytes originais ficam na sessão. Payloads decodificados não entram no relatório e são produzidos sob demanda, com limite padrão de 64 MiB.

## Ferramentas externas

`qpdf`, `mutool`, `pdfinfo` e Ghostscript não estavam disponíveis no ambiente. Não houve comparação externa. O próprio `lopdf` foi usado como gerador/oráculo auxiliar em testes de xref e object streams, sem virar contrato público.

## Erros e segurança

A fachada Python expõe `DeepStructureError.category`: `unsupported`, `malformed` ou `limit_exceeded`. Falhas de decode continuam controladas pela chamada sob demanda. Missing references viram warnings técnicos. Permanecem read-only, limite de arquivo, descompressão limitada, ausência de execução de JavaScript/anexos e ausência de `unsafe` no módulo.

## Relatório parcial

Não foi implementado. Recuperação tolerante usando varredura parcial paralela poderia misturar objetos confirmados pelo parser com candidatos lexicais. Até existir proveniência por campo e estados de completude claros, um erro estruturado é mais confiável que um relatório aparentemente completo.

## Structural dump

```text
python tools/dump_pdf_structure.py arquivo.pdf
python tools/dump_pdf_structure.py arquivo.pdf --output report.json
python tools/dump_pdf_structure.py arquivo.pdf --summary
```

A ferramenta usa exclusivamente `DeepFileStructureEngine` e não contém parsing PDF.

# UI Readiness

1. **Árvore estrutural:** sim para objetos indiretos, catálogo, páginas, recursos e referências; dicionários tipados permitem expansão recursiva.
2. **Ciclos:** sim; são edges, não expansão recursiva de objetos.
3. **Objeto selecionado:** sim, pela identidade composta estável.
4. **Properties:** sim, via valores tipados no relatório ou `get_object()`.
5. **Raw:** sim para stream e objeto físico com offset conhecido.
6. **Decoded:** sim para streams suportados, sob demanda e com limite.
7. **Preview:** sim para preview direto JPEG/JPX; imagens Flate ficam marcadas como potenciais, sem preview direto.
8. **Recursos por página:** sim, incluindo categoria, nome local, alvo e path semântico.
9. **Lacunas:** offsets/raw de objetos comprimidos, preview de pixels Flate, anotação por objeto, árvore completa de name trees/embedded files, herança aprofundada de page attributes, revisão incremental real e relatório parcial com proveniência.

## Riscos e itens adiados

- `lopdf` mantém o documento inteiro em memória; a sessão também conserva os bytes originais para raw objects.
- Offsets físicos permanecem aproximados para objetos normais e ausentes para objetos em object streams.
- Strings são preservadas com tipo e conteúdo convertido de forma loss-tolerant; bytes exatos continuam disponíveis via raw object quando possível.
- JPEG2000 foi declarado pelo contrato, mas não validado por fixture nesta sprint.
- Xref inconsistente pode impedir o `lopdf` de produzir relatório; isso resulta em erro controlado.
- Incremental revisions continuam observacionais e não são reconstruídas.
