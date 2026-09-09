# Performance Profiling V1

## Objetivo

Evoluir Configurações → Diagnóstico usando a observabilidade existente, com medidas auditáveis e cobertura explícita. Fluxo de trabalho: **MEASURE → BASELINE → OPTIMIZE → RE-MEASURE**. Nenhuma otimização arquitetural foi implementada.

## Auditoria e mapa de métricas

A aplicação usa PySide6, um AnalysisWorker em QThread e processamento sequencial de arquivos. AnalysisCoordinator chama AnalysisService, que adquire uma cópia de evidência e usa FileAnalyzer. O cache existente é um dicionário volátil de AnalysisResult mantido pelo MainWindow. Há correlação legada a cada resultado e uma execução final do pipeline canônico.

O ObservabilityService existente já tinha RLock, buffer de ExecutionMetric, erros limitados, ActiveJob, CasePerformance, health checks, sanitização e export JSON. A implementação evolui esse mesmo serviço. Não há um segundo armazenamento nem um novo worker pool.

| Métrica | Produtor | Armazenamento | Consumidor |
| --- | --- | --- | --- |
| Início, TTFR, duração, contagem e bytes lógicos do Caso | MainWindow.begin_case / AnalysisWorker | CasePerformance e milestones | Visão geral, Performance, JSON |
| Wall por operação/engine | profile_call nos limites reais em FileAnalyzer e AnalysisService; OCR em TextExtractionService | ExecutionMetric e agregados no ObservabilityService | Engines, detalhes, operações mais demoradas, JSON |
| Wall do artefato | Cronômetro do AnalysisWorker envolvendo AnalysisCoordinator.execute | analysis_pipeline / ArtifactMetric | Performance, detalhe de artefato, JSON |
| Cache de resultados | Consulta real ao dicionário recebido pelo worker | CacheStats, análise de lookup | Visão geral, Performance, JSON |
| Fila e execuções simultâneas | start_job / finish_job / update_case | QueueStats e ActiveJob | Jobs, Performance, JSON |
| Correlação canônica | CanonicalCasePipeline | Perfil leve no resultado; CorrelationStats no coletor | Performance, tabela de regras, JSON |
| Correlação legada | profile_call em correlate/correlate_case | ExecutionMetric sem file_ref | Engines / operações do Caso, JSON |
| Bytes efetivamente lidos pelo Hash | HashEngine.calculate_all | ExecutionMetric.bytes_read; contador acumulado independente da retenção | I/O parcial, JSON |
| CPU do processo na sessão | process_time no coletor | CasePerformance.case_cpu_ms | Performance, JSON |
| Ambiente e dependências | collect_environment e health checks existentes | EnvironmentSnapshot / ComponentHealth | Ambiente, JSON |
| Erros operacionais | AnalysisWorker e record_error existente | deque de OperationalError sanitizados | Erros, resumo, JSON |

## Instrumentação, isolamento e overhead

ProfilingBinding usa ContextVar para vincular o coletor à execução síncrona na thread de análise. Guarda somente referências pseudonimizadas e tamanho lógico; nunca argumentos, resultados, texto ou paths. profile_call devolve o mesmo resultado e propaga a mesma exceção da operação. Falhas do coletor são isoladas e registradas somente pela classe da exceção.

Os timestamps de StepResult não são reaproveitados como profiling: várias etapas os criam após executar. As chamadas reais de Hash, metadados, magic number, assinatura, parser, PDF, JSON, biometria, findings, análise binária, extração textual, OCR, verificação da cópia, entidades e timeline recebem cronômetros monotônicos. Etapas explicitamente skipped não geram chamadas fictícias. O custo da aquisição e montagem de contratos entra no total do artefato, mas não tem decomposição completa na V1.

A medição não adiciona callbacks por byte, novas leituras, subprocessos, cache ou dependências. O contador de Hash acumula len(chunk) no laço já existente e publica uma vez ao sair, inclusive se a operação falhar.

