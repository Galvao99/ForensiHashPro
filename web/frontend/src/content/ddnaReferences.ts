export interface DdnaReference {
  id: string
  institution: string
  date: string
  title: string
  summary: string
  href: string
}

export const ddnaReferences: DdnaReference[] = [
  {
    id: 'cpp-158', institution: 'Planalto', date: '1941 · atualização de 2019',
    title: 'Código de Processo Penal — arts. 158-A a 158-F',
    summary: 'Formaliza, no processo penal, procedimentos para manter e documentar a história cronológica do vestígio. Não impõe o uso do DDNA por organizações privadas.',
    href: 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm',
  },
  {
    id: 'stj-teses-281', institution: 'STJ', date: '3 jun. 2026',
    title: 'Jurisprudência em Teses 281 — prova digital',
    summary: 'Destaca preservação da cadeia de custódia, exame técnico independente e mecanismos como hash para integridade, auditabilidade e mesmidade.',
    href: 'https://www.stj.jus.br/sites/portalp/paginas/comunicacao/noticias/2026/03062026-nova-edicao-de-jurisprudencia-em-teses-traz-entendimentos-sobre-prova-digital-e-dados-estaticos-de-conexao.aspx',
  },
  {
    id: 'stj-inf-878', institution: 'STJ', date: '24 fev. 2026',
    title: 'Informativo 878 — AgRg no HC 1.014.212-ES',
    summary: 'Trata da confirmação técnica da fidedignidade de prova digital diante de dúvida razoável e ausência de certificação de integridade, sem extrapolar as circunstâncias do caso.',
    href: 'https://scon.stj.jus.br/jurisprudencia/externo/informativo/?acao=pesquisar&aplicacao=informativo&b=INFJ&i=21&l=20&livre=%22HC%22&p=true&refinar=S.DISP.',
  },
  {
    id: 'stj-inf-811', institution: 'STJ', date: '14 mai. 2024',
    title: 'Informativo 811 — mesmidade e auditabilidade',
    summary: 'Relaciona hash à verificação de mesmidade e enfatiza documentação, auditabilidade, repetibilidade e reprodutibilidade no tratamento da evidência digital.',
    href: 'https://processo.stj.jus.br/docs_internet/informativos/PDF/Inf0811.pdf',
  },
  {
    id: 'stj-tema-1061', institution: 'STJ', date: 'Tema repetitivo · 2021',
    title: 'Tema 1061 — assinatura em contrato bancário',
    summary: 'Quando o consumidor impugna a autenticidade da assinatura em contrato bancário juntado pela instituição, cabe à instituição provar a autenticidade. O tema não exige DDNA.',
    href: 'https://processo.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp?cod_tema_final=1061&cod_tema_inicial=1061&novaConsulta=true&tipo_pesquisa=T',
  },
  {
    id: 'stj-resp-2197156', institution: 'STJ', date: '18 mar. 2026',
    title: 'REsp 2.197.156-SP — contratação eletrônica',
    summary: 'Decisão da Terceira Turma que avaliou um conjunto de elementos eletrônicos, incluindo dados, selfie, documentos, geolocalização e dispositivo. É um caso concreto, não uma regra geral.',
    href: 'https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2026/18032026-Terceira-Turma-valida-emprestimo-digital-com-assinatura-em-plataforma-nao-certificada-pela-ICP-Brasil.aspx',
  },
  {
    id: 'iso-27037', institution: 'ISO', date: '2012',
    title: 'ISO/IEC 27037:2012',
    summary: 'Guidelines for identification, collection, acquisition and preservation of digital evidence.',
    href: 'https://www.iso.org/standard/44381.html',
  },
  {
    id: 'iso-27041', institution: 'ISO', date: '2015',
    title: 'ISO/IEC 27041:2015',
    summary: 'Guidance on assuring suitability and adequacy of incident investigative method.',
    href: 'https://www.iso.org/standard/44405.html',
  },
  {
    id: 'iso-27042', institution: 'ISO', date: '2015',
    title: 'ISO/IEC 27042:2015',
    summary: 'Guidelines for the analysis and interpretation of digital evidence, com continuidade, validade, repetibilidade e reprodutibilidade.',
    href: 'https://www.iso.org/standard/44406.html',
  },
  {
    id: 'iso-27043', institution: 'ISO', date: '2015',
    title: 'ISO/IEC 27043:2015',
    summary: 'Incident investigation principles and processes.',
    href: 'https://www.iso.org/standard/44407.html',
  },
  {
    id: 'icp-brasil', institution: 'ITI', date: 'atualizado em 2025',
    title: 'Infraestrutura de Chaves Públicas Brasileira',
    summary: 'Apresenta a cadeia hierárquica de confiança da ICP-Brasil e seus participantes, incluindo autoridades certificadoras e de carimbo do tempo.',
    href: 'https://www.gov.br/iti/pt-br/assuntos/icp-brasil',
  },
  {
    id: 'validar-iti', institution: 'ITI', date: 'serviço oficial',
    title: 'VALIDAR — validação de assinaturas eletrônicas',
    summary: 'Serviço do ITI para aferir o status de assinaturas eletrônicas; o próprio serviço distingue validação da assinatura de veracidade do conteúdo.',
    href: 'https://validar.iti.gov.br/index.html',
  },
  {
    id: 'lgpd', institution: 'Planalto', date: '2018',
    title: 'Lei 13.709/2018 — LGPD',
    summary: 'Disciplina o tratamento de dados pessoais, inclusive nos meios digitais. Custódia técnica não afasta finalidade, minimização, retenção, segurança e governança.',
    href: 'https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm',
  },
]
