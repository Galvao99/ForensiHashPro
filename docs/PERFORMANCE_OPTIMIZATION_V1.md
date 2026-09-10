# Performance Optimization V1

## 1. Objetivo

Reduzir trabalho redundante medido pelo Diagnostics sem reduzir a análise forense. Esta etapa trata primeiro a recomputação integral da correlação legacy, preservando resultados, proveniência, cache, cancelamento, progresso incremental e a correlação canônica.

## 2. Ambiente

O baseline foi fornecido a partir de uma execução real do ForensiHash Desktop. A identificação da máquina, as versões das dependências e o estado detalhado do sistema não estavam disponíveis nesta sessão. Uma comparação final exige a mesma máquina, configuração, conjunto de arquivos e estado conhecido do cache.

## 3. Baseline

| Métrica | Valor observado |
|---|---:|
| Arquivos | 40 |
| Tamanho lógico | aproximadamente 6,4 MB |
| Wall total | aproximadamente 455.163 ms |
| TTFR | aproximadamente 12.190 ms |
| Peak concurrency | 1 |
| Cache | 0 hits / 40 misses |
| Estado final | partial |
| Legacy correlation | 41 execuções; aproximadamente 244.058 ms acumulados |
| Binary | aproximadamente 93.169 ms acumulados |
| Metadata | aproximadamente 41.406 ms acumulados |
| OCR | aproximadamente 10.649 ms acumulados |
| Analysis pipeline | aproximadamente 196.305 ms acumulados |
| Correlação canônica final | aproximadamente 168 ms |

Tempos acumulados de engines podem se sobrepor e não representam parcelas exclusivas do wall total.

## 4. Dataset

O conjunto contém 40 arquivos e aproximadamente 6,4 MB lógicos. Este documento não registra nomes, caminhos ou conteúdo dos arquivos. O dataset real não estava disponível no workspace para reexecução automática.

## 5. Métricas

As métricas primárias são wall total, TTFR e equivalência do resultado final. `EngineMetric.executions` para `legacy_correlation` mede diretamente quantas avaliações completas ocorreram, sem ampliar o schema de exportação. Tempos acumulados de binary, metadata, OCR e legacy correlation são sinais auxiliares e podem se sobrepor.

TTFR mantém a definição existente: duração monotônica entre o início do Case e o primeiro `AnalysisResult` tecnicamente útil emitido. A correlação legacy ocorre depois da emissão do resultado de arquivo e, portanto, a mudança atual não reduz estruturalmente o TTFR do primeiro arquivo.

## 6. Gargalos observados

O `AnalysisWorker` executava correlação legacy com o Case vazio, depois de cada cache hit e depois de cada análise concluída. Cada chamada seguia para `AnalysisService.correlate_case`, `CorrelationService.update_case`, substituía o índice do Case e avaliava novamente o conjunto completo. Com 40 arquivos, isso gerava 41 avaliações integrais de tamanhos crescentes.

O custo medido da correlação legacy, aproximadamente 244 segundos acumulados, é muito maior que a correlação canônica final, aproximadamente 168 ms. A UI recebe progresso e resultados de arquivo por sinais próprios. O snapshot legacy alimenta o resumo de investigação e findings combinados, mas não precisa ser recalculado depois de cada arquivo para preservar o feedback incremental de ingestão.

### Call graph auditado

| Trigger anterior | Caller | Caminho | Consumer/UI | Alternativa disponível | Decisão |
|---|---|---|---|---|---|
| Início do Case vazio | `AnalysisWorker.run` | `correlate_case` → `update_case` → `replace` → `evaluate` | snapshot legacy vazio | progresso do Case | removido |
| Cache hit | `AnalysisWorker.run` | mesmo caminho integral | snapshot legacy intermediário | `file_analyzed` e progresso | coalescido |
| Arquivo analisado | `AnalysisWorker.run` | mesmo caminho integral | resumo/findings intermediários | `file_analyzed` e progresso | coalescido |
| Final do Case | `AnalysisWorker.run` | mesmo caminho integral | resumo e findings finais | nenhuma equivalente legacy completa | preservado, uma vez |
| Correlação canônica final | `AnalysisWorker.run` | pipeline V2 | Timeline e Correlation Explorer | já canônica | preservada |

Não foi encontrada uma segunda recomputação disparada pela MainWindow. Ela consome o sinal `investigation_completed`; não inicia outra correlação.

## 7. Hipóteses

A hipótese principal é que remover as 40 avaliações intermediárias reduz o wall total mantendo o mesmo resultado legacy final, pois a avaliação restante recebe a mesma lista final e na mesma ordem. A mudança não promete redução de TTFR: a primeira emissão útil já precedia a correlação legacy. O ganho real de wall precisa ser confirmado no dataset original.

Binary e metadata permanecem hipóteses secundárias. Binary faz múltiplas passagens pelo arquivo em scanners e extratores distintos. Metadata inicia um subprocesso ExifTool por arquivo. As métricas atuais não separam subestágios nem startup de subprocesso com precisão suficiente para justificar alteração nesta versão.

