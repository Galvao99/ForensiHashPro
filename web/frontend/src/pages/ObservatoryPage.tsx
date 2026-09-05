import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { SourceList, StateResearchList } from '../observatory/components'
import { observatoryArticles, regulatoryItems, stateResearch } from '../observatory/data'
import { comparableRanking, professionalsPer100k } from '../observatory/models'

export function ObservatoryPage() {
  const completed = stateResearch.filter(state => state.status === 'COMPLETED')
  const totalsAvailable = completed.length > 0
  const perCapitaRanking = comparableRanking(stateResearch, professionalsPer100k)
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
      <h3>Distribuição por estado</h3><StateResearchList states={stateResearch} />
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
