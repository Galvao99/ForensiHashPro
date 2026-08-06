# Auditoria técnica do ForensiHash

## 1. Resumo executivo

O projeto possui um núcleo funcional relevante e uma boa direção conceitual em partes recentes (`BinaryReader`, parser biométrico tipado, estados explícitos de assinatura e correlação). Contudo, **ainda precisa ser estabilizado antes do início do site**. Os maiores riscos são: chave de API exposta, ausência de uma unidade imutável de evidência, heurística PDF usada para compor integridade, erros de processamento silenciosos, score forense incompatível com as regras locais, recursos externos não reproduzíveis e contratos não serializáveis/versionados.

Foram inventariados 258 arquivos rastreáveis; 240 arquivos Python passaram por compilação/busca estática e 35 arquivos centrais foram revisados em profundidade. Todos os Markdown existentes (`README.md` e `AGENTS.md`) foram lidos. Não há documentação separada de arquitetura, backlog, changelog, regras, testes ou instalação.

Contagem consolidada: **3 críticos, 10 altos, 13 médios, 5 baixos e 3 informativos (34 achados)**. A enumeração detalhada está em `BUGS_E_RISCOS_FORENSIHASH.md`.

## 2. Estado atual

A aplicação desktop executa análise geral, hashes, ExifTool, magic number, assinatura PDF, estrutura PDF, integridade, texto/OCR, JSON Rust, biometria, estrutura binária e correlação. Existem telas de comparação, IP, timeline, OCR e binary structure. A interface usa `QThread` para a análise principal.

O núcleo Rust é opcional em runtime e não possui testes Rust. Persistência real limita-se a configurações JSON e histórico em memória. Não há schema central, banco, fila, isolamento de evidência ou API.

## 3. Arquitetura identificada

A composição `ApplicationFactory -> AnalysisService -> FileAnalyzer -> engines/services` é aproveitável. `investigation` correlaciona resultados após extração, coerente com a regra de que o Binary Engine produz fatos. A arquitetura real e os fluxos estão em `MAPA_ARQUITETURA_ATUAL.md`.

Pontos positivos:

- hashes são calculados em chunks;
- `BinaryReader` evita leitura integral e valida offsets;
- vários modelos novos usam `dataclass(slots=True)`;
- assinatura distingue presente, ausente, não aplicável e erro;
- worker mantém atualizações Qt fora do processamento pesado;
- linguagem de vários findings contém ressalvas técnicas.

## 4. Divergências entre documentação e código

- README lista OCR, comparação, biometria, geolocalização, snapshot e correlação como roadmap, mas há implementações atuais.
- README omite integridade, binary structure, PdfRawParser, JSON Rust, IP e biometria.
- AGENTS diz que `PdfRawParser` e `BinaryStructurePage` não estão completos/integrados; ambos existem e o parser é conectado ao `BinaryStructureEngine`, embora V1/limitado.
- README declara Python 3.12; o venv auditado usa 3.14.6.
- README cita integração pyHanko e “status técnico”, mas não deixa evidente que a validação criptográfica completa não é feita.
- A árvore documentada coloca testes sob `app/`; os testes reais estão na raiz.
- Não existem instruções completas de instalação, binários OCR/Poppler, build Rust ou PyInstaller.
- Implementações legadas de score permanecem apesar da regra local de não usar dashboards/score de fraude.

## 5. Bugs e inconsistências

Os dois testes inicialmente falhos demonstraram instabilidade de normalização de IPv4-mapped IPv6 no Python 3.14 (FH-015), corrigida com formato hexadecimal explícito. Ruff encontrou 21 problemas, incluindo `__init__` duplicado, imports redefinidos, variável morta e módulo `_init__.py` incorreto.

O parser PDF legado é o bug técnico mais sensível: busca substrings no arquivo inteiro, não separa objetos/streams de forma confiável e considera presença textual de marcadores equivalente a estrutura válida. `startxref` por si já contém a substring `xref`. Esses resultados alimentam `IntegrityResult` e score.