Medição sintética local em 09/09/2026, cinco repetições de 10.000 chamadas, com scripts/measure_profiling_overhead.py:

- passagem desabilitada: aproximadamente 0,20 µs/chamada;
- coleta habilitada: aproximadamente 68,53 µs/chamada;
- custo adicional isolado: aproximadamente 68,33 µs/chamada;
- snapshot com 2.000 amostras: aproximadamente 2,11 ms.

Esses valores foram obtidos durante trabalho de desenvolvimento no mesmo computador, não são uma promessa de desempenho ou uma medição percentual de um Caso real. Para um baseline representativo, medir novamente no ambiente e conjunto de arquivos de interesse.

## TTFR e milestones

TTFR é o tempo entre begin_case e a disponibilidade do primeiro AnalysisResult válido, imediatamente antes de file_analyzed.emit. Conta um SHA-256 com formato válido, metadados não vazios ou uma etapa success/partial/limit_exceeded com payload técnico não vazio de tipo suportado. Um StepResult contendo somente status ou mensagem não conta. Spinners, progresso, criação de job, placeholder, NO_FINDINGS sem payload, erro e resultado descartado por cancelamento não contam.

Um resultado válido vindo do cache pode marcar TTFR. A marca ocorre antes da correlação legada disparada após o arquivo. **Não mede a entrega do sinal nem a pintura efetiva da UI**: essa latência não pode ser inferida pelo worker e fica fora da V1.

case_started_at, first_useful_result_at e case_finished_at são timestamps UTC informativos. As durações e marcos relativos usam perf_counter, inclusive quando o relógio inicial retorna zero. A primeira marca e o fim não são sobrescritos por atualizações repetidas.

Marcos: analysis_started, first_parser_completed, first_useful_result, all_artifacts_processed, correlation_started, correlation_completed e case_complete, ou analysis_cancelled. Marcos ausentes permanecem ausentes. Cancelamento preserva execuções já medidas, não produz TTFR para um resultado cancelado e distingue jobs iniciados cancelados de itens removidos da fila antes de iniciar.

## Wall, CPU, engines e artefatos

Wall é tempo decorrido monotônico. Os totais de engines são acumulados e podem se sobrepor. Extração textual inclui OCR; o perfil OCR mede a chamada individual ao Tesseract, por imagem/página. Portanto, somar text_extraction e OCR não produz o wall do artefato.

ArtifactMetric.total_duration_ms vem do cronômetro do fluxo completo do artefato. Sem essa fronteira medida, total_duration_ms permanece null; stage_wall_ms guarda separadamente a soma das etapas disponíveis, que pode conter sobreposição. Correlação entre arquivos permanece Case-level, sem distribuição artificial entre artefatos.

A UI não exibe “% do Caso”. As microbarras monocromáticas informam explicitamente participação no wall acumulado instrumentado e excluem o total inclusivo do pipeline e o lookup do cache.

CPU por engine é UNAVAILABLE. process_time mede CPU do processo durante a sessão, inclui outras threads e exclui CPU de subprocessos externos. O campo do Caso é PARTIAL e a UI usa a descrição “CPU do processo durante a sessão”. Um zero retornado pelo relógio, inclusive devido à resolução do sistema, é uma observação real; ausência não vira zero.

## Cache, fila e concorrência

Só o cache de resultados existente é observado. A reutilização canônica aprovada pela validação de tamanho/mtime do MainWindow foi preservada. O contador legado do Caso registra toda reutilização; o CacheStats e seu hit rate contam apenas reutilizações de resultados completos. Resultados partial, failed, unavailable ou limit_exceeded reaproveitados permanecem parciais e não entram como cache completed válido. Miss significa ausência nesse conjunto, sem julgamento de falha. Lookup recebe duração real. Não se repetem timings históricos das engines para resultados reaproveitados.

