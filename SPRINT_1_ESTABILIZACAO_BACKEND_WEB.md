# Sprint 1 — estabilização do backend web

## Decisão arquitetural

A Sprint evolui `AnalysisJobExecutor` e a tabela `analysis_jobs` existentes. Não
foi criada fila paralela nem adicionados Redis, Celery ou broker. PostgreSQL
continua sendo a fonte do estado operacional e `AnalysisContract 1.0.0` continua
sendo a fonte oficial do resultado técnico.

O fluxo principal é:

```text
frontend -> POST /api/v1/analysis-jobs -> staging + AnalysisJob(queued)
         -> threads supervisoras -> claim SQL atômico -> processo isolado
         -> AnalysisCoordinator -> AnalysisContract -> presenter + PostgreSQL
         -> GET status/result
```

O `analysis_id` é criado antes do enqueue e coincide com `job_id`. O coordenador
aceita esse identificador opcionalmente; chamadas desktop que não o fornecem
continuam gerando seu próprio UUID.

## Estados

- `queued`: persistido e aguardando claim;
- `running`: claim exclusivo adquirido e processo em execução;
- `completed`: contrato final `completed`;
- `partial`: contrato utilizável com uma ou mais etapas parciais/falhas;
- `failed`: nenhuma resposta técnica válida, timeout, evidência rejeitada ou
  falha crítica.

Os códigos operacionais anteriores (`QUEUED`, `PROCESSING`, `SUCCESS`,
`PARTIAL`, `FAILED`, `LIMIT_EXCEEDED`, `CANCELLED`) foram preservados no campo
`status`. O campo `state` fornece a visão pública consolidada. Timestamps mínimos
e `current_stage` ficam no job; o resultado final conserva os timestamps do
contrato.

## Concorrência, capacidade e timeout

- `FORENSIHASH_ANALYSIS_CONCURRENCY`: processos simultâneos, padrão `1`, faixa
  `1..16`;
- `FORENSIHASH_ANALYSIS_QUEUE_CAPACITY`: jobs queued/running aceitos, padrão
  `20`, faixa `1..10000`;
- `FORENSIHASH_ANALYSIS_TIMEOUT_SECONDS`: prazo global, padrão `300`, faixa
  `1..86400`.

Cada thread supervisora reclama no máximo um job. O update condicional de
`QUEUED` para `PROCESSING` protege contra execução duplicada. A análise normal
roda em processo filho; timeout ou shutdown encerram esse processo antes da
remoção do staging. ExifTool, Tesseract e Poppler mantêm também seus timeouts
específicos.

A admissão executa recuperação de leases abandonados e conta exclusivamente
`QUEUED` e `PROCESSING` na mesma seção crítica. Em PostgreSQL, um advisory lock
transacional serializa `recovery -> count -> INSERT`; nos testes/SQLite, um lock
local equivalente evita ultrapassar o limite entre requisições concorrentes.
Estados terminais nunca consomem capacidade.

No restart de uma instância, jobs `PROCESSING` pertencentes ao token do executor
anterior são recuperados imediatamente. Se o staging ainda existe, retornam a
`QUEUED`; se foi perdido, terminam como `FAILED` com `staging_lost`. Durante a
vida do mesmo executor, heartbeat ausente ou anterior a 30 segundos aplica a
mesma política. Assim, um lease abandonado não bloqueia a fila indefinidamente.

## Falhas e logging

Falhas isoláveis de metadata, magic number, assinatura, PDF, JSON, biometria,
binário, texto e findings produzem `ProcessingIssue`/`StepResult`. O adaptador
oficial decide `partial` conforme as regras existentes. Aquisição, identidade da
evidência e hashing permanecem críticos.

Logs de job/etapa incluem, quando aplicável, `analysis_id`, `stage`, `engine`,
`status` e `duration_ms`. Conteúdo do arquivo, paths de staging, credenciais e
detalhes brutos de exceção não são registrados.

## Compatibilidade e limitações

`POST /api/v1/analyses` foi mantido e retirado do event loop com uma thread, mas
continua sendo uma chamada longa e não possui o isolamento/timeout global do
job. Clientes novos devem usar o fluxo de polling.

A solução suporta uma instância Uvicorn. Vários processos/instâncias exigem
lease distribuído, armazenamento temporário compartilhado e coordenação da
recuperação. O filesystem local continua efêmero. A capacidade da fila é uma
proteção global do backend e o workspace do navegador exibe apenas seus itens
locais; rejeições registram contagens globais seguras nos logs. Engines sem callback de
progresso não atualizam `current_stage` durante sua execução; sua duração e
estado ficam disponíveis nos logs e no contrato após retorno.
