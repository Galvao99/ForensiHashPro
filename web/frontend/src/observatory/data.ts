import type {
  CountType, CountUnit, MethodologyType, ObservatoryArticle, RegulatoryItem,
  ResearchCoverage, ResearchMetric, ResearchMetricId, ResearchSnapshot,
  ResearchSource, ResearchStatus, SpecialtyDictionaryEntry, StateResearch,
} from './models'
import { validateStateResearch, validateUniqueIds } from './models'

export const RESEARCH_VERSION = 'v1.1'
export const LATEST_SOURCE_ACCESS_DATE = '2026-09-05'

const source = (id: string, title: string, institution: string, url: string): ResearchSource => ({
  id, title, institution, url, sourceType: 'COURT_REGISTRY',
  accessedAt: LATEST_SOURCE_ACCESS_DATE, jurisdiction: 'Brasil',
})

export const cnjResolution233: ResearchSource = {
  id: 'cnj-resolution-233-2016',
  title: 'Resolução CNJ nº 233, de 13 de julho de 2016',
  institution: 'Conselho Nacional de Justiça',
  url: 'https://atos.cnj.jus.br/atos/detalhar/2310',
  sourceType: 'CNJ_ACT',
  publishedAt: '2016-07-13',
  accessedAt: LATEST_SOURCE_ACCESS_DATE,
  jurisdiction: 'Brasil',
  description: 'Dispõe sobre o cadastro de profissionais e órgãos técnicos ou científicos na Justiça de primeiro e segundo graus.',
}

const courtSources = {
  RJ: source('tjrj-public-experts', 'Lista de peritos', 'Tribunal de Justiça do Estado do Rio de Janeiro', 'https://www.tjrj.jus.br/servicos/peritos/lista-de-peritos'),
  SE: source('tjse-public-experts', 'Peritos', 'Tribunal de Justiça do Estado de Sergipe', 'https://www.tjse.jus.br/portal/servicos/judiciais/peritos'),
  PI: source('tjpi-public-experts', 'Cadastro de peritos', 'Tribunal de Justiça do Estado do Piauí', 'https://www.tjpi.jus.br/portaltjpi/servicos/cadastro-de-peritos/'),
  AP: source('tjap-public-experts', 'Lista pública de peritos', 'Tribunal de Justiça do Estado do Amapá', 'https://sig.tjap.jus.br/sgpe_grid_peritos/sgpe_grid_peritos.php'),
  PA: source('tjpa-public-experts', 'Peritos cadastrados', 'Tribunal de Justiça do Estado do Pará', 'https://apps.tjpa.jus.br/capjus/peritos-cadastrados'),
  TO: source('tjto-public-experts', 'Relação de profissionais credenciados e peritos cadastrados', 'Corregedoria-Geral da Justiça do Tocantins', 'https://corregedoria.tjto.jus.br/component/content/article/corregedoria-geral-da-justica-disponibiliza-relacao-de-profissionais-credenciados-e-peritos-cadastrados-em-seu-portal?catid=8&layout=blog'),
  RR: source('tjrr-public-experts', 'Credenciamentos — Cadastro Eletrônico de Peritos', 'Tribunal de Justiça do Estado de Roraima', 'https://www.tjrr.jus.br/index.php/credenciamentos-subalc'),
  PR: source('tjpr-caju', 'Cadastro de Auxiliares da Justiça', 'Tribunal de Justiça do Estado do Paraná', 'https://portal.tjpr.jus.br/caju/publico/credencial/perito.do?tjpr.url.crypto=8a6c53f8698c7ff7d88bd1d17bac0727d751336abc0458fc1ba0bb4c6e9b4853'),
}

const snapshotId = (uf: string) => `snapshot-${uf.toLowerCase()}-${RESEARCH_VERSION}`
const metric = (
  uf: string, sourceId: string, metricId: ResearchMetricId, label: string, value: number,
  unit: CountUnit, countType: CountType, methodologyType: MethodologyType,
  comparability: ResearchMetric['comparability'] = 'NOT_COMPARABLE',
): ResearchMetric => ({ metricId, label, value, unit, countType, methodologyType, comparability, sourceId, snapshotId: snapshotId(uf) })
const snapshot = (uf: string, sourceId: string, notes?: string): ResearchSnapshot => ({
  id: snapshotId(uf), version: RESEARCH_VERSION, sourceIds: [sourceId],
  methodologyVersion: RESEARCH_VERSION, notes,
})

