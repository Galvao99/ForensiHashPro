# Estabilização do ForensiHash — Parte 4 de 5

## Resumo

Esta etapa revisou as interpretações de PDF, produtor, datas, assinaturas,
contexto de IP e scores. O princípio adotado foi preservar o fato técnico e sua
origem sem converter, isoladamente, ausência de dado, característica legítima
ou métrica de terceiro em alegação de fraude, adulteração, autoria,
autenticidade ou invalidade.

A linha de base era de **286 testes aprovados**. Ao final, a suíte possui
**297 testes aprovados**.

## Heurísticas PDF revisadas

| Observação | Comportamento anterior | Comportamento atual |
|---|---|---|
| Xref tradicional | Busca textual por `xref`, inclusive dentro de `startxref` ou streams | Marcador reconhecido apenas em linha própria |
| Xref stream | Podia ser tratado como xref ausente | `/Type /XRef` é reconhecido como mecanismo legítimo |
| Trailer tradicional ausente | Reduzia o score mesmo em xref stream | Permanece fato observado; não gera penalização nem conclusão de invalidade |
| Múltiplos `%%EOF` | Contados como atualizações e usados no contexto de score | Registrados como marcadores compatíveis com revisões incrementais; sem conclusão de adulteração |
| Validade estrutural | Inferida por cinco marcadores simples | Marcada como não avaliada (`None`); o motor declara suas limitações |
| Objetos e streams | Contagem textual ampla | Contagem por marcadores em início de linha, ainda explicitamente limitada |

O `PdfRawParser` continua produzindo fatos estruturais e não findings
investigativos. Não foi feita a refatoração ampla do parser nem implementada
validação PDF completa.

Características como linearização, criptografia, JavaScript, arquivos
incorporados, formulários, produtor e revisões incrementais continuam
observáveis, mas não são conclusões sobre a história documental.

## Regras removidas ou alteradas

- Removidas as penalizações numéricas por ausência de assinatura, divergência
  de extensão, ausência de marcadores PDF, criptografia, JavaScript e arquivos
  incorporados.
- Producer/Creator/Software, inclusive iText, Word, LibreOffice, Ghostscript,
  Aspose e PDFium, passa a gerar somente informação técnica quando isolado.
- A comparação entre `CreateDate` e data textual deixa de declarar
  compatibilidade ou criação real. A mensagem identifica ambos como valores
  declarados, com origem e limitação.
- Datas do filesystem, aquisição, consulta IP e análise passaram a representar
  instantes UTC com timezone. Datas PDF/OCR sem fuso permanecem ambíguas e não
  são convertidas silenciosamente.
- A timeline não compara datetime com timezone a datetime ambígua. Os grupos
  são ordenados separadamente para evitar inferência de fuso.
- Saídas de depuração da assinatura (objetos internos e certificado) foram
  removidas do console.

## Score anterior e decisão

O score legado começava em 100 e aplicava penalizações heterogêneas. Entre
elas: hash ausente (-20), extensão divergente (-20), header/EOF ausentes (-15),
xref/trailer ausentes (-10), JavaScript ou anexos (-10), criptografia (-5) e
assinatura ausente (-5). Isso misturava disponibilidade, estrutura, segurança,
assinatura e metadados em uma escala sem fundamento calibrado.

**Decisão:** o score agregado foi desativado. O campo público `score` foi
preservado por compatibilidade, agora como `int | None`, e novos resultados usam
`None`. `ScoreEngine` também retorna `None` e emite `DeprecationWarning`. Hash,
tipo real, estrutura, assinatura, metadados, rastreabilidade e limitações devem
ser apresentados separadamente. Não foi criada fórmula substituta.

Os avaliadores legados por seção foram mantidos temporariamente para não
quebrar imports e integrações indiretas; não devem ser usados como conclusão
forense e são pendência de migração controlada.

## Tratamento de `fraud_score`

O valor é preservado com atribuição explícita ao provedor:

- `provider`;
- `provider_metric_name` (`fraud_score`);
- valor original;
- classificação declarada pelo provedor, quando disponível;
- timestamp UTC da consulta;
- limitações da consulta.

Um valor alto não produz severidade crítica nem determina finding crítico.
Proxy, VPN, Tor e data center são apresentados como características que exigem
contexto, no máximo como atenção. A interface informa que geolocalização e
reputação são aproximadas, dependem da base no instante consultado e não
individualizam pessoa ou dispositivo.

