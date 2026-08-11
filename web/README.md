# ForensiHash Web

Esta pasta contém os adaptadores web do ForensiHash Pro no mesmo repositório do
desktop. O backend reutiliza `ApplicationFactory.create_analysis_coordinator()`
e não chama engines ou `FileAnalyzer` diretamente.

## Estrutura

- `backend/app`: aplicação FastAPI, rotas, schemas HTTP mínimos e adapter;
- `backend/tests`: testes do backend;
- `frontend`: aplicação React/TypeScript com site institucional, app shell e
  consumo da API local.

## Instalação

No ambiente Python 3.12 do projeto:

```text
python -m pip install -r requirements.txt
```

Para executar somente o núcleo headless e a API, sem Qt:

```text
python -m pip install -r requirements-web.txt
```

## Execução local

A partir da raiz do repositório:

```text
python -m uvicorn web.backend.app.main:app --reload
```

Em outro terminal, inicie o frontend:

```text
cd web/frontend
npm install
npm run dev
```

O servidor Vite encaminha `/api` e `/health` ao backend local. Para apontar
para outro endereço, use `VITE_API_BASE_URL`; nenhuma variável do frontend
deve conter segredo.

## Docker

A imagem usa Linux Debian, Python 3.12, usuário não-root e inclui ExifTool,
Tesseract com idioma português, Poppler e a extensão Rust compilada em um stage
separado.

```text
docker build -t forensihash-api .
docker run --rm -p 8000:8000 forensihash-api
```

Também é possível executar o serviço local único com:

```text
docker compose up --build
```

A imagem normal inicia Uvicorn sem `--reload`. Para validar as dependências
nativas e a seleção de testes core/web durante o build:

```text
docker build --target test -t forensihash-api-test .
```

Variáveis aceitas em runtime incluem `FORENSIHASH_TEMP_DIR`,
`FORENSIHASH_CONFIG_DIR`, `FORENSIHASH_EXIFTOOL_PATH`,
`FORENSIHASH_TESSERACT_PATH`, `FORENSIHASH_POPPLER_PATH`,
`FORENSIHASH_ANALYSIS_CONCURRENCY`, `FORENSIHASH_ANALYSIS_QUEUE_CAPACITY`,
`FORENSIHASH_ANALYSIS_TIMEOUT_SECONDS`,
`IP2LOCATION_ENABLED` e `IP2LOCATION_API_KEY`. Segredos devem ser fornecidos
somente em runtime; arquivos `.env` não entram no contexto da imagem.

## Endpoints

- `GET /health`: estado do serviço;
- `GET /api/v1/capabilities`: módulos e integrações disponíveis no ambiente,
  sem paths ou configuração sensível;
- `POST /api/v1/analysis-jobs`: cria `analysis_id`/`job_id`, persiste o estado
  inicial e retorna `202` sem aguardar as engines;
- `GET /api/v1/analysis-jobs/{analysis_id}`: retorna estado, timestamps,
  estágio e erro seguro;
- `GET /api/v1/analysis-jobs/{analysis_id}/result`: retorna o
  `AnalysisContract 1.0.0` quando disponível;
- `POST /api/v1/analysis-sets`: correlaciona de 1 a 50 jobs terminais do mesmo
  usuário sem reabrir arquivos ou reexecutar engines;
- `GET /api/v1/analysis-sets/{set_id}`: retorna o resultado separado de
  correlação enquanto sua retenção temporária estiver válida;
- `POST /api/v1/analyses`: endpoint legado compatível; ainda aguarda o
  resultado, mas retira o processamento síncrono do event loop.
- `POST /api/v1/auth/register`, `login` e `logout`: conta e sessão por cookie
  HttpOnly;
- `GET/PATCH /api/v1/auth/me`: perfil e preferências do usuário autenticado;
- `GET /api/v1/analyses/history`: resultados cuja retenção foi autorizada;
- `GET/PATCH /api/v1/admin/users`: gestão restrita a administradores.

O resultado de análise mantém o formato do contrato central, sem criar um DTO
paralelo. Seções opcionais usam `null` quando não foram executadas, enquanto
`processing_steps` registra `success`, `no_findings`, `partial`, `skipped`,
`unavailable`, `failed`, `cancelled` ou `limit_exceeded`, conforme aplicável.

Entidades resolvidas na Sprint 2 são expostas como facts técnicos com valor
bruto, normalização, confidence determinística e proveniência. A API não expõe
o path local da fonte; cada ocorrência referencia a evidência do contrato. Não
há conclusão automática sobre fraude, autoria ou autenticidade.

Erros HTTP usam o envelope:

```json
{
  "error": {
    "code": "error_code",
    "message": "Mensagem segura.",
    "request_id": "identificador"
  }
}
```

## Apresentação e sanitização

O `AnalysisContract` permanece a fonte interna de verdade. Antes da resposta,
um presenter web remove recursivamente paths locais, diretórios temporários,
paths de ferramentas, segredos, detalhes de exceção, payloads brutos e bytes
binários. Hashes, metadados técnicos, estrutura, assinaturas, texto, findings,
limitações e estados de processamento são preservados.

O nome apresentado é somente o basename informativo e sanitizado enviado pelo
cliente. Ele nunca é usado para criar o arquivo de staging.

## Upload e limites

O upload recebe nome interno aleatório em um diretório exclusivo sob a pasta
temporária do sistema. Uma extensão curta e segura pode ser preservada apenas
como tipo declarado; o tipo real continua sendo determinado pelo núcleo. O
limite deriva de `ProcessingLimits.max_file_size_bytes`. O arquivo transitório
é removido após sucesso ou falha, e o núcleo ainda realiza sua própria aquisição
por `EvidenceManager`.

