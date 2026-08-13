import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AvailabilityBadge } from '../components/StatusBadge'
import { ArtifactIcon, artifactKind, formatArtifactBytes } from '../components/WorkspaceArtifact'
import { useAnalysisSession, type WorkspaceAnalysis } from '../context/AnalysisSessionContext'
import { getCapabilities } from '../lib/api'
import type { Capabilities } from '../types/api'

const labels: Record<string, string> = { hashes: 'Hash', metadata: 'Metadata', ocr: 'OCR', signature: 'Signature', rust_json: 'Rust / JSON' }
const statusLabels: Record<WorkspaceAnalysis['status'], string> = {
  WAITING: 'Aguardando', UPLOADING: 'Enviando', QUEUED: 'Fila remota', PROCESSING: 'Analisando',
  SUCCESS: 'Concluído', PARTIAL: 'Parcial', FAILED: 'Falhou', LIMIT_EXCEEDED: 'Limite excedido', CANCELLED: 'Cancelado',
}

function WorkspaceRow({ item }: { item: WorkspaceAnalysis }) {
  const content = <><ArtifactIcon item={item} /><span><strong>{item.filename}</strong>{item.relativePath && <small>{item.relativePath}</small>}</span></>
  return <tr><td>{item.contract ? <Link className="workspace-artifact-link" to={`/app/result/${encodeURIComponent(item.analysisId)}`}>{content}</Link> : <span className="workspace-artifact-link">{content}</span>}</td><td>{artifactKind(item)}</td><td>{formatArtifactBytes(item.sizeBytes)}</td><td><span className={`analysis-state state-${item.status.toLowerCase()}`}>{statusLabels[item.status]}</span></td><td>{item.currentStage ?? '—'}</td></tr>
}

export function DashboardPage() {
  const { workspace } = useAnalysisSession()
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const loadCapabilities = useCallback(() => {
    setLoading(true); setError(false)
    getCapabilities().then(setCapabilities).catch(() => setError(true)).finally(() => setLoading(false))
  }, [])
  useEffect(loadCapabilities, [loadCapabilities])
  const items = workspace.analyses
  const terminal = items.filter((item) => ['SUCCESS', 'PARTIAL', 'FAILED', 'LIMIT_EXCEEDED', 'CANCELLED'].includes(item.status)).length
  const active = items.filter((item) => ['UPLOADING', 'QUEUED', 'PROCESSING'].includes(item.status)).length
  const waiting = items.filter((item) => item.status === 'WAITING').length

  return <div className="app-page"><div className="page-heading"><div><p className="eyebrow">WORKSPACE ATUAL</p><h1>{workspace.label}</h1><p>Artefatos descobertos e estado operacional desta sessão.</p></div><Link className="button-link" to="/app/analysis">Adicionar artefatos</Link></div>
    <section className="operational-summary" aria-label="Resumo do workspace"><div><span>Artefatos</span><strong>{items.length}</strong></div><div><span>Concluídos</span><strong>{terminal}</strong></div><div><span>Em análise</span><strong>{active}</strong></div><div><span>Na fila</span><strong>{waiting}</strong></div></section>
    <section className="app-panel workspace-overview"><h2>Artefatos do workspace</h2>{items.length === 0 ? <div className="session-empty"><strong>Workspace vazio.</strong><p>Selecione arquivos ou uma pasta para iniciar uma análise técnica.</p><Link className="button-link" to="/app/analysis">Nova análise</Link></div> : <div className="table-scroll"><table><thead><tr><th>Artefato</th><th>Tipo</th><th>Tamanho</th><th>Estado</th><th>Etapa</th></tr></thead><tbody>{items.map((item) => <WorkspaceRow key={item.clientUploadId} item={item} />)}</tbody></table></div>}</section>
    <section className="app-panel environment-panel"><h2>Ambiente / módulos</h2>{loading && <p className="compact-message">Consultando módulos…</p>}{error && <div className="capability-error" role="status"><span>Backend indisponível no momento.</span><button type="button" className="text-button" onClick={loadCapabilities}>Tentar novamente</button></div>}{capabilities && <div className="capability-grid">{Object.entries(labels).map(([key, label]) => <div key={key}><span>{label}</span><AvailabilityBadge available={Boolean(capabilities[key]?.available)} /></div>)}</div>}</section>
  </div>
}
