import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, submitAnalysis } from '../lib/api'
import type { AnalysisContract, AnalysisSummary } from '../types/api'

export const ANALYSIS_CONCURRENCY = 2
export const MAX_WORKSPACE_FILES = 50

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
  analysisId: string
  filename: string
  relativePath?: string
  status: WorkspaceAnalysisStatus
  contract?: AnalysisContract
  persisted: boolean
  error?: string
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
}

interface InternalWorkspace extends Omit<AnalysisWorkspace, 'analyses'> {
  analyses: InternalWorkspaceAnalysis[]
}

interface AnalysisSessionValue {
  analyses: SessionEntry[]
  persistedAnalyses: SessionEntry[]
  workspace: AnalysisWorkspace
  addAnalysis: (result: AnalysisContract, options?: { persisted?: boolean; openInWorkspace?: boolean }) => void
  openAnalysis: (result: AnalysisContract, persisted?: boolean) => void
  enqueueFiles: (files: File[], options: EnqueueOptions) => { accepted: number; rejected: number; message?: string }
  setActiveAnalysis: (analysisId: string) => void
  closeAnalysis: (analysisId: string) => void
  closeAllAnalyses: () => void
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
  const workspaceRef = useRef(internalWorkspace)
  const running = useRef(new Set<string>())
  const dismissed = useRef(new Set<string>())

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

  const runAnalysis = useCallback(async (item: InternalWorkspaceAnalysis) => {
    running.current.add(item.analysisId)
    updateWorkspace((current) => ({
      ...current,
      analyses: current.analyses.map((candidate) => candidate.analysisId === item.analysisId ? { ...candidate, status: 'UPLOADING' } : candidate),
    }))
    const request = submitAnalysis(item.file, {
      retentionMode: item.request.retentionMode,
      privateSession: item.request.privateSession,
      csrfToken: item.request.csrfToken,
    })
    queueMicrotask(() => updateWorkspace((current) => ({
      ...current,
      analyses: current.analyses.map((candidate) => candidate.analysisId === item.analysisId ? { ...candidate, status: 'PROCESSING' } : candidate),
    })))
    try {
      const result = await request
      if (item.persisted || !dismissed.current.has(item.analysisId)) storeResult(result, item.persisted)
      updateWorkspace((current) => {
        if (dismissed.current.has(item.analysisId)) return current
        return {
          ...current,
          activeAnalysisId: current.activeAnalysisId === item.analysisId ? result.analysis_id : current.activeAnalysisId,
          analyses: current.analyses.map((candidate) => candidate.analysisId === item.analysisId ? {
            ...candidate,
            analysisId: result.analysis_id,
            filename: asString(result.file.name) ?? candidate.filename,
            status: resultStatus(result),
            contract: result,
            file: candidate.file,
          } : candidate),
        }
      })
    } catch (error) {
      if (!dismissed.current.has(item.analysisId)) {
        updateWorkspace((current) => ({
          ...current,
          analyses: current.analyses.map((candidate) => candidate.analysisId === item.analysisId ? {
            ...candidate,
            status: error instanceof ApiError && error.code === 'file_too_large' ? 'LIMIT_EXCEEDED' : 'FAILED',
            error: error instanceof ApiError ? error.message : 'Não foi possível concluir a análise.',
          } : candidate),
        }))
      }
    } finally {
      running.current.delete(item.analysisId)
      dismissed.current.delete(item.analysisId)
      updateWorkspace((current) => ({ ...current }))
    }
  }, [storeResult, updateWorkspace])

  useEffect(() => {
    const available = ANALYSIS_CONCURRENCY - running.current.size
    if (available <= 0) return
    const next = internalWorkspace.analyses
      .filter((item) => item.status === 'QUEUED' && !running.current.has(item.analysisId))
      .slice(0, available)
    next.forEach((item) => { void runAnalysis(item) })
  }, [internalWorkspace, runAnalysis])

  const addAnalysis = useCallback((result: AnalysisContract, options?: { persisted?: boolean; openInWorkspace?: boolean }) => {
    const persisted = options?.persisted ?? false
    storeResult(result, persisted)
    if (options?.openInWorkspace === false) return
    updateWorkspace((current) => {
      const item: InternalWorkspaceAnalysis = {
        analysisId: result.analysis_id,
        filename: asString(result.file.name) ?? 'Evidência sem nome',
        status: resultStatus(result),
        contract: result,
        persisted,
        file: new File([], asString(result.file.name) ?? 'evidence'),
        request: { privateSession: !persisted },
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
        analysisId: localId('queued'),
        filename: file.name,
        relativePath,
        status: 'QUEUED',
        persisted: !options.privateSession && options.retentionMode === 'RESULT_ONLY',
        file,
        request: options,
      })
    }
    if (accepted.length) {
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
    if (running.current.has(analysisId)) dismissed.current.add(analysisId)
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

  const closeAllAnalyses = useCallback(() => {
    const current = workspaceRef.current.analyses
    current.forEach((item) => { if (running.current.has(item.analysisId)) dismissed.current.add(item.analysisId) })
    const privateIds = new Set(current.filter((item) => !item.persisted && item.contract).map((item) => item.contract!.analysis_id))
    setAnalyses((entries) => entries.filter(({ summary }) => !privateIds.has(summary.analysisId)))
    updateWorkspace((workspace) => ({ ...workspace, analyses: [], activeAnalysisId: null, label: 'Análises abertas' }))
  }, [updateWorkspace])

  const workspace = useMemo<AnalysisWorkspace>(() => ({
    workspaceId: internalWorkspace.workspaceId,
    label: internalWorkspace.label,
    activeAnalysisId: internalWorkspace.activeAnalysisId,
    analyses: internalWorkspace.analyses.map((item) => ({
      analysisId: item.analysisId,
      filename: item.filename,
      relativePath: item.relativePath,
      status: item.status,
      contract: item.contract,
      persisted: item.persisted,
      error: item.error,
    })),
  }), [internalWorkspace])

  const value = useMemo<AnalysisSessionValue>(() => ({
    analyses,
    persistedAnalyses: analyses.filter((entry) => entry.persisted),
    workspace,
    addAnalysis,
    openAnalysis,
    enqueueFiles,
    setActiveAnalysis,
    closeAnalysis,
    closeAllAnalyses,
    getAnalysis(analysisId) {
      return analyses.find(({ summary }) => summary.analysisId === analysisId)?.result
    },
    isPersisted(analysisId) {
      return analyses.find(({ summary }) => summary.analysisId === analysisId)?.persisted ?? false
    },
  }), [addAnalysis, analyses, closeAllAnalyses, closeAnalysis, enqueueFiles, openAnalysis, setActiveAnalysis, workspace])

  return <AnalysisSessionContext.Provider value={value}>{children}</AnalysisSessionContext.Provider>
}

export function useAnalysisSession(): AnalysisSessionValue {
  const value = useContext(AnalysisSessionContext)
  if (!value) throw new Error('useAnalysisSession requer AnalysisSessionProvider')
  return value
}