Entries representa entradas elegíveis no início da execução, e não o tamanho de todos os caches do aplicativo. Evictions não existem como contador nesta implementação e permanecem null. Sem consultas, hit rate é null. Nenhum cache de parser ou persistente foi criado.

Jobs são execuções de análise de artefato, incluindo reutilização de cache. Não equivalem a threads ou processos de engine. QueueStats mede fila atual, pico da fila, execuções ativas, pico de concorrência e jobs concluídos, falhos, cancelados ou cancelados antes de iniciar. A UI usa nomenclatura de execuções, não inventa workers físicos.

## Correlação

O pipeline canônico mede duração total (incluindo fornecimento de candidatos e construção do grafo), construção de CaseEvidenceIndex, avaliação de regras e duração por regra. Fatos representam entidades canônicas do grafo efetivamente indexadas; ocorrências são a soma das ocorrências canônicas dessas entidades. Relações contam o grafo produzido. Não são estimativas da quantidade de texto ou candidatos descartados.

O perfil registra regras avaliadas, regras com findings, findings por regra e falhas, sem conteúdo dos findings. A tabela comum usa descrições de regras, com fallback neutro. Como não existe Developer Mode integrado à página, o export sanitizado substitui IDs internos de regra por referências estáveis pseudonimizadas.

## I/O e cobertura

Bytes lógicos do Caso são metadados dos arquivos selecionados. measured_engine_reads é a soma de comprimentos efetivamente retornados por read no HashEngine.calculate_all, preservada mesmo quando amostras detalhadas saem do buffer.

Outras engines, bibliotecas, processos externos, aquisição, releituras de verificação e escrita temporária não têm contadores confiáveis nesta V1. Não se usam tamanho do arquivo, suposições de leituras ou estimativas para preencher esses campos. temporary_bytes_written é null.

A interface diz “Leitura medida parcialmente”. measured_engine_reads / case_logical_bytes é somente a amplificação mínima observada pelas leituras instrumentadas, não amplificação física de disco nem total de I/O da aplicação. Nenhuma extrapolação é feita. O número de engines cobertas é fornecido junto ao total de engines observadas.

AVAILABLE, PARTIAL e UNAVAILABLE descrevem cobertura de medição. COMPLETED, PARTIAL, FAILED, CANCELLED e UNAVAILABLE descrevem resultados de execução; indisponibilidade não incrementa falhas. A cobertura global de profiling permanece parcial na V1, mesmo com uma sessão concluída. Resultado operacional parcial e cobertura parcial são conceitos distintos.

## Retenção e thread safety

A UI lê dataclasses congeladas e metadados em MappingProxyType, sem alterar o estado vivo. Um RLock protege atualizações e snapshot; referências de ContextVar são restauradas após cada chamada e sessão.

Limites padrão:

- uma sessão corrente; begin_case limpa métricas da sessão anterior, preservando health checks e o buffer operacional de erros;
- 2.000 amostras recentes de execução e 200 erros;
- até 128 IDs de engine, agregados por sessão;
- 128 durações recentes por engine para a mediana, com tamanho da amostra indicado;
- cinco execuções mais demoradas por engine;
- tabela de até dez artefatos, ordenados por duração e referência estável.

Contagem, wall acumulado, média, máximo, falhas, cancelamentos e bytes medidos não são truncados pela retenção de execuções. A mediana é de amostras recentes quando o limite é ultrapassado. Detalhes e ranking de artefatos derivam das execuções retidas, portanto podem ser parciais após descarte; a quantidade descartada é mostrada. Não há histórico persistente de sessões.

## Sanitização e export

O schema de diagnóstico é 1.1.0; performance_schema_version é 1.0.0. O export reutiliza a função local existente. Não envia dados pela rede.

O worker passa IDs curtos estáveis derivados de hash, nunca basename nem path absoluto. Campos de metadados aceitam apenas tamanho numérico e vocabulário operacional permitido. Mensagens livres de exceção são omitidas no armazenamento operacional e no export, pois regex não consegue garantir remoção de nomes pessoais. O export também omite display names livres de componentes e aplica sanitização defensiva a strings.

