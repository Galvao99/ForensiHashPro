# Staging do ForensiHash Web no Render

Este documento prepara o primeiro beta interno. Ele não autoriza produção e
nenhum recurso é criado automaticamente apenas por manter `render.yaml` no
repositório.

## Arquitetura

```text
Internet
  +-- Render Static Site (React/Vite)
  |     +-- HTTPS -> Render Web Service
  +-- Render Web Service (Docker/FastAPI)
        +-- rede interna -> Render PostgreSQL
        +-- ForensiHash Core e ferramentas nativas
```

O backend é construído pelo Render a partir do Dockerfile da raiz. Essa opção
foi escolhida para o primeiro staging porque permite **After CI Checks Pass** e
não exige credencial para ler o package privado no GHCR. A imagem
`ghcr.io/<owner>/forensihashpro-api:staging` continua sendo publicada, mas não é
a fonte do deploy inicial. Um serviço Render baseado em imagem exigiria uma
credencial GHCR com `read:packages` e atualização manual ou automação adicional.

## Criação manual pelo Blueprint

1. No Render Dashboard, escolha **New > Blueprint** e conecte este repositório.
2. Selecione a branch `main` e o arquivo `render.yaml`.
3. Revise os três recursos antes de confirmar. Todos estão declarados como
   `free`; não selecione upgrade ou recurso pago sem decisão explícita.
4. Informe `FORENSIHASH_ALLOWED_ORIGINS` com a origin HTTPS exata do Static
   Site, sem barra final, por exemplo
   `https://forensihash-staging-web.onrender.com`.
5. Informe `VITE_API_BASE_URL` com a URL HTTPS exata da API, por exemplo
   `https://forensihash-staging-api.onrender.com`.
6. Confirme que ambos os serviços mostram **After CI Checks Pass**. O Render
   deverá aguardar os checks do GitHub Actions associados ao commit da `main`.
7. Crie os recursos manualmente e acompanhe os logs do primeiro build.

Os nomes `onrender.com` podem receber ajuste se já estiverem ocupados. Nesse
caso, use as URLs efetivamente atribuídas nas duas variáveis acima e faça novo
deploy do frontend após ajustar `VITE_API_BASE_URL`.

## Backend, porta, health e migrations

O container executa:

```text
python -m alembic upgrade head
exec python -m uvicorn web.backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Uma migration com falha impede a inicialização da API. Essa estratégia é
aceitável enquanto staging tiver uma única instância. Antes de escalar, separe
migrations do startup ou adote exclusão que impeça execuções concorrentes.

O health check é `GET /health`. Ele é rápido, não consulta documentos ou
integrações e não expõe configuração. `/docs`, `/redoc` e `/openapi.json`
permanecem disponíveis no beta interno; a política de produção será decidida
separadamente.

## PostgreSQL

`FORENSIHASH_DATABASE_URL` recebe `connectionString` do banco pelo Blueprint.
O código também aceita `DATABASE_URL` e converte URLs `postgres://` ou
`postgresql://` para o driver Psycopg 3. O PostgreSQL não roda no container da
API e nenhuma migration é criada automaticamente.

O Blueprint bloqueia conexões públicas ao banco. O Compose local continua
usando o hostname `postgres`, e a execução local fora do Docker mantém o
fallback `localhost`.

## Variáveis

Backend:

```text
FORENSIHASH_ENV=staging
FORENSIHASH_DATABASE_URL=<Render internal connection string>
FORENSIHASH_DATABASE_CONNECT_TIMEOUT=5
FORENSIHASH_SESSION_SECRET=<gerado pelo Render; mínimo 32 caracteres>
FORENSIHASH_COOKIE_SECURE=true
FORENSIHASH_COOKIE_SAMESITE=none
FORENSIHASH_ALLOWED_ORIGINS=https://<frontend>.onrender.com
FORENSIHASH_REGISTRATION_ENABLED=false
FORENSIHASH_JOB_WORKER_ENABLED=true
FORENSIHASH_ANALYSIS_CONCURRENCY=1
FORENSIHASH_ANALYSIS_QUEUE_CAPACITY=20
FORENSIHASH_ANALYSIS_TIMEOUT_SECONDS=300
FORENSIHASH_TEMP_DIR=/tmp/forensihash
IP2LOCATION_ENABLED=false
PORT=<fornecido pelo Render>
```

Frontend, no momento do build:

```text
VITE_API_BASE_URL=https://<api>.onrender.com
VITE_API_TIMEOUT_MS=15000
VITE_JOB_UPLOAD_TIMEOUT_MS=60000
VITE_REGISTRATION_ENABLED=false
```

Variáveis `VITE_*` são públicas. Não coloque senha, session secret, URL de banco
ou API key no frontend.

## CORS, cookies e CSRF

A API aceita somente origins listadas em `FORENSIHASH_ALLOWED_ORIGINS`, com
credentials habilitadas; wildcard é rejeitado. Em staging, origins precisam
usar HTTPS.

