import { createContext, ReactNode, useContext, useMemo, useState } from 'react'
import type { AnalysisContract, AnalysisSummary } from '../types/api'

interface SessionEntry {
  result: AnalysisContract
  summary: AnalysisSummary
}

interface AnalysisSessionValue {
  analyses: SessionEntry[]
  addAnalysis: (result: AnalysisContract) => void
  getAnalysis: (analysisId: string) => AnalysisContract | undefined
}

const AnalysisSessionContext = createContext<AnalysisSessionValue | null>(null)

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

export function AnalysisSessionProvider({ children, initialResults = [] }: { children: ReactNode; initialResults?: AnalysisContract[] }) {
  const [analyses, setAnalyses] = useState<SessionEntry[]>(() => initialResults.map((result) => ({ result, summary: summarizeAnalysis(result) })))
  const value = useMemo<AnalysisSessionValue>(() => ({
    analyses,
    addAnalysis(result) {
      const entry = { result, summary: summarizeAnalysis(result) }
      setAnalyses((current) => [entry, ...current.filter(({ summary }) => summary.analysisId !== result.analysis_id)])
    },
    getAnalysis(analysisId) {
      return analyses.find(({ summary }) => summary.analysisId === analysisId)?.result
    },
  }), [analyses])
  return <AnalysisSessionContext.Provider value={value}>{children}</AnalysisSessionContext.Provider>
}

export function useAnalysisSession(): AnalysisSessionValue {
  const value = useContext(AnalysisSessionContext)
  if (!value) throw new Error('useAnalysisSession requer AnalysisSessionProvider')
  return value
}
