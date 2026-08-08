# Estabilização do ForensiHash — Parte 6

## Resumo

Esta etapa corrigiu somente fronteiras remanescentes da análise individual:
escopo do `AnalysisContract`, distinção entre seção vazia e não executada,
entrada adquirida do `FileAnalyzer` e estados explícitos de biometria, JSON e
IP. Correlação e comparação continuam resultados separados. Nenhuma regra
forense, API web, layout ou componente histórico foi removido.

Linha de base: **305 testes aprovados**. Resultado: **317 testes aprovados**.

## Problemas corrigidos

- coleções do contrato podiam parecer executadas apenas por estarem vazias;
- o contrato individual não declarava formalmente seu limite de uma evidência;
- `FileAnalyzer.analyze(Path)` permitia uso acidental como fronteira oficial;
- estados biométricos e JSON distintos podiam convergir para `None` ou para o
  mesmo DTO inválido;
- erros de IP eram transportados apenas por `severity="error"` e mensagem;
- a página IP não preservava o estado estruturado da consulta.

## Decisões arquiteturais

`AnalysisContract 1.0.0` representa uma análise individual de uma evidência.
`CorrelationResult` e `ComparisonResult` não são incorporados ao contrato. Os
campos públicos foram preservados; não houve alteração da versão do schema
porque a documentação v1 já permitia `null` para seções opcionais e a mudança
torna essa semântica determinística.

Seção não executada ou pertencente a outro escopo usa `None` e uma etapa
`SKIPPED` com `safe_details.reason`. Coleção vazia fica reservada para etapa
efetivamente executada sem itens. Os motivos usados são:

- `not_executed`;
- `not_part_of_individual_analysis`;
- `different_scope`.

## Proteção da aquisição

Entradas oficiais permanecem `AnalysisCoordinator.execute(original_path)` e
`AnalysisService.analyze(original_path)`. O serviço adquire `EvidenceLease` e
agora entrega `EvidenceSource` ao método interno `FileAnalyzer.analyze_acquired`.
Esse método exige estado `ACQUIRED`, cópia existente e caminho diferente do
original. `FileAnalyzer.analyze(Path)` bloqueia o uso como fronteira pública.

Testes unitários de engines não simulam cadeia de custódia: usam a entrada
explícita `analyze_fixture(Path)`. Assim, fixtures continuam simples sem serem
confundidas com uma análise oficial.

`ComparisonWorkspace` continua chamando `AnalysisService`, portanto cada lado
da comparação passa por aquisição controlada independente.

## Biometria

O campo legado `AnalysisResult.biometric_report` permanece opcional. A execução
agora também adiciona `biometric_analysis` a `processing_steps`:

| Situação | Status |
|---|---|
| arquivo não JSON | `SKIPPED` |
| parser não configurado | `UNAVAILABLE` |
| JSON inválido | `FAILED` |
| JSON válido não biométrico | `NO_FINDINGS` |
| parser falhou | `FAILED` |
| relatório com warnings | `PARTIAL` |
| relatório interpretado | `SUCCESS` |

## JSON / Rust

`JsonParserService.parse()` foi preservado como adaptador legado e a nova API
`parse_step()` diferencia:

- extensão não aplicável: `SKIPPED`;
- módulo Rust ausente: `UNAVAILABLE`;
- parser/exceção: `FAILED`;
- JSON inválido: `FAILED`;
- JSON válido sem campos: `NO_FINDINGS`;
- resultado truncado: `PARTIAL`;
- resultado válido com campos: `SUCCESS`.

O `JsonAnalysisResult` permanece disponível inclusive em falhas para preservar
consumidores existentes.

## IP

`IpAnalysisService.analyze()` e `IpLookupResult` foram preservados. A nova API
`analyze_step()` associa o resultado factual a `ProcessingStatus` e
`ProcessingIssue`. Integração desabilitada, chave ausente, timeout,
indisponibilidade de rede, limite do provedor, erro do provedor, IP inválido e
sucesso possuem códigos distintos. `analyze_text_steps()` permite processamento
em lote sem transformar falha de rede em ausência de endereço.

A página continua iniciando a consulta, mas usa `analyze_step()` e preserva o
último estado estruturado em `current_processing_step`.

## Compatibilidade preservada

- `AnalysisResult` e seus campos públicos;
- `AnalysisContract` schema `1.0.0`;
- `LegacyAnalysisAdapter`;
- `AnalysisWorker` e sinais Qt;
- `AnalysisCoordinator` headless;
- `JsonParserService.parse()`;
- `IpAnalysisService.analyze()` e `analyze_text()`;
- `IpLookupResult` e resultados biométricos;
- engines individuais baseados em `Path`.

## Testes criados e atualizados

Foi criado `tests/test_stabilization_part6.py`, com 12 casos cobrindo contrato
individual, separação da correlação, bloqueio da fronteira insegura, entrada de
fixture, estados biométricos, estados JSON/Rust e estados IP. Testes unitários
existentes do `FileAnalyzer` passaram a usar `analyze_fixture()`.

Resultado final:

- testes isolados da etapa e contrato: aprovados;
- suíte completa: **317 aprovados, 0 falhos**;
- compileall: aprovado;
- Ruff nos arquivos alterados: aprovado;
- `git diff --check`: aprovado, somente com avisos informativos LF/CRLF.

## Arquivos alterados

- `app/contracts/analysis.py`;
- `app/contracts/adapter.py`;
- `app/contracts/serialization.py`;
- `app/engines/file_analyzer.py`;
- `app/services/analysis_service.py`;
- `app/services/json_parser_service.py`;
- `app/integrations/ip/ip_exceptions.py`;
- `app/integrations/ip/ip_client.py`;
- `app/integrations/ip/ip_service.py`;
- `app/pages/ip_pages.py`;
- testes unitários do `FileAnalyzer`;
- `tests/test_stabilization_part6.py`;
- `CONTRATO_ANALISE_FORENSIHASH.md`;
- `ESTABILIZACAO_PARTE_6.md`.

## Segurança e riscos restantes

`aware_knomi_report.json` existe localmente, está rastreado e já possui regra no
`.gitignore`. Ele não foi exibido, apagado nem retirado do índice nesta etapa.
Removê-lo do índice atual não remove cópias de commits anteriores; origem,
retenção e eventual saneamento histórico exigem decisão humana coordenada.

Permanecem fora do escopo: cancelamento dentro de engines, contrato de lote,
timeline duplicada, correlação legada, score legado, Ruff global, sandbox de
parsers e validação em Python 3.12 limpo.
