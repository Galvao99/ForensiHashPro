import type {
  CountType, CountUnit, MethodologyType, ObservatoryArticle, RegulatoryItem,
  ResearchCoverage, ResearchMetric, ResearchMetricId, ResearchSnapshot,
  ResearchSource, ResearchStatus, SpecialtyDictionaryEntry, StateResearch,
} from './models'
import { validateStateResearch, validateUniqueIds } from './models'

export const RESEARCH_VERSION = 'v1.2'
export const LATEST_SOURCE_ACCESS_DATE = '2026-09-08'
const PREVIOUS_SOURCE_ACCESS_DATE = '2026-09-05'

const source = (id: string, title: string, institution: string, url: string, accessedAt = PREVIOUS_SOURCE_ACCESS_DATE): ResearchSource => ({
  id, title, institution, url, sourceType: 'COURT_REGISTRY',
  accessedAt, jurisdiction: 'Brasil',
})

export const cnjResolution233: ResearchSource = {
  id: 'cnj-resolution-233-2016',
  title: 'Resolução CNJ nº 233, de 13 de julho de 2016',
  institution: 'Conselho Nacional de Justiça',
  url: 'https://atos.cnj.jus.br/atos/detalhar/2310',
  sourceType: 'CNJ_ACT',
  publishedAt: '2016-07-13',
  accessedAt: PREVIOUS_SOURCE_ACCESS_DATE,
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
  MG: source('tjmg-aj-public-experts', 'Sistema Eletrônico Auxiliares da Justiça — módulo de peritos', 'Tribunal de Justiça do Estado de Minas Gerais', 'https://aj.tjmg.jus.br/aj/internet/loginInternet.jsf', '2026-08-07'),
  DF: source('tjdft-active-public-experts', 'Consulta pública aos peritos com cadastro ativo', 'Tribunal de Justiça do Distrito Federal e dos Territórios', 'https://auxiliares-justica.tjdft.jus.br/#/consultaPublicaAuxiliarJustica', '2026-09-08'),
  SP: source('tjsp-public-court-assistants', 'Consulta pública de Auxiliares da Justiça', 'Tribunal de Justiça do Estado de São Paulo', 'https://www.tjsp.jus.br/auxiliaresjustica/auxiliarjustica/consultapublica', '2026-09-08'),
}

