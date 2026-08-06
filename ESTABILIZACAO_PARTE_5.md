# Estabilização do ForensiHash — Parte 5 de 5

## Resumo executivo

Foi criado um contrato central v1 em paralelo aos DTOs legados, um adaptador de
compatibilidade, serialização JSON determinística, exportação técnica e uma
camada de aplicação sem Qt. O desktop permanece compatível: continua recebendo
o resultado legado e também pode receber o novo contrato pelo worker.

Linha de base: **297 testes aprovados**. Resultado após implementação: **305
testes aprovados**.

## Inventário dos contratos anteriores

| Forma | Exemplos | Problema observado |
|---|---|---|
| Dataclasses | `AnalysisResult`, `IntegrityResult`, modelos binários/biométricos | mutabilidade e semânticas diferentes; sem schema |
| Dicionários | metadados, contextos, detalhes de steps e IP | chaves livres, valores de terceiros e ausência de validação |
| Enums e strings | `Severity`, `ProcessingStatus`, `ok/warning/critical` | vocabulários sobrepostos |
| Tuplas | retorno de timeline, seletores e helpers | significado depende da posição |
| Listas | findings, fatos binários, eventos | itens sem IDs estáveis em modelos legados |
| Objetos Qt | worker, sinais, badges/widgets | não serializáveis e presos à apresentação |
| JSON específico | comparação e relatórios biométricos | schemas particulares sem versão central |
| Strings formatadas | status, resumos e relatórios TXT | perda de estrutura e origem |
| Resultados terceiros | ExifTool, IP2Location, pyHanko | campos/versões atribuídos de forma desigual |

Duplicações relevantes continuam: dois `TimelineEvent`, findings de domínio e
correlação com formatos distintos, severidade `SUCCESS` versus `ok`, caminhos
como `Path` e string, `score` com significados distintos, e identificadores de
correlação baseados provisoriamente em caminho.

## Arquitetura resultante

- `app/contracts`: schema, enums, IDs, adaptador e codec JSON;
- `app/application`: `AnalysisCoordinator`, cancelamento cooperativo de borda e
  eventos de progresso sem Qt;
- `AnalysisService`: aceita/propaga `analysis_id` e registra início/término UTC;
- `ExportService`: exporta `AnalysisContract` em UTF-8 determinístico;
- `AnalysisWorker`: adapta progresso para sinais e emite legado + contrato;
- `ApplicationFactory`: cria serviço desktop ou coordenador headless.

Não houve substituição em massa dos engines. O coordenador usa a aquisição
imutável da Parte 2 e adapta o resultado atual ao final.

## Contrato criado

O schema `1.0.0` contém identificação, evidência, arquivo, hashes, tipos,
metadados, estrutura, texto nativo, OCR, assinaturas, IP, timeline, comparação,
biometria, fatos, findings, limitações, erros, resultados externos, etapas e
execução. Campos não aplicáveis permanecem opcionais/vazios, enquanto falha e
limitação são explícitas.

Detalhes e política SemVer estão em `CONTRATO_ANALISE_FORENSIHASH.md`.

## Segurança e serialização

- datetime ingênua e números não finitos são rejeitados;
- chaves sensíveis e caminhos operacionais são removidos da exportação;
- exceção original e stack trace não são serializados;
- objetos desconhecidos são rejeitados;
- JSON usa chaves ordenadas, UTF-8 e newline final;
- IDs filhos não dependem da descrição traduzida.

## Componentes desacoplados

- início de uma análise individual;
- aquisição/orquestração principal por `AnalysisCoordinator`;
- progresso do núcleo por callback tipado;
- montagem do contrato;
- serialização/desserialização;
- exportação JSON;
- criação do coordenador pela factory sem janela ou QObject.

## Componentes ainda acoplados ao desktop

- lifecycle de múltiplos arquivos, correlação e cancelamento em curso no
  `AnalysisWorker`/`MainWindow`;
- seleção de arquivo, histórico e apresentação;
- consultas IP disparadas por páginas;
- badges, cores e findings de correlação com propriedades de UI;
- normalizações e textos em pages/widgets;
- relatórios visuais além do JSON técnico;
- alguns engines acessam filesystem/ferramentas diretamente.

## Testes criados

`tests/test_analysis_contract.py` adiciona oito testes para:

- schema versionado e saída determinística;
- round-trip com findings, limitações e resultado externo;
- datetime com timezone e rejeição de NaN;
- redação de segredos/caminhos;
- estabilidade de IDs após mudança de texto;
- execução sem Qt e progresso independente;
- cancelamento anterior à aquisição com estado explícito;
- worker desktop emitindo contrato;
- exportação UTF-8 versionada.

## Compatibilidade

`AnalysisResult` legado recebeu somente `analysis_id` e `completed_at` opcionais.
Widgets continuam usando o mesmo objeto. `LegacyAnalysisAdapter` é a ponte
temporária; engines podem ser migrados um a um para produzir fatos tipados.

## Pendências e riscos remanescentes

- IDs de itens legados ainda incluem posição da coleção;
- versões individuais reais de todos os motores/dependências ainda não são
  coletadas automaticamente;
- IP e comparação ainda não entram no envelope da análise individual sem um
  agregador de investigação;
- texto anterior à Parte 3 pode ter origem `legacy_unknown`;
- cancelamento não interrompe subprocesso ou parser já em execução;
- desserialização v1 não é migração de schemas futuros;
- modelos específicos ainda aceitam dicionários livres;
- não há validação por JSON Schema externo, persistência ou assinatura do
  relatório exportado;
- 18 ocorrências Ruff legadas permanecem fora desta mudança arquitetural;
- instalação/empacotamento Python 3.12 e PyInstaller ainda requerem smoke test
  em ambiente limpo.

## Avaliação

O desktop permanece funcional e agora possui uma saída técnica estável em
paralelo. O núcleo é **parcialmente reutilizável**: aquisição, coordenador,
contrato e exportação não dependem de Qt, mas correlação, IP, ciclo de múltiplos
arquivos e vários presenters ainda precisam de extração gradual.

O projeto não deve ser classificado como pronto para site. Contrato JSON é uma
pré-condição arquitetural, não substitui segurança de upload, isolamento,
storage, filas, autenticação, quotas, persistência ou sandbox.

## Validação final

- `python -m pytest -q -p no:cacheprovider`: **305 passed em 8,33 s**;
- `python -m compileall -q app`: aprovado;
- `git diff --check`: aprovado, com avisos informativos LF/CRLF;
- Ruff nos arquivos criados/alterados nesta etapa: aprovado;
- Ruff global: 18 ocorrências legadas já inventariadas;
- `cargo test --manifest-path rust/forensihash_core/Cargo.toml`: aprovado,
  porém o crate ainda contém **0 testes Rust**;
- cobertura: não há configuração/plugin de cobertura no projeto;
- empacotamento: não foi encontrado arquivo `.spec` ou suíte PyInstaller para
  executar; o smoke test de distribuição permanece pendente.