Não são transportados texto extraído, valores de evidência, valores de entidades, nomes de arquivos, coordenadas, CPF/CNPJ, IPs, e-mails, usuário do sistema ou hostname. As referências são pseudônimos, não uma garantia criptográfica de anonimato contra tentativa de adivinhar o identificador original.

O ambiente contém versão do FH, Python, Qt/PySide6, arquitetura, CPU, contagem lógica, memória quando disponível, espaço livre, Rust e dependências detectadas. Versões não detectáveis, memória indisponível no sistema e build_identifier sem informação publicada ficam null/indisponíveis. Não é executado git nem um subprocesso adicional para descobrir um build.

## UI e revisão

As seções são Visão geral, Performance, Engines, Jobs, Erros e Ambiente. Cards usam a largura efetiva do viewport; tabelas têm rolagem interna, ordenação numérica e tooltips. Detalhes de engine e artefato aparecem no mesmo painel. Estados operacionais OK/DEGRADED/UNAVAILABLE/ERROR continuam separados dos estados técnicos da evidência. Um snapshot com mais de cinco segundos desde generated_at é marcado explicitamente como obsoleto; seus valores continuam visíveis para diagnóstico.

Light usa superfícies claras e bordas discretas; Dark usa tons neutros e superfícies elevadas. Seleção/foco usam azul; cores semânticas ficam restritas a estados. As regras novas são escopadas ao Diagnóstico e reutilizam ThemeTokens.

scripts/review_diagnostics.py renderiza fixtures sintéticas em Qt offscreen: Light/Dark × 700/900/1200/1366, altura 768, com Visão geral, Performance, detalhe de engine, detalhe de artefato, Erros e Ambiente. Capturas e geometry.json ficam em .review_tmp/diagnostics, ignorados pelo Git. Os valores das fixtures não são benchmarks. Testes também cobrem sessão vazia, ativa, concluída e cancelada, nomes longos, valores grandes, seleção e export.

## Uso como baseline e próximos passos

1. Escolher um Caso de teste autorizado e representativo e manter o mesmo conjunto de arquivos, perfil, dependências e máquina.
2. Registrar explicitamente se o cache de resultados estava elegível.
3. Executar a análise e exportar o JSON sanitizado.
4. Comparar manualmente wall, TTFR, engines, artefatos, correlação, fila e cobertura entre execuções equivalentes.
5. Só então escolher uma otimização, medir novamente e verificar resultados técnicos idênticos.

O export permite preservar timestamp, versão, ambiente, bytes, quantidade de arquivos e medidas. Não importa dois datasets, não calcula reduções e não cria um benchmark automático.

Permanecem futuras: OCR condicional global, ExifTool persistente, cache de parser/persistente, tuning de workers, scheduler, leituras compartilhadas, mmap, batching, correlação canônica incremental, throttling de correlação legada, prefetch e warm startup. Sem baseline de Caso real, não há evidência para priorizar uma delas.

## Arquivos do patch

Criados: app/observability/profiling.py, tests/test_performance_profiling_v1.py, scripts/review_diagnostics.py, scripts/measure_profiling_overhead.py e este documento.

Modificados: .gitignore (exceção para este documento); app/observability/{__init__,models,service,sanitization,export}.py; app/engines/{file_analyzer,hash_engine}.py; app/services/{analysis_service,text_extraction_service}.py; app/workers/analysis_worker.py; app/correlation/v2/pipeline.py; app/ui/{main_window,theme}.py; app/pages/diagnostics_page.py; app/widgets/diagnostics.py; app/presentation/diagnostics_formatting.py; tests/test_diagnostics_observability.py; tests/test_diagnostics_ui_v2.py.

As quatro alterações preexistentes do Observatório em web/frontend foram preservadas. Frontend e Rust não foram alterados por esta tarefa.