O SHA-256 é calculado durante o staging e comparado com a identidade adquirida
pelo `EvidenceManager`, com o hash produzido pela análise e com o arquivo após
o processamento. Qualquer divergência interrompe a resposta válida. As engines
recebem somente a cópia read-only adquirida; derivados devem usar o diretório
`derived` do lease.

Datas de criação/acesso/modificação do staging e da cópia são metadados do
filesystem operacional e podem diferir. Isso não significa alteração dos
metadados internos do documento, que permanecem nos bytes imutáveis da
evidência e são extraídos por ferramentas em modo de leitura.

## Contas, privacidade e persistência

O backend usa PostgreSQL, SQLAlchemy 2 e migrações Alembic. Senhas recebem hash
Argon2id e a autenticação utiliza sessão assinada em cookie HttpOnly, com CSRF
nas operações mutáveis. `PRIVATE` é o padrão e não persiste o contrato;
`RESULT_ONLY` guarda somente o resultado HTTP sanitizado em JSONB.
`FILE_AND_RESULT` está modelado, porém recusado enquanto não houver object
storage: arquivos originais não são persistidos no PostgreSQL nem no filesystem.

Configure `FORENSIHASH_DATABASE_URL`, `FORENSIHASH_SESSION_SECRET` e
`FORENSIHASH_COOKIE_SECURE` por ambiente. Execute `python -m alembic upgrade
head` antes da API; o Compose faz isso automaticamente após o PostgreSQL ficar
saudável.

Uma assistente futura deverá consumir resultados estruturados, nunca substituir
engines, modificar findings ou recalcular severidade. Ela deverá citar os campos
que fundamentam interpretações e não poderá enviar documentos a serviços
externos sem consentimento explícito. Nenhuma IA foi implementada nesta fase.

## Execução e estados

O worker interno usa PostgreSQL para claim atômico e estado operacional. Threads
supervisoras limitam a concorrência; cada job padrão roda em processo filho
isolado. Se o timeout global expirar, o processo é encerrado antes do cleanup.
Os estados públicos são `queued`, `running`, `completed`, `partial` e `failed`;
os códigos operacionais legados em maiúsculas permanecem por compatibilidade.
`AnalysisContract.state` continua sendo a fonte oficial do estado final.

Os padrões são concorrência 1, capacidade 20 e timeout 300 segundos. Os valores
são configuráveis pelas três variáveis `FORENSIHASH_ANALYSIS_*` listadas acima.

## Limitações atuais

A fila interna pressupõe uma única instância. Não há fila distribuída,
comparação web, correlação web ou object storage. Exportação de dados e exclusão de conta são fluxos
futuros explicitamente indicados na interface. O healthcheck confirma
somente que a API está viva; ele não valida integrações externas. A imagem não
é uma configuração de produção nem substitui sandbox para arquivos hostis.
Timeline, IP automático, comparação e correlação não integram o contrato
individual normal.

Correlation V2 é exposta como `AnalysisSetResult` separado. O workspace cria o
set após os jobs terminais e apresenta correlações explicáveis com proveniência.
Resultados de set expiram após uma hora; não constituem storage de caso ou
escala distribuída.

Engines sem callback incremental só aparecem individualmente nos logs e em
`processing_steps` depois de retornarem. A capacidade é protegida no processo
da API; escala horizontal exige lease distribuído. O endpoint legado
`/analyses` não recebe o isolamento global do job e deve migrar para polling.

## Integração contínua

O GitHub Actions executa a cada pull request e em pushes para `main`,
`feature/**` e `fix/**`. O workflow valida a suíte Python 3.12 com PostgreSQL e
migrations, compila e verifica o backend, e executa testes, lint e build do
frontend com Node.js. Um job separado constrói a imagem Docker runtime completa,
incluindo a extensão Rust e as ferramentas forenses nativas.

As dependências exclusivas da suíte Python ficam em `requirements-test.txt`.
No runner Linux, o Qt usa a plataforma `offscreen`, sem depender de display real.

O CI não publica imagens e não executa staging, CD ou deploy.

## Imagem de staging no GHCR

Depois que o workflow `CI` aprova um push na `main`, um workflow separado
publica somente a imagem da API em:

```text
ghcr.io/<owner>/forensihashpro-api:staging
ghcr.io/<owner>/forensihashpro-api:<commit-sha>
```

A tag `staging` aponta para a publicação mais recente da `main` aprovada. A tag
com SHA identifica uma imagem imutável e permite selecionar exatamente uma
revisão anterior. Após o primeiro push, o pacote aparecerá em **GitHub →
Packages**, onde visibilidade e acesso podem ser revisados manualmente.

Essa publicação não realiza deploy e não inclui o build do frontend.
# Timeline Web V2

Resultados individuais exibem `AnalysisContract.timeline`; resultados de Analysis
Set podem incluir `timeline_result` agregado. A construção ocorre no job individual
e não reexecuta engines. O frontend oferece filtros por arquivo, categoria e tipo,
mantendo warnings separados de eventos.
# Archive Inspection

ZIPs identificados por conteúdo recebem inspeção estática no job existente. O
frontend lê `technical_structure.archive`, mostra resumo, flags e árvore expandível.
Entries não são abertas nem executadas no navegador. Limites são configurados pelas
variáveis `FORENSIHASH_ARCHIVE_*` documentadas no arquivo de Sprint 5.
