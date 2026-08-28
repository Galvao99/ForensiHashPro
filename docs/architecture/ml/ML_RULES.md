# ForensiHash — ML Rules

[Voltar ao README principal](../../../README.md)

## Estado e regra central

Este documento define a arquitetura conceitual da futura camada de Machine Learning e correlação avançada. Não afirma que modelos de ML estejam implementados e não cria regras executáveis, serviços, modelos de dados ou endpoints.

> O Machine Learning do ForensiHash auxilia na identificação, priorização e mensuração de relações entre vestígios técnicos, sem substituir a validação determinística quando aplicável ou a interpretação conclusiva do examinador.

## Regras

### ML Rule 00 — Machine Learning Assists Correlation

ML auxilia correlação, triagem e priorização; não produz conclusão pericial autônoma.

### ML Rule 01 — Consolidated Facts Only

Modelos devem consumir Facts consolidados e normalizados pelo pipeline, mantendo ligação auditável com os dados brutos.

### ML Rule 02 — Evidence Provenance Required

Todo Fact deve apontar para arquivo, objeto/campo, localização, método de extração e versão do componente. Sem provenance suficiente, não sustenta finding conclusivo.

### ML Rule 03 — No Fraud Probability

É proibido apresentar probabilidade ou score de fraude, autenticidade, autoria ou responsabilidade.

### ML Rule 04 — Four-State Correlation

Comparações devem admitir `MATCH`, `MISMATCH`, `UNKNOWN` e `NOT_APPLICABLE`, sempre com critério e justificativa preservados.

### ML Rule 05 — Missing Evidence Is Not Contradiction

Campo ausente, parser indisponível ou extração inconclusiva deve resultar em `UNKNOWN` ou `NOT_APPLICABLE`, conforme o contexto, e não automaticamente em `MISMATCH`.

### ML Rule 06 — Deterministic Evidence Has Priority

Correspondências exatas, validações criptográficas e relações estruturais verificáveis têm prioridade sobre inferências estatísticas.

### ML Rule 07 — ML May Suggest, Core Must Verify

ML pode sugerir candidato, relação ou grupo. Quando houver verificação determinística aplicável, o núcleo deve executá-la antes de confirmar a sugestão.

### ML Rule 08 — Explain Every Score

Todo score deve declarar significado, entradas, pesos, transformações, limitações e contribuição de cada relação.

### ML Rule 09 — Reproducibility

Mesma evidência, configuração e versões devem gerar resultado reproduzível dentro das tolerâncias documentadas; seeds, thresholds e parâmetros devem ser registrados.

### ML Rule 10 — Model Versioning

Nome, versão, artefato, configuração e métricas de validação do modelo devem acompanhar cada execução. Resultados históricos não devem mudar sem novo processamento identificado.

### ML Rule 11 — No Naive Case Average

O score do Caso não deve ser média simples dos arquivos ou relações. Cobertura, não aplicabilidade, dependência e relevância precisam ser consideradas.

### ML Rule 12 — Evidence Relevance Weighting

Pesos devem refletir relevância técnica, qualidade de provenance e confiabilidade do método, nunca suspeita subjetiva ou gravidade jurídica.

### ML Rule 13 — Avoid Evidence Double Counting

O mesmo vestígio derivado por múltiplos caminhos não pode ser contado repetidamente. Linhagem e dependência devem identificar Facts duplicados/correlacionados.

### ML Rule 14 — Exact Before Fuzzy

A ordem é `exact match → normalized match → semantic/fuzzy match → ML similarity`. Relações determinísticas permanecem distinguíveis e prioritárias.

### ML Rule 15 — Temporal Semantics

Criação, modificação, assinatura, operação, aceite, emissão e liberação não são equivalentes. Papel, fuso, precisão e origem devem ser preservados.

### ML Rule 16 — Positive and Negative Evidence

Devem ser registradas evidências favoráveis e desfavoráveis à relação. Evidência negativa requer comparação válida; ausência não é contradição.