const names: Record<string, string> = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceará',
  DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão',
  MT: 'Mato Grosso', MS: 'Mato Grosso do Sul', MG: 'Minas Gerais', PA: 'Pará',
  PB: 'Paraíba', PR: 'Paraná', PE: 'Pernambuco', PI: 'Piauí', RJ: 'Rio de Janeiro',
  RN: 'Rio Grande do Norte', RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima',
  SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe', TO: 'Tocantins',
}

type StateSeed = Partial<Omit<StateResearch, 'uf' | 'stateName'>> & {
  status: ResearchStatus
  coverage: ResearchCoverage
}

const researched: Record<string, StateSeed> = {
  RJ: {
    tribunal: 'TJRJ', status: 'CONSOLIDATED', coverage: 'INTEGRAL_DEDUPLICATED',
    notes: 'Núcleo Digital previamente classificado na base deduplicada do tribunal.',
    sources: [courtSources.RJ], snapshots: [snapshot('RJ', courtSources.RJ.id)],
    metrics: [
      metric('RJ', courtSources.RJ.id, 'SOURCE_RECORDS', 'Registros encontrados', 12165, 'SOURCE_RECORDS', 'ADMINISTRATIVE_COUNT', 'DIRECT_OBSERVATION'),
      metric('RJ', courtSources.RJ.id, 'GENERAL', 'Cadastro Geral', 10804, 'UNIQUE_PROFESSIONALS', 'OBSERVED_COUNT', 'DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('RJ', courtSources.RJ.id, 'DIGITAL', 'Núcleo Digital', 187, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
    ],
  },
  SE: {
    tribunal: 'TJSE', status: 'CONSOLIDATED', coverage: 'INTEGRAL',
    notes: 'Levantamento integral com classificação do Núcleo Digital.',
    sources: [courtSources.SE], snapshots: [snapshot('SE', courtSources.SE.id)],
    metrics: [
      metric('SE', courtSources.SE.id, 'SOURCE_RECORDS', 'Registros encontrados', 1999, 'SOURCE_RECORDS', 'ADMINISTRATIVE_COUNT', 'DIRECT_OBSERVATION'),
      metric('SE', courtSources.SE.id, 'DIGITAL', 'Núcleo Digital', 45, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
    ],
  },
  PI: {
    tribunal: 'TJPI', status: 'PARTIAL', coverage: 'TERM_BASED_SUBSET',
    notes: 'Recorte por termos; não representa o cadastro integral.',
    observedDifficulties: ['A pesquisa disponível é um recorte por termos e não representa a base integral.'],
    sources: [courtSources.PI], snapshots: [snapshot('PI', courtSources.PI.id)],
    metrics: [
      metric('PI', courtSources.PI.id, 'RESEARCHED_SUBSET', 'Profissionais únicos no recorte', 374, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'TERM_BASED_RESEARCH'),
      metric('PI', courtSources.PI.id, 'DIGITAL', 'Núcleo Digital', 51, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'TERM_BASED_RESEARCH'),
    ],
  },
  AP: {
    tribunal: 'TJAP', status: 'CONSOLIDATED', coverage: 'INTEGRAL_DEDUPLICATED',
    notes: 'Lista pública integral deduplicada.',
    sources: [courtSources.AP], snapshots: [snapshot('AP', courtSources.AP.id)],
    metrics: [
      metric('AP', courtSources.AP.id, 'GENERAL', 'Cadastro Geral', 352, 'UNIQUE_PROFESSIONALS', 'OBSERVED_COUNT', 'DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('AP', courtSources.AP.id, 'DIGITAL', 'Núcleo Digital', 11, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
    ],
  },
  PA: {
    tribunal: 'TJPA', status: 'CONSOLIDATED', coverage: 'PUBLIC_LIST_DEDUPLICATED',
    notes: '577 profissionais únicos identificados entre 918 linhas públicas.',
    observedDifficulties: ['A lista pública continha mais linhas do que profissionais únicos identificados, exigindo deduplicação.'],
    sources: [courtSources.PA], snapshots: [snapshot('PA', courtSources.PA.id)],
    metrics: [
      metric('PA', courtSources.PA.id, 'SOURCE_RECORDS', 'Linhas públicas observadas', 918, 'SOURCE_RECORDS', 'ADMINISTRATIVE_COUNT', 'DIRECT_OBSERVATION'),
      metric('PA', courtSources.PA.id, 'GENERAL', 'Cadastro Geral', 577, 'UNIQUE_PROFESSIONALS', 'OBSERVED_COUNT', 'DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('PA', courtSources.PA.id, 'DIGITAL', 'Núcleo Digital', 10, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
    ],
  },
  TO: {
    tribunal: 'TJTO', status: 'PARTIAL', coverage: 'EXACT_CORE_TYPES',
    notes: 'Tipos exatos Analista de TI + Forense. A base geral observada não é tratada como total comparável de pessoas.',
    observedDifficulties: ['O quantitativo do Núcleo Digital está limitado aos tipos exatos pesquisados.', 'A base geral observada não é tratada como total comparável de pessoas.'],
    sources: [courtSources.TO], snapshots: [snapshot('TO', courtSources.TO.id)],
    metrics: [
      metric('TO', courtSources.TO.id, 'SOURCE_RECORDS', 'Registros observados', 5272, 'SOURCE_RECORDS', 'ADMINISTRATIVE_COUNT', 'DIRECT_OBSERVATION'),
      metric('TO', courtSources.TO.id, 'DIGITAL', 'Núcleo Digital', 116, 'CLASSIFIED_RECORDS', 'SUBSET_COUNT', 'EXACT_TYPE_RESEARCH'),
    ],
  },
  RR: {
    tribunal: 'TJRR', status: 'PARTIAL', coverage: 'SUBSET',
    notes: 'Pessoas únicas no recorte; não representa o cadastro integral.',
    observedDifficulties: ['O quantitativo disponível corresponde a um recorte, não ao cadastro integral.'],
    sources: [courtSources.RR], snapshots: [snapshot('RR', courtSources.RR.id)],
    metrics: [
      metric('RR', courtSources.RR.id, 'RESEARCHED_SUBSET', 'Profissionais únicos no recorte', 13, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'DIRECT_OBSERVATION'),
      metric('RR', courtSources.RR.id, 'DIGITAL', 'Núcleo Digital', 13, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'CLASSIFIED_COUNT'),
    ],
  },
  AL: { tribunal: 'TJAL', status: 'PARTIAL', coverage: 'COLLECTION_INTERRUPTED', notes: 'Portal oficial confirmado; extração interrompida na rodada anterior.', observedDifficulties: ['A extração foi interrompida na rodada documentada.'] },
  BA: { tribunal: 'TJBA', status: 'IN_PROGRESS', coverage: 'SOURCE_CONFIRMED', notes: 'Fonte pública oficial confirmada; sem quantitativo consolidado.' },
  CE: { tribunal: 'TJCE', status: 'IN_PROGRESS', coverage: 'SOURCE_CONFIRMED', notes: 'Sistema CPTEC confirmado; lista pública agregada exportável não localizada.', observedDifficulties: ['Lista pública agregada exportável não localizada.'] },
  MA: { tribunal: 'TJMA', status: 'PARTIAL', coverage: 'RESTRICTED_ACCESS', notes: 'Sistema confirmado; acesso principal restrito por autenticação.', observedDifficulties: ['O acesso principal ao sistema é restrito por autenticação.'] },
  PB: { tribunal: 'TJPB', status: 'PARTIAL', coverage: 'FILTERED_QUERY', notes: 'Consulta pública requer filtros; não há agregado consolidado.', observedDifficulties: ['A consulta pública requer filtros e não apresenta agregado consolidado.'] },
  PE: { tribunal: 'TJPE', status: 'PARTIAL', coverage: 'SOURCE_UNAVAILABLE', notes: 'Fonte oficial confirmada; endpoint público indisponível durante a coleta.', observedDifficulties: ['O endpoint público estava indisponível durante a coleta documentada.'] },
  RN: { tribunal: 'TJRN', status: 'IN_PROGRESS', coverage: 'SOURCE_CONFIRMED', notes: 'Fonte pública confirmada; sem resultado quantitativo consolidado.' },
  PR: {
    tribunal: 'TJPR', status: 'PARTIAL', coverage: 'CREDENTIALS_ONLY',
    notes: '35.373 credenciais/especialidades observadas. Uma mesma pessoa pode possuir múltiplas credenciais.',
    observedDifficulties: ['O dado disponível representa credenciais/especialidades, não pessoas únicas.'],
    sources: [courtSources.PR], snapshots: [snapshot('PR', courtSources.PR.id)],
    metrics: [metric('PR', courtSources.PR.id, 'CREDENTIAL_SPECIALTIES', 'Credenciais/especialidades', 35373, 'CREDENTIALS_AND_SPECIALTIES', 'ADMINISTRATIVE_COUNT', 'DIRECT_OBSERVATION')],
  },
  SC: { tribunal: 'TJSC', status: 'IN_PROGRESS', coverage: 'SOURCE_CONFIRMED', notes: 'Sistema confirmado; total público agregado não localizado.', observedDifficulties: ['Total público agregado não localizado.'] },
  RS: { tribunal: 'TJRS', status: 'PARTIAL', coverage: 'TAXONOMY_ONLY', notes: 'Taxonomia e categorias observadas; nomes e contagens não foram consolidados com confiabilidade.', observedDifficulties: ['Apenas a taxonomia foi consolidada; nomes e contagens não foram incorporados.'] },
}

const commonLimitation = 'A presença no cadastro não implica atuação efetiva, disponibilidade atual ou número de nomeações.'
export const stateResearch: StateResearch[] = Object.entries(names).map(([uf, stateName]) => {
  const seed = researched[uf]
  if (!seed) return {
    uf, stateName, status: 'NO_CONSOLIDATED_COUNT', methodologyVersion: RESEARCH_VERSION,
    coverage: 'NOT_LOCATED', metrics: [], snapshots: [], revisions: [], sources: [],
    limitations: [commonLimitation], observedDifficulties: [],
  }
  return {
    uf, stateName, methodologyVersion: RESEARCH_VERSION,
    metrics: [], snapshots: [], revisions: [], sources: [],
    limitations: [commonLimitation], observedDifficulties: [], ...seed,
  }
})

export const researchSnapshots = stateResearch.flatMap(state => state.snapshots)
export const researchRevisions = stateResearch.flatMap(state => state.revisions)
export const specialtyDictionary: SpecialtyDictionaryEntry[] = []

export const regulatoryItems: RegulatoryItem[] = [{
  id: 'cnj-resolution-233',
  slug: 'resolucao-cnj-233-cadastro-peritos',
  title: 'Resolução CNJ nº 233 estrutura cadastro de profissionais e órgãos técnicos',
  summary: 'A norma disciplina a criação e a manutenção de cadastros eletrônicos no âmbito da Justiça de primeiro e segundo graus.',
  category: 'CNJ',
  institution: 'Conselho Nacional de Justiça',
  publishedAt: '2016-07-13',
  status: 'ALTERADO',
  relevance: 'É uma referência normativa central para delimitar o objeto e as fontes da pesquisa sobre cadastros judiciais.',
  sources: [cnjResolution233],
  tags: ['cadastro', 'CPTEC', 'perícia judicial'],
}]

export const observatoryArticles: ObservatoryArticle[] = []

stateResearch.forEach(validateStateResearch)
validateUniqueIds([...Object.values(courtSources), cnjResolution233])
validateUniqueIds(regulatoryItems)
