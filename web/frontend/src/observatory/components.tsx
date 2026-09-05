import { Link } from 'react-router-dom'
import type { ResearchSource, ResearchStatus, StateResearch } from './models'
import { COVERAGE_LABELS, STATUS_LABELS, professionalsPer100k } from './models'

export function BackLink({ to = '/observatorio', children = 'Voltar ao Observatório' }: { to?: string; children?: string }) {
  return <nav className="observatory-back" aria-label="Navegação de retorno"><Link to={to}>← {children}</Link></nav>
}

export function ResearchStatusBadge({ status }: { status: ResearchStatus }) {
  return <span className={`research-status research-status--${status.toLowerCase()}`}>{STATUS_LABELS[status]}</span>
}

export function SourceList({ sources }: { sources: ResearchSource[] }) {
  if (!sources.length) return <p className="observatory-empty">Fontes ainda não incorporadas.</p>
  return <ol className="observatory-sources">{sources.map(source => <li key={source.id}>
    <div><strong>{source.title}</strong><span>{source.organization} · acesso em {source.accessedAt}</span>{source.description && <p>{source.description}</p>}</div>
    <a href={source.url} target="_blank" rel="noopener noreferrer">Consultar fonte original ↗</a>
  </li>)}</ol>
}

export function Metric({ label, value }: { label: string; value?: number | string }) {
  return <div><strong>{value === undefined ? 'Dados em consolidação' : typeof value === 'number' ? value.toLocaleString('pt-BR') : value}</strong><span>{label}</span></div>
}

export function StateResearchList({ states }: { states: StateResearch[] }) {
  return <div className="state-research-list">{states.map(state => <article key={state.uf}>
    <div><span className="state-uf">{state.uf}</span><h3>{state.stateName}</h3></div>
    <ResearchStatusBadge status={state.status} />
    <p>{state.digitalCoreCount === undefined ? 'Sem quantitativo consolidado' : `${state.digitalCoreCount.toLocaleString('pt-BR')} · Núcleo digital/TI`}</p>
    <small>{COVERAGE_LABELS[state.coverage]}</small>
    <Link to={`/observatorio/estado/${state.uf.toLowerCase()}`}>Ver estado</Link>
  </article>)}</div>
}

export function StateMetrics({ state }: { state: StateResearch }) {
  const perCapita = professionalsPer100k(state)
  return <div className="observatory-metrics">
    <Metric label="Registros encontrados" value={state.sourceRecordsCount} />
    <Metric label="Profissionais únicos identificados" value={state.uniqueProfessionalsCount} />
    <Metric label="Profissionais do núcleo digital/TI" value={state.digitalCoreCount} />
    {state.researchedSubsetUniqueCount !== undefined && <Metric label="Profissionais únicos no recorte pesquisado" value={state.researchedSubsetUniqueCount} />}
    {state.credentialSpecialtyCount !== undefined && <Metric label="Credenciais/especialidades observadas — não representa pessoas" value={state.credentialSpecialtyCount} />}
    <Metric label="Profissionais cadastrados por 100 mil habitantes" value={perCapita === undefined ? undefined : perCapita.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} />
  </div>
}
