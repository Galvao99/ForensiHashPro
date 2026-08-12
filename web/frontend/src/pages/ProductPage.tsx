import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import { analysisLayers } from '../content/institutional'

export function ProductPage() {
  return (
    <>
      <DocumentMetadata title="ForensiHash | Análise de Artefatos Digitais — ARQEN" description="Análise técnica de hashes, metadados, estrutura, assinaturas e outros elementos observáveis em artefatos digitais." />
      <Section eyebrow="PRODUTO" title="FORENSIHASH PRO">
        <p className="lead">Uma plataforma para centralizar verificações que normalmente ficam distribuídas entre ferramentas distintas, mantendo fatos técnicos separados de interpretações e limitações.</p>
        <div className="hero-actions"><Link className="button-link" to="/app/analysis">Iniciar análise</Link></div>
      </Section>
      <Section className="surface-section" eyebrow="CAMADAS" title="ANÁLISE INDIVIDUAL DE EVIDÊNCIA">
        <div className="border-grid three-columns">{analysisLayers.map(([number, title, description]) => <article key={number}><span className="item-number">{number}</span><h3>{title}</h3><p>{description}</p></article>)}</div>
      </Section>
      <Section eyebrow="PRINCÍPIO" title="A FERRAMENTA APOIA. O PERITO INTERPRETA.">
        <p className="lead">O sistema apresenta hashes, metadados, estrutura, assinaturas, texto e vestígios observáveis. Não determina fraude, não substitui análise profissional e não produz score agregado de integridade.</p>
      </Section>
    </>
  )
}