### ML Rule 17 — Relationship Strength Is Not Truth

Força de relação mede suporte técnico entre nodes, não verdade material, intenção ou responsabilidade.

### ML Rule 18 — Separate Structural and Semantic Scores

Scores estruturais e semânticos devem ser calculados e exibidos separadamente; combinações conservam contribuições e limitações.

### ML Rule 19 — Automatic Evidence Linking

Links poderão usar hashes, `DocumentID`, `InstanceID`, XMP `DerivedFrom`, ContractID, CPF/CNPJ, UUID, IP/porta, IDs de sessão/transação/conta/dispositivo, filenames, timestamps, JSON/XML e referências entre objetos. Cada link registra método, normalização, origem e verificação.

### ML Rule 20 — Human in the Loop

O examinador poderá revisar, aceitar, rejeitar ou manter indeterminadas sugestões. Sua decisão e justificativa devem ser distinguíveis da saída do modelo.

### ML Rule 21 — Findings Must Carry Evidence

Um threshold isolado não cria finding: ele deve carregar Facts, relações, provenance, método, limitações e explicação revisável.

### ML Rule 22 — Model Confidence Is Not Evidence Confidence

Confidence estatística do modelo, qualidade da extração e força probatória são grandezas distintas em contrato, cálculo e apresentação.

### ML Rule 23 — Case Graph Is the Source of Correlation

Na arquitetura futura, o Evidence Graph será a fonte canônica das correlações; features e findings derivam de nodes/edges versionados, não de agregações paralelas opacas.

### ML Rule 24 — Score Decay for Weak Relations

Relações fuzzy, indiretas, antigas, incompletas ou com provenance limitada sofrem decaimento explícito, sem ocultar a relação nem convertê-la em contradição.

### ML Rule 25 — Case Score Must Be Decomposable

Qualquer score de Caso deve ser navegável até seus componentes:

```text
Case Score → Category Score → Relationship → Finding → Fact
→ Parser Result → File / Object / Field
```

Sem essa decomposição, o score não deve ser apresentado.

## Automatic Evidence Linking

Fontes conceituais: SHA-256/outros hashes, `DocumentID`, `InstanceID`, XMP `DerivedFrom`, ContractID, CPF/CNPJ, UUID, IP, porta, session ID, transaction ID, account ID, device ID, filename, embedded filename, timestamps, referências JSON/XML e referências entre objetos.

```text
exact match
→ normalized match
→ semantic/fuzzy match
→ ML similarity
```

Relacionamentos determinísticos sempre devem ter prioridade e sugestões fuzzy/ML não podem sobrescrever resultados determinísticos.

## Evidence Graph

Nodes possíveis: `File`, `Fact`, `Event`, `Entity`, `Device`, `Network`, `Document` e `Resource`.

Edges possíveis: `contains`, `references`, `matches`, `contradicts`, `derived_from`, `generated_by`, `occurred_before`, `occurred_after`, `same_identifier`, `same_hash` e `same_session`.

Cada edge deve preservar nodes, método de criação, regra/modelo, evidências positivas e negativas, estado, força e provenance. O grafo organiza relações auditáveis; não declara verdade material.

## Scores conceituais

- Structural Score
- Metadata Consistency Score
- Temporal Consistency Score
- Internal Correlation Score
- Cross-File Correlation Score
- Evidence Coverage
- Case / Folder Correlation Score

> Scores representam consistência, anomalia, cobertura ou força de correlação técnica. Não representam probabilidade de fraude, autenticidade, autoria ou responsabilidade.

Cada categoria deve declarar denominador, evidências aplicáveis, exclusões e tratamento de `UNKNOWN`/`NOT_APPLICABLE`. O Case Score é composição auditável, nunca média ingênua.

## Limite de interpretação

ML, regras, Facts, relações, scores e findings são instrumentos de apoio técnico. A interpretação conclusiva permanece sob responsabilidade do examinador e considera o conjunto das evidências, limitações e contexto do Caso.
