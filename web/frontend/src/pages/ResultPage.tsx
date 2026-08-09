import { ChangeEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { AlertTriangle, Check, Circle, FilePlus, FolderPlus, LoaderCircle, X } from 'lucide-react'
import { JsonView } from '../components/JsonView'
import { StatusBadge } from '../components/StatusBadge'
import { TechnicalValue } from '../components/ui'
import { useAnalysisSession, type WorkspaceAnalysis } from '../context/AnalysisSessionContext'
import { useAuth } from '../context/AuthContext'
import type { AnalysisContract, ProcessingStatus } from '../types/api'

function duration(result: AnalysisContract) { const start = Date.parse(String(result.execution.started_at ?? '')); const finish = Date.parse(String(result.execution.finished_at ?? '')); return Number.isFinite(start) && Number.isFinite(finish) ? `${((finish - start) / 1000).toLocaleString('pt-BR')} s` : '—' }
function stateStatus(state: string): ProcessingStatus { return state === 'completed' ? 'success' : state === 'partial' ? 'partial' : state === 'cancelled' ? 'cancelled' : 'failed' }
function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) { return <section id={id} className="result-section"><header><h2>{title}</h2></header>{children}</section> }
function KeyValues({ value }: { value: Record<string, unknown> }) { return <dl className="key-values">{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key}</dt><dd>{typeof item === 'object' && item !== null ? <details><summary>Ver dados</summary><JsonView value={item} /></details> : <TechnicalValue>{String(item ?? '—')}</TechnicalValue>}</dd></div>)}</dl> }

export function ResultView({ result }: { result: AnalysisContract }) {
  const nav = [['summary', 'Overview'], ['hashes', 'Hashes'], ['metadata', 'Metadados'], ['structure', 'Estrutura'], ['signatures', 'Assinaturas'], ['text', 'Texto / OCR'], ['biometrics', 'Biometria'], ['facts', 'Fatos'], ['findings', 'Findings'], ['limitations', 'Limitações'], ['execution', 'Execução']]
  return <div className="app-page result-page"><div className="result-header"><div><p className="eyebrow">RESULTADO TÉCNICO</p><h1>{String(result.file.name ?? 'Evidência')}</h1><div className="result-header-meta"><span>{result.detected_type ?? 'tipo não identificado'}</span><span>{Number(result.file.size_bytes ?? 0).toLocaleString('pt-BR')} bytes</span><span>{duration(result)}</span><span>{String(result.execution.finished_at ?? '—')}</span></div></div><StatusBadge status={stateStatus(result.state)} /></div><div className="primary-hash"><span>SHA-256</span><TechnicalValue canCopy>{result.hashes.sha256 ?? 'não disponível'}</TechnicalValue></div><nav className="result-nav" aria-label="Seções do resultado">{nav.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav><Section id="summary" title="Overview"><div className="technical-summary"><div><span>Tipo</span><strong>{result.detected_type ?? '—'}</strong></div><div><span>Hashes</span><strong>{Object.keys(result.hashes).length}</strong></div><div><span>Assinaturas</span><strong>{result.signatures.length}</strong></div><div><span>OCR</span><strong>{result.ocr === null ? 'NÃO EXECUTADO' : 'DISPONÍVEL'}</strong></div><div><span>Findings</span><strong>{result.findings.length}</strong></div><div><span>Limitações</span><strong>{result.limitations.length}</strong></div></div></Section><Section id="hashes" title="Hashes"><table className="technical-table"><thead><tr><th>Algoritmo</th><th>Valor</th></tr></thead><tbody>{Object.entries(result.hashes).map(([algorithm, value]) => <tr key={algorithm}><td>{algorithm.toUpperCase()}</td><td><TechnicalValue canCopy>{value}</TechnicalValue></td></tr>)}</tbody></table></Section><Section id="metadata" title="Metadados"><KeyValues value={result.metadata} /></Section><Section id="structure" title="Estrutura"><KeyValues value={result.technical_structure} /></Section><Section id="signatures" title="Assinaturas">{result.signatures.length ? result.signatures.map((signature, index) => <article className="signature-block" key={index}><h3>Assinatura {String(index + 1).padStart(2, '0')}</h3><KeyValues value={signature} /></article>) : <p className="empty-state">Nenhuma assinatura reportada. Isso não constitui, isoladamente, invalidade.</p>}</Section><Section id="text" title="Texto / OCR"><div className="text-columns"><article><h3>Texto nativo</h3>{result.native_text ? <JsonView value={result.native_text} /> : <p>Não executado ou fora do escopo.</p>}</article><article><h3>OCR</h3>{result.ocr ? <JsonView value={result.ocr} /> : <p>Não executado ou indisponível; consulte as etapas.</p>}</article></div></Section><Section id="biometrics" title="Biometria">{result.biometrics ? <KeyValues value={result.biometrics} /> : <p className="empty-state">Não executada ou não aplicável.</p>}</Section><Section id="facts" title="Fatos"><div className="technical-list">{result.facts.map((fact, index) => <article key={index}><JsonView value={fact} /></article>)}</div></Section><Section id="findings" title="Findings">{result.findings.length ? <div className="technical-list">{result.findings.map((finding, index) => <article key={index}><KeyValues value={finding} /></article>)}</div> : <p className="empty-state">Nenhum finding reportado.</p>}</Section><Section id="limitations" title="Limitações"><div className="technical-list">{result.limitations.map((item, index) => <article key={index}><KeyValues value={item} /></article>)}</div></Section><Section id="execution" title="Execução"><div className="steps-list">{result.processing_steps.map((step, index) => <div key={step.step_id ?? index}><span>{step.component ?? step.code}</span><StatusBadge status={step.status} /><TechnicalValue>{typeof step.duration_ms === 'number' ? `${step.duration_ms} ms` : '—'}</TechnicalValue><small>{step.user_message}</small></div>)}</div></Section><details className="raw-result"><summary>Ver resultado técnico completo — RAW JSON</summary><JsonView value={result} /></details></div>
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
