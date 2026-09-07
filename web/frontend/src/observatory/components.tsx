import { Link } from 'react-router-dom'
import type { ResearchMetric, ResearchSource, ResearchStatus, StateResearch } from './models'
import {
  COUNT_TYPE_LABELS, COVERAGE_LABELS, METHODOLOGY_LABELS, STATUS_LABELS,
  UNIT_LABELS, metricFor,
} from './models'

export function formatResearchDate(value: string): string {
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

export function BackLink({ to = '/observatorio', children = 'Voltar ao Observatório' }: { to?: string; children?: string }) {
  return <nav className="observatory-back" aria-label="Navegação de retorno"><Link to={to}>← {children}</Link></nav>
}

export function ResearchStatusBadge({ status }: { status: ResearchStatus }) {
  return <span className={`research-status research-status--${status.toLowerCase()}`}>{STATUS_LABELS[status]}</span>
}

export function SourceList({ sources }: { sources: ResearchSource[] }) {
  if (!sources.length) return <p className="observatory-empty">Fonte documental ainda não incorporada à publicação.</p>
  return <ol className="observatory-sources">{sources.map(source => <li key={source.id}>
    <div>
      <strong>{source.title}</strong>
      <span>{source.institution} · {source.sourceType} · acesso em {formatResearchDate(source.accessedAt)}</span>
      {source.description && <p>{source.description}</p>}
    </div>
    <a href={source.url} target="_blank" rel="noopener noreferrer">Consultar fonte original ↗</a>
  </li>)}</ol>
}

export function ResearchMetricCard({ metric }: { metric: ResearchMetric }) {
  return <div className="research-metric">
    <span>{metric.label}</span>
    <strong>{metric.value.toLocaleString('pt-BR')}</strong>
    <p>{UNIT_LABELS[metric.unit]}</p>
    <small>{COUNT_TYPE_LABELS[metric.countType]} · {METHODOLOGY_LABELS[metric.methodologyType]}</small>
  </div>
}

export function StateResearchList({ states }: { states: StateResearch[] }) {
  return <div className="state-research-list">{states.map(state => {
    const digital = metricFor(state, 'DIGITAL')
    return <article key={state.uf}>
      <div><span className="state-uf">{state.uf}</span><h3>{state.stateName}</h3></div>
      <ResearchStatusBadge status={state.status} />
      <p>{digital ? `${digital.value.toLocaleString('pt-BR')} · ${digital.label}` : 'Sem quantitativo de Núcleo Digital'}</p>
      <small>{COVERAGE_LABELS[state.coverage]}</small>
      <Link to={`/observatorio/estado/${state.uf.toLowerCase()}`}>Ver ficha metodológica</Link>
    </article>
  })}</div>
}

export function StateMetrics({ state }: { state: StateResearch }) {
  if (!state.metrics.length) return <p className="observatory-empty">Nenhum quantitativo foi publicado para esta UF.</p>
  return <div className="state-metric-grid">{state.metrics.map(metric => <ResearchMetricCard key={metric.metricId} metric={metric} />)}</div>
}

export function MethodologicalNotice() {
  return <div className="methodological-notice" role="note" aria-label="Aviso metodológico">
    <strong>Pesquisa em andamento</strong>
    <p>Os quantitativos representam resultados observados nas bases públicas consultadas. Não constituem censo oficial nem contagem definitiva de profissionais em atividade.</p>
    <p>Os números podem aumentar ou diminuir após novas coletas, atualizações dos tribunais, deduplicações, revisões de classificação ou aprimoramentos metodológicos.</p>
  </div>
}
