export const RESEARCH_STATUSES = ['CONSOLIDATED', 'PARTIAL', 'UNDER_REVIEW', 'NO_CONSOLIDATED_COUNT', 'IN_PROGRESS'] as const
export type ResearchStatus = typeof RESEARCH_STATUSES[number]

export const STATUS_LABELS: Record<ResearchStatus, string> = {
  CONSOLIDATED: 'Consolidado',
  PARTIAL: 'Parcial',
  UNDER_REVIEW: 'Em revisão',
  NO_CONSOLIDATED_COUNT: 'Sem quantitativo consolidado',
  IN_PROGRESS: 'Em levantamento',
}

export type ResearchSourceType = 'LAW' | 'CNJ_ACT' | 'COURT_ACT' | 'COURT_REGISTRY' | 'GOV_DATASET' | 'OFFICIAL_NEWS' | 'OTHER_PRIMARY' | 'SECONDARY'

export interface ResearchSource {
  id: string
  title: string
  institution: string
  url: string
  sourceType: ResearchSourceType
  publishedAt?: string
  accessedAt: string
  jurisdiction: string
  description?: string
}

export type ResearchMetricId = 'DIGITAL' | 'GENERAL' | 'SOURCE_RECORDS' | 'RESEARCHED_SUBSET' | 'CREDENTIAL_SPECIALTIES'
export type CountType = 'OBSERVED_COUNT' | 'ESTIMATE' | 'ADMINISTRATIVE_COUNT' | 'SUBSET_COUNT'
export type CountUnit = 'UNIQUE_PROFESSIONALS' | 'IDENTIFIED_PROFESSIONALS' | 'SOURCE_RECORDS' | 'UNIQUE_PROFESSIONALS_IN_SUBSET' | 'CLASSIFIED_RECORDS' | 'CREDENTIALS_AND_SPECIALTIES'
export type MethodologyType = 'DIRECT_OBSERVATION' | 'DEDUPLICATED_COUNT' | 'CLASSIFIED_COUNT' | 'CLASSIFIED_DEDUPLICATED_COUNT' | 'TERM_BASED_RESEARCH' | 'EXACT_TYPE_RESEARCH'
export type MetricComparability = 'DOCUMENTED_SCOPE_ONLY' | 'NOT_COMPARABLE'

export const COUNT_TYPE_LABELS: Record<CountType, string> = {
  OBSERVED_COUNT: 'Contagem observada',
  ESTIMATE: 'Estimativa',
  ADMINISTRATIVE_COUNT: 'Dado administrativo',
  SUBSET_COUNT: 'Contagem de recorte',
}

export const UNIT_LABELS: Record<CountUnit, string> = {
  UNIQUE_PROFESSIONALS: 'profissionais únicos identificados na base consultada',
  IDENTIFIED_PROFESSIONALS: 'profissionais identificados na classificação adotada',
  SOURCE_RECORDS: 'registros encontrados na fonte',
  UNIQUE_PROFESSIONALS_IN_SUBSET: 'profissionais únicos identificados no recorte pesquisado',
  CLASSIFIED_RECORDS: 'registros identificados nos tipos classificados',
  CREDENTIALS_AND_SPECIALTIES: 'credenciais/especialidades observadas; não equivale a pessoas únicas',
}

export const METHODOLOGY_LABELS: Record<MethodologyType, string> = {
  DIRECT_OBSERVATION: 'Contagem direta da fonte pública',
  DEDUPLICATED_COUNT: 'Contagem com deduplicação',
  CLASSIFIED_COUNT: 'Classificação segundo o recorte documentado',
  CLASSIFIED_DEDUPLICATED_COUNT: 'Deduplicação e classificação segundo o recorte documentado',
  TERM_BASED_RESEARCH: 'Pesquisa por termos; não representa a base integral',
  EXACT_TYPE_RESEARCH: 'Pesquisa por tipos exatos documentados',
}

export interface ResearchMetric {
  metricId: ResearchMetricId
  label: string
  value: number
  unit: CountUnit
  countType: CountType
  methodologyType: MethodologyType
  comparability: MetricComparability
  sourceId: string
  snapshotId: string
}

export interface ResearchSnapshot {
  id: string
  version: string
  collectedAt?: string
  publishedAt?: string
  sourceIds: string[]
  methodologyVersion: string
  notes?: string
}

export interface ResearchRevision {
  id: string
  date: string
  metricId?: ResearchMetricId
  oldValue?: number
  newValue?: number
  reason: string
  snapshotId: string
}

export interface SpecialtyDictionaryEntry {
  id: string
  originalSpecialty: string
  tribunal: string
  normalizedCategory: string
  classificationRule: string
  reviewStatus: 'REVIEWED' | 'UNDER_REVIEW'
  sourceId: string
}

