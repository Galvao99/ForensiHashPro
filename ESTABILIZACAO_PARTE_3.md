# Estabilização do ForensiHash — Parte 3 de 5

Data da execução: 05/08/2026.

## Confirmação da etapa anterior

A linha de base da Parte 2 foi confirmada com 273 testes aprovados. A aquisição continua criando uma cópia controlada, somente leitura e exclusiva; os motores migrados recebem o mesmo `working_path`; hashes e identidade são verificados; o original não é aberto para escrita.

Não foram alterados score, regras forenses, semântica do parser PDF, API, site, banco ou contratos web.

## Erros silenciosos identificados e classificação

A busca inicial encontrou catches amplos em quatro grupos:

1. **Fronteiras justificadas:** worker Qt, engine de correlação, componentes binários e parser de assinatura. Precisam impedir que um plugin/regra derrube o lote, mas devem converter a exceção em estado explícito.
2. **Fallbacks que confundiam falha e ausência:** OCR nativo retornava `""`; OCR PDF capturava qualquer erro; `AnalysisService` imprimia e mantinha texto vazio; falha binária total virava `None`.
3. **Erros já parcialmente explícitos:** assinatura possui `analysis_status=ERROR`; IP externo retorna `lookup_performed=False`, severidade `error` e mensagem; JSON retorna `is_valid=False` com mensagem.
4. **Apresentação:** widgets capturam erros para preservar a UI. Permanecem fora do contrato interno e deverão convergir gradualmente, sem esconder os status agora anexados ao resultado.

Após esta etapa, permanecem 20 catches amplos. Os catches em OCR e Binary são agora limites arquiteturais que criam `ProcessingIssue`; os restantes foram documentados e não removidos sem compreender o consumidor. Biometria, JSON e assinatura continuam com seus contratos legados específicos e são riscos de padronização futura.

## Contrato de status

Foi criado `app.processing`:

- `ProcessingStatus`: `SUCCESS`, `NO_FINDINGS`, `PARTIAL`, `SKIPPED`, `UNAVAILABLE`, `FAILED`, `CANCELLED` e `LIMIT_EXCEEDED`;
- `ProcessingImpact`: nenhum, somente componente, análise parcial ou análise bloqueada;
- `ProcessingIssue`: código, status, mensagens técnica/amigável, componente, instante UTC, detalhes seguros, impacto e exceção interna;
- `StepResult[T]`: valor parcial/final, issues, horários, duração e detalhes seguros.

A exceção original usa `repr=False`, não é serializada nem exibida. Mensagens amigáveis não incluem `stderr`, conteúdo documental ou stack trace.

`AnalysisResult.processing_steps` consolida estados de metadados, binário e texto. `BinaryAnalysisResult.processing_steps` mantém granularidade por scanner, strings, entropia e parser PDF bruto.

## Limites definidos

| Limite | Padrão | Aplicação atual |
|---|---:|---|
| Arquivo | 2 GiB | bloqueado antes da cópia |
| Páginas PDF | 1.000 | antes de texto/OCR |
| Largura/altura de imagem | 30.000 px | antes do OCR |
| Pixels de imagem | 100 milhões | antes do OCR |
| Memória estimada de imagem | 1 GiB | estimativa RGBA antes do OCR |
| OCR total | 120 s | orçamento monotônico e timeout do Tesseract/Poppler |
| Ferramenta externa | 60 s | ExifTool |
| Saída externa | 10 MiB | rejeitada antes de JSON; captura ainda é bufferizada |
| Objetos PDF bruto | 1.000.000 | parser interrompido com `LIMIT_EXCEEDED` |
| Strings binárias | 1.000 | preserva resultados e marca `PARTIAL` ao atingir teto |
| Profundidade de arquivo | 10 | reservado/documentado; ZIP ainda não é processado |
| Entradas compactadas | 10.000 | reservado/documentado; ZIP ainda não é processado |
| Total expandido | 4 GiB | reservado/documentado; ZIP ainda não é processado |

Todos são configuráveis em `settings.json` sob `limits`. Valores não positivos são inválidos. Limites ZIP foram apenas definidos para futura política; nenhum suporte ZIP foi inventado.

## Mudanças no OCR

- API nova `extract()` retorna `StepResult[TextExtractionResult]`; `extract_text()` permanece como adaptador legado.
- Formato sem suporte retorna `SKIPPED`, não texto ausente.
- PDF sem páginas retorna `NO_FINDINGS` com código técnico.
- Texto nativo suficiente retorna `SUCCESS` sem OCR.
- Tesseract/Poppler ausentes ou desabilitados retornam `UNAVAILABLE`.
- Texto nativo curto é preservado se OCR estiver indisponível, resultando em `PARTIAL`.
- PDFs são renderizados página a página; falha informa o número da página.
- Texto de páginas anteriores é preservado em falha parcial.
- Tempo total é controlado por relógio monotônico e repassado às ferramentas.
- Dimensões, pixels e memória estimada são verificados antes do OCR.
- OCR concluído sem texto retorna `NO_FINDINGS`; falha retorna `FAILED`.

## Mudanças na análise binária

