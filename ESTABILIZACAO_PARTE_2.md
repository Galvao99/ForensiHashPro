# Estabilização do ForensiHash — Parte 2 de 5

Data da execução: 05/08/2026.

## Confirmação da Parte 1

A Parte 1 estava concluída e sua linha de base foi confirmada antes das alterações: 262 testes aprovados. Configuração segura, caminhos centrais e detecção de ferramentas foram preservados.

Esta etapa não alterou parser PDF, score, regras forenses, API, site, banco, autenticação ou arquitetura multiusuário.

## Fluxo anterior

1. `MainWindow` recebe arquivos por `QFileDialog` ou pasta e impede uma segunda thread principal enquanto a atual está ativa.
2. `AnalysisWorker` chama `AnalysisService.analyze(Path)` sequencialmente por arquivo.
3. `AnalysisService` encaminhava o caminho original ao `FileAnalyzer` e, depois, ao OCR.
4. `FileAnalyzer` reutilizava o mesmo caminho em hash, ExifTool, magic number, assinatura, PDF, JSON, biometria e análise binária.
5. Cada componente abria o caminho independentemente. `BinaryReader` também abre novamente por operação/componente.
6. `TimelineService` podia reabrir o original para repetir extração textual.
7. Comparação usa resultados já calculados, mas cada lado inicia uma análise independente pelo mesmo `AnalysisService`.

Portanto, uma análise típica tinha pelo menos oito consumidores lógicos do caminho, e o número físico de aberturas podia ser maior conforme PDF, chunks binários e OCR. Uma substituição entre etapas permitia combinar estados diferentes.

A busca por modos de escrita confirmou que os motores não escreviam no original. Escritas existentes são configuração local e exportações em caminho explicitamente escolhido. OCR/PDF geram objetos em memória; não havia área formal de derivados.

## Fluxo novo

```text
Path selecionado
  -> EvidenceManager.acquire
     -> valida existência e arquivo regular
     -> captura identidade/stat
     -> cria <temp>/evidence/<UUID>/
     -> copia em blocos de 1 MiB e calcula SHA-256
     -> fsync da cópia
     -> relê/hash do original e confirma identidade/tamanho/mtime
     -> torna a cópia somente leitura
  -> AnalysisService
     -> FileAnalyzer(cópia controlada)
     -> hash, ExifTool, magic, assinatura, PDF, JSON, biometria, binário
     -> OCR(cópia controlada)
     -> confirma hash do motor, cópia e original
  -> resultado recebe EvidenceSource verificada e caminho original de exibição
  -> limpeza automática do workspace
```

Se fonte, identidade, tamanho ou hash divergirem, a fonte é marcada `COMPROMISED`. Um `EvidenceIntegrityError` preserva referência ao resultado parcial e impede que ele seja retornado como análise normal ou usado em correlação.

## Modelo criado

`EvidenceSource` é `dataclass(frozen=True, slots=True)` e não depende de Qt. Contém:

- `evidence_id` único;
- nome e caminho original;
- caminho da cópia de trabalho;
- tamanho e SHA-256 inicial/final;
- aquisição UTC timezone-aware;
- tipo declarado e detectado;
- estado `ACQUIRED`, `VERIFIED`, `COMPROMISED` ou `FAILED`;
- indicação de somente leitura;
- erros de aquisição/verificação;
- identidade do arquivo (`device`, `inode`, tamanho e timestamps nanosegundos).

Estados novos são produzidos por cópia via `dataclasses.replace`, preservando a imutabilidade do objeto publicado.

## Estratégia escolhida

Foi escolhida **cópia controlada em disco**, não snapshot integral em memória. A cópia:

- suporta arquivos grandes sem leitura integral;
- isola os parsers do original;
- permite APIs legadas baseadas em `Path`;
- possui diretório exclusivo por UUID;
- é aberta com modo exclusivo (`xb`);
- recebe permissão sem bits de escrita;
- tem conteúdo verificado antes e depois dos motores.

O original é lido durante aquisição e verificação, sempre em `rb`. Nenhuma permissão, metadado ou conteúdo do original é modificado.

## Serviços migrados

No fluxo `AnalysisService`, todos os consumidores de arquivo recebem o mesmo `working_path`:

- HashEngine;
- MetadataEngine/ExifTool;
- MagicNumberEngine;
- DigitalSignatureEngine/pyHanko;
- PDFStructureEngine;
- JsonParserService/Rust;
- BiometricReportService;
- BinaryStructureEngine e componentes;
- TextExtractionService/OCR.

