import { AlertTriangle, Check, Circle, FileWarning } from 'lucide-react'
import { ArtifactIcon, formatArtifactBytes } from './WorkspaceArtifact'
import { KeyValueGrid } from './ResultPresentation'
import { TechnicalValue } from './ui'
import type { AnalysisContract } from '../types/api'

function available(value: unknown): boolean {
  return value !== null && value !== undefined && value !== ''
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function findValue(value: unknown, keys: RegExp): unknown {
  const item = record(value)
  if (!item) return undefined
  for (const [key, child] of Object.entries(item)) {
    if (keys.test(key) && (typeof child !== 'object' || child === null)) return child
    const nested = findValue(child, keys)
    if (available(nested)) return nested
  }
}

function namedMetadata(metadata: Record<string, unknown>, matcher: RegExp): [string, unknown] | null {
  const entry = Object.entries(metadata).find(([key, value]) => matcher.test(key) && available(value))
  return entry ?? null
}

function SemanticMark({ tone }: { tone: 'ok' | 'neutral' | 'warning' | 'error' }) {
  if (tone === 'ok') return <Check size={15} aria-label="Confirmado" />
  if (tone === 'warning') return <AlertTriangle size={15} aria-label="Atenção" />
  if (tone === 'error') return <FileWarning size={15} aria-label="Erro técnico" />
  return <Circle size={11} aria-label="Informação neutra" />
}

function Metric({ label, value }: { label: string; value: unknown }) {
  if (!available(value)) return null
  return <div><dt>{label}</dt><dd>{String(value)}</dd></div>
}

export function ArtifactHeader({ result }: { result: AnalysisContract }) {
  const name = String(result.file.name ?? 'Evidência')
  const size = typeof result.file.size_bytes === 'number' ? formatArtifactBytes(result.file.size_bytes) : null
  const pages = findValue(result.technical_structure, /^(page_count|pages|number_of_pages)$/i)
  const version = findValue(result.technical_structure, /^(pdf_version|version)$/i)
  return <header className="artifact-result-header">
    <ArtifactIcon filename={name} detectedType={result.detected_type} size={34} />
    <div className="artifact-result-identity"><p className="eyebrow">ARTEFATO ANALISADO</p><h1>{name}</h1><p>{[result.detected_type ?? name.split('.').pop()?.toUpperCase() ?? 'ARQUIVO', size, available(pages) ? `${String(pages)} páginas` : null, available(version) ? `PDF ${String(version).replace(/^PDF\s*/i, '')}` : null].filter(Boolean).join(' · ')}</p></div>
    <span className={`artifact-analysis-state ${result.state}`}>{result.state === 'completed' ? 'ANÁLISE CONCLUÍDA' : result.state.toUpperCase()}</span>
    <div className="artifact-primary-hash"><span>SHA-256</span><TechnicalValue canCopy={Boolean(result.hashes.sha256)} copyValue={result.hashes.sha256}>{result.hashes.sha256 ?? 'Não disponibilizado'}</TechnicalValue></div>
  </header>
}

export function IdentificationSummary({ result }: { result: AnalysisContract }) {
  return <section className="forensic-summary-card" aria-labelledby="identification-summary-title"><h3 id="identification-summary-title">Identificação</h3><dl className="forensic-metrics">
    <Metric label="Nome" value={result.file.name} /><Metric label="Extensão declarada" value={result.declared_type} /><Metric label="Formato detectado" value={result.detected_type} />
    <Metric label="MIME" value={result.file.mime_type ?? result.metadata.mime_type} /><Metric label="Magic number" value={findValue(result.technical_structure, /magic(_number)?|signature/i)} />
    <Metric label="Tamanho" value={typeof result.file.size_bytes === 'number' ? `${Number(result.file.size_bytes).toLocaleString('pt-BR')} bytes` : null} />
  </dl></section>
}

export function StructureSummary({ result }: { result: AnalysisContract }) {
  const values = [
    ['Versão', findValue(result.technical_structure, /^(pdf_version|version)$/i)], ['Objetos', findValue(result.technical_structure, /^(object_count|objects)$/i)],
    ['Streams', findValue(result.technical_structure, /^(stream_count|streams)$/i)], ['XRef streams', findValue(result.technical_structure, /xref_stream/i)],
    ['Trailers', findValue(result.technical_structure, /trailer_count|trailers/i)], ['Revisões incrementais', findValue(result.technical_structure, /incremental.*(count|revision)|revision_count/i)],
    ['Marcadores EOF', findValue(result.technical_structure, /eof.*count|eof_markers/i)],
  ].filter(([, value]) => available(value))
  return <section className="forensic-summary-card" aria-labelledby="structure-summary-title"><h3 id="structure-summary-title">Estrutura</h3>{values.length ? <dl className="forensic-metrics">{values.map(([label, value]) => <Metric key={String(label)} label={String(label)} value={value} />)}</dl> : <p className="forensic-neutral"><SemanticMark tone="neutral" /> Nenhum resumo estrutural específico foi disponibilizado.</p>}</section>
}

export function MetadataSummary({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = [
    namedMetadata(metadata, /^(create|creation).*date$/i), namedMetadata(metadata, /^(modify|modification).*date$/i), namedMetadata(metadata, /producer/i), namedMetadata(metadata, /^creator$/i), namedMetadata(metadata, /^author$/i),
  ].filter((item): item is [string, unknown] => Boolean(item))
  return <section className="forensic-summary-card" aria-labelledby="metadata-summary-title"><h3 id="metadata-summary-title">Metadados relevantes</h3>{entries.length ? <dl className="forensic-metrics">{entries.map(([key, value]) => <Metric key={key} label={key} value={value} />)}</dl> : <p className="forensic-neutral"><SemanticMark tone="neutral" /> Nenhum metadado prioritário foi disponibilizado.</p>}</section>
}

export function SignatureSummary({ signatures }: { signatures: Array<Record<string, unknown>> }) {
  return <section className="forensic-summary-card" aria-labelledby="signature-summary-title"><h3 id="signature-summary-title">Assinaturas criptográficas</h3>{signatures.length ? <p className="forensic-confirmed"><SemanticMark tone="ok" /> {signatures.length} assinatura(s) incorporada(s) reportada(s).</p> : <p className="forensic-neutral"><SemanticMark tone="neutral" /> Nenhuma assinatura criptográfica incorporada foi encontrada.</p>}</section>
}

export function EntitySummary({ result }: { result: AnalysisContract }) {
  const entityFacts = result.facts.filter((fact) => /entit|cpf|cnpj|phone|email|address|date|value/i.test(String(fact.kind ?? '')))
  const count = (result.ip_addresses?.length ?? 0) + entityFacts.length
  return <section className="forensic-summary-card" aria-labelledby="entity-summary-title"><h3 id="entity-summary-title">Entidades</h3>{count ? <div className="entity-summary-list">{result.ip_addresses?.map((item, index) => <details key={String(item.ip ?? item.value ?? index)}><summary>IP · {String(item.ip ?? item.value ?? 'valor reportado')}</summary><KeyValueGrid value={item} /></details>)}{entityFacts.map((fact, index) => <details key={String(fact.fact_id ?? index)}><summary>{String(fact.kind ?? 'Entidade')}</summary><KeyValueGrid value={fact} /></details>)}</div> : <p className="forensic-neutral"><SemanticMark tone="neutral" /> Nenhuma entidade foi reportada no contrato.</p>}</section>
}

export function ForensicSummary({ result }: { result: AnalysisContract }) {
  return <section id="summary" className="forensic-summary" aria-labelledby="forensic-summary-title"><header><p className="eyebrow">CAMADA 1</p><h2 id="forensic-summary-title">Resumo forense</h2><p>Leitura sintética de fatos disponibilizados pelo AnalysisContract.</p></header><div className="forensic-summary-grid"><IdentificationSummary result={result} /><StructureSummary result={result} /><MetadataSummary metadata={result.metadata} /><SignatureSummary signatures={result.signatures} /><EntitySummary result={result} /></div></section>
}
