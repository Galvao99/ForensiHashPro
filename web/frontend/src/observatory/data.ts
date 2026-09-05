import type { ObservatoryArticle, RegulatoryItem, ResearchSource, StateResearch } from './models'
import { validateStateResearch, validateUniqueIds } from './models'

export const cnjResolution233: ResearchSource = {
  id: 'cnj-resolution-233-2016',
  title: 'Resolução CNJ nº 233, de 13 de julho de 2016',
  organization: 'Conselho Nacional de Justiça',
  url: 'https://atos.cnj.jus.br/atos/detalhar/2310',
  sourceType: 'CNJ_ACT',
  publishedAt: '2016-07-13',
  accessedAt: '2026-09-05',
  jurisdiction: 'Brasil',
  description: 'Dispõe sobre o cadastro de profissionais e órgãos técnicos ou científicos na Justiça de primeiro e segundo graus.',
}

const names: Record<string, string> = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal',
  ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MT: 'Mato Grosso', MS: 'Mato Grosso do Sul', MG: 'Minas Gerais',
  PA: 'Pará', PB: 'Paraíba', PR: 'Paraná', PE: 'Pernambuco', PI: 'Piauí', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
  RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima', SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe', TO: 'Tocantins',
}

export const stateResearch: StateResearch[] = Object.entries(names).map(([uf, stateName]) => ({
  uf, stateName, status: 'NOT_STARTED', methodologyVersion: 'v1.0', sources: [],
  limitations: ['Dados estaduais ainda não coletados ou consolidados.'],
}))

export const regulatoryItems: RegulatoryItem[] = [{
  id: 'cnj-resolution-233', slug: 'resolucao-cnj-233-cadastro-peritos',
  title: 'Resolução CNJ nº 233 estrutura cadastro de profissionais e órgãos técnicos',
  summary: 'A norma disciplina a criação e a manutenção de cadastros eletrônicos no âmbito da Justiça de primeiro e segundo graus.',
  category: 'CNJ', organization: 'Conselho Nacional de Justiça', publishedAt: '2016-07-13',
  status: 'ALTERADO', relevance: 'É uma referência normativa central para delimitar o objeto e as fontes da pesquisa sobre cadastros judiciais.',
  sources: [cnjResolution233], tags: ['cadastro', 'CPTEC', 'perícia judicial'],
}]

export const observatoryArticles: ObservatoryArticle[] = []

stateResearch.forEach(validateStateResearch)
validateUniqueIds(regulatoryItems)