export interface StateResearch {
  uf: string
  stateName: string
  tribunal?: string
  status: ResearchStatus
  coverage: ResearchCoverage
  updatedAt?: string
  methodologyVersion: string
  metrics: ResearchMetric[]
  snapshots: ResearchSnapshot[]
  revisions: ResearchRevision[]
  notes?: string
  limitations: string[]
  observedDifficulties: string[]
  sources: ResearchSource[]
}

export type ResearchCoverage = 'NOT_LOCATED' | 'SOURCE_CONFIRMED' | 'INTEGRAL' | 'INTEGRAL_DEDUPLICATED' | 'PUBLIC_LIST_DEDUPLICATED' | 'TERM_BASED_SUBSET' | 'EXACT_CORE_TYPES' | 'SUBSET' | 'RESTRICTED_ACCESS' | 'FILTERED_QUERY' | 'COLLECTION_INTERRUPTED' | 'SOURCE_UNAVAILABLE' | 'TAXONOMY_ONLY' | 'CREDENTIALS_ONLY'

export const COVERAGE_LABELS: Record<ResearchCoverage, string> = {
  NOT_LOCATED: 'Nenhuma base utilizável incorporada',
  SOURCE_CONFIRMED: 'Fonte oficial confirmada; quantitativo não consolidado',
  INTEGRAL: 'Levantamento integral',
  INTEGRAL_DEDUPLICATED: 'Base integral deduplicada',
  PUBLIC_LIST_DEDUPLICATED: 'Lista pública deduplicada',
  TERM_BASED_SUBSET: 'Recorte por termos',
  EXACT_CORE_TYPES: 'Classificação por tipos exatos do Núcleo Digital',
  SUBSET: 'Recorte pesquisado',
  RESTRICTED_ACCESS: 'Acesso principal restrito',
  FILTERED_QUERY: 'Consulta pública condicionada a filtros',
  COLLECTION_INTERRUPTED: 'Extração interrompida',
  SOURCE_UNAVAILABLE: 'Fonte indisponível durante a coleta',
  TAXONOMY_ONLY: 'Somente taxonomia observada',
  CREDENTIALS_ONLY: 'Credenciais/especialidades; não pessoas',
}

export interface RegulatoryItem {
  id: string
  slug: string
  title: string
  summary: string
  category: 'CNJ' | 'TRIBUNAIS' | 'LEGISLAÇÃO' | 'PREVIDENCIÁRIO' | 'PROCESSO_DIGITAL' | 'PROVA_TÉCNICA'
  institution: string
  publishedAt: string
  status: 'VIGENTE' | 'ALTERADO' | 'REVOGADO' | 'EM_ACOMPANHAMENTO'
  relevance: string
  sources: ResearchSource[]
  tags: string[]
}

export interface ObservatoryArticle {
  id: string
  slug: string
  type: 'ARTIGO' | 'ESTUDO' | 'NOTA_TÉCNICA'
  title: string
  publishedAt: string
  author: string
  summary: string
  body: string[]
  sources: ResearchSource[]
  methodologyVersion?: string
  tags: string[]
}

export function metricFor(state: StateResearch, metricId: ResearchMetricId): ResearchMetric | undefined {
  return state.metrics.find(metric => metric.metricId === metricId)
}

const UF_PATTERN = /^(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$/

export function validateStateResearch(state: StateResearch): void {
  if (!UF_PATTERN.test(state.uf)) throw new Error(`Invalid UF: ${state.uf}`)
  const sourceIds = new Set(state.sources.map(source => source.id))
  const snapshotIds = new Set(state.snapshots.map(snapshot => snapshot.id))
  for (const metric of state.metrics) {
    if (!Number.isInteger(metric.value) || metric.value < 0) throw new Error(`Invalid metric value for ${state.uf}:${metric.metricId}`)
    if (!sourceIds.has(metric.sourceId)) throw new Error(`Metric source is missing for ${state.uf}:${metric.metricId}`)
    if (!snapshotIds.has(metric.snapshotId)) throw new Error(`Metric snapshot is missing for ${state.uf}:${metric.metricId}`)
    if (metric.countType === 'ADMINISTRATIVE_COUNT' && metric.unit === 'UNIQUE_PROFESSIONALS') throw new Error(`Administrative count cannot represent unique professionals for ${state.uf}`)
    if (metric.countType === 'SUBSET_COUNT' && metric.comparability !== 'NOT_COMPARABLE') throw new Error(`Subset count cannot be marked comparable for ${state.uf}`)
  }
  if (new Set(state.metrics.map(metric => metric.metricId)).size !== state.metrics.length) throw new Error(`Duplicate metric for ${state.uf}`)
  for (const source of state.sources) {
    const url = new URL(source.url)
    if (!['https:', 'http:'].includes(url.protocol)) throw new Error(`Invalid source URL: ${source.id}`)
    if (Number.isNaN(Date.parse(source.accessedAt))) throw new Error(`Invalid access date: ${source.id}`)
  }
}

export function validateUniqueIds<T extends { id: string }>(items: T[]): void {
  if (new Set(items.map(item => item.id)).size !== items.length) throw new Error('Duplicate content ID')
}
