import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AvailabilityBadge } from '../components/StatusBadge'
import { TechnicalValue } from '../components/ui'
import { useAnalysisSession } from '../context/AnalysisSessionContext'
import { getCapabilities } from '../lib/api'
import type { AnalysisSummary, Capabilities } from '../types/api'

const labels: Record<string, string> = { hashes: 'Hash', metadata: 'Metadata', ocr: 'OCR', signature: 'Signature', rust_json: 'Rust / JSON' }

export function abbreviateHash(value: string): string {
  return value.length <= 16 ? value : `${value.slice(0, 8)}...${value.slice(-4)}`
}

function formatDuration(value: number | null): string {
  if (value === null) return '—'
  return value < 1000 ? `${value} ms` : `${(value / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`
}

function formatTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function AnalysisRow({ analysis }: { analysis: AnalysisSummary }) {
  return <tr><td><Link to={`/app/result/${encodeURIComponent(analysis.analysisId)}`}>{analysis.filename}</Link>{analysis.sha256 && <TechnicalValue canCopy copyValue={analysis.sha256}>{abbreviateHash(analysis.sha256)}</TechnicalValue>}</td><td><TechnicalValue>{analysis.detectedType ?? '—'}</TechnicalValue></td><td><span className={`analysis-state state-${analysis.status}`}>{analysis.status}</span></td><td><TechnicalValue>{formatDuration(analysis.durationMs)}</TechnicalValue></td><td>{analysis.findingsCount}</td><td>{analysis.limitationsCount}</td><td><TechnicalValue>{formatTime(analysis.createdAt)}</TechnicalValue></td></tr>
}

export function DashboardPage() {
  const { analyses } = useAnalysisSession()
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const loadCapabilities = useCallback(() => {
    setLoading(true); setError(false)
    getCapabilities().then(setCapabilities).catch(() => setError(true)).finally(() => setLoading(false))
  }, [])
  useEffect(loadCapabilities, [loadCapabilities])
  const summaries = analyses.map(({ summary }) => summary)
  const counts = {
    total: summaries.length,
    completed: summaries.filter(({ status }) => status === 'completed').length,
    partial: summaries.filter(({ status }) => status === 'partial').length,
    failed: summaries.filter(({ status }) => status === 'failed').length,
  }
  return <div className="app-page"><div className="page-heading"><div><p className="eyebrow">OVERVIEW</p><h1>Ambiente de análise</h1><p>Resultados desta sessão.</p></div><Link className="button-link" to="/app/analysis">Nova análise</Link></div><section className="operational-summary" aria-label="Resumo operacional"><div><span>Análises</span><strong>{counts.total}</strong></div><div><span>Concluídas</span><strong>{counts.completed}</strong></div><div><span>Parciais</span><strong>{counts.partial}</strong></div><div><span>Falhas</span><strong>{counts.failed}</strong></div></section><section className="app-panel recent-analyses"><h2>Últimas análises</h2>{summaries.length === 0 ? <div className="session-empty"><strong>Nenhuma análise nesta sessão.</strong><p>Envie um arquivo para iniciar uma análise técnica.</p><Link className="button-link" to="/app/analysis">Nova análise</Link></div> : <div className="table-scroll"><table><thead><tr><th>Arquivo</th><th>Tipo</th><th>Status</th><th>Duração</th><th>Findings</th><th>Limitações</th><th>Horário</th></tr></thead><tbody>{summaries.slice(0, 5).map((analysis) => <AnalysisRow key={analysis.analysisId} analysis={analysis} />)}</tbody></table></div>}</section><section className="app-panel environment-panel"><h2>Ambiente / módulos</h2>{loading && <p className="compact-message">Consultando módulos…</p>}{error && <div className="capability-error" role="status"><span>Backend indisponível no momento.</span><button type="button" className="text-button" onClick={loadCapabilities}>Tentar novamente</button></div>}{capabilities && <div className="capability-grid">{Object.entries(labels).map(([key, label]) => <div key={key}><span>{label}</span><AvailabilityBadge available={Boolean(capabilities[key]?.available)} /></div>)}</div>}</section></div>
}