const snapshotId = (uf: string) => `snapshot-${uf.toLowerCase()}-${RESEARCH_VERSION}`
const metric = (
  uf: string, sourceId: string, metricId: ResearchMetricId, label: string, value: number,
  unit: CountUnit, countType: CountType, methodologyType: MethodologyType,
  comparability: ResearchMetric['comparability'] = 'NOT_COMPARABLE',
): ResearchMetric => ({ metricId, label, value, unit, countType, methodologyType, comparability, sourceId, snapshotId: snapshotId(uf) })
const snapshot = (uf: string, sourceId: string, notes?: string, collectedAt?: string): ResearchSnapshot => ({
  id: snapshotId(uf), version: RESEARCH_VERSION, sourceIds: [sourceId],
  methodologyVersion: RESEARCH_VERSION, notes, collectedAt,
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
  MG: {
    tribunal: 'TJMG', status: 'CONSOLIDATED', coverage: 'INTEGRAL_DEDUPLICATED', updatedAt: '2026-08-07',
    notes: 'Levantamento integral e deduplicado. A classificação preserva a prioridade Core FH > Adjacente dentro do tribunal.',
    sources: [courtSources.MG], snapshots: [snapshot('MG', courtSources.MG.id, 'Referência do agregado: 07/08/2026.', '2026-08-07')],
    metrics: [
      metric('MG', courtSources.MG.id, 'GENERAL', 'Cadastro Geral', 13644, 'UNIQUE_PROFESSIONALS', 'OBSERVED_COUNT', 'DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('MG', courtSources.MG.id, 'DIGITAL', 'Core FH', 137, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('MG', courtSources.MG.id, 'ADJACENT', 'Mercado adjacente classificado', 4598, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('MG', courtSources.MG.id, 'CORE_ADJACENT', 'Core + adjacente', 4735, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
    ],
  },
  DF: {
    tribunal: 'TJDFT', status: 'CONSOLIDATED', coverage: 'INTEGRAL', updatedAt: '2026-09-08',
    notes: 'Levantamento integral da base ativa consultada. A base pública é dinâmica. Mercado adjacente não quantificado.',
    observedDifficulties: ['A base pública consultada é dinâmica; o resultado representa o estado observado na data de referência.', 'O mercado adjacente não foi quantificado.'],
    sources: [courtSources.DF], snapshots: [snapshot('DF', courtSources.DF.id, 'Referência do levantamento: 08/09/2026.', '2026-09-08')],
    metrics: [
      metric('DF', courtSources.DF.id, 'GENERAL', 'Cadastro geral ativo observado', 1995, 'ACTIVE_REGISTRY_ENTRIES', 'OBSERVED_COUNT', 'DIRECT_OBSERVATION', 'DOCUMENTED_SCOPE_ONLY'),
      metric('DF', courtSources.DF.id, 'DIGITAL', 'Core FH', 91, 'IDENTIFIED_PROFESSIONALS', 'OBSERVED_COUNT', 'CLASSIFIED_COUNT', 'DOCUMENTED_SCOPE_ONLY'),
      metric('DF', courtSources.DF.id, 'SPECIALTIES_OBSERVED', 'Especialidades ativas observadas', 350, 'SPECIALTIES', 'OBSERVED_COUNT', 'DIRECT_OBSERVATION', 'DOCUMENTED_SCOPE_ONLY'),
      metric('DF', courtSources.DF.id, 'SPECIALTIES_CATALOG', 'Especialidades existentes no catálogo', 493, 'SPECIALTIES', 'OBSERVED_COUNT', 'DIRECT_OBSERVATION', 'DOCUMENTED_SCOPE_ONLY'),
    ],
  },
  SP: {
    tribunal: 'TJSP', status: 'PARTIAL', coverage: 'SUBSET', updatedAt: '2026-09-08',
    notes: 'A consulta pública exibe auxiliares com pelo menos uma nomeação. Core FH e adjacentes são limites inferiores observados na extração parcial (22,36%); não houve extrapolação para o estado.',
    observedDifficulties: ['A extração analisou 4.400 linhas, cerca de 22,36% dos 19.665 peritos ou entidades com nome visível na consulta pública.', 'A consulta pública não representa todos os profissionais cadastrados no estado.', 'Os códigos de tipo 70 e 74 foram preservados como dados brutos no levantamento de origem, sem equivalência presumida entre pessoa física e pessoa jurídica.'],
    sources: [courtSources.SP], snapshots: [snapshot('SP', courtSources.SP.id, 'Extração parcial de 4.400 linhas; 4.397 entidades únicas.', '2026-09-08')],
    metrics: [
      metric('SP', courtSources.SP.id, 'GENERAL', 'Total público visível', 19665, 'PUBLICLY_VISIBLE_NAMED_EXPERTS_OR_ENTITIES', 'OBSERVED_COUNT', 'DIRECT_OBSERVATION'),
      metric('SP', courtSources.SP.id, 'SOURCE_RECORDS', 'Linhas extraídas na análise parcial', 4400, 'SOURCE_RECORDS', 'SUBSET_COUNT', 'DIRECT_OBSERVATION'),
      metric('SP', courtSources.SP.id, 'RESEARCHED_SUBSET', 'Entidades únicas na extração', 4397, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'DEDUPLICATED_COUNT'),
      metric('SP', courtSources.SP.id, 'DIGITAL', 'Core FH observado na extração', 220, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT'),
      metric('SP', courtSources.SP.id, 'ADJACENT', 'Mercado adjacente observado na extração', 1215, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT'),
      metric('SP', courtSources.SP.id, 'CORE_ADJACENT', 'Core + adjacente observado', 1435, 'UNIQUE_PROFESSIONALS_IN_SUBSET', 'SUBSET_COUNT', 'CLASSIFIED_DEDUPLICATED_COUNT'),
      metric('SP', courtSources.SP.id, 'SPECIALTIES_OBSERVED', 'Especialidades observadas', 791, 'SPECIALTIES', 'SUBSET_COUNT', 'DIRECT_OBSERVATION'),
      metric('SP', courtSources.SP.id, 'SPECIALTIES_CATALOG', 'Especialidades existentes no catálogo consultado', 892, 'SPECIALTIES', 'OBSERVED_COUNT', 'DIRECT_OBSERVATION'),
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
const spDigitalSpecialties: Array<[string, number]> = [
  ['Análise de Sistemas e Tecnologias da Informação', 105],
  ['Computação e Informática', 101],
  ['Segurança da Informação', 76],
  ['Análise de Sistemas', 70],
  ['Ciências da Computação', 69],
  ['Tecnologia da Informação', 68],
  ['Computação', 60],
  ['Análise e Desenvolvimento de Sistemas', 55],
  ['Banco de Dados', 54],
  ['Gestão da Tecnologia da Informação', 52],
  ['Desenvolvimento de Sistemas de Informação', 51],
  ['Redes de Computadores', 44],
]
export const specialtyDictionary: SpecialtyDictionaryEntry[] = spDigitalSpecialties.map(([originalSpecialty, observedCount], index) => ({
  id: `tjsp-digital-specialty-${index + 1}`,
  originalSpecialty,
  tribunal: 'TJSP',
  normalizedCategory: 'Core FH',
  classificationRule: 'Especialidade digital explicitamente observada na extração parcial fornecida.',
  reviewStatus: 'REVIEWED',
  sourceId: courtSources.SP.id,
  observedCount,
}))

const observedCore = stateResearch.reduce((total, state) => total + (state.metrics.find(item => item.metricId === 'DIGITAL')?.value ?? 0), 0)
export const observedTotals = {
  core: observedCore,
  // Agregado consolidado fornecido para os tribunais em que houve classificação adjacente.
  adjacentClassified: 6690,
  coreAndAdjacent: observedCore + 6690,
  scope: 'OBSERVED_APPROXIMATION',
} as const

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
validateUniqueIds(specialtyDictionary)
validateUniqueIds(regulatoryItems)
