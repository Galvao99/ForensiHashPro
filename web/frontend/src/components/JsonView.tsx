import { TechnicalValue } from './ui'

export function JsonView({ value }: { value: unknown }) {
  if (value === null) return <p className="empty-state">Etapa não executada ou fora do escopo.</p>
  if (Array.isArray(value) && value.length === 0) return <p className="empty-state">Etapa executada sem itens.</p>
  if (typeof value !== 'object') return <TechnicalValue>{String(value)}</TechnicalValue>
  return <pre className="json-view">{JSON.stringify(value, null, 2)}</pre>
}
