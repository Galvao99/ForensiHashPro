# ForensiHash – DDNA Snapshot

## Definição

**ForensiHash – DDNA Snapshot é um registro técnico derivado dos resultados de uma análise ForensiHash.** Ele documenta o que a ferramenta observou ou produziu durante uma análise individual específica.

O Snapshot não descreve a história original do artefato e não transfere para o momento da pactuação nenhuma observação feita posteriormente pelo ForensiHash.

## Não é

- DDNA Manifest;
- cadeia de custódia original;
- assinatura digital;
- CAdES;
- timestamp ICP-Brasil;
- certificado;
- prova de pactuação;
- preservação retroativa;
- DDNA Core ou ledger.

## Arquitetura

A geração ocorre no backend Web, dentro da infraestrutura ForensiHash, usando PyMuPDF já presente no projeto. Nenhum dado é enviado para serviço externo e o navegador não usa `window.print()`.

O endpoint autenticado é:

```text
POST /api/v1/analyses/{analysis_id}/ddna-snapshot
```

Ele exige CSRF e resolve o contrato exclusivamente em resultados individuais pertencentes ao usuário:

- resultado privado ainda não expirado no job; ou
- resultado cuja retenção foi autorizada em `StoredAnalysis`.

Análises de outros usuários retornam a mesma ausência utilizada para recursos não encontrados, evitando exposição de ownership.

## Pacote gerado

Uma requisição gera um ZIP chamado:

```text
forensihash_ddna_snapshot_<analysis_id>.zip
```

Conteúdo:

```text
forensihash_ddna_snapshot_<analysis_id>.pdf
forensihash_ddna_snapshot_<analysis_id>.sha256
```

O ZIP não é chamado de Evidence Package DDNA.

## PDF

O relatório possui capa off-white, branding ARQEN discreto, marca ForensiHash predominante, tipografia técnica, linhas finas, hashes monoespaçados e páginas numeradas.

Seções, quando existirem dados reais:

1. identificação do Snapshot;
2. artefato analisado;
3. identificação técnica;
4. hashes do artefato;
5. metadados;
6. estrutura;
7. assinaturas incorporadas;
8. findings;
9. limitações;
10. processamento ForensiHash;
11. provenance/references;
12. integridade do Snapshot.

Campos são ordenados, limitados em tamanho e tratados como texto, sem interpretação HTML. Paths, tokens, secrets, staging e outros campos internos são excluídos. Texto OCR integral e conteúdo binário bruto não são exportados nesta versão.

## Hash do Snapshot

A sequência é obrigatoriamente:

```text
finalizar PDF
→ obter bytes finais
→ calcular SHA-256
→ escrever arquivo .sha256
→ empacotar PDF e checksum
```

Formato:

```text
SHA256(forensihash_ddna_snapshot_<analysis_id>.pdf)=<digest hexadecimal>
```

O PDF não contém seu próprio digest final. Inserir esse digest alteraria os bytes que ele pretende verificar e criaria uma recursão inválida. O PDF contém os hashes do artefato analisado e aponta para o arquivo `.sha256` como verificação do próprio relatório.

## Free e Pro

O Snapshot Free exporta somente identificação, hashes, metadados, estrutura, assinatura básica, findings, limitações e execução efetivamente produzidos. Capabilities não executadas podem aparecer discretamente como limitações de escopo, nunca como resultado vazio ou falha.

O mesmo gerador aceita contratos Pro e preserva os dados atualmente selecionados. Enriquecimentos específicos como OCR integral, entidades, timeline, biometria, correlação e Analysis Set Snapshot ficam fora desta primeira versão.

## Determinismo e idempotência

Ordem de mapas, metadata PDF e timestamps ZIP são controlados. O timestamp de geração e o Snapshot ID são explícitos e variam entre gerações. Uma única requisição executa uma única geração, sem loops ou retries internos.

## Relação futura com DDNA

Uma evolução futura poderá usar o fluxo:

```text
ForensiHash Snapshot
→ DDNA Evidence Adapter
→ DDNA Canonical Model
```

Esse adapter e qualquer dependência do DDNA Core não fazem parte desta implementação.

## Limitações

- documento não assinado digitalmente;
- sem timestamp confiável externo;
- não prova eventos anteriores à análise;
- resultado limitado ao contrato individual disponível;
- ausência de informação não significa inexistência de evento;
- novas gerações legítimas possuem Snapshot ID, timestamp e hash diferentes.

