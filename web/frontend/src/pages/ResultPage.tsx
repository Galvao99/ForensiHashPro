import { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { AlertTriangle, Check, Circle, FilePlus, FolderPlus, LoaderCircle, X } from 'lucide-react'
import { TechnicalValue } from '../components/ui'
import { ArtifactIcon, artifactDuration, artifactKind, formatArtifactBytes } from '../components/WorkspaceArtifact'
import { ArtifactHeader, ForensicSummary } from '../components/ForensicSummary'
import {
  ArchiveResultView, BiometricResultView, CorrelationResultView, ExecutionResultView, FactsResultView, FindingsResultView,
  HashResultView, LimitationsResultView, MetadataResultView,
  RawTechnicalDataView, SignatureResultView, StructureResultView, TechnicalSection,
  TextOcrResultView, TimelineResultView,
} from '../components/ResultPresentation'
import { useAnalysisSession, type WorkspaceAnalysis } from '../context/AnalysisSessionContext'
import { useAuth } from '../context/AuthContext'
import type { AnalysisContract, AnalysisSetResult } from '../types/api'

export function ResultView({ result, analysisSet }: { result: AnalysisContract; analysisSet?: AnalysisSetResult | null }) {
  const isPro = String(result.execution.analysis_profile ?? 'pro').toLowerCase() === 'pro'
  const archive = result.technical_structure.archive as Record<string, unknown> | null | undefined
  const nav = [['summary', 'Resumo'], ['identification', 'Identificação'], ['structure', 'Estrutura'], ['metadata', 'Metadados'], ['signatures', 'Assinaturas'], ...(isPro ? [['entities', 'Entidades'], ['timeline', 'Timeline'], ['text', 'Texto / OCR'], ['biometrics', 'Biometria']] : []), ['findings', 'Evidências'], ...(isPro && analysisSet ? [['correlations', 'Correlações']] : []), ['limitations', 'Limitações'], ['details', 'Detalhes']]
  const visibleSteps = isPro ? result.processing_steps : result.processing_steps.filter((step) => !['ocr', 'text_extraction', 'entity_extraction', 'timeline', 'ip_analysis', 'biometric'].includes(String(step.component ?? step.code)))
  return <div className="app-page result-page"><ArtifactHeader result={result} /><p className="analysis-profile-badge">FORENSIHASH {isPro ? 'PRO' : 'FREE'}</p><nav className="result-nav" aria-label="Seções do resultado">{nav.map(([id, navLabel]) => <a key={id} href={`#${id}`}>{navLabel}</a>)}</nav><ForensicSummary result={result} /><div id="details" className="technical-layer-heading"><p className="eyebrow">CAMADA 2</p><h2>Detalhamento técnico</h2><p>Dados estruturados preservados para inspeção e auditoria.</p></div><TechnicalSection id="identification" title="Identificação e hashes"><HashResultView hashes={result.hashes} /></TechnicalSection><TechnicalSection id="metadata" title="Metadados"><MetadataResultView metadata={result.metadata} /></TechnicalSection><TechnicalSection id="structure" title="Estrutura"><StructureResultView structure={result.technical_structure} /></TechnicalSection>{archive && <TechnicalSection id="archive" title="Archive Inspection"><ArchiveResultView archive={archive} /></TechnicalSection>}<TechnicalSection id="signatures" title="Assinaturas"><SignatureResultView signatures={result.signatures} /></TechnicalSection>{isPro && <><TechnicalSection id="entities" title="Entidades e endereços IP"><FactsResultView facts={[...result.facts.filter((fact) => /entit|cpf|cnpj|phone|email|address|date|value/i.test(String(fact.kind ?? ''))), ...(result.ip_addresses ?? []).map((item) => ({ kind: 'ip_address', data: item }))]} /></TechnicalSection><TechnicalSection id="timeline" title="Timeline"><TimelineResultView timeline={result.timeline} aggregate={analysisSet?.timeline_result} /></TechnicalSection><TechnicalSection id="text" title="Texto / OCR"><TextOcrResultView nativeText={result.native_text} ocr={result.ocr} /></TechnicalSection><TechnicalSection id="biometrics" title="Biometria"><BiometricResultView biometrics={result.biometrics} /></TechnicalSection></>}<TechnicalSection id="facts" title="Fatos técnicos"><FactsResultView facts={result.facts} /></TechnicalSection><TechnicalSection id="findings" title="Evidências e findings"><FindingsResultView findings={result.findings} /></TechnicalSection>{isPro && analysisSet && <TechnicalSection id="correlations" title="Correlações do Analysis Set"><CorrelationResultView result={analysisSet} /></TechnicalSection>}{!isPro && <ProContinuation />}<TechnicalSection id="limitations" title="Limitações"><LimitationsResultView limitations={result.limitations} /></TechnicalSection><TechnicalSection id="execution" title="Execução"><ExecutionResultView steps={visibleSteps} /></TechnicalSection><section className="raw-technical-section" aria-labelledby="raw-technical-title"><h2 id="raw-technical-title">Dados técnicos completos</h2><RawTechnicalDataView result={result} /></section></div>
}

function ProContinuation() {
  return <section className="pro-continuation" aria-labelledby="pro-continuation-title"><p className="eyebrow">ANÁLISE FREE CONCLUÍDA</p><h2 id="pro-continuation-title">Continue a investigação com o ForensiHash Pro</h2><p>Este artefato pode ser submetido a uma análise mais profunda, sem presumir resultados ainda não executados.</p><div className="pro-capability-grid"><article><strong>CONTENT INTELLIGENCE</strong><span>OCR e análise de conteúdo.</span></article><article><strong>TEMPORAL ANALYSIS</strong><span>Timeline investigativa.</span></article><article><strong>CROSS-ARTIFACT CORRELATION</strong><span>Relações entre evidências.</span></article><article><strong>CONTEXT ANALYSIS</strong><span>IPs, entidades e contexto.</span></article><article><strong>SPECIALIZED FORENSICS</strong><span>Biometria e parsers avançados.</span></article></div><Link className="button-link" to="/forensihash">Continuar análise com ForensiHash Pro</Link><small>Fluxo informativo; nenhum pagamento será iniciado.</small></section>
}

const workspaceStatusLabels: Record<WorkspaceAnalysis['status'], string> = {
  WAITING: 'Aguardando',
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

function WorkspaceProcessingView({ items, onSelect }: { items: WorkspaceAnalysis[]; onSelect: (analysisId: string) => void }) {
  const [, tick] = useState(0)
  const terminal = items.filter((item) => ['SUCCESS', 'PARTIAL', 'FAILED', 'LIMIT_EXCEEDED', 'CANCELLED'].includes(item.status))
  const active = items.find((item) => ['UPLOADING', 'QUEUED', 'PROCESSING'].includes(item.status))
  const waiting = items.filter((item) => item.status === 'WAITING')
  const percent = items.length ? Math.round((terminal.length / items.length) * 100) : 0
  useEffect(() => {
    if (active?.status !== 'PROCESSING') return
    const timer = window.setInterval(() => tick((value) => value + 1), 1_000)
    return () => window.clearInterval(timer)
  }, [active?.status])
  return <div className="app-page queue-processing-view">
    <p className="eyebrow">ANÁLISE EM ANDAMENTO</p>
    <h1>Processamento do workspace</h1><p>{items.length} artefatos · fila serial controlada</p>
    <section className="queue-section" aria-labelledby="queue-progress-title">
      <div className="queue-section-heading"><h2 id="queue-progress-title">Progresso do conjunto</h2><strong>{percent}%</strong></div>
      <div className="queue-progress" role="progressbar" aria-valuemin={0} aria-valuemax={items.length} aria-valuenow={terminal.length}><span style={{ width: `${percent}%` }} /></div>
      <p className="queue-counts"><span>{terminal.length} concluídos</span><span>{active ? 1 : 0} analisando</span><span>{waiting.length} na fila</span></p>
    </section>
    {active && <section className="queue-section" aria-labelledby="queue-active-title">
      <p className="queue-label" id="queue-active-title">Analisando agora</p>
      <button className="queue-active-item" type="button" onClick={() => onSelect(active.analysisId)}><ArtifactIcon item={active} size={22} /><span><strong>{active.filename}</strong><small>{artifactKind(active)} · {formatArtifactBytes(active.sizeBytes)}</small></span><em>{workspaceStatusLabels[active.status]}</em></button>
      <dl className="queue-stage"><div><dt>Etapa atual</dt><dd>{active.currentStage === 'CONSOLIDATING' ? 'CONSOLIDANDO RESULTADOS' : active.currentStage ?? (active.status === 'QUEUED' ? 'AGUARDANDO EXECUTOR' : active.status === 'UPLOADING' ? 'PREPARANDO UPLOAD SEGURO' : 'ANÁLISE TÉCNICA EM ANDAMENTO')}</dd></div><div><dt>Tempo decorrido</dt><dd>{active.status === 'PROCESSING' ? elapsed(active.startedAt) : '00:00'}</dd></div></dl>
    </section>}
    {waiting.length > 0 && <section className="queue-section" aria-labelledby="queue-waiting-title"><p className="queue-label" id="queue-waiting-title">Na fila</p><ol className="queue-list">{waiting.map((item, index) => <li key={item.clientUploadId}><button type="button" onClick={() => onSelect(item.analysisId)}><span>{String(index + 1).padStart(2, '0')}</span><ArtifactIcon item={item} /><strong>{item.filename}</strong><small>{artifactKind(item)} · {formatArtifactBytes(item.sizeBytes)}</small><em>aguardando</em></button></li>)}</ol></section>}
    {terminal.length > 0 && <section className="queue-section" aria-labelledby="queue-completed-title"><p className="queue-label" id="queue-completed-title">Concluídos</p><ul className="queue-list queue-completed">{terminal.map((item) => <li key={item.clientUploadId}><button type="button" onClick={() => onSelect(item.analysisId)}><span>{item.status === 'SUCCESS' ? '✓' : item.status === 'PARTIAL' ? '△' : '×'}</span><ArtifactIcon item={item} /><strong>{item.filename}</strong><small>{artifactDuration(item)}</small><em>{workspaceStatusLabels[item.status]}</em></button></li>)}</ul></section>}
  </div>
}

function elapsed(startedAt?: string): string {
  if (!startedAt) return '00:00'
  const total = Math.max(0, Math.floor((Date.now() - Date.parse(startedAt)) / 1000))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function PendingAnalysis({ item, onRetry }: { item: WorkspaceAnalysis; onRetry: () => void }) {
  const { user } = useAuth()
  const [, tick] = useState(0)
  useEffect(() => {
    if (item.status !== 'PROCESSING') return
    const timer = window.setInterval(() => tick((value) => value + 1), 1_000)
    return () => window.clearInterval(timer)
  }, [item.status])
  const busy = isRunning(item)
  const free = user?.analysis_profile === 'FREE'
  return <div className="app-page workspace-pending" aria-live="polite" aria-busy={busy}><p className="eyebrow">{free ? 'ANALISANDO ARTEFATO' : 'ANÁLISE EM ANDAMENTO'}</p><h1>{item.filename}</h1>{item.relativePath && <p><TechnicalValue>{item.relativePath}</TechnicalValue></p>}<div className="processing-indicator"><ActivityIcon status={item.status} /><strong>{workspaceStatusLabels[item.status]}</strong></div>{free && <ol className="free-processing-steps"><li>Identificando formato</li><li>Calculando hashes</li><li>Extraindo metadados</li><li>Inspecionando estrutura</li><li>Verificando assinatura</li></ol>}<dl className="processing-facts"><div><dt>Etapa atual</dt><dd>{item.currentStage === 'CONSOLIDATING' ? 'Consolidando resultados' : item.status === 'QUEUED' ? 'Aguardando executor' : item.status === 'UPLOADING' ? 'Preparando upload seguro' : 'Análise técnica em andamento'}</dd></div><div><dt>Status</dt><dd>{item.status}</dd></div><div><dt>Tempo decorrido</dt><dd>{item.status === 'PROCESSING' ? elapsed(item.startedAt) : '00:00'}</dd></div></dl>{item.error ? <><p role="alert" className="error-panel">{item.error}</p>{(item.status === 'FAILED' || item.status === 'LIMIT_EXCEEDED') && <button type="button" onClick={onRetry}>Tentar novamente</button>}</> : <p>{free ? 'Somente as etapas do perfil Free estão sendo executadas.' : 'O restante do workspace permanece disponível durante o processamento.'}</p>}</div>
}

export function ResultPage() {
  const location = useLocation()
  const { analysisId } = useParams()
  const { privacy, csrfToken } = useAuth()
  const { workspace, analysisSetResult, getAnalysis, isPersisted, openAnalysis, enqueueFiles, retryAnalysis, setActiveAnalysis, closeAnalysis, closeAllAnalyses } = useAnalysisSession()
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
    if (item.status === 'WAITING') counts.queued += 1
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

  const workspaceProcessing = workspace.analyses.length > 1 && workspace.analyses.some((item) => item.status === 'WAITING' || isRunning(item))

  return <div className="workspace-page">
    {workspaceProcessing ? <WorkspaceProcessingView items={workspace.analyses} onSelect={setActiveAnalysis} /> : active?.contract ? <ResultView result={active.contract} analysisSet={analysisSetResult} /> : active ? <PendingAnalysis item={active} onRetry={() => retryAnalysis(active.clientUploadId)} /> : <div className="app-page"><p>Preparando workspace…</p></div>}
    <section className="workspace-dock" aria-label="Workspace de análises">
      <div className="workspace-toolbar"><div className="workspace-summary"><strong>{workspace.label}</strong><small>{workspace.analyses.length} arquivos · {workspaceCounts.completed} concluídos · {workspaceCounts.processing} analisando · {workspaceCounts.queued} na fila</small></div><div><input ref={filesInput} type="file" multiple aria-label="Adicionar arquivos" onChange={enqueue} /><input ref={folderInput} type="file" multiple aria-label="Adicionar pasta" onChange={enqueue} {...directoryAttributes} /><button type="button" onClick={() => filesInput.current?.click()}><FilePlus size={15} />Adicionar arquivos</button><button type="button" onClick={() => folderInput.current?.click()}><FolderPlus size={15} />Adicionar pasta</button><button type="button" onClick={closeAll}>Fechar todas as abas</button></div></div>
      {message && <p role="alert" className="workspace-message">{message}</p>}
      <div className="workspace-tabs" role="tablist" aria-label="Análises abertas">
        {workspace.analyses.map((item) => <div key={item.clientUploadId} role="tab" tabIndex={0} aria-selected={item.analysisId === workspace.activeAnalysisId} className={`workspace-tab ${item.analysisId === workspace.activeAnalysisId ? 'active' : ''}`} onClick={() => setActiveAnalysis(item.analysisId)} onKeyDown={(event) => tabKeyboard(event, item)}><ActivityIcon status={item.status} /><span className="workspace-tab-name" title={item.relativePath ?? item.filename}>{item.filename}</span><small className={`workspace-tab-status state-${item.status.toLowerCase()}`}>{workspaceStatusLabels[item.status]}</small><button type="button" aria-label={`Fechar análise de ${item.filename}`} onClick={(event) => { event.stopPropagation(); close(item) }}><X size={13} /></button></div>)}
      </div>
    </section>
  </div>
}
