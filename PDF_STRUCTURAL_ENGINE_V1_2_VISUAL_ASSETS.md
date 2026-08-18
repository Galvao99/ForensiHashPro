# PDF Structural Engine V1.2 — Visual Assets & Embedded Content

## Escopo e arquitetura

A V1.2 mantém o parser local, neutro e independente. O `StructureReport` passou de `1.1` para `1.2` porque novos campos públicos foram adicionados. Payloads continuam fora do relatório e são recuperados pela sessão PyO3.

```text
StructureReport 1.2
  ├── visual_resources / forms
  ├── embedded_files / metadata_streams
  ├── annotations / signatures
  └── previewable_assets

DeepStructureSession
  ├── get_visual_asset
  ├── get_preview
  ├── get_composite_preview
  ├── get_embedded_file
  └── get_metadata_text
```

`VisualAsset` contém identidade, dimensões, bits, ColorSpace, filtros, encoding de origem e preview, status, masks, warnings e `PreviewProvenance`. Ele não expõe tipos `lopdf`.

## Contrato 1.2

Campos adicionados ao relatório:

- `visual_resources`: mapa página/container/recurso/alvo/path/profundidade;
- `forms`: BBox, Matrix, Resources, Group e disponibilidade do content stream;
- `embedded_files`: nomes, MIME, tamanho declarado e objeto do stream;
- `metadata_streams`;
- `annotations` com propriedades estruturais selecionadas;
- `signatures` com propriedades estruturais selecionadas;
- contagens `pages_with_annotations`, `unique_annotation_objects`, `annotation_references`, `visual_resource_references` e `invoked_xobject_usages`.

`annotation_count` agora significa objetos de annotation únicos. A semântica anterior — páginas que continham `/Annots` — foi movida para `pages_with_annotations`.

## Visual assets e proveniência

Status possíveis:

- `direct`: bytes de codificação visual original são devolvidos sem recompressão;
- `reconstructed`: pixels decodificados foram convertidos em PNG derivado;
- `unsupported`: propriedades/filtros não suportados; nenhum preview é produzido;
- `failed`: reservado para falhas futuras diferenciadas; erros atuais são warnings/erros técnicos.

Exemplos de proveniência:

```json
{"source_filter":"/DCTDecode","transformation":"none","reconstructed":false,"mime_type":"image/jpeg"}
```

```json
{"source_filter":"/FlateDecode","transformation":"decoded_pixels_to_png","reconstructed":true,"mime_type":"image/png"}
```

CMYK usa `cmyk_to_rgb_png`. O PNG é preview derivado; raw stream e decoded stream continuam acessíveis separadamente.

## Matriz validada

| Feature | Detect | Extract | Preview | Tested |
|---|---:|---:|---:|---:|
| DCTDecode/JPEG | yes | yes | direct | yes, JPEG real |
| JPXDecode/JPEG2000 | yes | yes | direct | yes, JP2 real via Pillow/OpenJPEG |
| Flate DeviceRGB 8 bpc | yes | yes | PNG | yes |
| Flate DeviceGray 8 bpc | yes | yes | PNG | yes |
| Flate DeviceCMYK 8 bpc | yes | yes | RGB PNG derivado | yes |
| Predictor 1 | yes | yes | PNG | yes |
| PNG Predictor 10–15 | yes | delegated to bounded lopdf decode | PNG | Predictor 12 tested |
| Predictor fora de 1/10–15 | yes | no | no | yes |
| 1/2/4/16 bpc | yes | raw/decoded | no | 4 bpc recusado em teste |
| ICCBased | yes | raw/decoded | no | yes, PDF real |
| Indexed/CalGray/CalRGB/Lab/Separation/DeviceN | preserved | raw/decoded | no | not preview-tested |
| ImageMask | yes | raw/decoded | no | inventory only |
| Explicit `/Mask` | yes | object separately accessible | if target is supported image | relation tested |
| `/SMask` | yes | yes | separate; composite RGB+Gray | yes |
| Form XObject | yes | content stream | no form rendering | yes |
| Nested Forms | yes | resources mapped | child image preview | yes |
| Resource cycle | yes | bounded | n/a | yes |
| Thumbnail | yes | image API | according to image encoding | yes |
| EmbeddedFile/FileSpec/EF | yes | bytes on demand | no auto-open | yes, real PDF |
| Metadata XML/XMP | yes | raw/decoded/text | n/a | yes, real PDF |
| Annotations | yes | properties | no rendering | yes, multiple real annotations |
| Signature dictionary | yes | properties | n/a | yes, synthetic |

## Flate, ColorSpace e predictors

Preview Flate exige dimensões válidas e `BitsPerComponent = 8`.

- DeviceGray: 1 byte por pixel → PNG grayscale.
- DeviceRGB: 3 bytes por pixel → PNG RGB.
- DeviceCMYK: 4 bytes por pixel → conversão determinística simples para RGB; a proveniência registra a transformação.

O comprimento decodificado deve ser exatamente `width × height × channels`. Multiplicações usam operações verificadas. ICCBased e demais espaços complexos são preservados e recusados para preview para evitar cor visualmente incorreta.

Predictor 1 e PNG predictors 10–15 são aceitos. A decodificação bounded é fornecida pelo `lopdf`; Predictor 12 possui fixture aprovada. Valores fora desse conjunto retornam warning técnico.

## Masks e SMask

`VisualAsset` expõe `image_mask`, `mask_object_id` e `soft_mask_object_id`. A máscara permanece um objeto recuperável separadamente.

