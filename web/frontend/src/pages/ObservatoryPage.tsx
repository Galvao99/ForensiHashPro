import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { MethodologicalNotice, ResearchStatusBadge, SourceList, StateResearchList, formatResearchDate } from '../observatory/components'
import { BrazilResearchMap, MAP_MODE_LABELS, type MapMode } from '../observatory/BrazilResearchMap'
import { LATEST_SOURCE_ACCESS_DATE, RESEARCH_VERSION, observatoryArticles, regulatoryItems, stateResearch } from '../observatory/data'
import { COUNT_TYPE_LABELS, COVERAGE_LABELS, METHODOLOGY_LABELS, UNIT_LABELS, metricFor } from '../observatory/models'

const modeDescription: Record<MapMode, string> = {
  DIGITAL: 'Resultados identificados na categoria metodológica Núcleo Digital, respeitando o recorte documentado de cada tribunal.',
  GENERAL: 'Profissionais únicos identificados somente nas bases em que essa unidade de contagem foi metodologicamente sustentada.',
  OTHER: 'Estrutura reservada à expansão da pesquisa. Nenhum quantitativo foi publicado nesta versão.',
}

export function ObservatoryPage() {
  const [mapMode, setMapMode] = useState<MapMode>('DIGITAL')
  const [selectedUf, setSelectedUf] = useState('RJ')
  const selected = stateResearch.find(state => state.uf === selectedUf) ?? stateResearch[0]
  const selectedMetric = mapMode === 'OTHER' ? undefined : metricFor(selected, mapMode)
  const digital = metricFor(selected, 'DIGITAL')
  const general = metricFor(selected, 'GENERAL')
  const source = selectedMetric
    ? selected.sources.find(item => item.id === selectedMetric.sourceId)
    : selected.sources[0]
  const consolidated = stateResearch.filter(state => state.status === 'CONSOLIDATED').length
  const partial = stateResearch.filter(state => state.status === 'PARTIAL').length
  const sourced = stateResearch.filter(state => state.sources.length > 0).length

  return <article className="observatory-page">
    <DocumentMetadata title="Observatório da Perícia Judicial | Arqen" description="Pesquisa contínua, dados agregados, fontes e metodologia sobre cadastros periciais nos tribunais brasileiros." />
    <Section className="observatory-hero" eyebrow="OBSERVATÓRIO DA PERÍCIA JUDICIAL" title="O que já sabemos — e como sabemos." headingLevel="h1">
      <p className="lead">Projeto de pesquisa contínua da Arqen sobre a distribuição de profissionais, especialidades, regulamentação e evolução da perícia judicial nos tribunais brasileiros.</p>
      <div className="research-progress"><strong>Pesquisa Nacional 2026 · {RESEARCH_VERSION}</strong><span>Pesquisa em andamento</span></div>
      <nav className="observatory-local-nav" aria-label="Seções do Observatório">
        <a href="#pesquisa">Mapa da pesquisa</a>
        <Link to="/observatorio/metodologia">Pesquisa e Metodologia</Link>
        <a href="#radar">Contexto normativo</a>
        <a href="#estados">Fichas estaduais</a>
      </nav>
    </Section>

    <Section id="pesquisa" eyebrow="PESQUISA NACIONAL" title="Mapa da pesquisa">
      <p className="lead">Dados agregados provenientes das fontes públicas e institucionais incorporadas. Cadastro identificado não implica profissional ativo, e cadastro em tribunal não equivale a censo nacional.</p>
      <div className="observatory-metrics national-metrics">
        <div><strong>27</strong><span>UFs previstas no escopo</span></div>
        <div><strong>{consolidated}</strong><span>UFs com pesquisa consolidada</span></div>
        <div><strong>{partial}</strong><span>UFs com pesquisa parcial</span></div>
        <div><strong>{sourced}</strong><span>UFs com fonte incorporada</span></div>
        <div><strong>{formatResearchDate(LATEST_SOURCE_ACCESS_DATE)}</strong><span>Último acesso entre as fontes incorporadas</span></div>
      </div>
      <MethodologicalNotice />

      <div className="map-heading">
        <div>
          <p className="eyebrow">MAPA GEOGRÁFICO · {MAP_MODE_LABELS[mapMode]}</p>
          <h3>{mapMode === 'OTHER' ? 'Outras especialidades — em levantamento' : `${MAP_MODE_LABELS[mapMode]} por UF`}</h3>
          <p>{modeDescription[mapMode]}</p>
        </div>
        <div className="map-mode" role="group" aria-label="Métrica do mapa">
          {(['DIGITAL', 'GENERAL', 'OTHER'] as const).map(mode => <button
            key={mode}
            type="button"
            aria-pressed={mapMode === mode}
            onClick={() => setMapMode(mode)}
          >{MAP_MODE_LABELS[mode]}{mode === 'OTHER' && <small>Em levantamento</small>}</button>)}
        </div>
      </div>

      <div className="map-explorer">
        <div>
          <BrazilResearchMap states={stateResearch} mode={mapMode} selectedUf={selected.uf} onSelect={state => setSelectedUf(state.uf)} />
          <div className="map-legend" aria-label="Legenda do mapa">
            <span><i className="legend-bubble legend-bubble--large" /> Área da bolha = quantidade</span>
            <span><i className="legend-line legend-line--solid" /> Consolidado</span>
            <span><i className="legend-line legend-line--dashed" /> Parcial</span>
            <span><i className="legend-line legend-line--dotted" /> Em revisão</span>
            <span>Sem bolha = sem quantitativo para a métrica</span>
          </div>
        </div>
        <aside className="map-summary" aria-live="polite">
          <span>{selected.stateName.toUpperCase()} — {selected.uf}</span>
          <h3>{selected.tribunal ?? 'Tribunal em levantamento'}</h3>
          <ResearchStatusBadge status={selected.status} />
          <div className="map-summary__metric">
            <small>{MAP_MODE_LABELS[mapMode]}</small>
            <strong>{selectedMetric?.value.toLocaleString('pt-BR') ?? (mapMode === 'OTHER' ? 'Em levantamento' : 'Sem quantitativo consolidado')}</strong>
            {selectedMetric && <p>{UNIT_LABELS[selectedMetric.unit]}</p>}
          </div>
          <div className="map-summary__comparative" aria-label="Métricas disponíveis para a UF">
            <p><span>Núcleo Digital</span><b>{digital?.value.toLocaleString('pt-BR') ?? 'Sem quantitativo'}</b></p>
            <p><span>Cadastro Geral</span><b>{general?.value.toLocaleString('pt-BR') ?? 'Sem quantitativo'}</b></p>
            <p><span>Outras especialidades</span><b>Em levantamento</b></p>
          </div>
          <dl>
            <div><dt>Status da pesquisa</dt><dd>{selected.status === 'CONSOLIDATED' ? 'Consolidado' : selected.status === 'PARTIAL' ? 'Parcial' : selected.status === 'UNDER_REVIEW' ? 'Em revisão' : selected.status === 'IN_PROGRESS' ? 'Em levantamento' : 'Sem quantitativo consolidado'}</dd></div>
            <div><dt>Cobertura</dt><dd>{COVERAGE_LABELS[selected.coverage]}</dd></div>
            {selectedMetric && <div><dt>Tipo de contagem</dt><dd>{COUNT_TYPE_LABELS[selectedMetric.countType]}</dd></div>}
            {selectedMetric && <div><dt>Metodologia</dt><dd>{METHODOLOGY_LABELS[selectedMetric.methodologyType]}</dd></div>}
            {source && <div><dt>Fonte</dt><dd><a href={source.url} target="_blank" rel="noopener noreferrer">{source.institution} ↗</a></dd></div>}
            {source && <div><dt>Data de acesso</dt><dd>{formatResearchDate(source.accessedAt)}</dd></div>}
          </dl>
          {selected.notes && <p className="map-summary__note">{selected.notes}</p>}
          <Link className="button-link" to={`/observatorio/estado/${selected.uf.toLowerCase()}`}>Ver metodologia deste estado</Link>
        </aside>
      </div>

      <div id="estados" className="observatory-subheading"><p className="eyebrow">FICHAS METODOLÓGICAS</p><h3>Pesquisa por estado</h3><p>A lista oferece navegação textual completa por teclado, toque e telas pequenas.</p></div>
      <StateResearchList states={stateResearch} />
    </Section>

    <Section id="radar" className="surface-section" eyebrow="CONTEXTO INSTITUCIONAL E NORMATIVO" title="Referências que delimitam a pesquisa">
      <p className="lead">Acompanhamento seletivo de atos institucionais e normativos relevantes. Os resumos são neutros e não constituem interpretação ou aconselhamento jurídico.</p>
      {regulatoryItems.map(item => <article className="regulatory-item" key={item.id}>
        <span>{item.category} · {item.status}</span>
        <h3>{item.title}</h3>
        <p>{item.summary}</p>
        <dl>
          <div><dt>Órgão</dt><dd>{item.institution}</dd></div>
          <div><dt>Data</dt><dd>{formatResearchDate(item.publishedAt)}</dd></div>
          <div><dt>Relevância para a pesquisa</dt><dd>{item.relevance}</dd></div>
        </dl>
        <SourceList sources={item.sources} />
      </article>)}
    </Section>

    <Section eyebrow="ANÁLISE EDITORIAL" title="Análises, estudos e notas técnicas">
      {observatoryArticles.length === 0 && <p className="observatory-empty">Conteúdos em preparação. Nenhuma completude editorial é presumida.</p>}
    </Section>
    <Section eyebrow="TRANSPARÊNCIA" title="Pesquisa rastreável">
      <p>Cada quantitativo publicado mantém sua fonte, unidade de contagem, tipo de contagem, método, status e snapshot. A incerteza atual é metodológica e de cobertura; nenhuma margem de erro estatística genérica é aplicada.</p>
      <Link className="text-link" to="/observatorio/metodologia">Ver Pesquisa e Metodologia {RESEARCH_VERSION} →</Link>
    </Section>
  </article>
}
