import { KeyValueGrid } from './ResultPresentation'
import type { AnalysisContract } from '../types/api'

const ENTITY_LABELS: Record<string, string> = {
  cpf: 'CPF', phone: 'Telefone', ip: 'Endereço IP', email: 'E-mail', datetime: 'Data', date: 'Data', money: 'Valor', value: 'Valor',
  unknown_numeric_identifier: 'Identificador numérico', ambiguous: 'Entidade ambígua', cnpj: 'CNPJ', name: 'Nome', document: 'Documento',
}

const SOURCE_LABELS: Record<string, string> = {
  native_text: 'Texto nativo', ocr: 'OCR', metadata: 'Metadados', json: 'JSON', structured: 'Dados estruturados', legacy_text: 'Texto extraído',
}

export interface PresentedEntity {
  id: string
  originalType: string
  label: string
  value: string | null
  fact: Record<string, unknown>
  provenance: Array<Record<string, unknown>>
}

function object(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

export function entityLabel(type: string): string {
  return ENTITY_LABELS[type.toLowerCase()] ?? type.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function summaryValue(type: string, value: string): string {
  if (type === 'cpf' && value.replace(/\D/g, '').length === 11) return `${value.replace(/\D/g, '').slice(0, 3)}.***.***-**`
  if (type === 'phone') return value.length > 4 ? `${'*'.repeat(Math.min(8, value.length - 4))}${value.slice(-4)}` : value
  if (type === 'ip') return value.split('.').map((part, index) => index === 0 || index === 3 ? part : 'xxx').join('.')
  if (type === 'email') { const [name, domain] = value.split('@'); return domain ? `${name.slice(0, 1)}***@${domain}` : value }
  return value
}

export function entitiesFromResult(result: AnalysisContract): PresentedEntity[] {
  const facts = result.facts.flatMap((fact, index) => {
    const data = object(fact.data)
    const originalType = String(data?.type ?? (String(fact.kind ?? '') !== 'entity' ? fact.kind ?? '' : '')).toLowerCase()
    if (String(fact.kind ?? '') !== 'entity' && !data?.type) return []
    const rawValue = data?.normalized_value ?? (Array.isArray(data?.raw_values) ? data.raw_values[0] : null)
    return [{ id: String(fact.fact_id ?? `entity-${index}`), originalType: originalType || 'entity', label: entityLabel(originalType || 'entity'), value: rawValue == null ? null : String(rawValue), fact, provenance: Array.isArray(data?.provenance) ? data.provenance.filter((item): item is Record<string, unknown> => Boolean(object(item))) : [] }]
  })
  const ips = (result.ip_addresses ?? []).map((item, index): PresentedEntity => ({ id: String(item.evidence_ref ?? item.ip ?? item.value ?? `ip-${index}`), originalType: 'ip', label: 'Endereço IP', value: item.ip == null && item.value == null ? null : String(item.ip ?? item.value), fact: item, provenance: [], }))
  return [...facts, ...ips]
}

function EntityDetails({ entity }: { entity: PresentedEntity }) {
  const data = object(entity.fact.data) ?? entity.fact
  return <details className="entity-card"><summary><span><strong>{entity.label}</strong><small>{entity.value ? summaryValue(entity.originalType, entity.value) : 'Valor não disponibilizado'}</small></span><span aria-hidden="true">＋</span></summary><div className="entity-card-details"><dl><div><dt>Tipo</dt><dd>{entity.label}</dd></div>{entity.value && <div><dt>Valor</dt><dd>{entity.value}</dd></div>}</dl>{entity.provenance.map((source, index) => <section key={index} aria-label={`Proveniência ${index + 1}`}><h4>Proveniência {entity.provenance.length > 1 ? index + 1 : ''}</h4><KeyValueGrid value={{ artifact: source.filename ?? source.evidence_ref, origin: SOURCE_LABELS[String(source.source_type ?? '')] ?? source.source_type, engine: source.extractor, page: source.page, evidence_reference: source.evidence_ref, field: source.field_path, context_before: source.context_before, context_after: source.context_after }} /></section>)}<details className="technical-details"><summary>Ver entidade técnica</summary><KeyValueGrid value={data} /></details></div></details>
}

export function EntityResultView({ result, compact = false }: { result: AnalysisContract; compact?: boolean }) {
  const entities = entitiesFromResult(result)
  if (!entities.length) return <p className="empty-state technical-empty">Nenhuma entidade foi identificada neste artefato.</p>
  return <div className={compact ? 'entity-summary-list' : 'entity-result-list'}>{entities.map((entity) => <EntityDetails key={entity.id} entity={entity} />)}</div>
}
