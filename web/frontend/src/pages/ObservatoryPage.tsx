import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { ResearchStatusBadge, SourceList, StateResearchList } from '../observatory/components'
import { BrazilResearchMap, type MapMode } from '../observatory/BrazilResearchMap'
import { observatoryArticles, regulatoryItems, stateResearch } from '../observatory/data'
import { COVERAGE_LABELS, comparableRanking, isDigitalComparable, professionalsPer100k } from '../observatory/models'

export function ObservatoryPage() {
  const [mapMode,setMapMode] = useState<MapMode>('DIGITAL')
  const [selectedUf,setSelectedUf] = useState('RJ')
  const selected = stateResearch.find(state => state.uf === selectedUf) ?? stateResearch[0]
  const completed = stateResearch.filter(state => state.status === 'COMPLETED')
  const totalsAvailable = completed.length > 0
  const perCapitaRanking = comparableRanking(stateResearch, professionalsPer100k)
  const digitalRanking = stateResearch.filter(isDigitalComparable).sort((a,b) => (b.digitalCoreCount ?? 0) - (a.digitalCoreCount ?? 0))
  const generalRanking = comparableRanking(stateResearch, state => state.uniqueProfessionalsCount)
  return <article className="observatory-page">
    <DocumentMetadata title="Observatório da Perícia Judicial | Arqen" description="Dados, normas e transformações da atividade pericial no Brasil, com metodologia e fontes primárias." />
    <Section className="observatory-hero" eyebrow="OBSERVATÓRIO DA PERÍCIA JUDICIAL" title="Dados, normas e transformações da atividade pericial no Brasil." headingLevel="h1">
      <p className="lead">Projeto de pesquisa contínua da Arqen sobre a distribuição de profissionais, regulamentação e evolução da perícia judicial nos tribunais brasileiros.</p>
      <div className="research-progress"><strong>Pesquisa Nacional 2026</strong><span>Pesquisa em andamento</span></div>
      <nav className="observatory-local-nav" aria-label="Seções do Observatório"><a href="#pesquisa">Pesquisa Nacional</a><a href="#radar">Radar Regulatório</a><a href="#analises">Análises</a><Link to="/observatorio/metodologia">Metodologia</Link></nav>
    </Section>
    <Section id="pesquisa" eyebrow="DADOS" title="Pesquisa Nacional">
      <p className="lead">Mapeamento dos cadastros públicos consultados dos Tribunais de Justiça brasileiros.</p>
      <div className="observatory-metrics national-metrics"><div><strong>{totalsAvailable ? completed.length : 'Em levantamento'}</strong><span>Estados analisados</span></div><div><strong>Dados em consolidação</strong><span>Profissionais únicos identificados</span></div><div><strong>Dados em consolidação</strong><span>Especialidades identificadas</span></div><div><strong>Em levantamento</strong><span>Fontes oficiais consultadas</span></div><div><strong>Não disponível</strong><span>Última atualização dos dados</span></div></div>
      <div className="map-heading"><div><p className="eyebrow">MAPA DA PERÍCIA DIGITAL</p><h3>Profissionais do núcleo digital/TI identificados</h3><p>Os números destacados no mapa representam profissionais identificados em especialidades relacionadas à perícia digital, tecnologia da informação, computação forense, sistemas, redes e áreas técnicas diretamente aderentes ao recorte digital da pesquisa.</p><p className="map-disclaimer">Quando disponível, o cadastro geral do tribunal é apresentado como contexto. A presença no cadastro não implica atuação efetiva, disponibilidade atual ou número de nomeações realizadas.</p></div><div className="map-mode" role="group" aria-label="Modo do mapa"><button type="button" aria-pressed={mapMode === 'DIGITAL'} onClick={() => setMapMode('DIGITAL')}>Núcleo digital/TI</button><button type="button" aria-pressed={mapMode === 'GENERAL'} onClick={() => setMapMode('GENERAL')}>Cadastro geral</button></div></div>
      <div className="map-explorer"><div><BrazilResearchMap states={stateResearch} mode={mapMode} selectedUf={selected.uf} onSelect={state => setSelectedUf(state.uf)} /><div className="map-legend" aria-label="Legenda do mapa"><span>■ Dados consolidados</span><span>▨ Pesquisa parcial</span><span>□ Sem quantitativo consolidado</span><span>○ Não iniciado</span></div></div><aside className="map-summary" aria-live="polite"><span>{selected.uf} · {selected.tribunal ?? 'Tribunal em levantamento'}</span><h3>{selected.stateName}</h3><ResearchStatusBadge status={selected.status} /><strong>{(mapMode === 'DIGITAL' ? selected.digitalCoreCount : selected.uniqueProfessionalsCount)?.toLocaleString('pt-BR') ?? 'Sem quantitativo consolidado'}</strong><p>{mapMode === 'DIGITAL' ? 'Profissionais do núcleo digital/TI identificados' : 'Profissionais únicos no cadastro consultado'}</p>{selected.uniqueProfessionalsCount !== undefined && <p><b>{selected.uniqueProfessionalsCount.toLocaleString('pt-BR')}</b> profissionais únicos no cadastro consultado</p>}{selected.researchedSubsetUniqueCount !== undefined && <p><b>{selected.researchedSubsetUniqueCount.toLocaleString('pt-BR')}</b> profissionais únicos no recorte pesquisado</p>}<dl><div><dt>Cobertura</dt><dd>{COVERAGE_LABELS[selected.coverage]}</dd></div><div><dt>Última coleta</dt><dd>{selected.collectionDate ?? 'Não informada'}</dd></div><div><dt>Fonte</dt><dd>{selected.sources[0]?.organization ?? 'Fonte documental pendente de incorporação'}</dd></div></dl><Link className="button-link" to={`/observatorio/estado/${selected.uf.toLowerCase()}`}>Ver detalhes do estado</Link></aside></div>
      <h3>Estados</h3><p>A lista abaixo é uma alternativa integral ao mapa para navegação por teclado, toque ou telas pequenas.</p><StateResearchList states={stateResearch} />
      <div className="observatory-rankings"><section><h3>Núcleo digital/TI — resultados observados</h3><ol>{digitalRanking.map(state => <li key={state.uf}><Link to={`/observatorio/estado/${state.uf.toLowerCase()}`}><strong>{state.uf}</strong><span>{state.digitalCoreCount?.toLocaleString('pt-BR')}</span><small>{COVERAGE_LABELS[state.coverage]} · {state.status === 'COMPLETED' ? 'Concluído' : 'Parcial'}</small></Link></li>)}</ol></section><section><h3>Cadastro geral — bases integrais comparáveis</h3><ol>{generalRanking.map(item => <li key={item.state.uf}><Link to={`/observatorio/estado/${item.state.uf.toLowerCase()}`}><strong>{item.state.uf}</strong><span>{item.value.toLocaleString('pt-BR')}</span><small>{COVERAGE_LABELS[item.state.coverage]}</small></Link></li>)}</ol></section></div>
      <div className="ranking-empty"><h3>Profissionais cadastrados por 100 mil habitantes</h3>{perCapitaRanking.length ? <ol>{perCapitaRanking.map(item => <li key={item.state.uf}>{item.state.stateName}: {item.value.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}</li>)}</ol> : <p>Ranking indisponível enquanto não houver estados concluídos e comparáveis.</p>}</div>
    </Section>
    <Section id="radar" className="surface-section" eyebrow="FONTE + CONTEXTO" title="Radar Regulatório">
      <p className="lead">Acompanhamento seletivo de atos institucionais e normativos relevantes. Não constitui aconselhamento jurídico.</p>
      {regulatoryItems.map(item => <article className="regulatory-item" key={item.id}><span>{item.category} · {item.status}</span><h3>{item.title}</h3><p>{item.summary}</p><dl><div><dt>Quem publicou</dt><dd>{item.organization}</dd></div><div><dt>Quando</dt><dd>{item.publishedAt}</dd></div><div><dt>Por que é relevante</dt><dd>{item.relevance}</dd></div></dl><SourceList sources={item.sources} /></article>)}
    </Section>
    <Section id="analises" eyebrow="ANÁLISE EDITORIAL" title="Análises, estudos e notas técnicas">
      {observatoryArticles.length === 0 ? <p className="observatory-empty">Conteúdos em preparação.</p> : null}
    </Section>
    <Section eyebrow="MÉTODO" title="Pesquisa rastreável"><p>Cada conjunto publicado deve separar registros de origem, profissionais únicos, método de deduplicação, período de coleta, limitações e fontes.</p><Link className="text-link" to="/observatorio/metodologia">Consultar metodologia v1.0 →</Link></Section>
  </article>
}
