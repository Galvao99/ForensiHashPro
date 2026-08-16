# Auditoria estrutural do backend — 2026-08-16

## Escopo e método

Auditoria estática e dinâmica de `app/` e `web/backend/`, com verificação cruzada em testes, factories, registries, entrypoints, migrations, imports diretos, imports dinâmicos e profiles FREE/PRO. Frontend e Desktop UI foram considerados apenas como consumidores; não são alvo de correção.

O inventário foi produzido com `rg`, AST da biblioteca padrão, Ruff e leitura dos fluxos. Candidatos sem import direto não foram classificados automaticamente como mortos: migrations, entrypoints, reexports e módulos carregados por `importlib` foram tratados separadamente.

## Inventário

- 294 arquivos Python em `app/` + `web/backend/`.
- 375 classes.
- 1.398 funções/métodos: 219 funções de módulo e 1.179 métodos.
- 57 arquivos de teste backend/compartilhados (`tests/` e `web/backend/tests/`, descontando sobreposição).
- 18 módulos sob `app/engines` (incluindo package marker e evaluators).
- 21 módulos de serviços: 14 compartilhados e 7 Web.
- 14 módulos de parser nas famílias genérica, binária, assinatura e biometria.
- 24 models compartilhados, 4 contracts e 5 migrations Web.

Diretórios principais: `application`, `binary`, `biometric`, `contracts`, `engines`, `entities`, `evidence`, `factory`, `integrations`, `investigation`, `models`, `parsers`, `processing`, `services`, `settings` e `web/backend/app`.

## Grafo resumido

```text
Desktop / Web route / job worker
  -> ApplicationFactory
    -> AnalysisCoordinator
      -> AnalysisService (shared orchestration)
        -> EvidenceManager (controlled copy + verification)
        -> FileAnalyzer
          -> hash / metadata / magic / signature / PDF / binary / parsers / findings
        -> TextExtractionService (profile-gated)
        -> EntityExtractionService (profile-gated)
        -> TimelineService (profile-gated)
      -> LegacyAnalysisAdapter -> AnalysisContract
  -> AnalysisPresenter -> API payload / StoredAnalysis / DDNA Snapshot

Analysis Set
  -> stored individual contracts
  -> AnalysisSetEngine -> CorrelationEngine V2
```

`WebAnalysisService` é um adaptador HTTP/headless e não repete engines. `AnalysisJobExecutor` é o lifecycle assíncrono/persistido; `AnalysisCoordinator` é o caso de uso síncrono compartilhado. A separação tem responsabilidade real e não deve ser fundida apenas para reduzir arquivos.

## Arquivos vazios e placeholders

Foram encontrados 30 arquivos de 0 bytes.

Marcadores de pacote necessários/aceitáveis: `app/__init__.py`, `engines/__init__.py`, `factory/__init__.py`, `integrations/__init__.py`, `pages/__init__.py`, `repositories/__init__.py`, `rules/__init__.py`, `services/__init__.py`, `ui/__init__.py`, `widgets/__init__.py`, packages de integrations/parsers/findings.

Placeholders intencionais ou de roadmap, sem efeito runtime atual: `binary/parsers/base_parser.py`, `pages/binary_structure_page.py`, `repositories/history_repository.py`, `services/snapshot_service.py`, `integrations/base/api_client.py`, `integrations/ip/ip_cache.py`, cinco regras investigativas vazias e cinco módulos vazios em `knowledge/findings/`. **LOW**, confiança média para remoção: não removidos porque nomes públicos/roadmap podem ser consumidores futuros.

`app/knowledge/_init__.py` é import-only, possui nome incorreto para package initializer, tem zero imports inbound e nenhum registro/entrypoint. **LOW**, HIGH CONFIDENCE candidato a remoção.

`app/pages/comparison_pages.py` contém apenas código comentado. **LOW**, confiança média: fora do escopo backend e não removido.

## Achados comprovados

### BA-001 — seis passagens de hashing onde uma basta

- Severidade: **HIGH**.
- Confiança: **HIGH**.
- Evidência: `HashEngine.calculate_all()` chama `calculate_file_hash()` seis vezes; cada chamada abre e percorre o arquivo integralmente.
- Impacto: 6 × tamanho do arquivo em leitura apenas nessa engine. Além disso, cadeia de custódia faz leituras SHA-256 separadas, mas estas têm finalidade de verificação temporal e não são redundância descartável.
- Correção segura: atualizar os seis objetos digest em uma única passagem, preservando algoritmos e API individual.
- Medição objetiva planejada: teste de instrumentação `Path.open` deve passar de 6 para 1 chamada em `calculate_all()`.
- Medição realizada em arquivo temporário de 33.554.432 bytes: implementação anterior reproduzida em 6 passagens = 0,275783 s; implementação em 1 passagem = 0,201690 s; digests idênticos. É uma amostra local, não uma promessa percentual de performance.

### BA-002 — timeline parcial pode ser descartada pelo adapter

