import { Link } from 'react-router-dom'
import { ArtifactGraph } from '../components/ArtifactGraph'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { EvidenceExplorer } from '../components/EvidenceExplorer'
import { Section } from '../components/ui'
import { ddnaReferences } from '../content/ddnaReferences'

const principles = [
  ['01', 'Integridade', 'Identidade verificável dos artefatos.'],
  ['02', 'Proveniência', 'Origem e contexto preservados quando disponíveis.'],
  ['03', 'Rastreabilidade', 'Relações e eventos tecnicamente documentados.'],
  ['04', 'Custódia', 'Histórico do artefato ao longo do tempo.'],
  ['05', 'Reprodutibilidade', 'Resultados técnicos passíveis de verificação.'],
  ['06', 'Interoperabilidade', 'Arquitetura independente de um único fornecedor.'],
]

const sectors = ['Instituições financeiras', 'Seguradoras', 'Jurídico', 'Tecnologia', 'Compliance', 'Auditoria', 'Órgãos públicos', 'Perícia / investigação']

export function HomePage() {
  return (
    <>
      <DocumentMetadata title="ARQEN | Infraestrutura para Evidências Digitais" />
      <section className="arqen-hero">
        <div className="container arqen-hero__grid">
          <div className="arqen-hero__copy">
            <p className="eyebrow">INFRAESTRUTURA PARA EVIDÊNCIAS DIGITAIS</p>
            <h1>Proveniência.<br />Integridade.<br />Rastreabilidade.</h1>
            <p>A ARQEN desenvolve infraestrutura para preservar, relacionar, analisar e tornar verificáveis artefatos digitais ao longo de seu ciclo de vida.</p>
            <div className="hero-actions"><a className="button-link button-light" href="#solutions">Conheça nossas soluções</a><Link className="text-link text-link--light" to="/forensihash">Entender uma análise <span aria-hidden="true">↗</span></Link></div>
          </div>
          <ArtifactGraph />
        </div>
        <p className="hero-coordinate" aria-hidden="true">23°S / DIGITAL EVIDENCE INFRASTRUCTURE / 2026</p>
      </section>

      <section className="principles-strip" aria-label="Princípios de arquitetura ARQEN"><div className="container principles-grid">{principles.map(([number, title, text]) => <article key={number}><span>{number}</span><h2>{title}</h2><p>{text}</p></article>)}</div></section>

      <Section id="solutions" className="arqen-section solutions-section" eyebrow="SOLUÇÕES ARQEN" title="Do registro à análise técnica.">
        <p className="lead">Produtos distintos para etapas complementares do ciclo de evidências digitais, sob uma única arquitetura de marca.</p>
        <div className="solution-grid">
          <article className="solution-card solution-card--ddna"><span className="solution-index">01 / DIGITAL CUSTODY · PROVENANCE</span><div><h3>DDNA</h3><p>Infraestrutura proposta para registrar o estado de artefatos digitais, contexto, relações e histórico de custódia a partir de um marco T0, permitindo verificações posteriores.</p></div><Link to="/ddna">Conhecer DDNA <span aria-hidden="true">↗</span></Link><small>RESEARCH / DEVELOPMENT</small></article>
          <article className="solution-card solution-card--forensi"><span className="solution-index">02 / DIGITAL ANALYSIS</span><div><h3>ForensiHash</h3><p>Ferramenta de análise técnica de artefatos digitais, hashes, metadados, estrutura, timeline, correlações e outros elementos disponíveis no produto.</p></div><Link to="/forensihash">Conhecer ForensiHash <span aria-hidden="true">↗</span></Link><small>PRODUTO EM DESENVOLVIMENTO</small></article>
        </div>
      </Section>

      <Section className="arqen-section evidence-cycle-section" eyebrow="CICLO DA EVIDÊNCIA DIGITAL" title="Preservar e analisar são papéis distintos.">
        <div className="evidence-cycle" role="img" aria-label="Um artefato digital pode ser preservado pelo DDNA e analisado pelo ForensiHash, contribuindo para evidência técnica">
          <strong>ARTEFATO DIGITAL</strong><div className="cycle-stem" aria-hidden="true" /><div className="cycle-products"><article><span>DDNA</span><b>Preservar</b><small>proveniência · custódia</small></article><article><span>FORENSIHASH</span><b>Analisar</b><small>inspeção · correlação</small></article></div><div className="cycle-output">EVIDÊNCIA TÉCNICA</div>
        </div>
        <p className="cycle-note">O DDNA atua na preservação, proveniência e custódia propostas. O ForensiHash atua na inspeção e análise técnica. Um artefato não precisa, necessariamente, passar pelos dois produtos.</p>
      </Section>

      <Section className="arqen-section problem-section" eyebrow="CONTEXTO" title="Arquivos digitais não carregam, por si só, toda a sua história.">
        <div className="problem-grid"><div><p className="lead">Ao longo de uma operação, arquivo, metadados, logs, eventos, contexto de sessão, hashes, sistemas produtores, timestamps e versões podem permanecer distribuídos em fontes diferentes.</p><p>Quando esses elementos não são preservados e relacionados de maneira adequada, a reconstrução posterior pode se tornar limitada.</p></div><div className="fragment-map" role="img" aria-label="Elementos de uma transação digital podem se fragmentar ao longo do tempo"><strong>TRANSAÇÃO</strong>{['arquivo', 'logs', 'eventos', 'contexto', 'identidade', 'metadados'].map(item => <span key={item}>{item}</span>)}<b>↓ TEMPO</b><em>fragmentação / perda de contexto</em></div></div>
      </Section>

      <Section className="arqen-section explorer-section" eyebrow="EXEMPLO DIDÁTICO" title="Um artefato. Diferentes camadas de informação.">
        <p className="lead">Selecione uma categoria para compreender o papel técnico de cada registro — e os limites do que ele permite afirmar.</p>
        <EvidenceExplorer />
      </Section>

      <Section className="arqen-section applications-section" eyebrow="APLICAÇÕES" title="Setores com desafios de evidência digital.">
        <div className="sector-grid">{sectors.map((sector, index) => <div key={sector}><span>{String(index + 1).padStart(2, '0')}</span><strong>{sector}</strong></div>)}</div>
        <p className="institutional-note">Áreas em que infraestrutura de evidência digital pode ser aplicável. Esta lista não representa clientes, parceiros ou implantações da ARQEN.</p>
      </Section>

      <Section className="arqen-section foundations-section" eyebrow="FUNDAMENTOS" title="Engenharia orientada por referências técnicas e jurídicas.">
        <p className="lead">Cadeia de custódia, evidência digital, integridade, preservação, auditabilidade e proteção de dados formam o contexto de pesquisa dos produtos. As referências não certificam ou homologam a ARQEN.</p>
        <div className="foundation-links">{ddnaReferences.filter(item => ['cpp-158', 'stj-inf-811', 'iso-27037', 'lgpd', 'icp-brasil'].includes(item.id)).map(item => <Link key={item.id} to={`/ddna#${item.id}`}><span>{item.institution} · {item.date}</span><strong>{item.title}</strong><i aria-hidden="true">↗</i></Link>)}</div>
        <Link className="button-link button-dark" to="/ddna#como-funciona">Explorar fundamentos técnicos e jurídicos</Link>
      </Section>
    </>
  )
}
