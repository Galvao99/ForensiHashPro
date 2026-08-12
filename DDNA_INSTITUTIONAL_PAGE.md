# Página institucional DDNA

## Objetivo e status

A rota pública `/ddna` apresenta a arquitetura DDNA de forma técnica e
didática. Ela não implementa custódia, manifesto, assinatura, timestamp,
ledger ou verificação. O produto aparece explicitamente como `Research /
Development` e o desenho pode mudar após implementação, testes de segurança e
estudos normativos.

## Narrativa

A página começa pela dificuldade de demonstrar, anos depois, o estado de um
arquivo que circulou entre sistemas. Em seguida separa identidade binária de
cadeia de custódia, define o T0, mostra aquisição integrada, Artifact Record e
Context Record, manifesto externo, CAdES destacada, timestamp e verificação.

Contratação eletrônica é apresentada apenas como um perfil. Selfie por hash é
expressamente distinguida de biometria; geolocalização de IP é descrita como
estimativa da fonte consultada; preservação DDNA e análise ForensiHash mantêm
papéis diferentes. Context Intelligence está rotulado como roadmap separado.

## Diagramas

Os diagramas são componentes React/CSS sem imagens ou biblioteca adicional:

1. circulação do arquivo;
2. hash e identidade binária;
3. T0;
4. T0 integrado;
5. Artifact versus Context;
6. arquivo e enriquecimento por formato;
7. Manifest/CAdES/timestamp;
8. DDNA Verify;
9. verificação independente;
10. Evidence Set de contratação;
11. selfie por hash;
12. snapshot contextual de IP;
13. Custody Ledger e hash chaining;
14. DDNA versus ForensiHash;
15. Context Engine futuro.

Todos usam HTML semântico, `role="img"` e descrição acessível. O layout passa
de grids para coluna única em telas estreitas, preservando texto e ordem de
leitura sem depender exclusivamente de cor.

## Decisões editoriais

Linguagem permitida: `propõe`, `busca`, `pretende`, `pode auxiliar`,
`arquitetura em desenvolvimento`.

Não são permitidas alegações de autenticidade absoluta, veracidade material,
eliminação de fraude, impossibilidade de adulteração, certificação ISO,
homologação governamental, reconhecimento judicial do produto ou
obrigatoriedade legal. O DDNA não descreve fatos anteriores ao T0.

CAdES é apresentada como proteção criptográfica do manifesto conforme a
infraestrutura de certificados utilizada. O manifesto referencia o arquivo. A
assinatura não transforma o conteúdo referenciado em materialmente verdadeiro.

## Fontes verificadas

- CPP, arts. 158-A a 158-F, e Lei 13.709/2018: Planalto;
- Jurisprudência em Teses 281, Informativos 811 e 878, Tema 1061 e REsp
  2.197.156-SP: STJ;
- ISO/IEC 27037:2012, 27041:2015, 27042:2015 e 27043:2015: ISO;
- ICP-Brasil, Autoridades de Carimbo do Tempo e VALIDAR: ITI/Gov.br.

Essas fontes contextualizam problemas técnicos e jurídicos. Não validam nem
recomendam o DDNA. Links externos abrem em nova aba com `noopener noreferrer`.

## SEO e acessibilidade

A rota define título e descrição próprios, preservando os valores globais ao
sair da página. O documento-base contém metadados Open Graph de site e tipo.
Headings são hierárquicos, CTAs são links nativos navegáveis por teclado, o
contraste usa os tokens dos temas existentes e o conteúdo permanece
compreensível sem cor.