`get_composite_preview()` suporta atualmente apenas:

- imagem principal DeviceRGB 8 bpc;
- SMask DeviceGray 8 bpc;
- mesmas dimensões;
- streams decodificáveis dentro dos limites.

O resultado é PNG RGBA derivado. Nenhum objeto original é alterado. Color-key masks e combinações adicionais não são compostas nesta versão.

## Forms, recursos aninhados e uso `Do`

Resources são percorridos por página e por Form XObject. Cada uso registra:

- página;
- container (página ou Form);
- nome local;
- objeto alvo;
- tipo;
- path completo;
- profundidade;
- declarado;
- invocado por operador `Do`.

Exemplo:

```text
/Resources/XObject/Fm1/Resources/XObject/Fm2/Resources/XObject/Im1
```

O parser de conteúdo apenas identifica `Do`; ele não afirma visibilidade. Recursos declarados sem `Do` permanecem distinguíveis. Ciclos usam conjunto de visitados e a profundidade é configurável. CTM/operadores `cm` ainda não são registrados.

## Embedded files, metadata, annotations e signatures

FileSpec direto ou aninhado é correlacionado com `/EF`; `F` e `UF` são preservados. `get_embedded_file()` devolve bytes somente sob chamada explícita e nunca grava, abre ou executa o conteúdo.

Metadata streams podem ser acessados como raw, decoded ou texto loss-tolerant. O conteúdo XMP não é tratado como verdade pericial.

Annotations expõem `/Subtype`, `/Rect`, `/Contents`, `/Name`, `/FS`, `/A` e `/AA` sem executar actions. Signatures expõem `/Type`, `/Filter`, `/SubFilter`, `/ByteRange`, `/Contents`, `/M`, `/Name`, `/Reason` e `/Location`, sem validação criptográfica e sem substituir o DigitalSignatureEngine.

## Limites e cache

Defaults:

- arquivo: 512 MiB;
- stream decodificado: 64 MiB;
- preview: 16.384 × 16.384;
- pixels: 100 milhões;
- Forms aninhados: profundidade 16;
- embedded file: 128 MiB (também sujeito ao limite decodificado);
- cache de preview: 128 MiB.

O cache pertence à sessão e usa chave por objeto/tipo de preview. Ao exceder o limite, ele realiza eviction total simples antes de inserir o novo item. Payload maior que o cache não é armazenado. Essa política evita complexidade LRU prematura, mas pode causar regeneração sob pressão.

## Corpus automatizado

Não há PDFs sigilosos ou binários permanentes. São 31 casos automatizados nesta área (21 Rust e 10 Python), todos construindo streams/PDFs durante o teste. Cinco integrações Python geram PDFs reais para JPEG, JPX, ICCBased/Flate, DeviceRGB/Flate e embedded/XMP/annotations.

## Performance observada

Build de desenvolvimento, Windows, CPython 3.14; uma execução diagnóstica:

| Caso | Páginas | Objetos | Streams | Visual refs | Parse | Preview |
|---|---:|---:|---:|---:|---:|---:|
| pequeno | 1 | 6 | 1 | 0 | 19,94 ms | n/a |
| médio | 25 | 78 | 25 | 0 | 52,85 ms | n/a |
| 200 páginas | 200 | 603 | 200 | 0 | 1.065,82 ms | n/a |
| imagem grande JPEG | 5 | 22 | 8 | 1 | 72,08 ms | 0,07 ms |
| 40 usos de imagem | 1 | 47 | 42 | 40 | 291,55 ms | 0,11 ms |
| Forms aninhados | 1 | 14 | 7 | 5 | 66,80 ms | 0,10 ms |
| Flate RGB 1600×1200 | — | — | — | — | separado | 391,87 ms |

Preview é lazy e não integra o tempo de inventário. Tempos não são benchmarks formais.

## Visual Explorer Readiness

1. **Listar recursos visuais por página:** sim, diretos, via Forms e thumbnail.
2. **Declarado versus utilizado:** sim, por `declared` e `invoked_by_do`.
3. **Objeto original:** sim, identidade composta estável.
4. **Properties:** sim, `get_object()`/PdfValue.
5. **Raw:** sim, raw object e raw stream quando disponíveis.
6. **Decoded:** sim, sob demanda e com limite.
7. **Preview:** sim para matriz marcada como suportada.
8. **Saber se foi reconstruído:** sim, status e proveniência.
9. **Page → Form → Image:** sim, com path e profundidade.
10. **Masks separadamente:** sim quando são objetos Image suportados; composição SMask limitada.
11. **Embedded files:** sim, bytes explícitos sem execução.
12. **Lacunas para “tudo visual”:** renderer de Forms/pages, CTM e posição, espaços de cor avançados, bpc diferentes de 8, color-key masks, patterns/shadings, inline images e verificação de pintura/visibilidade final.

## Limitações deliberadas

- Não há renderer PDF completo nem preview do Form em si.
- Operador `Do` indica invocação, não visibilidade; CTM foi adiado.
- Inline images (`BI/ID/EI`) não são assets independentes nesta versão.
- Indexed, ICCBased, CalGray, CalRGB, Lab, Separation e DeviceN não são reconstruídos.
- ImageMask e color-key mask não são compostas.
- O PNG CMYK usa conversão simples, não color management ICC.
- Cache usa eviction total, não LRU granular.
- O relatório mantém inventário leve; geração de preview continua lazy.
