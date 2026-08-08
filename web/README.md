# ForensiHash Web

Esta pasta contém os adaptadores web do ForensiHash Pro no mesmo repositório do
desktop. O backend reutiliza `ApplicationFactory.create_analysis_coordinator()`
e não chama engines ou `FileAnalyzer` diretamente.

## Estrutura

- `backend/app`: aplicação FastAPI, rotas, schemas HTTP mínimos e adapter;
- `backend/tests`: testes do backend;
- `frontend`: reservado para uma fase futura, sem React nesta etapa.

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
`IP2LOCATION_ENABLED` e `IP2LOCATION_API_KEY`. Segredos devem ser fornecidos
somente em runtime; arquivos `.env` não entram no contexto da imagem.

## Endpoints

- `GET /health`: estado do serviço;
- `GET /api/v1/capabilities`: módulos e integrações disponíveis no ambiente,
  sem paths ou configuração sensível;
- `POST /api/v1/analyses`: recebe um arquivo no campo multipart `file`, executa
  uma análise individual síncrona e retorna o `AnalysisContract 1.0.0`.

O resultado de análise mantém o formato do contrato central, sem criar um DTO
paralelo. Seções opcionais usam `null` quando não foram executadas, enquanto
`processing_steps` registra `success`, `no_findings`, `partial`, `skipped`,
`unavailable`, `failed`, `cancelled` ou `limit_exceeded`, conforme aplicável.

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

## Limitações atuais

A execução é local e síncrona. Não há frontend, autenticação, persistência,
fila, polling, comparação web, correlação web ou deploy. O healthcheck confirma
somente que a API está viva; ele não valida integrações externas. A imagem não
é uma configuração de produção nem substitui sandbox para arquivos hostis.
Timeline, IP automático, comparação e correlação não integram o contrato
individual normal. Não há persistência nem consulta posterior por ID.
