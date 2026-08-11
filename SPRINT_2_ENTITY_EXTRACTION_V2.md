# Sprint 2 — Entity Extraction V2

## Arquitetura anterior

CPF, telefone, e-mail e datas eram pesquisados independentemente por regex em
`OcrContextRule`. O match era convertido diretamente em finding. CPF possuía
checksum, mas uma sequência inválida ainda era apresentada como CPF inválido;
telefone aceitava qualquer sequência com dez ou mais dígitos. Os dois padrões
podiam disputar a mesma ocorrência sem conhecer um ao outro.

IP já possuía `IpExtractionService` e `DetectedIp`, com validação pela biblioteca
`ipaddress`, offsets e contexto. Datas possuíam uma implementação mais robusta e
paralela em `ContractDateExtractor`. Não havia extrator monetário integrado.

`AnalysisResult.extracted_text` reunia texto nativo e OCR sem proveniência por
trecho. O `AnalysisContract` separava o texto pelo rótulo global da etapa, mas
não expunha entidades estruturadas. JSON era categorizado no Rust pela chave,
sem validação semântica do valor.

## Fluxo V2

```text
TextSegment native/OCR + metadata + JsonField
    -> CandidateExtractor
    -> EntityCandidate
    -> validadores independentes
    -> EntityResolver
    -> NormalizedEntity + proveniências
    -> AnalysisResult.resolved_entities
    -> Fact(kind="entity") no AnalysisContract
    -> adapter compatível do OcrContextRule
```

Regex localiza candidatos; nunca confirma uma entidade. O resolver testa todas
as hipóteses aplicáveis antes de decidir.

## Modelos

- `EntityCandidate`: valor bruto, forma candidata, fonte e hints iniciais;
- `EntitySource`: tipo da fonte, arquivo interno, página, offsets, contexto,
  extractor e field path;
- `ValidationResult`: resultado isolado de um validador;
- `NormalizedEntity`: tipo, valor normalizado, confidence, valores brutos,
  proveniências, atributos e possíveis hipóteses;
- `EntityResolutionResult`: candidatos avaliados e entidades finais.

O mapper do contrato substitui o arquivo interno por `evidence_ref`. A API não
expõe path local. O nome público continua no bloco `file` do contrato.

## Tipos suportados

- `cpf`;
- `phone`;
- `ip`;
- `money`;
- `datetime`;
- `email`;
- `unknown_numeric_identifier`;
- `ambiguous`.

Não há inferência de RG, CNH, CNPJ, conta bancária ou número de contrato.

## Validadores e normalização

CPF exige onze dígitos, rejeita repetição e aplica os dois dígitos verificadores.
Telefone exige DDD brasileiro conhecido e formato fixo ou celular, aceitando
`+55`. IP usa `ipaddress`; classificação público/privado/reservado continua no
serviço de IP. MONEY exige `R$` ou contexto monetário e formato decimal BR,
normalizado em decimal e `BRL`. DATETIME valida calendário/ISO, preserva raw,
precisão e presença ou ausência de timezone. E-mail usa sintaxe conservadora e
valida parte local e labels do domínio.

## Confidence

Confidence é determinística e representa confiança na classificação/extração,
não autenticidade, autoria, veracidade ou fraude. O valor é a soma limitada a
`0..1` de componentes armazenados junto à entidade:

| Componente | Regra |
|---|---|
| estrutural | CPF `0.65`; telefone `0.55`; IP `0.80`; MONEY `0.50`; DATETIME/EMAIL `0.70` |
| formatação | até `0.10`; MONEY com `R$` `0.20` |
| contexto compatível | `+0.20` |
| fonte | structured `+0.10`; JSON/metadata `+0.08`; native `+0.05`; OCR/legado `+0.00` |
| contexto conflitante CPF/telefone | `-0.25` quando o rótulo concorrente é mais próximo |
| identificador contratual genérico | `-0.35` para CPF/telefone sem formatação |

OCR não é tratado como evidência inferior. O fator apenas registra que a
extração de caracteres possui uma etapa derivada adicional. O conteúdo e todas
as origens são preservados.

## Ambiguidade e unknown

Hipóteses abaixo de `0.50` não são confirmadas. Se as duas melhores hipóteses
válidas diferirem menos de `0.12`, o resultado é `ambiguous` e ambas permanecem
em `hypotheses`. Contexto explícito de CPF ou telefone favorece um tipo e
penaliza o concorrente.

Sequências numéricas com cinco ou mais dígitos que nenhum validador confirma
viram `unknown_numeric_identifier`, com confidence `0.0`. Isso preserva o fato
sem inventar a espécie do identificador.

## Proveniência e deduplicação

Texto nativo e OCR são preservados como `TextSegment`, com página quando o
extrator a conhece. Metadata e JSON usam field path. Cada source mantém contexto,
offsets e extractor.

A chave de deduplicação é `tipo + valor normalizado`. Formas como telefone com
ou sem máscara são unificadas, mas todos os raw values e sources distintos são
mantidos. Valores diferentes nunca são fundidos. Native e OCR divergentes
permanecem como entidades separadas, sem conclusão.

## Compatibilidade

- `AnalysisCoordinator` não mudou;
- `AnalysisResult.extracted_text` foi preservado;
- `AnalysisResult.resolved_entities` é opcional e inicia vazio;
- o contrato continua `1.0.0`; entidades usam o mecanismo extensível de `Fact`;
- `ip_addresses` continua `null` no fluxo individual;
- `OcrContextRule` mapeia entidades V2 para os títulos/metadados legados;
- o builder resolve texto legado somente quando `resolved_entities` está vazio;
- frontend e endpoints não exigem alteração, pois facts já eram genéricos.

## Limitações conhecidas

- Página só existe quando PyMuPDF/OCR a informa; metadata e JSON não têm página.
- Não há correlação de divergências native/OCR nesta Sprint.
- Valores monetários suportam inicialmente BRL no formato brasileiro.
- Telefone cobre o plano brasileiro atual modelado; ramais não são entidades.
- E-mail não realiza DNS nem afirma existência da caixa postal.
- DATETIME não inventa timezone e não converte valor ingênuo para UTC.
- A categoria de chave produzida pelo Rust continua ampla; o resolver valida o
  valor depois do parser.
- A Sprint não transforma entidade em finding de fraude, suspeita ou autoria.
