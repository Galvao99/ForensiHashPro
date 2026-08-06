# Plano de estabilização do ForensiHash

## Estado consolidado após as Partes 1 a 5

- **Fase 0 — parcialmente concluída:** segredo removido do working tree,
  configuração segura, evidência imutável, limites e heurísticas críticas
  corrigidas. Revogação/limpeza do histórico permanecem manuais.
- **Fase 1 — parcialmente concluída:** erros tipados, limites, ferramentas e
  caminhos centralizados. Ambiente limpo Python 3.12/PyInstaller e Ruff global
  permanecem pendentes.
- **Fase 2 — concluída em versão inicial:** `AnalysisContract 1.0.0`, adaptador,
  IDs, serialização, exportação e testes implementados. Engines ainda migram
  gradualmente.
- **Fase 3 — parcialmente concluída:** coordenador e progresso são independentes
  de Qt; worker é adaptador. Pages, correlação multi-arquivo e IP permanecem
  acoplados.
- **Fase 4 — iniciada:** camada de aplicação executa análise individual e aceita
  cancelamento de borda. Cancelamento cooperativo dentro dos motores e
  agregação de investigação ainda faltam.
- **Fases 5 e 6 — não iniciadas:** nenhuma API ou site foi implementado.

## Fase 0 — correções críticas

**Objetivo:** impedir exposição de segredo e mistura/afirmação incorreta de evidência.

**Tarefas:** revogar a chave exposta e limpar o histórico; quarentenar/sanitizar o relatório biométrico real; criar `EvidenceSource` somente leitura com identidade, stat/hash antes e depois; rebaixar o parser PDF textual a heurística; remover score de fraude da classificação automática; criar limites emergenciais de tamanho/páginas/tempo.

**Dependências:** decisão sobre retenção de dados e compatibilidade do score; credencial nova fora do repositório.

**Riscos:** mudança de saída legada e descoberta de relatórios produzidos com heurísticas antigas.

**Critérios de aceite:** nenhum segredo/dado real no Git; alteração concorrente detectada; nenhuma heurística PDF apresentada como validação; etapas incompletas explícitas.

**Testes:** mutação concorrente da fonte; PDF com tokens dentro de streams, xref stream, incremental/híbrido/corrompido; segredo ausente; limites e timeout.

## Fase 1 — estabilização do núcleo

**Objetivo:** tornar execução determinística, observável e resistente a entradas hostis.

**Tarefas:** recriar ambiente Python 3.12; adicionar `pyproject.toml` raiz e lock/constraints; `ResourceLocator`; timeouts e erros tipados; OCR por página; capability checks; logging com redaction; cancelar por token; corrigir Ruff e duplicações seguras.

**Dependências:** Fase 0 e matriz de plataformas suportadas.

**Riscos:** diferenças entre wheels/binários Windows e bundle PyInstaller.

**Critérios de aceite:** instalação limpa documentada; execução fora do CWD; modo sem OCR/ExifTool/internet explícito; nenhuma leitura ilimitada conhecida.

**Testes:** ambiente sem cada ferramenta, caminhos Unicode, vazio/grande/corrompido/protegido, PyInstaller smoke test e cancelamento.

## Fase 2 — padronização dos contratos de dados

**Objetivo:** criar saída versionada, JSON-safe e semanticamente inequívoca.

**Tarefas:** implementar envelope proposto na auditoria; unificar severidades; IDs estáveis; separar fatos, findings, limitações e erros; preservar raw value/source/timezone; versionar engines/regras; adaptadores de compatibilidade.

**Dependências:** inventário de consumidores desktop e formatos exportados.

**Riscos:** migração de campos e perda de nuances em dicionários legados.

**Critérios de aceite:** round-trip JSON; schema versionado; nenhum Qt/`Path`/bytes/datetime cru no payload; migração documentada.

**Testes:** golden files, round-trip, versões anteriores, enums desconhecidos, timezone e ausência versus erro.

## Fase 3 — separação da interface PySide6

**Objetivo:** manter desktop funcional enquanto lógica sai de pages/widgets.

**Tarefas:** presenters/view-models; mover parsing/normalização para aplicação; protocolos de progresso; adaptar QThread na borda; eliminar `print`; separar cores/badges do domínio.

**Dependências:** contrato central da Fase 2.

**Riscos:** regressões de atualização e lifecycle Qt.

**Critérios de aceite:** núcleo importa sem PySide6; páginas apenas apresentam/comandam; desktop mantém funcionalidades.

**Testes:** imports sem Qt, presenters unitários, sinais únicos, thread affinity, repetição e cancelamento.

## Fase 4 — camada de aplicação reutilizável

**Objetivo:** expor casos de uso independentes de desktop/web.

**Tarefas:** `AnalyzeEvidence`, `CorrelateInvestigation`, `LookupIp`, `ExportReport`; políticas de capacidade/limite; unidades de trabalho; progresso, idempotência, cancelamento e cleanup; interfaces de storage/auditoria.

**Dependências:** Fases 1–3.

**Riscos:** concorrência e compatibilidade com análises antigas.

**Critérios de aceite:** casos de uso executam em CLI/teste sem Qt; análise repetida é rastreável; derivados segregados.

**Testes:** integração por portas fake, falhas parciais, concorrência, idempotência, cleanup e isolamento.

## Fase 5 — preparação da API

**Objetivo:** definir limites e fronteiras do serviço sem construir frontend.

**Tarefas:** threat model; API/schema; storage temporário por tenant; fila/worker; autenticação/autorização; quotas Free/Pro; auditoria; download seguro; retenção; malware sandbox; observabilidade.

**Dependências:** camada de aplicação e decisões legais/operacionais.

**Riscos:** upload hostil, path traversal, abuso de recursos, vazamento entre usuários.

**Critérios de aceite:** ADRs aprovados, OpenAPI/schema, política de retenção e protótipo técnico isolado com testes de segurança.

**Testes:** autorização, tenant isolation, traversal, ZIP/image/PDF bombs, quotas, retries, worker crash e expiração.

## Fase 6 — desenvolvimento do site

**Objetivo:** entregar API e frontend sobre núcleo estabilizado.

**Tarefas:** endpoints, fila, status/progresso, cancelamento, relatórios, autenticação, planos e frontend; operação e suporte.

**Dependências:** todas as fases anteriores.

**Riscos:** escopo de produto, custo de processamento e privacidade.

**Critérios de aceite:** fluxos ponta a ponta, observabilidade, recuperação, segurança e paridade definida com desktop.

**Testes:** E2E multiusuário, carga, segurança, acessibilidade, compatibilidade de schemas e disaster recovery.