Findings, correlação, IP e comparação consomem resultados/dados em memória e não precisam abrir a evidência. Timeline passou a usar `AnalysisResult.extracted_text`, eliminando sua reabertura tardia.

## Migração gradual e pendências

As APIs internas dos motores continuam aceitando `Path`. Isso é um adaptador transitório deliberado para evitar uma migração arriscada de todos os contratos. Chamadas diretas a `FileAnalyzer` ou a um engine fora de `AnalysisService` não fazem aquisição automática; o fluxo oficial do desktop e o ComparisonWorkspace usam `AnalysisService` e estão protegidos.

A apresentação ainda usa `file_info.path` original para identificação e visualização posterior. Essa visualização não participa dos resultados calculados, mas pode mostrar uma versão posteriormente alterada; uma estratégia de retenção opcional para visualização deve ser decidida sem confundir cópia temporária com preservação pericial.

## Proteção do original e derivados

`EvidenceLease.derivative_path()` cria derivados somente em `<workspace>/derived`, rejeita traversal, caminho absoluto e colisão. Nenhum derivado é criado ao lado do original. Atualmente o OCR mantém imagens em memória; a API prepara uma área segura para componentes futuros sem mudar o fluxo forense.

Permissão somente leitura reduz escrita acidental, mas não constitui sandbox contra código privilegiado capaz de restaurar permissões. A garantia principal é arquitetural: todos os motores recebem apenas o caminho da cópia, nunca o original.

## Concorrência e isolamento

- Cada aquisição usa UUID e `mkdir` atômico com `exist_ok=False`.
- Até 20 colisões são toleradas antes de erro explícito.
- Evidências com o mesmo nome ficam em diretórios diferentes.
- Duas threads podem adquirir simultaneamente sem compartilhar workspace.
- O desktop continua impedindo duas análises principais simultâneas; ComparisonWorkspace pode executar análises independentes, também isoladas.
- Engines permanecem majoritariamente stateless; não foi adicionada fila ou estado global.

## Ciclo de vida e limpeza

`EvidenceLease` é context manager e o `AnalysisService` mantém a posse somente durante a análise. O workspace completo, incluindo derivados, é apagado:

- após sucesso;
- após erro de motor;
- após comprometimento;
- após exceção no bloco consumidor.

Antes da remoção, permissões dos arquivos controlados são restauradas. A limpeza valida que o workspace é filho direto da raiz controlada e nunca aponta para o original. Resultados preservam hashes, identidade, estado e caminho histórico da cópia, embora o arquivo temporário deixe de existir.

## Testes criados

`tests/test_evidence_source.py` adiciona 11 testes cobrindo:

- inexistente e diretório;
- vazio e nome/conteúdo com acentos;
- alteração após aquisição;
- substituição com mesmos bytes detectada por identidade;
- aquisições simultâneas;
- mesmo nome sem colisão;
- SHA-256 inicial e final;
- permissão somente leitura;
- derivados segregados, traversal e colisão;
- limpeza após sucesso e falha;
- todos os consumidores recebendo exatamente o mesmo `working_path`;
- substituição durante análise bloqueando o resultado parcial;
- timeline sem reabrir o original.

## Resultado dos testes

- baseline: 262 aprovados;
- após implementação: **273 aprovados**, 0 falhos, 0 ignorados, 7,79 s;
- `python -m compileall -q app`: aprovado;
- `git diff --check`: aprovado;
- Ruff nos arquivos criados/alterados nesta etapa: aprovado;
- Ruff global: 19 ocorrências legadas já existentes, sem nova ocorrência da Parte 2.

## Limitações restantes

- Não existe monitoramento contínuo capaz de detectar mudança seguida de restauração perfeita entre verificações; hash/identidade antes e depois reduzem, mas não eliminam esse cenário extremo.
- A cópia temporária dobra temporariamente o espaço necessário.
- Falha por disco cheio/permissão é explícita, mas a padronização geral de erros pertence à Parte 3.
- O arquivo temporário é isolamento de processamento, não cópia de preservação nem cadeia de custódia externa.
- Secure deletion não é prometido; SSD, filesystem e SO podem manter blocos/caches.
- Chamadas diretas legadas por `Path` permanecem possíveis fora da orquestração oficial.
- A visualização posterior pelo caminho original não é snapshot e deve ser apresentada como tal.
