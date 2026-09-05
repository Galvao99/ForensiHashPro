import { useParams } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { BackLink, ResearchStatusBadge, SourceList, StateMetrics } from '../observatory/components'
import { stateResearch } from '../observatory/data'
import { COVERAGE_LABELS } from '../observatory/models'

export function ObservatoryStatePage() {
  const uf = useParams().uf?.toUpperCase()
  const state = stateResearch.find(item => item.uf === uf)
  if (!state) return <Section eyebrow="OBSERVATÓRIO" title="Estado não encontrado" headingLevel="h1"><BackLink /></Section>
  const compatibleShare = state.uniqueProfessionalsCount !== undefined && state.digitalCoreCount !== undefined && ['INTEGRAL_DEDUPLICATED','PUBLIC_LIST_DEDUPLICATED'].includes(state.coverage)
  return <article className="observatory-page"><DocumentMetadata title={`${state.stateName} — Observatório da Perícia Judicial | Arqen`} description={`Situação, metodologia e fontes da pesquisa do Observatório para ${state.stateName}.`} />
    <Section eyebrow={`PESQUISA ESTADUAL · ${state.uf}`} title={state.stateName} headingLevel="h1"><BackLink /><p className="state-tribunal">{state.tribunal ?? 'Tribunal em levantamento'}</p><ResearchStatusBadge status={state.status} /><p>Última coleta: {state.collectionDate ?? 'data não informada'} · Metodologia {state.methodologyVersion}</p><StateMetrics state={state} />{compatibleShare && <p className="derived-context">Participação do núcleo digital/TI na base consultada: {((state.digitalCoreCount! / state.uniqueProfessionalsCount!) * 100).toLocaleString('pt-BR',{maximumFractionDigits:1})}%.</p>}</Section>
    <Section eyebrow="COBERTURA" title="Recorte da pesquisa"><p><strong>{COVERAGE_LABELS[state.coverage]}</strong></p><p>{state.notes ?? 'Dados ainda não consolidados. Nenhuma ausência é apresentada como zero.'}</p></Section>
    <Section eyebrow="METODOLOGIA" title="Situação e limitações"><ul>{state.limitations.map(item => <li key={item}>{item}</li>)}</ul></Section>
    <Section eyebrow="FONTES" title="Referências da pesquisa"><SourceList sources={state.sources} /></Section>
  </article>
}
