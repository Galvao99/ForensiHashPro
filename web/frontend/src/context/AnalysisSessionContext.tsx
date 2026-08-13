import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, createAnalysisJob, createAnalysisSet, getAnalysisJob, getAnalysisJobResult } from '../lib/api'
import type { AnalysisContract, AnalysisSetResult, AnalysisSummary } from '../types/api'

export const ANALYSIS_CONCURRENCY = 2
export const MAX_WORKSPACE_FILES = 50
export const JOB_POLL_INTERVAL_MS = 2_500

export type WorkspaceAnalysisStatus =
  | 'QUEUED'
  | 'UPLOADING'
  | 'PROCESSING'
  | 'SUCCESS'
  | 'PARTIAL'
  | 'FAILED'
  | 'LIMIT_EXCEEDED'
  | 'CANCELLED'

export interface WorkspaceAnalysis {
  clientUploadId: string
  analysisId: string
  jobId?: string
  filename: string
  relativePath?: string
  status: WorkspaceAnalysisStatus
  contract?: AnalysisContract
  persisted: boolean
  error?: string
  errorCode?: string
  currentStage?: string
  startedAt?: string
}

export interface AnalysisWorkspace {
  workspaceId: string
  label: string
  analyses: WorkspaceAnalysis[]
  activeAnalysisId: string | null
}

interface SessionEntry {
  result: AnalysisContract
  summary: AnalysisSummary
  persisted: boolean
}

interface EnqueueOptions {
  retentionMode?: string
  privateSession: boolean
  csrfToken?: string
}

interface InternalWorkspaceAnalysis extends WorkspaceAnalysis {
  file: File
  request: EnqueueOptions
  submissionState: 'SELECTED' | 'SUBMITTING' | 'SUBMITTED' | 'FAILED'
}

interface InternalWorkspace extends Omit<AnalysisWorkspace, 'analyses'> {
  analyses: InternalWorkspaceAnalysis[]
}

interface AnalysisSessionValue {
  analyses: SessionEntry[]
  persistedAnalyses: SessionEntry[]
  workspace: AnalysisWorkspace
  analysisSetResult: AnalysisSetResult | null
  addAnalysis: (result: AnalysisContract, options?: { persisted?: boolean; openInWorkspace?: boolean }) => void
  openAnalysis: (result: AnalysisContract, persisted?: boolean) => void
  enqueueFiles: (files: File[], options: EnqueueOptions) => { accepted: number; rejected: number; message?: string }
  setActiveAnalysis: (analysisId: string) => void
  closeAnalysis: (analysisId: string) => void
  closeAllAnalyses: () => void
  retryAnalysis: (clientUploadId: string) => void
  getAnalysis: (analysisId: string) => AnalysisContract | undefined
  isPersisted: (analysisId: string) => boolean
}

const AnalysisSessionContext = createContext<AnalysisSessionValue | null>(null)
let localSequence = 0

