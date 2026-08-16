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

## Browser staging regression — multiple POSTs after first fix

### Evidência e auditoria

Após a primeira correção, um teste manual em staging registrou vários `POST /api/v1/analysis-jobs` com `202` para uma única seleção. A auditoria subsequente verificou o artefato público servido pelo Render (`index-D-5onzCO.js`) e confirmou que ele continha `clientUploadId`, `submissionState`, `SUBMITTING` e a barreira baseada em `jobId`. Portanto, o incidente não foi atribuído apenas a um bundle anterior.

A árvore real possui uma única declaração de `AnalysisSessionProvider`, na rota pai autenticada `/app`. Não existem providers em `main`, `AppShell`, `ResultPage`, dashboard ou workspace; não existem `key={pathname}`, `key={analysisId}` ou `key={location.key}` acima dele. Navegação entre `/app/analysis`, `/app/result` e `/app` preserva a mesma instância. Um refresh desmonta o provider, mas também perde o `File`, e não há restauração automática capaz de reenviá-lo.

Há um único call site de criação: `AnalysisSessionContext -> createAnalysisJob`. O API client usa `fetch` diretamente, sem interceptor ou retry. Não existem React Query, service worker, PWA, offline replay ou background sync.

### Lacuna adicional encontrada

A primeira barreira possuía uma reivindicação temporária (`submissionClaims`) apagada no `finally`. Depois disso, a proteção dependia de o snapshot React consultado já conter `SUBMITTED` ou `jobId`. Essa dependência foi removida: `submittedUploadIds` é agora monotônico durante a vida do provider e só libera o ID em retry manual explícito.

Toda criação passa pela função autoritativa `submitUpload(clientUploadId, source, reason)`. Ela resolve o item atual pelo ID no `workspaceRef`; não aceita mais um objeto `UploadItem` potencialmente obsoleto capturado por effect. Antes do request, registra permanentemente o upload como submetido.

Essa fragilidade era real, mas o teste automatizado do App completo não reproduziu os múltiplos POSTs observados no navegador antes da nova barreira. Sem o log diagnóstico da sessão original, ela não é apresentada como prova retrospectiva de que todos os POSTs de staging vieram desse intervalo.

### Instrumentação de staging

Com `VITE_ANALYSIS_DIAGNOSTICS=true`, o console registra eventos `[analysis-lifecycle]` sem conteúdo, hash, path, token ou payload:

- `provider.mounted` / `provider.unmounted`;
- `upload.created`;
- `submit.attempt` / `submit.claimed` / `submit.blocked`;
- `upload.transition`;
- `job.created`;
- `poller.created` / `poller.disposed`.

Cada registro inclui `buildId`, `providerInstanceId`, `submissionAttemptId`, `clientUploadId`, filename, estado, `jobId`, source, reason e timestamp. O `buildId` usa `RENDER_GIT_COMMIT` durante o build. Isso permite distinguir provider duplicado, novo UploadItem, tentativa obsoleta, retry manual e cache/deploy divergente.

O HTML recebe `Cache-Control: no-cache`; assets com nome content-hashed recebem cache imutável. Assim o navegador revalida o documento e continua reutilizando com segurança bundles cujo nome muda quando o conteúdo muda.

### Teste App completo

O teste `app-analysis-job-browser-regression.test.tsx` renderiza `<StrictMode><App /></StrictMode>` e inclui BrowserRouter, AuthProvider, ThemeProvider, ProtectedRoute, AnalysisSessionProvider, AppShell, AnalysisPage e ResultPage. Ele executa:

```text
seleção de contrato.pdf
-> POST 202
-> GET PROCESSING
-> GET SUCCESS
-> GET result
-> POST Analysis Set
-> rota Overview
-> retorno à rota de análise
-> unmount/remount completo
```

Asserções: um upload ID, um POST de job, um job ID, um poller, um POST de set e nenhum reenvio após rotas ou remount.

### Validação manual após deploy