Cada componente registra sucesso, ausência legítima, parcial, skipped, limite ou falha. Exceções não são mais representadas somente por listas vazias. Findings técnicos legados foram preservados para compatibilidade, mas não incluem mais a mensagem bruta da exceção. Scanner/parser podem falhar sem apagar strings, entropia, header ou footer já obtidos.

O limite de strings gera `PARTIAL` e registra quantidade preservada. O limite de objetos interrompe o parser PDF bruto antes de acumulação ilimitada e mantém os demais fatos binários.

## Subprocessos revisados

- ExifTool usa lista de argumentos, `shell=False` implícito, encoding UTF-8 com replacement, timeout e retorno verificado.
- `stderr` não é propagado para usuário, logs ou detalhes seguros.
- Saída acima do limite é rejeitada explicitamente.
- Tesseract é chamado por `pytesseract` com timeout.
- Poppler é chamado por `pdf2image` com páginas delimitadas e timeout.
- Rust é extensão em processo, não subprocesso; seus erros continuam no resultado JSON legado.
- Nenhuma chave IP2Location participa desses comandos.

Limitação: `subprocess.run(capture_output=True)` ainda pode alocar a saída completa antes de aplicar o teto. Leitura incremental limitada exigiria um runner dedicado e permanece risco documentado.

## Logs

`log_step()` registra somente evento fixo e campos estruturados: `analysis_id`, `evidence_id`, componente, código, status e duração. Não registra mensagens, conteúdo, caminhos, respostas externas, exceções ou segredos. A orquestração registra as etapas depois da verificação da evidência.

## Interface mínima

As páginas OCR e Metadados agora exibem a mensagem amigável da etapa quando ela foi pulada, ficou indisponível, parcial, falhou ou excedeu limite. Texto parcial continua visível. Binary Structure mantém suas falhas técnicas na apresentação já existente e agora também possui status estruturado no modelo. Não houve redesign visual.

## Testes criados

`tests/test_processing_reliability.py` cobre:

- Tesseract ausente;
- Poppler ausente;
- ExifTool ausente;
- timeout do ExifTool;
- retorno externo diferente de zero e `stderr` sensível;
- OCR parcial com página anterior preservada;
- arquivo acima do limite;
- imagem acima do limite de pixels;
- PDF acima do limite de páginas;
- componente binário parcial;
- limite de objetos PDF preservando dados binários;
- log estruturado sem segredo.

`tests/test_settings_and_environment.py` passou a validar limites configuráveis. A suíte também continua cobrindo limpeza e imutabilidade da Parte 2.

## Resultado final

- pytest: **286 aprovados**, 0 falhos, 0 ignorados, 8,95 s;
- `python -m compileall -q app`: aprovado;
- `git diff --check`: aprovado;
- Ruff nos arquivos criados/alterados nesta etapa: aprovado;
- Ruff global: 19 ocorrências legadas fora desta etapa.

## Riscos restantes

- Assinatura, JSON, biometria, IP e regras possuem contratos próprios ainda não unificados a `StepResult`.
- Cancelamento existe entre arquivos; `CANCELLED` está modelado, mas OCR/ExifTool em curso ainda não recebem token cooperativo do worker.
- Saída do ExifTool é limitada após captura em memória.
- PyMuPDF e parsers nativos continuam no processo principal do worker, sem sandbox de processo.
- Limite de arquivo exige decisão de produto para casos periciais legítimos acima de 2 GiB.
- A UI apresenta estados explícitos em OCR/Metadados; uma visão consolidada pertence a etapa posterior de apresentação.
- Regras de ZIP são apenas política futura, pois o projeto ainda não extrai arquivos compactados.

## Tabela comparativa

| Componente | Comportamento anterior | Comportamento novo | Testes correspondentes |
|---|---|---|---|
| OCR/Tesseract | Ausência/falha podia virar texto vazio | `UNAVAILABLE`, `FAILED`, `NO_FINDINGS` ou `PARTIAL` | `test_tesseract_absent_*`, `test_ocr_partial_*` |
| OCR/Poppler | Falha genérica retornava vazio | indisponibilidade explícita e página delimitada | `test_poppler_absent_*` |
| Imagem | Sem teto de pixels/dimensões | `LIMIT_EXCEEDED` antes do OCR | `test_image_pixel_limit_*` |
| PDF OCR | Todas as páginas de uma vez | limite, página a página, timeout e parcial | `test_pdf_page_limit_*`, `test_ocr_partial_*` |
| ExifTool | Sem timeout; erro bruto | timeout, retorno, JSON e saída diferenciados | `test_exiftool_*` |
| Binary scanner | Falha parecia lista vazia + finding | `FAILED` com outros resultados preservados | `test_binary_component_failure_*` |
| Strings binárias | truncamento sem estado | `PARTIAL` ao atingir teto | suíte Binary Structure |
| PDF bruto | objetos sem teto | `LIMIT_EXCEEDED`, demais fatos preservados | `test_pdf_object_limit_*` |
| Arquivo de entrada | sem limite central | bloqueio antes da cópia | `test_file_above_limit_*` |
| Logs | prints e mensagens heterogêneas | evento estruturado sem conteúdo/segredo | `test_structured_log_*` |
| UI OCR/Metadados | vazio genérico | mensagem de skipped, parcial, indisponível, falha ou limite | testes de contrato + suíte UI existente |
