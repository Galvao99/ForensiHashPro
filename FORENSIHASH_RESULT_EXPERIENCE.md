# ForensiHash — experiência de resultado por artefato

## Princípio

A tela de resultado funciona como uma bancada forense em duas camadas. O **Resumo forense** oferece leitura rápida dos fatos presentes no `AnalysisContract`; o **Detalhamento técnico** preserva as estruturas completas, as etapas e o JSON público para auditoria. A camada de apresentação não altera nem complementa o contrato.

## Hierarquia

1. Cabeçalho do artefato: nome público, tipo detectado, tamanho, estado e SHA-256.
2. Resumo forense: identificação, estrutura, metadados prioritários, assinaturas e entidades.
3. Evidências: findings individuais expansíveis.
4. Timeline: eventos temporais e eventos estruturais sem data determinável.
5. Correlações: findings do Analysis Set, quando ele existe.
6. Detalhamento técnico: hashes, árvores estruturais, metadados completos, texto/OCR, fatos, limitações, execução e JSON.

## Progressive disclosure

O resumo mostra apenas campos prioritários que estejam presentes. Coleções e estruturas completas continuam acessíveis nas seções técnicas e em elementos expansíveis. A ausência de um campo não produz um valor estimado, uma contagem presumida ou uma provenance genérica.

## Proveniência

Proveniência é apresentada somente a partir de campos reais:

- `Fact.source` e `Fact.data` para fatos técnicos;
- `FindingContract.rule_id` e `evidence_refs` para findings individuais;
- `source_engine`, `evidence`, `entities`, `metadata` e `limitations` para correlações;
- `source_type`, `filename` ou `evidence_ref` para eventos da timeline.

Quando esses campos não existem, a interface não cria uma origem substituta.

## Estados semânticos

- Confirmação: fato positivo explicitamente reportado.
- Neutro: ausência ou indisponibilidade que não implica problema, como nenhuma assinatura criptográfica incorporada.
- Atenção: warning, divergência ou limitação reportada.
- Erro técnico: somente erro efetivamente reportado.

Revisão incremental, múltiplos EOFs e ausência de assinatura não são descritos como fraude ou adulteração.

## Timeline

Eventos com timestamp válido usam um eixo horizontal proporcional. A posição é calculada por `(evento - primeiro) / (último - primeiro)`, usando o intervalo global do conjunto mesmo quando filtros ocultam eventos. Assim, a referência espacial permanece estável durante a comparação.

Eventos temporalmente próximos mantêm sua coordenada real e recebem apenas lanes verticais diferentes para evitar colisão de labels. Timestamps iguais ocupam exatamente a mesma posição, também em lanes distintas. Um evento temporal isolado é centralizado. O eixo possui largura mínima e rolagem horizontal controlada para preservar legibilidade.

Cada marcador é um botão acessível e abre um painel com o timestamp e a provenance realmente disponível. Eventos com timestamp inválido ou `temporal_status: structural_only` são identificados como **Eventos sem data determinável**, ficam fora do eixo cronológico e nunca recebem uma posição temporal inventada. Warnings e limitações permanecem separados dos eventos.

## Findings e correlações

Findings são controles expansíveis acessíveis. O estado fechado mostra título e severidade; a expansão apresenta statement, regra, referências, confiança e outros campos existentes. Correlações seguem a mesma abordagem e listam os artefatos/evidências reportados pelo Analysis Set.

## Campos opcionais e limitações

O contrato usa mapas genéricos para `metadata` e `technical_structure`; nomes variam por parser e formato. O resumo reconhece apenas chaves técnicas conhecidas e mantém o restante na camada detalhada. Entidades individuais não possuem um campo dedicado universal: IPs vêm de `ip_addresses`, e outras entidades só aparecem quando entregues como fatos de entidade. A UI não infere validade criptográfica, autoria, autenticidade ou fraude.