O cookie de sessão é host-only, `HttpOnly`, `Secure`, `Path=/` e expira em oito
horas. `onrender.com` consta na Public Suffix List, portanto frontend e API em
subdomínios distintos são cross-site. O Blueprint usa `SameSite=None`, que o
backend só aceita com Secure, e o frontend usa `credentials: include`. Alguns
navegadores ou políticas corporativas podem bloquear cookies de terceiros; o
smoke de login deve confirmar o navegador-alvo. Um domínio próprio que coloque
frontend e API no mesmo site elimina essa dependência futura, mas não faz parte
desta fase. O cookie CSRF continua legível pelo navegador conforme o desenho
atual, e operações mutáveis autenticadas continuam exigindo `X-CSRF-Token`.

## Cadastro e primeiro ADMIN

Com `FORENSIHASH_REGISTRATION_ENABLED=false`, a API rejeita cadastro público
com erro seguro e o frontend apresenta **Acesso restrito**. Login e gestão
administrativa continuam disponíveis. Não existe endpoint HTTP de bootstrap.

Depois de aplicar as migrations, crie o primeiro administrador explicitamente:

```text
python -m web.backend.cli create-admin
```

A ferramenta solicita nome, e-mail e senha; a senha não é argumento nem é
exibida. Ela usa o mesmo Argon2id, validação e configuração de banco da API e
recusa duplicidade. O plano gratuito não oferece Render Shell. Para executar a
CLI de uma máquina confiável, autorize temporariamente apenas o IP do operador
nas regras externas do banco, exporte `FORENSIHASH_DATABASE_URL`, execute a CLI
e restaure imediatamente `ipAllowList: []`. A alternativa é usar Shell/one-off
job de um plano que ofereça o recurso; nenhum upgrade é feito pelo repositório.

## Uploads e retenção

Uploads criam `AnalysisJob` persistente no PostgreSQL e usam um staging local
temporário até o worker interno concluir. O staging gratuito mantém concorrência
1. Cada job roda em processo isolado, tem timeout global de 300 segundos,
reutiliza o pipeline forense normal e sempre tenta remover o staging ao finalizar. Arquivos
brutos não são gravados no PostgreSQL. Se um restart perder o staging, o job
termina com `staging_lost`, sem expor o path interno.

`PRIVATE` permanece o padrão: o resultado sanitizado fica temporariamente no
job por uma hora para permitir polling e é excluído logicamente ao expirar; ele
não entra no histórico. `RESULT_ONLY` persiste somente o resultado sanitizado
na tabela de análises. `FILE_AND_RESULT` continua recusado.

Esta fila V1 pressupõe uma única instância. O filesystem do Render é efêmero,
cold starts interrompem trabalho em curso e escala horizontal ainda exigirá um
worker/queue dedicado com leasing distribuído. PostgreSQL é a fonte de verdade
do estado operacional, mas não substitui armazenamento temporário do arquivo.

## Smoke tests

Use somente uma fixture sintética e não sensível:

- `GET <api>/health` retorna 200;
- `GET <api>/api/v1/capabilities` retorna 200 e reflete ExifTool, Tesseract,
  Poppler e Rust detectados no container;
- `GET <frontend>/` retorna 200;
- atualizar `<frontend>/login` retorna a aplicação, não 404;
- cadastro público retorna `registration_disabled`;
- login retorna 200 e estabelece sessão Secure/HttpOnly;
- `GET /api/v1/auth/me` retorna 200 após login;
- upload pequeno retorna 202, o job progride até estado terminal e seu endpoint
  de resultado retorna `AnalysisContract` 1.0.0;
- SHA-256 do contrato coincide com o SHA-256 calculado localmente;
- sessão `PRIVATE` não cria item no histórico;
- opção `RESULT_ONLY` cria item no histórico;
- logout com CSRF retorna 204 e revoga a sessão.

## Rollback

Como o primeiro staging é Git-backed, use **Rollback** no histórico do Render
ou faça deploy manual do commit anterior. Não execute downgrade automático do
Alembic. Antes do rollback, confirme que a versão anterior da aplicação é
compatível com o schema atual. Se futuramente o serviço consumir GHCR, fixe uma
tag SHA anterior em vez de `staging`.

## Troubleshooting

- API não inicia: confira logs da migration e presença de
  `FORENSIHASH_DATABASE_URL`.
- Erro de configuração: confira secret com 32+ caracteres, origin HTTPS e
  cookie Secure.
- CORS/cookie: confira as origins exatas, sem path ou barra final, e a URL usada
  em `VITE_API_BASE_URL`.
- Rotas frontend retornam 404: confirme o rewrite `/* -> /index.html`.
- Capacidade indisponível: consulte `/api/v1/capabilities` e logs de build; não
  hardcode o estado das ferramentas.

## Custos e limites

Static Site, Web Service e PostgreSQL estão declarados como `free`. O serviço
web gratuito pode dormir após inatividade e perder arquivos locais; isso é
compatível apenas porque uploads são temporários. O PostgreSQL gratuito expira
em 30 dias, não possui backups e precisa ser recriado ou promovido para manter
o staging. Shell, one-off jobs, instâncias permanentes, backups e maior
capacidade podem exigir plano pago. Revise o Dashboard antes de confirmar.
