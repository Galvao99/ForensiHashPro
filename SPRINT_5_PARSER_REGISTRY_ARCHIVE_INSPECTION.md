# Sprint 5 — Parser Registry + Safe Archive Inspection V1

## Arquitetura anterior

O `MagicNumberEngine` já identificava formatos pelo cabeçalho e diferenciava ZIP,
OpenXML, APK e JAR por estrutura interna. A seleção especializada, porém, ainda
estava distribuída entre `FileAnalyzer`, assinatura, JSON, biometria, texto e PDF,
com alguns fallbacks baseados em extensão. ZIP era aberto apenas para enriquecer a
identificação do container, sem inventário, limites próprios ou embedded artifacts.

## Fluxo final

```text
EvidenceManager
  -> Hash / MagicNumberEngine
  -> ArtifactIdentification
  -> ParserRegistry
      -> ZipArtifactParser
      -> BinaryFallbackParser
  -> ParsedArtifact
  -> AnalysisResult
  -> AnalysisContract 1.0.0 technical_structure
  -> Desktop / Web
```

O registro é uma camada compatível. JSON, biometria, assinatura e PDF continuam nos
fluxos legados nesta versão para evitar uma migração ampla e arriscada.

## ArtifactParser e ParsedArtifact

`ArtifactParser` é um `Protocol` com `parser_id`, `supported_types`, `priority`,
`can_parse()` e `parse()`. Parsers são instâncias explicitamente registradas pelo
factory; nenhum módulo é importado dinamicamente a partir do upload.

`ParsedArtifact` preserva parser, tipo detectado, extensão declarada, MIME, magic,
estado, metadados, estrutura, embedded artifacts, warnings e limitações.

## Identificação

`ArtifactIdentification` deriva do resultado do `MagicNumberEngine`, considerando
magic, MIME, formato detectado, extensão e filename. A extensão nunca decide
sozinha o parser ZIP. Entradas internas usam uma identificação pequena e limitada
por bytes para PDF, PE, JPEG, PNG, ZIP e JSON.

Arquivos de conteúdo PE com nome PDF continuam identificados como PE pelo magic e
registram divergência factual. Nenhum arquivo é executado para descobrir o tipo.

## ParserRegistry e fallback

O registro ordena parsers por prioridade e ID, rejeita IDs duplicados e seleciona o
primeiro `can_parse()` aplicável. Na ausência de parser especializado,
`BinaryFallbackParser` informa que a análise binária geral permanece disponível.
O fallback não reabre ou executa o artefato.

## ArchiveInspectionEngine

A primeira implementação suporta ZIP por meio da biblioteca padrão `zipfile`.
Ela lê o diretório central e abre entradas individualmente somente quando seus
metadados passam pelos limites preventivos. Não existe extração integral.

Cada `ArchiveEntry` inclui:

- `embedded_artifact_ref` determinístico;
- filename e path interno;
- extensão;
- tamanhos comprimido/descomprimido;
- taxa de expansão;
- CRC32 e método de compressão;
- estado encrypted;
- file, directory, symlink ou special;
- magic, MIME e tipo detectado;
- SHA-256, quando calculável;
- flags, profundidade, children e limitações.

Embedded artifacts não geram AnalysisJobs nesta sprint.

## Inspeção estática e streaming

Entradas permitidas são lidas em chunks de 64 KiB. O mesmo fluxo calcula SHA-256,
captura somente o cabeçalho necessário e contabiliza bytes reais. O tamanho real
continua limitado mesmo se o diretório central declarar um valor menor.

Nested ZIP usa `SpooledTemporaryFile` controlado e sem nome derivado da entrada. O
buffer migra para arquivo temporário do sistema apenas quando necessário e é sempre
fechado. Nenhum path da entry determina destino no filesystem.

## Limites

Defaults:

| Variável | Default |
|---|---:|
| `FORENSIHASH_ARCHIVE_MAX_ENTRIES` | 1000 |
| `FORENSIHASH_ARCHIVE_MAX_TOTAL_UNCOMPRESSED_BYTES` | 1073741824 |
| `FORENSIHASH_ARCHIVE_MAX_ENTRY_UNCOMPRESSED_BYTES` | 268435456 |
| `FORENSIHASH_ARCHIVE_MAX_COMPRESSION_RATIO` | 200 |
| `FORENSIHASH_ARCHIVE_MAX_NESTING_DEPTH` | 3 |
| `FORENSIHASH_ARCHIVE_INSPECTION_TIMEOUT_SECONDS` | 30 |

Valores são validados no startup web e na composição desktop. Valores negativos,
zero fora de escopo ou limites absurdamente altos são rejeitados. O limite por
entrada não pode exceder o total.

## Flags factuais

- `executable_content_detected`;
- `script_content_detected`;
- `macro_enabled_office_detected`;
- `extension_content_mismatch`;
- `double_extension`;
- `archive_path_traversal`;
- `archive_expansion_limit`;
- `archive_entry_limit`;
- `archive_depth_limit`;
- `encrypted_entry`;
- `corrupted_entry`;
- `nested_archive_detected`;
- `archive_timeout`.

Essas flags descrevem conteúdo ou limitações. Não representam malware, vírus,
trojan, intenção, autoria ou fraude.

## Path traversal e entradas especiais

São detectados `..`, paths Unix absolutos, drives Windows e separadores Windows.
Entries nunca são extraídas para esses caminhos. Symlinks e tipos especiais são
registrados e não materializados.

## Encrypted e corrupted

Entries encrypted não recebem tentativa de senha e ficam sem inspeção/hash, com
limitação explícita. ZIP corrompido ou CRC inválido produz resultado parcial seguro,
sem stack trace ou exception interna pública.

## Pipeline e contrato

`FileAnalyzer` adiciona `artifact_parsing` aos ProcessingSteps. Falha especializada
é isolada como parcial, mantendo hash e identidade. `AnalysisResult.parsed_artifact`
é serializado em `technical_structure.parsed_artifact`; ZIP também é disponibilizado
em `technical_structure.archive`. O AnalysisContract permanece 1.0.0.

## Frontend

A seção “Archive Inspection” apresenta resumo, warnings factuais, árvore técnica
expandível e detalhes. `TechnicalTree` é reutilizado, portanto nodes internos só são
renderizados quando expandidos. A engine limita a quantidade máxima de nodes antes
da serialização. Não há ação de abrir, baixar ou executar entradas.

## Segurança

- zero shell, eval ou execução;
- zero import dinâmico baseado em upload;
- paths internos nunca controlam filesystem;
- nenhuma credencial é quebrada;
- tamanho declarado e tamanho real são limitados;
- nesting e tempo são finitos;
- SHA-256 é calculado por streaming;
- paths absolutos do servidor são removidos pelo presenter web.

## Limitações

- somente ZIP é parser especializado nesta versão;
- RAR e 7Z permanecem apenas identificados pelo magic;
- ZIP multipart e métodos de compressão não suportados pela biblioteca padrão podem
  resultar em inspeção parcial;
- não há análise profunda de macros, executáveis ou scripts;
- hashes de entries bloqueadas por limite/encryption não são calculados;
- parsers legados serão migrados gradualmente para o registry em sprint futura.
