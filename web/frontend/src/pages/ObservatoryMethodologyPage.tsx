import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { BackLink, MethodologicalNotice, SourceList, formatResearchDate } from '../observatory/components'
import {
  LATEST_SOURCE_ACCESS_DATE, RESEARCH_VERSION, cnjResolution233, regulatoryItems,
  researchRevisions, researchSnapshots, specialtyDictionary, stateResearch,
} from '../observatory/data'
import { COVERAGE_LABELS } from '../observatory/models'

const glossary = [
  ['Cadastro Geral', 'Profissionais únicos identificados na base consultada, somente quando a deduplicação e a unidade “pessoa” são sustentadas.'],
  ['Núcleo Digital', 'Categoria metodológica da pesquisa Arqen para especialidades relacionadas ao domínio digital/TI. Não é uma classificação oficial nacional única.'],
  ['Registro', 'Linha, ocorrência ou item administrativo encontrado na fonte; pode não corresponder a uma pessoa única.'],
  ['Profissional único identificado', 'Pessoa distinguida dentro do escopo da base consultada segundo a deduplicação documentada. Não implica atividade profissional atual.'],
  ['Especialidade original', 'Nomenclatura tal como publicada pelo tribunal, preservada antes de qualquer normalização.'],
  ['Categoria normalizada', 'Categoria analítica aplicada pela pesquisa sem apagar a nomenclatura original.'],
  ['Base integral', 'Conjunto completo disponibilizado no recorte e momento documentados pela fonte.'],
  ['Recorte', 'Subconjunto obtido por termos, filtros, tipos ou outra delimitação explícita.'],
  ['Parcial', 'Pesquisa com cobertura limitada ou etapa ainda não integralmente consolidada.'],
  ['Consolidado', 'Estágio metodológico concluído para o escopo documentado; não significa censo, precisão estatística ou imutabilidade.'],
  ['Snapshot', 'Versão imutável da estrutura publicada em determinado ciclo de pesquisa.'],
  ['Deduplicação', 'Procedimento para evitar que ocorrências repetidas sejam contadas como pessoas distintas, quando a fonte permite.'],
  ['Cobertura', 'Descrição do alcance efetivamente pesquisado: base integral, lista pública, recorte, consulta filtrada ou outra condição.'],
  ['Unidade de contagem', 'Entidade que o número representa, como pessoa única, registro ou credencial/especialidade.'],
  ['Comparabilidade', 'Condição limitada ao escopo documentado; não autoriza ranking nacional ou equivalência automática entre metodologias.'],
]

const possibleDifficulties = [
  'ausência de padronização nacional e nomenclaturas distintas',
  'formatos não estruturados, páginas paginadas ou consultas condicionadas a filtros',
  'registros repetidos e múltiplas especialidades por profissional',
  'dados agregados que não representam pessoas e ausência de identificador público uniforme',
  'diferentes datas de atualização e impossibilidade de inferir atividade profissional',
  'necessidade de contagem ou deduplicação manual ou assistida em algumas bases',
]

