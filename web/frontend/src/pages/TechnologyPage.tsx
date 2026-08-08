import { Section } from '../components/ui'
import { currentTechnologies, roadmapTechnologies } from '../content/technologies'

function TechnologyGrid({ items }: { items: string[][] }) {
  return <div className="border-grid three-columns">{items.map(([name, description]) => <article key={name}><h3>{name}</h3><p>{description}</p></article>)}</div>
}

export function TechnologyPage() {
  return (
    <>
      <Section eyebrow="TECNOLOGIA" title="COMPONENTES REAIS. RESPONSABILIDADES DEFINIDAS."><p className="lead">A plataforma combina um núcleo Python, componentes especializados e ferramentas externas detectadas pelo ambiente. A interface não replica regras de análise.</p></Section>
      <Section className="surface-section" eyebrow="UTILIZADO ATUALMENTE" title="STACK TÉCNICA"><TechnologyGrid items={currentTechnologies} /></Section>
      <Section eyebrow="ROADMAP" title="EM DESENVOLVIMENTO / PLANEJADO"><TechnologyGrid items={roadmapTechnologies} /></Section>
    </>
  )
}
