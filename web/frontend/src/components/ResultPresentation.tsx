import type { ReactNode } from 'react'
import { JsonView } from './JsonView'
import { StatusBadge } from './StatusBadge'
import { TechnicalValue } from './ui'
import type { AnalysisContract, ProcessingStatus } from '../types/api'

const PROCESSING_STATUSES = new Set<ProcessingStatus>(['success', 'no_findings', 'partial', 'skipped', 'unavailable', 'failed', 'cancelled', 'limit_exceeded'])

function present(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return false
  if (Array.isArray(value)) return value.some(present)
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).some(present)
  return true
}

function label(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

function textValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não'
  return String(value)
}

function statusBadge(value: unknown): ReactNode {
  const normalized = String(value ?? '').toLowerCase() as ProcessingStatus
  return PROCESSING_STATUSES.has(normalized) ? <StatusBadge status={normalized} /> : <span className="technical-state">{String(value ?? 'Não disponível')}</span>
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state technical-empty">{children}</p>
}

export function TechnicalSection({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return <section id={id} className="result-section"><header><h2>{title}</h2></header>{children}</section>
}

export function KeyValueGrid({ value, depth = 0 }: { value: Record<string, unknown>; depth?: number }) {
  const entries = Object.entries(value).filter(([, item]) => present(item))
  if (!entries.length) return <EmptyState>Nenhum dado aplicável foi reportado.</EmptyState>
  return <dl className="key-value-grid">{entries.map(([key, item]) => <div key={key}><dt>{label(key)}</dt><dd><StructuredValue value={item} depth={depth} /></dd></div>)}</dl>
}

function StructuredValue({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (!present(value)) return null
  if (Array.isArray(value)) {
    return <div className="structured-list">{value.filter(present).map((item, index) => <article key={index}>{typeof item === 'object' && item !== null ? <KeyValueGrid value={item as Record<string, unknown>} depth={depth + 1} /> : <TechnicalValue>{textValue(item)}</TechnicalValue>}</article>)}</div>
  }
  if (typeof value === 'object' && value !== null) {
    if (depth >= 2) return <details className="technical-details"><summary>Ver detalhes</summary><KeyValueGrid value={value as Record<string, unknown>} depth={depth + 1} /></details>
    return <KeyValueGrid value={value as Record<string, unknown>} depth={depth + 1} />
  }
  return <TechnicalValue>{textValue(value)}</TechnicalValue>
}

function duration(result: AnalysisContract): string {
  const start = Date.parse(String(result.execution.started_at ?? ''))
  const finish = Date.parse(String(result.execution.finished_at ?? ''))
  return Number.isFinite(start) && Number.isFinite(finish) ? `${((finish - start) / 1000).toLocaleString('pt-BR')} s` : 'Não disponível'
}

export function OverviewResultView({ result }: { result: AnalysisContract }) {
  const values = [
    ['Arquivo', result.file.name], ['Tipo detectado', result.detected_type], ['Tamanho', present(result.file.size_bytes) ? `${Number(result.file.size_bytes).toLocaleString('pt-BR')} bytes` : null],
    ['Estado', result.state], ['Duração', duration(result)], ['Finalização', result.execution.finished_at],
    ['Findings', result.findings.length], ['Limitações', result.limitations.length],
    ['Assinaturas', result.signatures.length ? `${result.signatures.length} identificada(s)` : 'Nenhuma identificada'],
    ['OCR', result.ocr ? 'Executado / disponível' : 'Não executado ou indisponível'],
  ] as Array<[string, unknown]>
  return <div className="overview-grid">{values.filter(([, value]) => present(value)).map(([key, value]) => <div key={key}><span>{key}</span>{key === 'Estado' ? statusBadge(value) : <strong>{String(value)}</strong>}</div>)}</div>
}

export function HashResultView({ hashes }: { hashes: Record<string, string> }) {
  const entries = Object.entries(hashes).filter(([, value]) => present(value))
  if (!entries.length) return <EmptyState>Nenhum hash foi reportado.</EmptyState>
  return <div className="table-scroll"><table className="technical-table hash-table"><thead><tr><th>Algoritmo</th><th>Valor</th><th>Ação</th></tr></thead><tbody>{entries.map(([algorithm, value]) => <tr key={algorithm}><td>{algorithm.toUpperCase()}</td><td><TechnicalValue>{value}</TechnicalValue></td><td><TechnicalValue canCopy copyValue={value}>{value.slice(0, 8)}…{value.slice(-4)}</TechnicalValue></td></tr>)}</tbody></table></div>
}

const METADATA_GROUPS = [
  ['Documento', /producer|creator|author|title|subject|description|document|pdf/i],
  ['Datas', /date|time|created|modified/i],
  ['Software', /software|application|firmware|tool/i],
  ['Dispositivo', /device|model|make|camera|lens|serial/i],
  ['Imagem', /image|width|height|resolution|color|pixel|orientation/i],
  ['Localização', /gps|latitude|longitude|location|city|country/i],
] as const

export function MetadataResultView({ metadata }: { metadata: Record<string, unknown> }) {
  const remaining = new Map(Object.entries(metadata).filter(([, value]) => present(value)))
  const groups: Array<[string, Record<string, unknown>]> = METADATA_GROUPS.map(([name, matcher]): [string, Record<string, unknown>] => {
    const fields: Record<string, unknown> = {}
    for (const [key, value] of remaining) if (matcher.test(key)) { fields[key] = value; remaining.delete(key) }
    return [name, fields]
  }).filter(([, fields]) => Object.keys(fields).length)
  if (remaining.size) groups.push(['Outros metadados', Object.fromEntries(remaining)])
  if (!groups.length) return <EmptyState>Nenhum metadado útil foi reportado.</EmptyState>
  return <div className="technical-groups">{groups.map(([name, fields]) => <section key={name}><h3>{name}</h3><KeyValueGrid value={fields} /></section>)}<details className="technical-details"><summary>Ver todos os metadados</summary><KeyValueGrid value={metadata} /></details></div>
}

export function StructureResultView({ structure }: { structure: Record<string, unknown> }) {
  return present(structure) ? <KeyValueGrid value={structure} /> : <EmptyState>Nenhum dado estrutural foi reportado.</EmptyState>
}

export function SignatureResultView({ signatures }: { signatures: Array<Record<string, unknown>> }) {
  if (!signatures.length) return <EmptyState>Nenhuma assinatura digital incorporada foi identificada.</EmptyState>
  return <div className="technical-card-list">{signatures.map((signature, index) => <article className="technical-card" key={index}><h3>Assinatura #{index + 1}</h3><KeyValueGrid value={signature} /></article>)}</div>
}

function ExtractedText({ title, value, unavailable }: { title: string; value: Record<string, unknown> | null; unavailable: string }) {
  if (!value) return <article className="technical-card"><h3>{title}</h3><EmptyState>{unavailable}</EmptyState></article>
  const contentKey = ['text', 'content', 'value'].find((key) => typeof value[key] === 'string')
  const content = contentKey ? String(value[contentKey]) : ''
  const details = Object.fromEntries(Object.entries(value).filter(([key, item]) => key !== contentKey && present(item)))
  return <article className="technical-card"><h3>{title}</h3><div className="text-metrics"><span>Caracteres</span><strong>{content.length.toLocaleString('pt-BR')}</strong></div>{Object.keys(details).length > 0 && <KeyValueGrid value={details} />}{content && <details className="extracted-text"><summary>Ver texto extraído</summary><TechnicalValue canCopy copyValue={content}>{content}</TechnicalValue></details>}</article>
}

export function TextOcrResultView({ nativeText, ocr }: { nativeText: Record<string, unknown> | null; ocr: Record<string, unknown> | null }) {
  return <div className="text-columns"><ExtractedText title="Texto nativo" value={nativeText} unavailable="Texto nativo não identificado." /><ExtractedText title="OCR" value={ocr} unavailable="OCR não executado ou indisponível; consulte as etapas de execução." /></div>
}

export function BiometricResultView({ biometrics }: { biometrics: Record<string, unknown> | null }) {
  return biometrics && present(biometrics) ? <KeyValueGrid value={biometrics} /> : <EmptyState>Biometria não executada ou não aplicável.</EmptyState>
}

export function FactsResultView({ facts }: { facts: Array<Record<string, unknown>> }) {
  if (!facts.length) return <EmptyState>Nenhum fato técnico foi reportado.</EmptyState>
  return <div className="technical-card-list">{facts.map((fact, index) => <article className="technical-card" key={String(fact.fact_id ?? index)}><h3>Fato técnico: {label(String(fact.kind ?? index + 1))}</h3><KeyValueGrid value={fact} /></article>)}</div>
}

export function FindingsResultView({ findings }: { findings: Array<Record<string, unknown>> }) {
  if (!findings.length) return <EmptyState>Nenhum finding foi reportado.</EmptyState>
  return <div className="technical-card-list">{findings.map((finding, index) => <article className="technical-card finding-card" key={String(finding.finding_id ?? finding.id ?? index)}><header><h3>{String(finding.title ?? finding.kind ?? `Finding ${index + 1}`)}</h3>{present(finding.severity) && <span className="technical-state">{String(finding.severity)}</span>}</header><KeyValueGrid value={finding} /></article>)}</div>
}

export function LimitationsResultView({ limitations }: { limitations: Array<Record<string, unknown>> }) {
  if (!limitations.length) return <EmptyState>Nenhuma limitação foi reportada.</EmptyState>
  return <div className="limitation-list">{limitations.map((limitation, index) => <article key={String(limitation.limitation_id ?? limitation.id ?? index)}><h3>{String(limitation.message ?? limitation.title ?? 'Limitação')}</h3><KeyValueGrid value={Object.fromEntries(Object.entries(limitation).filter(([key]) => key !== 'message' && key !== 'title'))} /></article>)}</div>
}

export function ExecutionResultView({ steps }: { steps: AnalysisContract['processing_steps'] }) {
  if (!steps.length) return <EmptyState>Nenhuma etapa de execução foi reportada.</EmptyState>
  return <div className="table-scroll"><table className="technical-table execution-table"><thead><tr><th>Etapa</th><th>Status</th><th>Duração</th><th>Mensagem</th></tr></thead><tbody>{steps.map((step, index) => <tr key={step.step_id ?? index}><td>{String(step.component ?? step.code)}</td><td>{statusBadge(step.status)}</td><td><TechnicalValue>{typeof step.duration_ms === 'number' ? `${step.duration_ms} ms` : '—'}</TechnicalValue></td><td>{step.user_message ?? step.technical_message ?? '—'}</td></tr>)}</tbody></table></div>
}

export function RawTechnicalDataView({ result }: { result: AnalysisContract }) {
  const raw = JSON.stringify(result, null, 2)
  return <details className="raw-result"><summary>Expandir JSON</summary><div className="raw-result-actions"><TechnicalValue canCopy copyValue={raw}>AnalysisContract 1.0.0 completo</TechnicalValue></div><JsonView value={result} /></details>
}
