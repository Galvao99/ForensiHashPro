# JPEG Deep Structure Engine V1

## Objetivo e posição arquitetural

O motor descreve a anatomia física de JPEG/JPG localmente, sem score, inferência de fraude ou correlação investigativa. Ele integra `deep_structure`, mas usa `JpegStructureReport` e `JpegDeepStructureSession` próprios. Essa decisão preserva integralmente o contrato PDF 1.2, cujo modelo é específico de objetos PDF, e permite evoluir JPEG sob o contrato versionado 1.0.

O parser Rust não depende do `MetadataEngine` nem expõe tipos de crates externas. A fachada Python apenas converte o JSON estável em dataclasses imutáveis e encaminha acessos lazy à sessão PyO3.

## Contrato 1.0

O relatório contém `format`, `structure_version`, `parser`, `physical_info`, `segments`, `scans`, `frames`, `quantization_tables`, `huffman_tables`, `exif`, `xmp`, `icc`, `visual_assets`, `comments`, `warnings` e `capabilities`. Offsets são absolutos no arquivo, exceto campos explicitamente nomeados `offset_relative_to_tiff`. `end_offset` é exclusivo.

Cada segmento preserva código do marker, nome, categoria, marker/payload offsets, comprimento declarado, comprimento efetivamente disponível, fim, resumo e metadados interpretados. Payloads não são incorporados ao relatório.

## Markers e scans

São nomeados SOI, EOI, APP0–APP15, COM, DQT, DHT, SOF0/1/2/3/5/6/7/9/10/11/13/14/15, SOS, DRI, RST0–RST7 e TEM. Códigos reservados/desconhecidos continuam inventariados.

Após SOS, o scanner distingue `FF00` (stuffing), fill bytes e RST0–RST7. Cada scan termina no próximo marker estrutural; JPEG progressive com múltiplos SOS produz múltiplos registros. Pixels não são decodificados.

## Interpretação suportada

- SOF: tipo baseline/extended/progressive/lossless, variantes aritméticas, precisão, dimensões e componentes/amostragem.
- DQT: múltiplas tabelas, precisão de 8/16 bits e 64 valores.
- DHT: classe DC/AC, id, 16 contagens e símbolos.
- APP0: JFIF e JFXX, incluindo inventário de thumbnails; preview apenas para JFXX JPEG válido.
- APP1 EXIF: byte order TIFF, magic 42, IFD0, ExifIFD, GPSIFD, InteroperabilityIFD, IFD1, entries tipadas, ids desconhecidos, valores/offsets e thumbnail JPEG.
- APP1 XMP: pacote padrão UTF-8 sob demanda. Extended XMP é inventariado e marcado parcial, sem reconstrução.
- APP2 ICC: chunks, sequência e total; reconstrução lazy apenas quando a série é completa, única e dentro do limite.
- APP13/APP14: reconhecimento de Photoshop 3.0 (IRB profundo adiado) e campos Adobe.
- COM: bytes preservados e texto apenas quando UTF-8/ASCII é válido.

## Proveniência e APIs lazy

`analyze_jpeg()` cria a sessão. Estão disponíveis `get_segment`, `get_segment_raw`, `get_scan`, `get_scan_raw`, `get_exif_ifd`, `get_exif_entry`, `get_visual_asset`, `get_preview`, `get_xmp_text`, `get_xmp_raw`, `get_icc_profile` e `get_trailing_bytes`.

O asset `jpeg_main` referencia os bytes originais completos, sem recompressão. Thumbnails JPEG EXIF/JFXX referenciam sua faixa original. Assets não triviais permanecem com preview indisponível.

## EOI, trailing e neutralidade

O primeiro EOI estrutural encerra o inventário principal. O relatório registra offset e tamanho da região posterior. Um SOI nessa região gera `trailing_jpeg_signature` com offset; nenhum desses fatos recebe interpretação de intenção, autenticidade ou fraude.

## Segurança e limites

Há limites configuráveis para arquivo, segmentos, APP, IFDs, entries EXIF, profundidade EXIF, ICC, XMP, thumbnail e scans. A implementação usa aritmética verificada para ranges, limita alocações reconstruídas, detecta ciclos de IFD, pointers fora do payload, lengths inválidos/truncados, EOI ausente e ICC incompleto/duplicado. O inventário é linear no arquivo e não copia payloads grandes; a cópia ocorre somente quando uma API lazy é chamada.

Categorias de erro públicas permanecem `unsupported`, `malformed` e `limit_exceeded`. Warnings são observações técnicas, não findings.

## Validação e performance diagnóstica

O corpus automatizado combina JPEG progressive real gerado por Pillow e fixtures binárias determinísticas, necessárias para controlar exatamente stuffing, restart markers, scans, truncamentos, offsets e trailing bytes. Os testes Rust cobrem a máquina de markers e regressão PDF; os testes Python cobrem contrato/fachada e round-trip nativo.

Medição diagnóstica local (CPython 3.14, build PyO3 de desenvolvimento; valores não são benchmark formal): JPEG 320×240/1,8 KB em 7,15 ms; JPEG 12 MP/188,7 KB em 11,31 ms; progressive 1920×1080/12,8 KB com 10 scans em 13,12 ms; e JPEG com 8 MiB de trailing em 76,80 ms. Imagens uniformes foram usadas, portanto os tamanhos não representam fotografias típicas. O comportamento observado é compatível com uma passagem O(tamanho do arquivo), mantendo apenas inventários e metadados pequenos.

ExifTool, jpeginfo, ImageMagick/identify e exiv2 não estavam instalados no ambiente de validação; nenhuma comparação externa foi possível. Essas ferramentas continuam opcionais e não fazem parte do contrato.

## Funcionalidades parciais e itens adiados

Extended XMP não é reconstruído; APP13 apenas identifica o contêiner Photoshop; ICC não recebe interpretação colorimétrica; thumbnail TIFF não comprimido não recebe preview; múltiplos JPEG após EOI não são reconstruídos. Também ficam fora: qualidade estimada, atribuição de câmera/software, double-JPEG, ELA, esteganografia, carving, recuperação, decoder de pixels, comparação, UI, Web/API, `AnalysisContract`, correlação e timeline.
