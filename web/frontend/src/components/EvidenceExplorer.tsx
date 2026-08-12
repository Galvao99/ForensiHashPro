import { useState } from 'react'

const categories = [
  { id: 'arquivo', label: 'Arquivo', fields: ['SHA-256', 'Metadata', 'Producer'], detail: 'O hash permite comparar a identidade binária de um artefato. Metadados descrevem campos técnicos disponíveis no próprio arquivo.' },
  { id: 'contexto', label: 'Contexto', fields: ['IP observado', 'User-Agent', 'Timestamp'], detail: 'O IP pode registrar contexto de rede observado por determinado sistema. Não identifica, isoladamente, uma pessoa.' },
  { id: 'eventos', label: 'Eventos', fields: ['Visualização', 'Aceite', 'Finalização'], detail: 'Eventos documentam ocorrências registradas pelo sistema produtor, dentro das garantias e limitações desse mecanismo.' },
  { id: 'custodia', label: 'Custódia', fields: ['T0', 'T1', 'T2'], detail: 'Marcos de custódia organizam o histórico documentado do artefato sem afirmar o que ocorreu antes do primeiro registro.' },
]

export function EvidenceExplorer() {
  const [active, setActive] = useState(categories[0])
  return (
    <div className="evidence-explorer">
      <div className="evidence-explorer__file"><span>ARTEFATO / EXEMPLO DIDÁTICO</span><strong>CONTRATO.PDF</strong><small>application/pdf · document</small></div>
      <div className="evidence-explorer__tabs" role="tablist" aria-label="Categorias de informação do artefato">
        {categories.map(category => <button key={category.id} id={`tab-${category.id}`} type="button" role="tab" aria-selected={active.id === category.id} aria-controls={`panel-${category.id}`} onClick={() => setActive(category)}>{category.label}</button>)}
      </div>
      <div id={`panel-${active.id}`} className="evidence-explorer__panel" role="tabpanel" aria-labelledby={`tab-${active.id}`} tabIndex={0}>
        <div>{active.fields.map(field => <code key={field}>{field}</code>)}</div>
        <p>{active.detail}</p>
      </div>
    </div>
  )
}