- Severidade: **MEDIUM**.
- Confiança: **HIGH**.
- Evidência: `LegacyAnalysisAdapter.convert()` só serializa timeline se `timeline_events` for não vazio; warnings/limitations existentes sem eventos são ignorados.
- Impacto: caminho iniciado cujo resultado não chega ao `AnalysisContract`/Snapshot.
- Correção segura: considerar eventos, warnings ou limitações ao decidir presença da seção.

### BA-003 — memória de saída do ExifTool não é limitada durante captura

- Severidade: **HIGH**.
- Confiança: **HIGH**.
- Evidência: `subprocess.run(capture_output=True, text=True)` materializa stdout/stderr integralmente; `max_output_bytes` é verificado somente depois do término.
- Timeout, `shell=False`, encoding e retorno são tratados corretamente.
- Recomendação: migrar futuramente para `Popen` com leitura limitada e encerramento testado. Não corrigido nesta rodada por envolver semântica de subprocesso e testes de plataforma.

### BA-004 — múltiplas leituras integrais com finalidades parcialmente distintas

- Severidade: **MEDIUM**.
- Confiança: **HIGH**.
- Fluxo Web: hash no staging; aquisição copia+hash; aquisição relê original; HashEngine; verificação relê working copy e original; `WebAnalysisService` relê staging ao final.
- Parte é defense-in-depth/cadeia de custódia (antes/depois e fonte/cópia) e não deve ser removida. BA-001 é a única redundância inequívoca.
- PDF é aberto/lido por assinatura, estrutura (`read_bytes()` integral), raw parser mmap, binary reader e extração Fitz. São representações diferentes e hoje não existe cache compartilhado seguro.

### BA-005 — candidatos de entidade usam filtro quadrático

- Severidade: **MEDIUM**.
- Confiança: **HIGH**.
- Evidência: `CandidateExtractor.extract_text()` testa cada candidato numérico/decimal contra todos os candidatos para containment: O(c²).
- Normalmente `c` é pequeno, mas textos com milhares de sequências podem degradar. Recomendação: índice de intervalos por posição/hint, acompanhado de testes de equivalência. Não alterado para preservar semântica classificatória.

### BA-006 — correlação é quadraticamente proporcional às entidades comparáveis

- Severidade: **INFO/MEDIUM**.
- Confiança: **HIGH**.
- `EntityCorrelationRule` usa `combinations(items, 2)` entre arquivos e novamente dentro do arquivo: O(e²). `EmbeddedHashMatchRule` também compara pares declarados.
- É coerente com a regra atual, mas deve ser monitorado com 1.000+ entidades. Otimização futura pode agrupar por `(tipo, papel, arquivo)` sem alterar regra.

### BA-007 — warnings de timeline têm produto cartesiano limitado

- Severidade: **LOW**.
- Confiança: **HIGH**.
- `TimelineService._warnings()` executa creation × modification, O(c·m), filtrando por metadata group. Quantidades usuais são pequenas; não requer mudança agora.

### BA-008 — módulos legados coexistem com V2

- Severidade: **MEDIUM** de manutenção, **LOW** runtime.
- `app/engines/correlation_engine.py` tem zero imports inbound; a implementação ativa é `app/investigation/correlation_engine.py` via `CorrelationService` e Analysis Set.
- `ScoreEngine`, `IntegrityEngine` legado e `contract_date_rules.py` também têm zero inbound direto. Score está explicitamente desativado, mas pode constituir API de compatibilidade.
- Confiança para remoção: **MEDIUM**. Não removidos sem depreciação pública explícita.

### BA-009 — jobs e background execution

- Severidade: **INFO**.
- Polling tem intervalo configurado, wake event, stop, timeout global e lifecycle start/stop. O loop de processo isolado possui deadline, cancelamento, terminate/kill, join, pipe close e descarte do registro.
- Heartbeat é daemon, recebe stop e join em `finally`. Staging é limpo em sucesso/falha. Não foi encontrado retry infinito ou worker órfão comprovado.
- `process_next()` realiza recovery/expiry/claim com commits distintos; são fronteiras de estado e idempotência, não redundância comprovada.

### BA-010 — async/sync

- Severidade: **INFO**.
- Upload é lido de forma assíncrona em chunks. A rota síncrona pesada `/analyses` usa `asyncio.to_thread`; jobs usam worker/processo. Não foi encontrado parsing/OCR CPU-bound executado diretamente no event loop.

### BA-011 — recursos e temporários

- Severidade: **INFO**.
- Evidence lease, ZIP, nested ZIP, spool, Fitz, Pillow, arquivos, DB sessions e upload staging possuem context manager/finally.
- `EvidenceManager.acquire()` limpa workspace em `BaseException`; lease valida raiz antes de `rmtree`.
- Não foi comprovado vazamento de file handle ou temporário nos caminhos auditados.

### BA-012 — dependências

