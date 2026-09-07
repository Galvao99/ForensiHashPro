import { Link, useParams } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { BackLink, ResearchStatusBadge, SourceList, StateMetrics, formatResearchDate } from '../observatory/components'
import { stateResearch } from '../observatory/data'
import { COUNT_TYPE_LABELS, COVERAGE_LABELS, METHODOLOGY_LABELS, UNIT_LABELS } from '../observatory/models'

export function ObservatoryStatePage() {
  const uf = useParams().uf?.toUpperCase()
  const state = stateResearch.find(item => item.uf === uf)
  if (!state) return <Section eyebrow="OBSERVATÓRIO" title="Estado não encontrado" headingLevel="h1"><BackLink /></Section>

  return <article className="observatory-page">
    <DocumentMetadata title={`${state.stateName} — metodologia do Observatório | Arqen`} description={`Cobertura, métricas, fontes e limitações da pesquisa do Observatório para ${state.stateName}.`} />
    <Section className="observatory-hero" eyebrow={`COMO ESTE ESTADO FOI PESQUISADO · ${state.uf}`} title={state.stateName} headingLevel="h1">
      <BackLink />
      <p className="state-tribunal">{state.tribunal ?? 'Tribunal ainda não incorporado à pesquisa publicada'}</p>
      <ResearchStatusBadge status={state.status} />
      <p>Metodologia {state.methodologyVersion}. O status descreve o estágio e a cobertura da pesquisa; não representa confiança estatística, qualidade profissional ou relevância.</p>
      <nav className="observatory-local-nav" aria-label="Navegação da ficha estadual">
        <a href="#metricas">Métricas</a><a href="#metodo">Método e limitações</a><a href="#fontes">Fontes</a><a href="#historico">Histórico</a>
        <Link to="/observatorio/metodologia">Metodologia geral</Link>
      </nav>
    </Section>

    <Section id="metricas" eyebrow="QUANTITATIVOS PUBLICADOS" title="Unidades de contagem separadas">
      <StateMetrics state={state} />
      <p className="state-caution">Campos ausentes não são exibidos como zero. Registros, credenciais, recortes e pessoas únicas permanecem unidades distintas.</p>
    </Section>

    <Section id="metodo" className="surface-section" eyebrow="COBERTURA" title="Escopo efetivamente pesquisado">
      <div className="state-method-grid">
        <div><span>Status metodológico</span><strong><ResearchStatusBadge status={state.status} /></strong></div>
        <div><span>Cobertura</span><strong>{COVERAGE_LABELS[state.coverage]}</strong></div>
      </div>
      {state.notes && <p>{state.notes}</p>}
      {state.metrics.length > 0 && <div className="metric-method-list">
        <h3>Método por quantitativo</h3>
        {state.metrics.map(metric => <article key={metric.metricId}>
          <h4>{metric.label}</h4>
          <dl>
            <div><dt>Unidade</dt><dd>{UNIT_LABELS[metric.unit]}</dd></div>
            <div><dt>Tipo de contagem</dt><dd>{COUNT_TYPE_LABELS[metric.countType]}</dd></div>
            <div><dt>Método</dt><dd>{METHODOLOGY_LABELS[metric.methodologyType]}</dd></div>
            <div><dt>Comparabilidade</dt><dd>{metric.comparability === 'DOCUMENTED_SCOPE_ONLY' ? 'Somente dentro do escopo documentado' : 'Não comparável como total estadual ou nacional'}</dd></div>
          </dl>
        </article>)}
      </div>}
      <h3>Limitações</h3>
      <ul>{state.limitations.map(item => <li key={item}>{item}</li>)}</ul>
      {state.observedDifficulties.length > 0 && <><h3>Dificuldades observadas neste tribunal</h3><ul>{state.observedDifficulties.map(item => <li key={item}>{item}</li>)}</ul></>}
    </Section>

    <Section id="fontes" eyebrow="FONTES" title="Referências da pesquisa">
      <SourceList sources={state.sources} />
      {state.sources.length > 0 && <p className="state-caution">As datas exibidas são datas de acesso às fontes. Data de coleta distinta só será apresentada quando documentada.</p>}
    </Section>

    <Section id="historico" eyebrow="SNAPSHOTS E REVISÕES" title="Histórico da pesquisa">
      {state.snapshots.length > 0
        ? <ol className="snapshot-list">{state.snapshots.map(snapshot => <li key={snapshot.id}>
          <strong>{snapshot.version}</strong><span>{snapshot.id}</span>
          {snapshot.collectedAt && <span>Coleta: {formatResearchDate(snapshot.collectedAt)}</span>}
          {snapshot.publishedAt && <span>Publicação: {formatResearchDate(snapshot.publishedAt)}</span>}
        </li>)}</ol>
        : <p className="observatory-empty">Nenhum snapshot quantitativo publicado para esta UF.</p>}
      {state.revisions.length > 0
        ? <ol>{state.revisions.map(revision => <li key={revision.id}>{formatResearchDate(revision.date)} — {revision.reason}</li>)}</ol>
        : <p className="observatory-empty">Nenhuma revisão histórica documentada. Nenhum evento foi presumido.</p>}
      <p>Valores futuros podem aumentar ou diminuir após novas coletas, atualizações da fonte, deduplicações, revisão de classificação ou mudança de recorte.</p>
    </Section>
  </article>
}