1. Abra DevTools, aba **Console**, e confirme eventos `[analysis-lifecycle]` com o `buildId` esperado.
2. Na aba **Network**, marque **Preserve log** e filtre por `analysis-jobs`.
3. Selecione um único arquivo sintético.
4. Na coluna **Method**, deve existir exatamente um `POST` para a URL terminada em `/analysis-jobs`, com status `202`.
5. As linhas posteriores devem ter método `GET` e URL terminada no mesmo `jobId`. `POST` cria; `GET` apenas consulta.
6. Se houver outro POST, copie os eventos `submit.attempt`, `submit.claimed`, `job.created`, `provider.mounted` e `upload.created` correspondentes. IDs iguais indicam repetição do mesmo lifecycle; IDs de provider ou upload diferentes indicam criação em outra instância/origem.

## Fila controlada para múltiplos arquivos e pastas

Seleção e processamento são fases separadas. Todos os arquivos aceitos são inseridos imediatamente no workspace com estado local `WAITING`, mas `MAX_ACTIVE_ANALYSES = 1` limita o workspace Web a um job remoto não terminal.

O slot não é liberado quando o POST retorna `202`. A resposta apenas muda o item para `QUEUED`, que significa que o job já existe e aguarda o executor remoto. O próximo item só avança quando o item corrente chega a `SUCCESS`, `PARTIAL`, `FAILED`, `LIMIT_EXCEEDED` ou `CANCELLED`.

```text
WAITING (fila local, sem jobId)
  -> UPLOADING (submissão reivindicada)
  -> QUEUED (job remoto criado)
  -> PROCESSING
  -> SUCCESS | PARTIAL | FAILED | LIMIT_EXCEEDED | CANCELLED
```

Uma falha terminal libera o slot para o próximo artefato. A barreira monotônica por `clientUploadId` continua aplicada; a fila apenas decide quando chamar o caminho único `submitUpload`.

O backend atual informa estado operacional e `current_stage`, mas não fornece percentual de progresso por engine nem capacidade segura específica do workspace. Por isso:

- o progresso do conjunto é a razão real entre itens terminais e total de itens;
- a etapa atual exibe apenas `current_stage` ou uma descrição derivada do estado;
- não é exibido percentual inventado para o arquivo ativo;
- a capacidade global do backend continua sendo autoridade e pode responder `429`.

O Analysis Set permanece inelegível até todos os itens possuírem `jobId` e estarem terminais. Assim, a fila de uploads não dispara correlação parcial durante o processamento da pasta.

## Refinamento do Analysis Workspace

### Polling adaptativo

O polling anterior usava intervalo fixo de 2,5 segundos. Como a primeira consulta é imediata, uma análise de aproximadamente 10 segundos produzia em torno de cinco GETs de status. O intervalo continua moderado durante processamento, mas jobs aguardando executor agora são consultados com menor frequência:

```text
QUEUED remoto: 4.000 ms
PROCESSING:     2.500 ms
TERMINAL:       encerramento imediato
```

Uma análise de 10 segundos inteiramente em `PROCESSING` continua produzindo aproximadamente cinco consultas, incluindo a inicial. Se permanecer `QUEUED` durante os 10 segundos, produz aproximadamente quatro. Erros transitórios de rede usam 2,5 segundos; nenhum POST é repetido.

### Processing View

A tela do conjunto mostra apenas dados derivados do workspace ou retornados pelo backend: artefatos terminais, item ativo, fila local, tipo detectado ou extensão, tamanho, `current_stage`, tempo decorrido desde `started_at` e duração final do contrato. Não existe percentual por arquivo porque o contrato não fornece progresso granular por engine.

### Overview

O Overview autenticado representa o workspace corrente, não uma lista truncada de resultados recentes. Ele inclui itens `WAITING`, jobs remotos, processamento e terminais, mantendo `clientUploadId` como identidade da linha. O histórico autorizado continua separado na página Histórico e nunca alimenta a fila.

### Identidade visual interna

O shell autenticado utiliza os assets existentes `forensihash_logo_preto.png` no tema claro e `forensihash_logo_branco.png` no tema escuro. Os arquivos não foram renomeados nem recriados. A identidade pública ARQEN permanece inalterada.
# Perfis de execução

Cada job persiste `analysis_profile`, resolvido server-side a partir do usuário no momento da admissão. O worker usa esse snapshot no processo isolado. Jobs Free não inicializam OCR e registram etapas Pro como `skipped/capability_not_enabled`. O navegador nunca concede Pro enviando um campo no upload. Consulte `FORENSIHASH_ANALYSIS_PROFILES.md`.
