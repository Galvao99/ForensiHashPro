import { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { AlertTriangle, Check, Circle, FilePlus, FolderPlus, LoaderCircle, X } from 'lucide-react'
import { TechnicalValue } from '../components/ui'
import {
  BiometricResultView, ExecutionResultView, FactsResultView, FindingsResultView,
  HashResultView, LimitationsResultView, MetadataResultView, OverviewResultView,
  RawTechnicalDataView, SignatureResultView, StructureResultView, TechnicalSection,
  TextOcrResultView,
} from '../components/ResultPresentation'
import { useAnalysisSession, type WorkspaceAnalysis } from '../context/AnalysisSessionContext'
import { useAuth } from '../context/AuthContext'
import type { AnalysisContract } from '../types/api'

export function ResultView({ result }: { result: AnalysisContract }) {
  const nav = [['summary', 'Overview'], ['hashes', 'Hashes'], ['metadata', 'Metadados'], ['structure', 'Estrutura'], ['signatures', 'Assinaturas'], ['text', 'Texto / OCR'], ['biometrics', 'Biometria'], ['facts', 'Fatos'], ['findings', 'Findings'], ['limitations', 'Limitações'], ['execution', 'Execução']]
  return <div className="app-page result-page"><div className="result-header"><div><p className="eyebrow">RESULTADO TÉCNICO</p><h1>{String(result.file.name ?? 'Evidência')}</h1></div><span className="technical-state">{result.state}</span></div><div className="primary-hash"><span>SHA-256</span><TechnicalValue canCopy copyValue={result.hashes.sha256}>{result.hashes.sha256 ?? 'Não disponível'}</TechnicalValue></div><nav className="result-nav" aria-label="Seções do resultado">{nav.map(([id, navLabel]) => <a key={id} href={`#${id}`}>{navLabel}</a>)}</nav><TechnicalSection id="summary" title="Overview"><OverviewResultView result={result} /></TechnicalSection><TechnicalSection id="hashes" title="Hashes"><HashResultView hashes={result.hashes} /></TechnicalSection><TechnicalSection id="metadata" title="Metadados"><MetadataResultView metadata={result.metadata} /></TechnicalSection><TechnicalSection id="structure" title="Estrutura"><StructureResultView structure={result.technical_structure} /></TechnicalSection><TechnicalSection id="signatures" title="Assinaturas"><SignatureResultView signatures={result.signatures} /></TechnicalSection><TechnicalSection id="text" title="Texto / OCR"><TextOcrResultView nativeText={result.native_text} ocr={result.ocr} /></TechnicalSection><TechnicalSection id="biometrics" title="Biometria"><BiometricResultView biometrics={result.biometrics} /></TechnicalSection><TechnicalSection id="facts" title="Fatos"><FactsResultView facts={result.facts} /></TechnicalSection><TechnicalSection id="findings" title="Findings"><FindingsResultView findings={result.findings} /></TechnicalSection><TechnicalSection id="limitations" title="Limitações"><LimitationsResultView limitations={result.limitations} /></TechnicalSection><TechnicalSection id="execution" title="Execução"><ExecutionResultView steps={result.processing_steps} /></TechnicalSection><section className="raw-technical-section" aria-labelledby="raw-technical-title"><h2 id="raw-technical-title">Dados técnicos completos</h2><RawTechnicalDataView result={result} /></section></div>
}

const workspaceStatusLabels: Record<WorkspaceAnalysis['status'], string> = {
  QUEUED: 'Na fila',
  UPLOADING: 'Enviando',
  PROCESSING: 'Analisando',
  SUCCESS: 'Concluído',
  PARTIAL: 'Parcial',
  FAILED: 'Falhou',
  LIMIT_EXCEEDED: 'Limite excedido',
  CANCELLED: 'Cancelado',
}

function isRunning(item: WorkspaceAnalysis) {
  return item.status === 'UPLOADING' || item.status === 'QUEUED' || item.status === 'PROCESSING'
}

function ActivityIcon({ status }: { status: WorkspaceAnalysis['status'] }) {
  if (status === 'UPLOADING' || status === 'PROCESSING') return <LoaderCircle className="activity-spinner" size={15} aria-hidden="true" />
  if (status === 'SUCCESS') return <Check size={15} aria-hidden="true" />
  if (status === 'FAILED' || status === 'LIMIT_EXCEEDED') return <AlertTriangle size={15} aria-hidden="true" />
  return <Circle size={11} aria-hidden="true" />
}

function elapsed(startedAt?: string): string {
  if (!startedAt) return '00:00'
  const total = Math.max(0, Math.floor((Date.now() - Date.parse(startedAt)) / 1000))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function PendingAnalysis({ item }: { item: WorkspaceAnalysis }) {
  const [, tick] = useState(0)
  useEffect(() => {
    if (item.status !== 'PROCESSING') return
    const timer = window.setInterval(() => tick((value) => value + 1), 1_000)
    return () => window.clearInterval(timer)
  }, [item.status])
  const busy = isRunning(item)
  return <div className="app-page workspace-pending" aria-live="polite" aria-busy={busy}><p className="eyebrow">ANÁLISE EM ANDAMENTO</p><h1>{item.filename}</h1>{item.relativePath && <p><TechnicalValue>{item.relativePath}</TechnicalValue></p>}<div className="processing-indicator"><ActivityIcon status={item.status} /><strong>{workspaceStatusLabels[item.status]}</strong></div><dl className="processing-facts"><div><dt>Etapa atual</dt><dd>{item.currentStage === 'CONSOLIDATING' ? 'Consolidando resultados' : item.status === 'QUEUED' ? 'Aguardando executor' : item.status === 'UPLOADING' ? 'Preparando upload seguro' : 'Análise técnica em andamento'}</dd></div><div><dt>Status</dt><dd>{item.status}</dd></div><div><dt>Tempo decorrido</dt><dd>{item.status === 'PROCESSING' ? elapsed(item.startedAt) : '00:00'}</dd></div></dl>{item.error ? <p role="alert" className="error-panel">{item.error}</p> : <p>O restante do workspace permanece disponível durante o processamento.</p>}</div>
}

export function ResultPage() {
  const location = useLocation()
  const { analysisId } = useParams()
  const { privacy, csrfToken } = useAuth()
  const { workspace, getAnalysis, isPersisted, openAnalysis, enqueueFiles, setActiveAnalysis, closeAnalysis, closeAllAnalyses } = useAnalysisSession()
  const [message, setMessage] = useState('')
  const filesInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const openedRoute = useRef<string | null>(null)
  const routedState = location.state as { result?: AnalysisContract; persisted?: boolean } | null
  const routed = routedState?.result ?? (analysisId ? getAnalysis(analysisId) : undefined)

  useEffect(() => {
    if (routed && openedRoute.current !== routed.analysis_id) {
      openedRoute.current = routed.analysis_id
      openAnalysis(routed, routedState?.persisted ?? (analysisId ? isPersisted(analysisId) : false))
    }
  }, [analysisId, isPersisted, openAnalysis, routed, routedState?.persisted])

  const active = workspace.analyses.find((item) => item.analysisId === workspace.activeAnalysisId)
  const workspaceCounts = workspace.analyses.reduce((counts, item) => {
    if (item.status === 'SUCCESS' || item.status === 'PARTIAL') counts.completed += 1
    if (item.status === 'PROCESSING' || item.status === 'UPLOADING') counts.processing += 1
    if (item.status === 'QUEUED') counts.queued += 1
    return counts
  }, { completed: 0, processing: 0, queued: 0 })

  function enqueue(event: ChangeEvent<HTMLInputElement>) {
    const result = enqueueFiles(Array.from(event.target.files ?? []), {
      retentionMode: privacy?.retention_mode,
      privateSession: privacy?.retention_mode === 'PRIVATE',
      csrfToken,
    })
    setMessage(result.message ?? '')
    event.target.value = ''
  }

  function close(item: WorkspaceAnalysis) {
    if (isRunning(item) && !window.confirm(`A análise de ${item.filename} continuará no servidor. Fechar a aba mesmo assim?`)) return
    closeAnalysis(item.analysisId)
  }

  function closeAll() {
    if (workspace.analyses.some(isRunning) && !window.confirm('Análises em processamento continuarão no servidor. Fechar todas as abas mesmo assim?')) return
    closeAllAnalyses()
  }

  function tabKeyboard(event: KeyboardEvent<HTMLDivElement>, analysis: WorkspaceAnalysis) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setActiveAnalysis(analysis.analysisId)
    }
  }

  const directoryAttributes = { webkitdirectory: '', directory: '' }

  if (!active && workspace.analyses.length === 0 && !routed) return <div className="app-page"><h1>Resultado não disponível nesta sessão</h1><Link className="button-link" to="/app/analysis">Iniciar análise</Link></div>

  return <div className="workspace-page">
    {active?.contract ? <ResultView result={active.contract} /> : active ? <PendingAnalysis item={active} /> : <div className="app-page"><p>Preparando workspace…</p></div>}
    <section className="workspace-dock" aria-label="Workspace de análises">
      <div className="workspace-toolbar"><div className="workspace-summary"><strong>{workspace.label}</strong><small>{workspace.analyses.length} arquivos · {workspaceCounts.completed} concluídos · {workspaceCounts.processing} analisando · {workspaceCounts.queued} na fila</small></div><div><input ref={filesInput} type="file" multiple aria-label="Adicionar arquivos" onChange={enqueue} /><input ref={folderInput} type="file" multiple aria-label="Adicionar pasta" onChange={enqueue} {...directoryAttributes} /><button type="button" onClick={() => filesInput.current?.click()}><FilePlus size={15} />Adicionar arquivos</button><button type="button" onClick={() => folderInput.current?.click()}><FolderPlus size={15} />Adicionar pasta</button><button type="button" onClick={closeAll}>Fechar todas as abas</button></div></div>
      {message && <p role="alert" className="workspace-message">{message}</p>}
      <div className="workspace-tabs" role="tablist" aria-label="Análises abertas">
        {workspace.analyses.map((item) => <div key={item.analysisId} role="tab" tabIndex={0} aria-selected={item.analysisId === workspace.activeAnalysisId} className={`workspace-tab ${item.analysisId === workspace.activeAnalysisId ? 'active' : ''}`} onClick={() => setActiveAnalysis(item.analysisId)} onKeyDown={(event) => tabKeyboard(event, item)}><ActivityIcon status={item.status} /><span className="workspace-tab-name" title={item.relativePath ?? item.filename}>{item.filename}</span><small className={`workspace-tab-status state-${item.status.toLowerCase()}`}>{workspaceStatusLabels[item.status]}</small><button type="button" aria-label={`Fechar análise de ${item.filename}`} onClick={(event) => { event.stopPropagation(); close(item) }}><X size={13} /></button></div>)}
      </div>
    </section>
  </div>
}