Outras inconsistências: dois tipos `TimelineEvent`; `AnalysisResult` mutável com campos adicionados após construção; uso misto de enums/strings; JSON inválido e módulo Rust ausente representados de forma semelhante; somente a primeira assinatura é detalhada; falha binária/OCR vira ausência de resultado.

## 6. Riscos forenses

1. Não existe snapshot/handle imutável. Cada motor reabre o caminho, permitindo mistura de estados se o arquivo for substituído ou modificado durante a análise.
2. Hash calculado não é vinculado a cada resultado de etapa nem revalidado no encerramento.
3. Datas do filesystem são ingênuas e dependentes do SO; `ctime` não possui semântica portátil.
4. OCR não é marcado no contrato como derivado com versão/idioma/configuração; texto vazio oculta falha.
5. Ausência de assinatura reduz score, embora não invalide documento; presença não significa validade/autenticidade.
6. PDF com múltiplos EOF, JavaScript, anexos, criptografia ou revisão incremental recebe penalidades sem correlação suficiente.
7. Deduplicação pode apagar achados distintos com mesmo título/regra/par de arquivos.
8. IP2Location fornece localização aproximada e score proprietário; IP/CGNAT nunca identifica pessoa individualmente. Algumas ressalvas existem, mas a severidade automática por score contradiz essa cautela.

## 7. Segurança

A chave versionada foi removida do arquivo corrente, mas deve ser considerada comprometida: revogação e limpeza do histórico continuam obrigatórias. O settings local permanece em texto claro.

Não foi encontrado `shell=True`, `pickle` ou escrita deliberada no arquivo original. ExifTool recebe argumentos em lista, reduzindo risco de injeção. Ainda assim, subprocesso sem timeout, PDFs/imagens sem limites, OCR em lote, dados biométricos versionados e chamadas externas representam riscos altos. Exportação escreve no caminho fornecido e precisa de uma política de destino seguro antes da web.

## 8. Redundâncias, obsolescência e código morto

- `TimelineEvent` duplicado.
- `app/engines/correlation_engine.py` e `app/investigation/correlation_engine.py` representam versões/nomes concorrentes; a service usa a segunda.
- `ScoreEngine`, evaluators e weights continuam importáveis/testados, mas não aparecem na composição principal.
- `comparison_pages.py` contém implementação antiga comentada.
- `config/settings.py`, `config/constants.py` e `ip_cache.py` estão vazios.
- `aware_knomi_report.json` duplica conceitualmente uma fixture, mas não tem o mesmo hash.
- `app/knowledge/_init__.py` não inicializa o pacote.

Nada foi excluído, pois imports indiretos, testes e compatibilidade ainda precisam ser fechados.

## 9. Dependências e ambiente

`requirements.txt` fixa também dependências transitivas, não há `pyproject.toml` raiz nem lock multiplataforma. `pytesseract` e `pdf2image` foram adicionados porque são imports diretos comprovados. O venv contém pacotes extras e `pip check` marcou como não suportados em Python 3.14: `charset-normalizer`, `forensihash-core`, `ijson`, `jiter`, `lxml`, `pydantic_core` e `PyYAML`.

ExifTool e um instalador Tesseract estão versionados, sem verificação de checksum/licença no projeto. O executável Tesseract esperado e Poppler não existem no layout. Caminhos relativos quebram fora da raiz e não há tratamento explícito de `_MEIPASS` ou outro locator de bundle.

Licenças não puderam ser validadas como conformidade de distribuição nesta auditoria; deve haver inventário SBOM e revisão jurídica antes de distribuir binários.

## 10. Testes e análise estática

### Linha de base

- Python: 3.14.6 (diverge do 3.12 declarado)
- pytest: 249 coletados; 247 passaram; 2 falharam; 0 ignorados; 2 warnings; 30,26 s
- falhas: duas asserções de IPv4-mapped IPv6
- warnings: cache `.pytest_cache` inacessível/inválido

### Após a correção