export function ObservatoryMethodologyPage() {
  const statesWithObservedDifficulties = stateResearch.filter(state => state.observedDifficulties.length > 0)
  return <article className="observatory-page">
    <DocumentMetadata title="Pesquisa e Metodologia do Observatório | Arqen" description="Objetivo, conceitos, fontes, cobertura, limitações e versionamento da pesquisa do Observatório da Perícia Judicial." />
    <Section className="observatory-hero" eyebrow={`PESQUISA E METODOLOGIA · ${RESEARCH_VERSION}`} title="Como sabemos o que apresentamos." headingLevel="h1">
      <BackLink />
      <p className="lead">A metodologia documenta como informações públicas sobre cadastros periciais são coletadas, distinguidas e publicadas. Transparência metodológica tem prioridade sobre completude aparente.</p>
      <div className="methodology-meta">
        <div><span>Versão da pesquisa</span><strong>{RESEARCH_VERSION}</strong></div>
        <div><span>Último acesso entre fontes incorporadas</span><strong>{formatResearchDate(LATEST_SOURCE_ACCESS_DATE)}</strong></div>
        <div><span>Revisões históricas documentadas</span><strong>{researchRevisions.length}</strong></div>
      </div>
      <nav className="observatory-local-nav" aria-label="Navegação da metodologia">
        <a href="#fontes">Ver fontes</a><a href="#conceitos">Ver conceitos</a><a href="#tribunais">Dificuldades por tribunal</a><a href="#historico">Histórico da pesquisa</a>
      </nav>
    </Section>

    <Section eyebrow="OBJETIVO E ESCOPO" title="Uma pesquisa contínua, não um censo">
      <MethodologicalNotice />
      <div className="methodology-sections">
        <section><h2>Objetivo</h2><p>Estruturar informações públicas relacionadas aos cadastros periciais brasileiros, começando por Cadastro Geral e Núcleo Digital e permitindo expansão futura para outras especialidades.</p></section>
        <section><h2>Escopo</h2><p>A unidade territorial é a UF e a unidade institucional é o tribunal indicado na ficha. Resultados descrevem a base e o recorte consultados; não estimam automaticamente o universo nacional.</p></section>
        <section><h2>O que a pesquisa não afirma</h2><p>Cadastro não comprova atividade, disponibilidade, qualidade, número de nomeações ou atuação recente. “Consolidado” descreve apenas o estágio da pesquisa no escopo documentado.</p></section>
      </div>
    </Section>

    <Section eyebrow="PROCESSO" title="Coleta, preservação e classificação">
      <div className="methodology-flow" aria-label="Etapas da metodologia">
        <span>Fonte pública</span><b>→</b><span>Preservação do contexto</span><b>→</b><span>Normalização</span><b>→</b><span>Deduplicação, quando aplicável</span><b>→</b><span>Classificação</span><b>→</b><span>Revisão e snapshot</span>
      </div>
      <div className="methodology-sections">
        <section><h2>Coleta</h2><p>Tribunais podem disponibilizar planilhas, PDFs, consultas web, tabelas públicas, relatórios agregados, consultas por especialidade ou listagens paginadas. Um formato só é atribuído a tribunal quando estiver documentado na base desta pesquisa.</p></section>
        <section><h2>Normalização e deduplicação</h2><p>Nomes e categorias podem ser normalizados para comparação interna, preservando o valor original. Deduplicação só sustenta contagem de pessoas quando o conjunto e os campos disponíveis permitem esse procedimento.</p></section>
        <section><h2>Classificação</h2><p>“Núcleo Digital” é uma categoria metodológica Arqen, não uma taxonomia oficial nacional. Termos como “Perícia Digital”, “Informática”, “Análise de Sistemas” e “Forense” podem existir nas fontes, mas não são considerados equivalentes de forma automática.</p></section>
        <section><h2>Regra de publicação</h2><p>Nenhum quantitativo é publicado sem fonte, unidade de contagem, tipo de contagem e status metodológico. Informação essencial ausente impede que o resultado seja apresentado como consolidado.</p></section>
      </div>
    </Section>

    <Section id="conceitos" className="surface-section" eyebrow="CONCEITOS DA PESQUISA" title="Glossário metodológico">
      <dl className="research-glossary">{glossary.map(([term, definition]) => <div key={term}><dt>{term}</dt><dd>{definition}</dd></div>)}</dl>
    </Section>

    <Section eyebrow="DIFICULDADES" title="Limitações gerais e evidências observadas">
      <div className="methodology-columns">
        <section><h3>Dificuldades gerais possíveis</h3><p>Estas condições são riscos comuns de pesquisa e não são atribuídas automaticamente a um tribunal.</p><ul>{possibleDifficulties.map(item => <li key={item}>{item}</li>)}</ul></section>
        <section><h3>Limitações permanentes de interpretação</h3><ul><li>Cadastros podem mudar entre coletas.</li><li>Metodologias podem variar entre tribunais.</li><li>Ausência de quantitativo não significa zero.</li><li>A incerteza atual é metodológica e de cobertura, não uma margem de erro estatística.</li></ul></section>
      </div>
    </Section>

    <Section id="tribunais" eyebrow="EVIDÊNCIA POR TRIBUNAL" title="Como os dados puderam ser consolidados">
      <p>A tabela é descritiva e não classifica tribunais como melhores ou piores. Exibe somente condições já registradas no dataset.</p>
      <div className="research-table-wrap"><table className="research-table">
        <thead><tr><th>Tribunal</th><th>UF</th><th>Cobertura observada</th><th>Dificuldade efetivamente documentada</th><th>Ficha</th></tr></thead>
        <tbody>{statesWithObservedDifficulties.map(state => <tr key={state.uf}>
          <td>{state.tribunal}</td><td>{state.uf}</td><td>{COVERAGE_LABELS[state.coverage]}</td>
          <td>{state.observedDifficulties.join(' ')}</td>
          <td><Link to={`/observatorio/estado/${state.uf.toLowerCase()}`}>Ver metodologia</Link></td>
        </tr>)}</tbody>
      </table></div>
    </Section>

    <Section eyebrow="DICIONÁRIO DE ESPECIALIDADES" title="Taxonomia rastreável">
      <p>A estrutura prevê nomenclatura original, tribunal, categoria normalizada, regra de classificação, status de revisão e fonte. Nenhuma entrada será criada sem evidência documental.</p>
      {specialtyDictionary.length === 0
        ? <p className="observatory-empty">Dicionário público em preparação; nenhuma especialidade fictícia foi adicionada.</p>
        : <div className="research-table-wrap"><table className="research-table">
          <thead><tr><th>Especialidade original</th><th>Tribunal</th><th>Categoria normalizada</th><th>Quantidade observada</th></tr></thead>
          <tbody>{specialtyDictionary.map(entry => <tr key={entry.id}>
            <td>{entry.originalSpecialty}</td><td>{entry.tribunal}</td><td>{entry.normalizedCategory}</td><td>{entry.observedCount?.toLocaleString('pt-BR') ?? 'Não quantificado'}</td>
          </tr>)}</tbody>
        </table></div>}
    </Section>

    <Section id="historico" className="surface-section" eyebrow="VERSIONAMENTO" title="Histórico da pesquisa">
      <p>Snapshots preservam a referência de cada métrica publicada. Valores futuros poderão subir ou descer por nova fonte, atualização do tribunal, deduplicação, remoção de duplicatas, melhoria de classificação ou mudança de recorte. Uma revisão não significa necessariamente que o valor anterior era um erro.</p>
      <div className="snapshot-summary"><strong>{researchSnapshots.length}</strong><span>snapshots atuais estruturados em {RESEARCH_VERSION}</span></div>
      {researchRevisions.length === 0
        ? <p className="observatory-empty">Nenhum evento histórico anterior foi documentado na base atual. A infraestrutura de revisões está pronta, sem eventos inventados.</p>
        : null}
    </Section>

    <Section id="fontes" eyebrow="FONTES" title="Contexto institucional e normativo">
      <p>Fontes oficiais têm prioridade. Cada item informa título, instituição, data de acesso, tipo e link para o produtor original.</p>
      <SourceList sources={[cnjResolution233]} />
      {regulatoryItems.map(item => <article className="regulatory-item" key={item.id}>
        <span>{item.status}</span><h3>{item.title}</h3><p>{item.relevance}</p>
      </article>)}
    </Section>

    <Section eyebrow="PRIVACIDADE E EVOLUÇÃO" title="Agregados públicos, expansão controlada">
      <p>A V1 publica somente agregados, metodologia, fontes, classificações e cobertura. Nenhuma lista nominal de profissionais integra o bundle público.</p>
      <p>A estrutura permite incorporar outras especialidades, novos snapshots e revisões futuras. Não inclui backend complexo, scraping automático, estimativa nacional, ranking, score ou inferência de profissional ativo.</p>
    </Section>
  </article>
}
