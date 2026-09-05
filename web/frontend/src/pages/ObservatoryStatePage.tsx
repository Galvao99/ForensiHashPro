import { Link, useParams } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { ResearchStatusBadge, SourceList, StateMetrics } from '../observatory/components'
import { stateResearch } from '../observatory/data'

export function ObservatoryStatePage() {
  const uf = useParams().uf?.toUpperCase()
  const state = stateResearch.find(item => item.uf === uf)
  if (!state) return <Section eyebrow="OBSERVATÓRIO" title="Estado não encontrado" headingLevel="h1"><Link to="/observatorio">Voltar ao Observatório</Link></Section>
  return <article className="observatory-page"><DocumentMetadata title={`${state.stateName} — Observatório da Perícia Judicial | Arqen`} description={`Situação, metodologia e fontes da pesquisa do Observatório para ${state.stateName}.`} />
    <Section eyebrow={`PESQUISA ESTADUAL · ${state.uf}`} title={state.stateName} headingLevel="h1"><ResearchStatusBadge status={state.status} /><p>{state.collectionDate ? `Coleta: ${state.collectionDate}` : 'Coleta ainda não realizada.'} · Metodologia {state.methodologyVersion}</p><StateMetrics state={state} /></Section>
    <Section eyebrow="METODOLOGIA" title="Situação e limitações"><ul>{state.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>{state.notes ?? 'Dados ainda não consolidados. Nenhuma ausência é apresentada como zero.'}</p></Section>
    <Section eyebrow="FONTES" title="Referências da pesquisa"><SourceList sources={state.sources} /></Section>
  </article>
}