## 8. Mudanças implementadas

- `AnalysisWorker` deixou de executar correlação legacy no Case vazio e após cada arquivo/cache hit.
- Uma correlação legacy final obrigatória é executada após a ingestão, inclusive quando nenhum artefato produz resultado válido, para substituir qualquer índice stale pelo estado final vazio.
- A correlação canônica final continua sendo executada uma vez quando existem resultados.
- O cancelamento continua retornando antes das correlações finais e permanece separado de falha.
- Testes cobrem 1, múltiplos e 40 artefatos, cache hit, falha parcial, cancelamento, stale Case, equivalência do resultado final, ordem e contagem observável.

## 9. Riscos

Durante a ingestão, o resumo legacy e os findings combinados deixam de receber snapshots intermediários completos. O progresso, os estados de arquivo e os `AnalysisResult` continuam incrementais. A UI recebe o snapshot final antes do sinal de conclusão. O risco é limitado a consumidores externos que tenham assumido, sem contrato explícito, um sinal legacy por arquivo; os consumidores internos auditados não dependem dessa frequência.

## 10. Testes

Os resultados exatos da validação final desta sessão devem ser registrados no relatório da execução. Os testes adicionados verificam a contagem de uma execução final em um Case simulado de 40 artefatos e exercitam os contratos de cache, falha, cancelamento, stale Case e projeção canônica.

## 11. Before/After

| Metric | Before | After | Delta | Delta % |
|---|---:|---:|---:|---:|
| Total wall | ~455.163 ms | aguardando medição real | — | — |
| TTFR | ~12.190 ms | aguardando medição real | — | — |
| Legacy correlation executions | 41 | aguardando medição real; teste simulado: 1 | — | — |
| Legacy correlation accumulated wall | ~244.058 ms | aguardando medição real | — | — |
| Binary accumulated wall | ~93.169 ms | aguardando medição real | — | — |
| Metadata accumulated wall | ~41.406 ms | aguardando medição real | — | — |
| OCR accumulated wall | ~10.649 ms | aguardando medição real | — | — |
| Peak concurrency | 1 | aguardando medição real | — | — |
| Process CPU | indisponível no resumo | aguardando medição real | — | — |
| Cache hits/misses | 0 / 40 | aguardando medição real | — | — |

O teste estrutural de 40 artefatos confirma a meta de uma execução final, uma redução esperada de 40 execuções ou 97,56% na contagem. Esse valor não substitui um benchmark real e não permite inferir a redução percentual do wall.

## 12. Impacto

A análise técnica por arquivo, a ordem dos resultados, a correlação canônica, os IDs determinísticos e a proveniência não foram modificados. Cache hits entram na lista final na mesma posição. Falhas continuam ausentes dos resultados correlacionáveis e registradas separadamente. A correlação legacy final recebe exatamente os resultados válidos acumulados.

## 13. Limitações

- O dataset real e seu export de diagnóstico não estavam presentes no workspace.
- O AFTER, os deltas de wall/TTFR/CPU e a equivalência de findings reais aguardam nova execução.
- O baseline não inclui process CPU no resumo fornecido.
- A cobertura de I/O é parcial e não mede leituras internas de bibliotecas externas.
- Variação da máquina, cache do SO, processos concorrentes e versões de ferramentas pode afetar runs.
- A equivalência unitária caracteriza a entrada/saída do caminho legacy; a equivalência do Caso real precisa ser verificada pelo export e pelas telas finais.

## 14. Próximos passos

1. Reexecutar o mesmo Case de 40 arquivos, na mesma máquina e configuração, com profiling habilitado e cache em estado equivalente ao baseline (0 hits / 40 misses).
2. Exportar o Diagnostics sanitizado e registrar wall, TTFR, process CPU, cache, estado, contagem e tempo legacy, binary, metadata, OCR e peak concurrency.
3. Comparar os resultados canônicos, findings, timeline, correlação final e proveniência.
4. Instrumentar subestágios de binary antes de alterar suas múltiplas leituras.
5. Medir separadamente execução e parsing do ExifTool antes de considerar um processo persistente.
6. Auditar profundamente o estado compartilhado antes de testar concorrência limitada de artefatos.

### Auditoria de concorrência

| Componente | Classificação V1 | Motivo |
|---|---|---|
| Hash | SAFE_PARALLEL | operação local e sem estado compartilhado observado |
| Metadata/ExifTool | SAFE_WITH_LIMIT | subprocesso por arquivo; custo e cancelamento precisam de medição |
| OCR/Tesseract | SAFE_WITH_LIMIT | subprocesso e configuração global do executável |
| Binary | UNKNOWN | componentes compostos e múltiplas leituras ainda sem prova de thread-safety |
| Cache | UNKNOWN | acesso concorrente não caracterizado nesta etapa |
| Observability collector | SAFE_PARALLEL | sincronização interna existente |
| Legacy correlation | SERIAL_ONLY | índice mutável por Case |
| Canonical correlation | SERIAL_ONLY nesta etapa | executada ao final; paralelismo sem benefício comprovado |
| AnalysisService/FileAnalyzer | UNKNOWN | engines compartilhadas e contrato global ainda não auditados integralmente |

