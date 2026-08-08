export interface InstitutionalReference {
  id: string
  title: string
  institution: string
  date: string
  category: string
  url: string
  purpose: string
}

export const references: InstitutionalReference[] = [
  {
    id: 'mp-2200-2',
    title: 'Medida Provisória nº 2.200-2, de 24 de agosto de 2001',
    institution: 'Presidência da República — Casa Civil',
    date: '2001',
    category: 'Legislação',
    url: 'https://www.planalto.gov.br/ccivil_03/mpv/antigas_2001/2200-2.htm',
    purpose: 'Instituição da ICP-Brasil e contexto jurídico de documentos eletrônicos.',
  },
  {
    id: 'lei-14063',
    title: 'Lei nº 14.063, de 23 de setembro de 2020',
    institution: 'Presidência da República — Secretaria-Geral',
    date: '2020',
    category: 'Legislação',
    url: 'https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm',
    purpose: 'Definições e classificação de assinaturas eletrônicas em seu âmbito legal.',
  },
  {
    id: 'iti-icp-brasil',
    title: 'ICP-Brasil',
    institution: 'Instituto Nacional de Tecnologia da Informação',
    date: 'Atualizado em 2025',
    category: 'Infraestrutura de confiança',
    url: 'https://www.gov.br/iti/pt-br/assuntos/icp-brasil',
    purpose: 'Descrição institucional da cadeia hierárquica de confiança da ICP-Brasil.',
  },
  {
    id: 'nist-fips-180-4',
    title: 'FIPS 180-4 — Secure Hash Standard',
    institution: 'National Institute of Standards and Technology',
    date: '2015',
    category: 'Padrão técnico',
    url: 'https://csrc.nist.gov/pubs/fips/180-4/upd1/final',
    purpose: 'Referência técnica para algoritmos de hash seguro, incluindo a família SHA-2.',
  },
]

export function getReference(id: string): InstitutionalReference | undefined {
  return references.find((reference) => reference.id === id)
}