- Severidade: **MEDIUM** de manutenção.
- `requirements.txt` mistura runtime Desktop/Web, dependências transitivas e ferramentas de teste (`pytest`, `ruff`). `requirements-web.txt` duplica quase todo o conjunto. `requirements-test.txt` declara `httpx2`, enquanto os testes FastAPI normalmente dependem de `httpx`; não há import `httpx2` no repositório.
- Bibliotecas de baixo nível como `certifi`, `cffi`, `idna`, `pluggy`, `pycparser`, `urllib3` podem estar pinadas intencionalmente como lock transitivo. Não removidas sem definir política de lock e reproduzir instalação limpa.

### BA-013 — imports e código privado morto

- Severidade: **LOW**.
- Antes das correções, Ruff encontrou 36 ocorrências: cinco pertenciam ao arquivo órfão e ao modelo compartilhado; as demais estavam na UI Desktop, fora do escopo.
- O import `field` não utilizado de `app/models/comparison_view.py` foi removido. O Ruff escopado ao backend/camada compartilhada passou; o Ruff global ainda informa 31 ocorrências na UI Desktop preexistente (19 E702, cinco E701, cinco F401 e duas F811), mantidas fora desta tarefa.
- Métodos privados `_calculate_weighted_score`, `_risk_level`, `_confidence_level` pertencem a engine desativada sem inbound; remoção tem confiança média e não foi feita.

### BA-014 — logging e exceptions

- Severidade: **LOW/MEDIUM**.
- `AnalysisService._print_correlation_result()` usa `print()` no core compartilhado, mas é chamado pelo fluxo Desktop e alterar observabilidade pode afetar comportamento; documentado.
- Broad exceptions em engines são convertidas para `ProcessingIssue`/resultado parcial, não silenciosamente descartadas. Correlation V2 não expõe texto sensível da exceção. Não há `except Exception: pass` no backend.

### BA-015 — API, auth e banco

- Severidade: **INFO**.
- `/analyses` síncrono e `/analysis-jobs` são contratos diferentes (imediato vs lifecycle persistido), não endpoints duplicados.
- Ownership, CSRF e filtros por usuário são repetidos como defense-in-depth e foram preservados.
- Não foi encontrado N+1 óbvio nas rotas atuais; relações de privacy podem implicar lazy load unitário por request, não coleção N+1.
- Índices existem nos campos mais consultados de job/analysis. Busca do próximo queued usa `(status, created_at)` em índices separados; índice composto é recomendação futura dependente de métricas/migração.

### BA-016 — configuração e artefatos

- Severidade: **INFO**.
- Variáveis FORENSIHASH/IP2LOCATION encontradas possuem consumidores ou testes. `FORENSIHASH_RUST_JSON_ENABLED` é carregada em settings, mas não foi encontrado consumo operacional do flag: candidato **MEDIUM CONFIDENCE**, não removido por ser configuração pública.
- Nenhum `__pycache__`, `.pyc`, build, dist, coverage, logs ou output indevido apareceu em `git ls-files`.

## Perfis e contratos

- FREE não inicializa `TextExtractionService`, entity resolver ou timeline; teste existente comprova o gating.
- PRO/Desktop habilita o conjunto completo. Biometria e parsers possuem instâncias leves; subprocessos externos só são executados durante a etapa aplicável.
- `LegacyAnalysisAdapter` é necessário para AnalysisContract e DDNA; não é wrapper redundante.
- DDNA consome payload persistido e não reexecuta engines.

## Correções autorizadas nesta rodada

1. BA-001: hashing múltiplo em uma passagem, com teste de call count e equivalência.
2. BA-002: preservar timeline warnings/limitations no contrato, com regressão.
3. Remover `app/knowledge/_init__.py`, único órfão HIGH CONFIDENCE comprovado.
4. Remover o import morto comprovado de `field` no modelo compartilhado de comparação.

Todos os demais achados ficam documentados para decisão arquitetural ou profiling dedicado.

## Validação das correções

- Benchmark sintético local, arquivo temporário de 32 MiB: implementação anterior simulada em seis passagens `0,275783 s`; implementação atual em uma passagem `0,201690 s`; aberturas `6 -> 1`; os seis digests foram idênticos. A medição comprova a redução de I/O, mas não é promessa percentual de desempenho em outros discos/arquivos.
- Testes focados (hash I/O, AnalysisContract, perfis e DDNA Snapshot): **21 passed**.
- Suíte Python principal (`tests/`): **559 passed, 7 skipped**, 41,55 s.
- Suíte Web backend: **77 passed, 6 skipped**, 22,73 s.
- `compileall app web/backend`: passou.
- Ruff do backend e camada compartilhada: passou.
- Ruff global: não passou pelas 31 ocorrências Desktop/UI preexistentes e fora do escopo descritas em BA-013.
- `git diff --check`: passou; apenas avisos informativos de futura normalização LF/CRLF no Windows.
- Frontend Vitest foi iniciado por haver impacto aditivo no contrato de timeline, porém não concluiu nem produziu casos após 120 s; uma segunda execução serial também permaneceu bloqueada e foi encerrada. Não há alteração de frontend nesta rodada; esta limitação permanece explícita.
- Pytest emitiu aviso de permissão do cache `.pytest_cache` sob OneDrive; isso não afetou os testes.
