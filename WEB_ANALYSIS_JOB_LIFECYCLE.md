# Lifecycle Web de AnalysisJob

## Invariante

Um `UploadItem` selecionado uma vez pode criar no máximo um `AnalysisJob`. Uma nova criação só é permitida por uma nova seleção ou por retry manual explícito.

A identidade do item é `clientUploadId`. Ela é criada uma vez para cada `File` aceito e não depende de nome, hash, índice do array, `jobId` ou `analysisId`. Arquivos distintos com conteúdo idêntico continuam sendo uploads distintos.

## Causa raiz corrigida

O executor frontend usava o mesmo status `QUEUED` para dois estados diferentes: arquivo local ainda não submetido e job remoto já criado e enfileirado. Após o `POST /analysis-jobs`, a resposta colocava o item novamente em `QUEUED`. O bloco `finally` removia o item da coleção transitória `running` e forçava nova atualização do workspace. O effect da fila selecionava qualquer item `QUEUED` que não estivesse em `running`, sem verificar `jobId`, e fazia outro POST.

Cada nova resposta sobrescrevia o `jobId` da mesma entrada. Pollers dos jobs anteriores continuavam autorizados a atualizar essa entrada. Assim, um poller antigo podia marcá-la como terminal enquanto o `jobId` corrente ainda estava `QUEUED` ou `PROCESSING`. A criação automática de Analysis Set usava o `jobId` corrente com o status terminal obsoleto e recebia `409 analysis_set_not_ready`. A falha removia a trava do set, permitindo novas tentativas em atualizações posteriores. Os jobs repetidos consumiam a capacidade real do backend até o guard responder `429 analysis_capacity_reached`.

## Lifecycle corrigido

Submissão e estado operacional do job são independentes:

```text
SELECTED -> SUBMITTING -> SUBMITTED
                     \-> FAILED --retry manual--> SELECTED

QUEUED -> PROCESSING -> SUCCESS | PARTIAL | FAILED | LIMIT_EXCEEDED | CANCELLED
```

Antes do request, o frontend reivindica sincronamente o `clientUploadId` e inicia a transição para `SUBMITTING`. O effect só seleciona itens com `submissionState === SELECTED`, sem `jobId` e sem reivindicação ativa. Ao receber um `jobId`, o item passa para `SUBMITTED`; o status remoto `QUEUED` não o torna novamente submetível.

## Polling

Polling recebe apenas `clientUploadId` e `jobId` já existentes. Ele nunca chama a função de submissão. Existe no máximo um poller por `jobId`.

Uma resposta só pode atualizar o item quando ambos `clientUploadId` e `jobId` ainda coincidem. Respostas obsoletas não alteram a entrada. Estados terminais encerram o poller; unmount e fechamento da aba abortam o request e limpam o timer.

## Analysis Set

O conjunto só é elegível quando todos os itens possuem `jobId` e status terminal. A identidade lógica da tentativa é a lista ordenada de `jobId`s. Cada identidade possui no máximo uma tentativa automática, registrada antes do POST.

O `set_id` recebido é armazenado imediatamente junto do resultado. Falhas, inclusive `409`, não devolvem automaticamente o conjunto ao estado elegível e não geram loop. O contrato atual do backend para `409 analysis_set_not_ready` não fornece um `set_id` recuperável; portanto a resposta é tratada como falha terminal da tentativa automática.

## 429 e retry

`429 analysis_capacity_reached` deixa o upload em estado local `FAILED`, preserva sua identidade e exibe a mensagem segura do backend. Não há retry automático. O botão **Tentar novamente** é a única transição que remove o `jobId` (quando houver), limpa o erro e recoloca o item em `SELECTED` para uma nova tentativa explícita.

## Sessão e restauração

O workspace continua intencionalmente apenas em memória. `File` não é serializado em `localStorage` ou `sessionStorage`, e dados arbitrários nesses storages não são usados para submissão. Após refresh, o frontend não recria nem reenvia uploads automaticamente. Resultados autorizados permanecem recuperáveis pelo histórico do backend; o arquivo original precisa ser selecionado novamente para uma nova análise explícita.

Essa limitação evita tratar um job restaurado como arquivo pendente e mantém a política existente de não persistir dados da sessão no navegador.

## Fronteira backend

O endpoint de criação permanece não idempotente por contrato: cada POST válido cria um job. A causa atual era exclusivamente o lifecycle frontend, portanto não foram adicionados `Idempotency-Key`, mudanças de capacidade, retries de infraestrutura nem alterações nos engines.