Nenhuma concorrência foi introduzida porque a cadeia completa não está comprovadamente thread-safe e isso exigiria uma alteração mais ampla do worker.

# PERFORMANCE OPTIMIZATION V1 — DOCUMENTATION SUMMARY

## A. Baseline original

- 40 arquivos, aproximadamente 6,4 MB.
- Wall total de aproximadamente 455.163 ms e TTFR de aproximadamente 12.190 ms.
- Peak concurrency 1; cache 0 hits / 40 misses; Case partial.
- Legacy correlation: 41 execuções e aproximadamente 244.058 ms acumulados.
- Binary: ~93.169 ms; metadata: ~41.406 ms; OCR: ~10.649 ms; pipeline: ~196.305 ms.

## B. Problema principal identificado

O worker reconstruía e reavaliava a correlação legacy completa no início e depois de cada artefato. O custo crescia com o Case e produzia 41 avaliações para 40 arquivos. O feedback incremental de arquivos e progresso já usa sinais independentes, portanto essas avaliações completas intermediárias não eram necessárias para manter a ingestão visível.

## C. Mudanças implementadas

- `app/workers/analysis_worker.py`: coalescimento das avaliações legacy em uma execução final, mantendo ordem e entrada final.
- `tests/test_analysis_contract.py`: cobertura funcional de lote, cache, erro, cancelamento, stale Case, ordem e equivalência final.
- `tests/test_performance_profiling_v1.py`: prova observável de uma execução legacy em 40 artefatos simulados.
- Documentação e JSON de comparação: baseline sanitizado e AFTER explicitamente pendente.

## D. Mudanças NÃO implementadas

- Concorrência de artefatos: cadeia completa ainda não demonstrou thread-safety.
- Otimização de binary: faltam timings confiáveis de subestágios.
- ExifTool persistente: mudança arquitetural e cleanup/cancelamento exigem medição específica.
- Publicação parcial antecipada para TTFR: exigiria mudança de contrato e UI.
- Alterações na correlação canônica e cache: não há evidência de gargalo ou erro que as justifique.

## E. Validação funcional

Os resultados exatos de pytest, compileall, Ruff e `git diff --check` são registrados no relatório final da sessão. A cobertura inclui contagem, resultado final, cache hit, falha de artefato, cancelamento, stale Case e preservação da projeção canônica.

## F. Resultado de performance

| Metric | Before | After | Delta | Delta % |
|---|---:|---:|---:|---:|
| Total wall | ~455.163 ms | aguardando medição | — | — |
| TTFR | ~12.190 ms | aguardando medição | — | — |
| Legacy correlation executions | 41 | aguardando medição; simulação: 1 | — | — |
| Legacy correlation accumulated wall | ~244.058 ms | aguardando medição | — | — |
| Binary accumulated wall | ~93.169 ms | aguardando medição | — | — |
| Metadata accumulated wall | ~41.406 ms | aguardando medição | — | — |
| OCR accumulated wall | ~10.649 ms | aguardando medição | — | — |
| Peak concurrency | 1 | aguardando medição | — | — |
| Process CPU | indisponível | aguardando medição | — | — |
| Cache hits/misses | 0 / 40 | aguardando medição | — | — |

## G. Integridade funcional

Os testes confirmam preservação da ordem, da entrada da correlação final, do caminho canônico, do cache e do cancelamento. A equivalência dos resultados canônicos, findings, timeline, correlação final e proveniência do Case real aguarda a nova execução comparável.

## H. Conclusão

Classificação: **inconclusivo para performance end-to-end**. A remoção do trabalho redundante está comprovada estruturalmente e em teste (41 execuções no baseline contra 1 na simulação de 40 artefatos), mas wall, TTFR e equivalência do dataset real ainda não foram medidos depois da mudança.

## I. Próximos gargalos observados

1. Binary, aproximadamente 93.169 ms acumulados, sujeito a medição por subestágio.
2. Metadata/ExifTool, aproximadamente 41.406 ms, sujeito à separação de startup, execução e parsing.
3. TTFR, aproximadamente 12.190 ms, sujeito a estudo do contrato de publicação parcial.
4. Concorrência de artefatos, atualmente 1, somente após auditoria completa de thread-safety.

## J. Limitações da comparação

O AFTER depende do mesmo dataset, máquina, configuração, versões e estado de cache. Cache do SO e carga concorrente podem variar. A cobertura de I/O é parcial. O process CPU original não foi fornecido. Nenhum valor AFTER foi inferido ou fabricado.