function localId(prefix: string): string {
  localSequence += 1
  return `${prefix}-${Date.now()}-${localSequence}`
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function summarizeAnalysis(result: AnalysisContract): AnalysisSummary {
  const startedAt = asString(result.execution.started_at)
  const finishedAt = asString(result.execution.finished_at)
  let durationMs = asNumber(result.execution.duration_ms)
  if (durationMs === null && startedAt && finishedAt) {
    const elapsed = Date.parse(finishedAt) - Date.parse(startedAt)
    durationMs = Number.isFinite(elapsed) && elapsed >= 0 ? elapsed : null
  }
  return {
    analysisId: result.analysis_id,
    filename: asString(result.file.name) ?? 'Evidência sem nome',
    detectedType: result.detected_type,
    sha256: asString(result.hashes.sha256),
    status: result.state,
    createdAt: finishedAt ?? startedAt,
    durationMs,
    findingsCount: result.findings.length,
    limitationsCount: result.limitations.length,
  }
}

export function safeRelativePath(file: File): string | undefined | null {
  const raw = (file as File & { webkitRelativePath?: string }).webkitRelativePath
  if (!raw) return undefined
  const normalized = raw.replaceAll('\\', '/')
  if (normalized.startsWith('/') || /^[a-zA-Z]:\//.test(normalized) || normalized.includes('\0')) return null
  const segments = normalized.split('/')
  if (segments.some((segment) => segment === '..' || segment === '.' || segment.length === 0)) return null
  return segments.join('/')
}

function resultStatus(result: AnalysisContract): WorkspaceAnalysisStatus {
  if (result.state === 'completed') return 'SUCCESS'
  if (result.state === 'partial') return 'PARTIAL'
  if (result.state === 'cancelled') return 'CANCELLED'
  return 'FAILED'
}

export function AnalysisSessionProvider({ children, initialResults = [] }: { children: ReactNode; initialResults?: AnalysisContract[] }) {
  const [analyses, setAnalyses] = useState<SessionEntry[]>(() => initialResults.map((result) => ({ result, summary: summarizeAnalysis(result), persisted: false })))
  const [internalWorkspace, setInternalWorkspace] = useState<InternalWorkspace>(() => ({
    workspaceId: localId('workspace'),
    label: 'Análises abertas',
    analyses: [],
    activeAnalysisId: null,
  }))
  const [analysisSetResult, setAnalysisSetResult] = useState<AnalysisSetResult | null>(null)
  const attemptedAnalysisSets = useRef(new Set<string>())
  const workspaceRef = useRef(internalWorkspace)
  const running = useRef(new Set<string>())
  const submissionClaims = useRef(new Set<string>())
  const dismissed = useRef(new Set<string>())
  const polling = useRef(new Map<string, { controller: AbortController; timer?: number }>())

  const updateWorkspace = useCallback((update: (current: InternalWorkspace) => InternalWorkspace) => {
    setInternalWorkspace((current) => {
      const next = update(current)
      workspaceRef.current = next
      return next
    })
  }, [])

  const storeResult = useCallback((result: AnalysisContract, persisted: boolean) => {
    const entry = { result, summary: summarizeAnalysis(result), persisted }
    setAnalyses((current) => [entry, ...current.filter(({ summary }) => summary.analysisId !== result.analysis_id)])
  }, [])

  const pollJob = useCallback((clientUploadId: string, jobId: string, persisted: boolean) => {
    if (polling.current.has(jobId)) return
    const controller = new AbortController()
    const state = { controller, timer: undefined as number | undefined }
    polling.current.set(jobId, state)
    const poll = async () => {
      try {
        const job = await getAnalysisJob(jobId, controller.signal)
        if (dismissed.current.has(clientUploadId)) return
        updateWorkspace((current) => ({ ...current, analyses: current.analyses.map((candidate) => candidate.clientUploadId === clientUploadId && candidate.jobId === jobId ? {
          ...candidate, status: job.status, currentStage: job.current_stage ?? undefined,
          startedAt: job.started_at ?? candidate.startedAt, error: job.safe_error_message ?? undefined,
          errorCode: job.error_code ?? undefined,
          submissionState: ['FAILED', 'LIMIT_EXCEEDED', 'CANCELLED'].includes(job.status) ? 'FAILED' : candidate.submissionState,
        } : candidate) }))
        if (job.status === 'SUCCESS' || job.status === 'PARTIAL') {
          const result = await getAnalysisJobResult(jobId, controller.signal)
          storeResult(result, persisted)
          updateWorkspace((current) => {
            const target = current.analyses.find((candidate) => candidate.clientUploadId === clientUploadId && candidate.jobId === jobId)
            if (!target) return current
            return {
              ...current,
              activeAnalysisId: current.activeAnalysisId === target.analysisId ? result.analysis_id : current.activeAnalysisId,
              analyses: current.analyses.map((candidate) => candidate.clientUploadId === clientUploadId && candidate.jobId === jobId ? {
                ...candidate, analysisId: result.analysis_id, filename: asString(result.file.name) ?? candidate.filename,
                status: resultStatus(result), contract: result,
              } : candidate),
            }
          })
          polling.current.delete(jobId)
          return
        }
        if (['FAILED', 'LIMIT_EXCEEDED', 'CANCELLED'].includes(job.status)) {
          polling.current.delete(jobId)
          return
        }
        state.timer = window.setTimeout(poll, JOB_POLL_INTERVAL_MS)
      } catch (error) {
        if (controller.signal.aborted || dismissed.current.has(clientUploadId)) return
        if (error instanceof ApiError && (error.code === 'network_error' || error.code === 'request_timeout')) {
          updateWorkspace((current) => ({ ...current, analyses: current.analyses.map((candidate) => candidate.clientUploadId === clientUploadId && candidate.jobId === jobId ? {
            ...candidate, errorCode: 'status_unavailable', error: 'Não foi possível atualizar o status; uma nova tentativa será feita.',
          } : candidate) }))
          state.timer = window.setTimeout(poll, JOB_POLL_INTERVAL_MS)
          return
        }
        updateWorkspace((current) => ({ ...current, analyses: current.analyses.map((candidate) => candidate.clientUploadId === clientUploadId && candidate.jobId === jobId ? {
          ...candidate, status: 'FAILED', submissionState: 'FAILED', errorCode: error instanceof ApiError ? error.code : 'status_unavailable',
          error: error instanceof ApiError ? error.message : 'Não foi possível acompanhar a análise.',
        } : candidate) }))
        polling.current.delete(jobId)
      }
    }
    void poll()
  }, [storeResult, updateWorkspace])

  const runAnalysis = useCallback(async (item: InternalWorkspaceAnalysis) => {
    if (item.submissionState !== 'SELECTED' || item.jobId || submissionClaims.current.has(item.clientUploadId)) return
    submissionClaims.current.add(item.clientUploadId)
    running.current.add(item.clientUploadId)
    updateWorkspace((current) => ({
      ...current,
      analyses: current.analyses.map((candidate) => candidate.clientUploadId === item.clientUploadId && candidate.submissionState === 'SELECTED' && !candidate.jobId
        ? { ...candidate, status: 'UPLOADING', submissionState: 'SUBMITTING' }
        : candidate),
    }))
    try {
      const created = await createAnalysisJob(item.file, {
        retentionMode: item.request.retentionMode, privateSession: item.request.privateSession, csrfToken: item.request.csrfToken,
      })
      if (!dismissed.current.has(item.clientUploadId)) {
        updateWorkspace((current) => ({ ...current, analyses: current.analyses.map((candidate) => candidate.clientUploadId === item.clientUploadId ? {
          ...candidate, jobId: created.job_id, status: created.status, submissionState: 'SUBMITTED',
        } : candidate) }))
        pollJob(item.clientUploadId, created.job_id, item.persisted)
      }
    } catch (error) {
      if (!dismissed.current.has(item.clientUploadId)) {
        updateWorkspace((current) => ({
          ...current,
          analyses: current.analyses.map((candidate) => candidate.clientUploadId === item.clientUploadId ? {
            ...candidate,
            status: error instanceof ApiError && error.code === 'file_too_large' ? 'LIMIT_EXCEEDED' : 'FAILED',
            submissionState: 'FAILED',
            errorCode: error instanceof ApiError ? error.code : 'analysis_failed',
            error: error instanceof ApiError ? error.message : 'Não foi possível concluir a análise.',
          } : candidate),
        }))
      }
    } finally {
      running.current.delete(item.clientUploadId)
      submissionClaims.current.delete(item.clientUploadId)
      dismissed.current.delete(item.clientUploadId)
      updateWorkspace((current) => ({ ...current }))
    }
  }, [pollJob, updateWorkspace])

  useEffect(() => () => {
    polling.current.forEach(({ controller, timer }) => {
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    })
    polling.current.clear()
  }, [])

  useEffect(() => {
    const available = ANALYSIS_CONCURRENCY - running.current.size
    if (available <= 0) return
    const next = internalWorkspace.analyses
      .filter((item) => item.submissionState === 'SELECTED' && !item.jobId && !running.current.has(item.clientUploadId))
      .slice(0, available)
    next.forEach((item) => { void runAnalysis(item) })
  }, [internalWorkspace, runAnalysis])

  useEffect(() => {
    const items = internalWorkspace.analyses
    const terminal = new Set<WorkspaceAnalysisStatus>(['SUCCESS', 'PARTIAL', 'FAILED', 'LIMIT_EXCEEDED', 'CANCELLED'])
    if (!items.length) return
    if (!items.every((item) => item.jobId && terminal.has(item.status))) return
    const attemptKey = items.map((item) => item.jobId).sort().join(':')
    if (attemptedAnalysisSets.current.has(attemptKey)) return
    attemptedAnalysisSets.current.add(attemptKey)
    const csrfToken = items.find((item) => item.request.csrfToken)?.request.csrfToken
    void createAnalysisSet(items.map((item) => item.jobId!), csrfToken)
      .then((result) => {
        if (result?.correlation_result && Array.isArray(result.correlation_result.findings)) {
          setAnalysisSetResult(result)
        }
      })
      .catch(() => undefined)
  }, [internalWorkspace])

  const addAnalysis = useCallback((result: AnalysisContract, options?: { persisted?: boolean; openInWorkspace?: boolean }) => {
    const persisted = options?.persisted ?? false
    storeResult(result, persisted)
    if (options?.openInWorkspace === false) return
    updateWorkspace((current) => {
      const item: InternalWorkspaceAnalysis = {
        clientUploadId: localId('restored'),
        analysisId: result.analysis_id,
        filename: asString(result.file.name) ?? 'Evidência sem nome',
        status: resultStatus(result),
        contract: result,
        persisted,
        file: new File([], asString(result.file.name) ?? 'evidence'),
        request: { privateSession: !persisted },
        submissionState: 'SUBMITTED',
      }
      return {
        ...current,
        analyses: [item, ...current.analyses.filter((candidate) => candidate.analysisId !== result.analysis_id)],
        activeAnalysisId: result.analysis_id,
      }
    })
  }, [storeResult, updateWorkspace])

  const openAnalysis = useCallback((result: AnalysisContract, persisted = false) => {
    addAnalysis(result, { persisted })
  }, [addAnalysis])

  const enqueueFiles = useCallback((files: File[], options: EnqueueOptions) => {
    const capacity = Math.max(0, MAX_WORKSPACE_FILES - workspaceRef.current.analyses.length)
    const accepted: InternalWorkspaceAnalysis[] = []
    let rejected = 0
    for (const file of files) {
      const relativePath = safeRelativePath(file)
      if (relativePath === null || accepted.length >= capacity) {
        rejected += 1
        continue
      }
      accepted.push({
        clientUploadId: localId('upload'),
        analysisId: localId('queued'),
        filename: file.name,
        relativePath,
        status: 'QUEUED',
        persisted: !options.privateSession && options.retentionMode === 'RESULT_ONLY',
        file,
        request: options,
        submissionState: 'SELECTED',
      })
    }
    if (accepted.length) {
      setAnalysisSetResult(null)
      const folder = accepted[0].relativePath?.split('/')[0]
      const sharedFolder = folder && accepted.every((item) => item.relativePath?.startsWith(`${folder}/`)) ? folder : undefined
      updateWorkspace((current) => ({
        ...current,
        label: sharedFolder ? `Workspace: ${sharedFolder}` : current.label,
        analyses: [...current.analyses, ...accepted],
        activeAnalysisId: current.activeAnalysisId ?? accepted[0].analysisId,
      }))
    }
    const message = rejected > 0
      ? `Foram recusados ${rejected} arquivo(s) por caminho relativo inseguro ou pelo limite de ${MAX_WORKSPACE_FILES} abas.`
      : undefined
    return { accepted: accepted.length, rejected, message }
  }, [updateWorkspace])

  const setActiveAnalysis = useCallback((analysisId: string) => {
    updateWorkspace((current) => current.analyses.some((item) => item.analysisId === analysisId) ? { ...current, activeAnalysisId: analysisId } : current)
  }, [updateWorkspace])

  const closeAnalysis = useCallback((analysisId: string) => {
    const closing = workspaceRef.current.analyses.find((item) => item.analysisId === analysisId)
    if (!closing) return
    const activePoll = closing.jobId ? polling.current.get(closing.jobId) : undefined
    activePoll?.controller.abort()
    if (activePoll?.timer !== undefined) window.clearTimeout(activePoll.timer)
    if (closing.jobId) polling.current.delete(closing.jobId)
    if (running.current.has(closing.clientUploadId)) dismissed.current.add(closing.clientUploadId)
    if (!closing.persisted && closing.contract) {
      setAnalyses((current) => current.filter(({ summary }) => summary.analysisId !== closing.contract?.analysis_id))
    }
    updateWorkspace((current) => {
      const index = current.analyses.findIndex((item) => item.analysisId === analysisId)
      const remaining = current.analyses.filter((item) => item.analysisId !== analysisId)
      const nextActive = current.activeAnalysisId === analysisId
        ? remaining[Math.min(index, remaining.length - 1)]?.analysisId ?? null
        : current.activeAnalysisId
      return { ...current, analyses: remaining, activeAnalysisId: nextActive }
    })
  }, [updateWorkspace])

  const retryAnalysis = useCallback((clientUploadId: string) => {
    updateWorkspace((current) => ({
      ...current,
      analyses: current.analyses.map((item) => item.clientUploadId === clientUploadId && item.submissionState === 'FAILED'
        ? { ...item, jobId: undefined, status: 'QUEUED', submissionState: 'SELECTED', error: undefined, errorCode: undefined }
        : item),
    }))
  }, [updateWorkspace])

  const closeAllAnalyses = useCallback(() => {
    const current = workspaceRef.current.analyses
    polling.current.forEach(({ controller, timer }) => { controller.abort(); if (timer !== undefined) window.clearTimeout(timer) })
    polling.current.clear()
    current.forEach((item) => { if (running.current.has(item.clientUploadId)) dismissed.current.add(item.clientUploadId) })
    const privateIds = new Set(current.filter((item) => !item.persisted && item.contract).map((item) => item.contract!.analysis_id))
    setAnalyses((entries) => entries.filter(({ summary }) => !privateIds.has(summary.analysisId)))
    updateWorkspace((workspace) => ({ ...workspace, analyses: [], activeAnalysisId: null, label: 'Análises abertas' }))
  }, [updateWorkspace])

  const workspace = useMemo<AnalysisWorkspace>(() => ({
    workspaceId: internalWorkspace.workspaceId,
    label: internalWorkspace.label,
    activeAnalysisId: internalWorkspace.activeAnalysisId,
    analyses: internalWorkspace.analyses.map((item) => ({
      clientUploadId: item.clientUploadId,
      analysisId: item.analysisId,
      jobId: item.jobId,
      filename: item.filename,
      relativePath: item.relativePath,
      status: item.status,
      contract: item.contract,
      persisted: item.persisted,
      error: item.error,
      errorCode: item.errorCode,
      currentStage: item.currentStage,
      startedAt: item.startedAt,
    })),
  }), [internalWorkspace])

  const value = useMemo<AnalysisSessionValue>(() => ({
    analyses,
    persistedAnalyses: analyses.filter((entry) => entry.persisted),
    workspace,
    analysisSetResult,
    addAnalysis,
    openAnalysis,
    enqueueFiles,
    setActiveAnalysis,
    closeAnalysis,
    closeAllAnalyses,
    retryAnalysis,
    getAnalysis(analysisId) {
      return analyses.find(({ summary }) => summary.analysisId === analysisId)?.result
    },
    isPersisted(analysisId) {
      return analyses.find(({ summary }) => summary.analysisId === analysisId)?.persisted ?? false
    },
  }), [addAnalysis, analyses, analysisSetResult, closeAllAnalyses, closeAnalysis, enqueueFiles, openAnalysis, retryAnalysis, setActiveAnalysis, workspace])

  return <AnalysisSessionContext.Provider value={value}>{children}</AnalysisSessionContext.Provider>
}

export function useAnalysisSession(): AnalysisSessionValue {
  const value = useContext(AnalysisSessionContext)
  if (!value) throw new Error('useAnalysisSession requer AnalysisSessionProvider')
  return value
}
