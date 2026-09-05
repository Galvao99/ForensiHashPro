export const RESEARCH_STATUSES = ['NOT_STARTED', 'IN_RESEARCH', 'PARTIAL', 'COMPLETED', 'NEEDS_REVIEW'] as const
export type ResearchStatus = typeof RESEARCH_STATUSES[number]

export const STATUS_LABELS: Record<ResearchStatus, string> = {
  NOT_STARTED: 'Não iniciado', IN_RESEARCH: 'Em pesquisa', PARTIAL: 'Parcial',
  COMPLETED: 'Concluído', NEEDS_REVIEW: 'Em revisão',
}

export type ResearchSourceType = 'LAW' | 'CNJ_ACT' | 'COURT_ACT' | 'COURT_REGISTRY' | 'GOV_DATASET' | 'OFFICIAL_NEWS' | 'OTHER_PRIMARY' | 'SECONDARY'

export interface ResearchSource {
  id: string
  title: string
  organization: string
  url: string
  sourceType: ResearchSourceType
  publishedAt?: string
  accessedAt: string
  jurisdiction: string
  description?: string
}

export interface PopulationData {
  value: number
  referenceYear: number
  source: ResearchSource
}

export interface StateResearch {
  uf: string
  stateName: string
  status: ResearchStatus
  sourceRecordsCount?: number
  uniqueProfessionalsCount?: number
  specialtiesCount?: number
  population?: PopulationData
  collectionDate?: string
  lastReviewedAt?: string
  methodologyVersion: string
  notes?: string
  limitations: string[]
  sources: ResearchSource[]
}

export interface RegulatoryItem {
  id: string
  slug: string
  title: string
  summary: string
  category: 'CNJ' | 'TRIBUNAIS' | 'LEGISLAÇÃO' | 'PREVIDENCIÁRIO' | 'PROCESSO_DIGITAL' | 'PROVA_TÉCNICA'
  organization: string
  publishedAt: string
  effectiveAt?: string
  updatedAt?: string
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
  updatedAt?: string
  author: string
  summary: string
  body: string[]
  sources: ResearchSource[]
  methodologyVersion?: string
  tags: string[]
}

export function professionalsPer100k(state: StateResearch): number | undefined {
  const count = state.uniqueProfessionalsCount
  const population = state.population?.value
  if (count === undefined || population === undefined || population <= 0) return undefined
  return count / population * 100_000
}

export function isComparable(state: StateResearch): boolean {
  return state.status === 'COMPLETED'
}

export function comparableRanking(states: StateResearch[], metric: (state: StateResearch) => number | undefined) {
  return states.flatMap(state => {
    const value = isComparable(state) ? metric(state) : undefined
    return value === undefined ? [] : [{ state, value }]
  }).sort((left, right) => right.value - left.value || left.state.uf.localeCompare(right.state.uf))
}

const UF_PATTERN = /^(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$/

export function validateStateResearch(state: StateResearch): void {
  if (!UF_PATTERN.test(state.uf)) throw new Error(`Invalid UF: ${state.uf}`)
  for (const [field, value] of Object.entries({ sourceRecordsCount: state.sourceRecordsCount, uniqueProfessionalsCount: state.uniqueProfessionalsCount, specialtiesCount: state.specialtiesCount })) {
    if (value !== undefined && (!Number.isInteger(value) || value < 0)) throw new Error(`Invalid ${field} for ${state.uf}`)
  }
  if (state.population && (!Number.isInteger(state.population.value) || state.population.value <= 0)) throw new Error(`Invalid population for ${state.uf}`)
  for (const source of [...state.sources, ...(state.population ? [state.population.source] : [])]) {
    const url = new URL(source.url)
    if (url.protocol !== 'https:' && url.protocol !== 'http:') throw new Error(`Invalid source URL: ${source.id}`)
    if (Number.isNaN(Date.parse(source.accessedAt))) throw new Error(`Invalid access date: ${source.id}`)
  }
}

export function validateUniqueIds<T extends { id: string }>(items: T[]): void {
  if (new Set(items.map(item => item.id)).size !== items.length) throw new Error('Duplicate content ID')
}