CGNAT, IP móvel, dinâmico e compartilhado permanecem limitações de
individualização. Ausência de VPN na resposta não comprova ausência de
mascaramento.

## Assinaturas

Foram separados os estados de detecção (`PRESENT`, `ABSENT`, `UNSUPPORTED`,
`ERROR`) dos estados de validação (`NOT_PERFORMED`, `VALID`, `INVALID`,
`UNVERIFIABLE`). A implementação atual detecta assinatura incorporada, mas não
executa validação criptográfica completa; portanto retorna `NOT_PERFORMED`.

- ausência de assinatura não reduz score e não prova falsidade;
- ausência de ICP-Brasil não implica invalidade;
- presença não comprova validade, confiança da cadeia ou identidade do
  operador;
- falha do parser não é apresentada como assinatura ausente.

## Critérios de severidade

- **SUCCESS/OK:** etapa técnica concluída e condição estritamente verificada;
  não significa autenticidade global.
- **INFO:** fato técnico, ausência de dado opcional ou observação sem impacto
  grave comprovado.
- **WARNING:** limitação ou inconsistência reproduzível que exige correlação e
  pode afetar uma conclusão específica.
- **CRITICAL:** falha grave tecnicamente comprovada, perda/comprometimento da
  evidência ou impacto determinante demonstrável. Métrica externa isolada,
  produtor, revisão incremental e ausência de metadado não satisfazem esse
  critério.

O modelo legado ainda usa `SUCCESS` em alguns fluxos e `ok` nas correlações;
a unificação dos enums pertence à evolução dos contratos, não foi antecipada.

## Testes de regressão

Foi criado `tests/test_forensic_interpretation_regressions.py`, cobrindo:

- PDF com xref stream e sem trailer tradicional;
- PDF com marcadores de atualização incremental;
- iText, Word, LibreOffice e Ghostscript como informação técnica;
- metadados opcionais ausentes sem alegação de adulteração;
- `fraud_score` 99 sem severidade crítica;
- limitações e timestamp UTC da consulta IP;
- Ghostscript sem warning na correlação;
- `CreateDate` sem atestado de data contratual;
- instante de análise com timezone.

Testes existentes de score, PDF e assinatura foram atualizados porque suas
expectativas antigas codificavam precisamente o comportamento forense removido.
Não foram relaxadas verificações de falha técnica.

## Impacto sobre relatórios anteriores

**Sim, esta versão pode alterar resultados emitidos anteriormente.** Scores
numéricos deixam de ser emitidos, produtores deixam de elevar severidade,
xref streams deixam de parecer ausência de xref, ausência de assinatura deixa
de penalizar o arquivo e `fraud_score` alto deixa de criar criticidade automática.

Relatórios antigos não devem ser reinterpretados como se tivessem sido gerados
pelas regras atuais. Recomenda-se registrar a versão do motor/regras e, quando
material ao caso, reprocessar a mesma cópia controlada da evidência, preservando
ambos os relatórios e explicando a mudança metodológica.

## Limitações restantes

- Não há validação PDF completa nem reconstrução abrangente de xref híbrido.
- A contagem de revisões por `%%EOF` é uma aproximação factual, não uma prova da
  quantidade ou natureza das alterações.
- Não há validação criptográfica completa, cadeia ICP-Brasil ou política de
  confiança implementada nesta etapa.
- Os avaliadores legados de score continuam importáveis para compatibilidade.
- Métricas e bases externas podem mudar posteriormente; o retorno bruto segue
  disponível internamente e deve ser protegido por conter dados potencialmente
  sensíveis.
- A normalização completa de todas as fontes de data e contratos de relatório
  permanece para etapa arquitetural posterior.

Nenhuma tarefa de API, site, autenticação, banco de dados ou multiusuário foi
antecipada.

## Validação final

- `python -m pytest -q -p no:cacheprovider`: **297 passed em 8,27 s**;
- `python -m compileall -q app`: aprovado;
- `git diff --check`: aprovado (somente avisos de normalização LF/CRLF);
- Ruff nos arquivos alterados nesta etapa: aprovado;
- Ruff global: 18 ocorrências preexistentes fora do escopo interpretativo
  desta etapa, mantidas sem correção precipitada.
