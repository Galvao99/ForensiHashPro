import { Section } from '../components/ui'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { references } from '../content/references'

export function ReferencesPage() {
  return (
    <><DocumentMetadata title="Referências Técnicas e Jurídicas | ARQEN" description="Fontes técnicas, normativas e jurídicas que contextualizam temas abordados pelos produtos ARQEN." /><Section eyebrow="FONTES" title="REFERÊNCIAS INSTITUCIONAIS E TÉCNICAS">
      <p className="lead">Fontes utilizadas para contextualizar afirmações específicas. Elas não representam certificação, homologação ou reconhecimento do ForensiHash ou do DDNA.</p>
      <div className="reference-list">{references.map((reference) => <article key={reference.id}><div><span>{reference.category}</span><h2>{reference.title}</h2><p>{reference.institution} · {reference.date}</p><p>{reference.purpose}</p></div><a href={reference.url} target="_blank" rel="noreferrer">Abrir fonte original ↗</a></article>)}</div>
    </Section></>
  )
}