- pytest: 249 coletados; **249 passaram**; 0 falharam; 0 ignorados; 0 warnings; 8,87 s (cache plugin desativado por causa do diretório local defeituoso)
- `python -m compileall -q app`: passou
- `git diff --check`: passou
- Ruff: 21 ocorrências; não foram autoaplicadas
- `cargo test`: passou formalmente, mas executou 0 testes
- cobertura: não configurada; percentual indisponível

Os testes cobrem bem a fundação binária, vários estados de assinatura, IP, biometria e algumas regras de neutralidade. Faltam suites robustas de PDF real (xref streams/híbridos/incrementais/protegidos), OCR/capabilities, timezone/DST, arquivos grandes/hostis, mudança concorrente da evidência, serialização, rede offline, empacotamento e instalação limpa.

## 11. Correções realizadas

- Normalização estável de IPv4-mapped IPv6 entre versões Python.
- Remoção do valor da chave de API no working tree.
- Declaração de `pytesseract==0.3.13` e `pdf2image==1.17.0`.
- Criação destes quatro documentos de auditoria.

Não houve alteração de regra forense, renomeação pública ou grande refatoração.

## 12. Contrato central proposto

Um envelope futuro deve ser independente de Qt e JSON-safe:

```text
AnalysisEnvelope v1
├── analysis_id, schema_version, status
├── evidence
│   ├── evidence_id, original_name, ingested_at_utc
│   ├── size_bytes, media_type_declared, media_type_observed
│   └── hashes, source_stat, custody_events
├── facts
│   ├── metadata[]              {namespace, key, raw_value, normalized_value, source}
│   ├── structure              {format, observations[], parser_details}
│   ├── text[]                 {kind: native|ocr, text_ref, language, engine}
│   ├── signatures[]           {presence, crypto_validation, trust_validation, certificate}
│   ├── ip_addresses[]         {raw, normalized, classification, context, lookup?}
│   └── timeline[]             {kind, instant_utc?, raw_value, timezone?, source, confidence_basis}
├── findings[]                 {finding_id, rule_id/version, severity, statement, evidence_refs[]}
├── limitations[]              {code, stage, description}
├── processing_issues[]        {code, stage, status, safe_message, technical_detail_ref}
└── execution
    ├── started_at_utc, finished_at_utc, host/runtime
    ├── engine_versions, rule_versions, configuration_digest
    └── derived_artifacts[]    {artifact_id, kind, hash, retention}
```

Regras essenciais: `severity` não representa fraude; fatos não carregam conclusões; IDs não derivam de caminho; valor bruto nunca é perdido; ausência, não aplicável, indisponível e erro são estados distintos; textos OCR são derivados; datas sempre preservam fonte e timezone; localização IP é aproximada e atribuída ao provedor.

## 13. Preparação para web

O domínio potencialmente reutilizável inclui modelos técnicos (após normalização), binary readers/parsers, regras de correlação e timeline. Infraestrutura deve englobar filesystem, ExifTool, OCR, PDF, assinatura, Rust JSON, IP, cache, storage e logs. A camada de aplicação deve controlar ingestão, limites, progresso, cancelamento, idempotência e erros. PySide6, relatórios e futura API são adaptadores de apresentação.

Antes de upload/multiusuário, são indispensáveis: diretórios aleatórios por análise, nomes do cliente apenas como metadado, abertura segura sem traversal/symlink, quotas, sandbox de parsers, storage por tenant, lifecycle/cleanup auditável, autenticação/autorização, fila e proteção contra conteúdo hostil.

## 14. Pendências e recomendações priorizadas

1. Revogar a chave exposta, limpar histórico Git e decidir sobre o relatório biométrico real.
2. Implementar unidade imutável de evidência e detectar alteração durante toda a análise.
3. Impedir que heurística PDF e scores componham conclusões de integridade; validar o novo contrato com perito.
4. Criar contratos versionados de resultado/erro/limitação e adapters de compatibilidade desktop.
5. Reproduzir ambiente Python 3.12, recursos externos e smoke tests de instalação/PyInstaller.

Conclusão: **o projeto ainda precisa ser estabilizado; não está pronto para iniciar o site**. O plano faseado está em `PLANO_ESTABILIZACAO_FORENSIHASH.md`.
