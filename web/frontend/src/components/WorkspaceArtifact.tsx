import { File, FileJson, FileText, Image } from 'lucide-react'
import type { WorkspaceAnalysis } from '../context/AnalysisSessionContext'

export function artifactKind(item: WorkspaceAnalysis): string {
  const detected = item.contract?.detected_type
  if (detected) return detected
  const extension = item.filename.split('.').pop()?.toUpperCase()
  return extension && extension !== item.filename.toUpperCase() ? extension : 'ARQUIVO'
}

export function ArtifactIcon({ item, size = 18 }: { item: WorkspaceAnalysis; size?: number }) {
  const kind = artifactKind(item)
  if (['JPG', 'JPEG', 'PNG', 'GIF', 'WEBP', 'IMAGE'].some((value) => kind.includes(value))) return <Image size={size} aria-hidden="true" />
  if (kind.includes('JSON')) return <FileJson size={size} aria-hidden="true" />
  if (kind.includes('PDF') || kind.includes('TEXT') || kind === 'TXT') return <FileText size={size} aria-hidden="true" />
  return <File size={size} aria-hidden="true" />
}

export function formatArtifactBytes(value: number): string {
  if (value < 1_024) return `${value} B`
  if (value < 1_048_576) return `${(value / 1_024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} KB`
  return `${(value / 1_048_576).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`
}

export function artifactDuration(item: WorkspaceAnalysis): string {
  const value = item.contract?.execution.duration_ms
  if (typeof value === 'number' && Number.isFinite(value)) return value < 1_000 ? `${value} ms` : `${(value / 1_000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`
  const started = item.contract?.execution.started_at
  const finished = item.contract?.execution.finished_at
  if (typeof started === 'string' && typeof finished === 'string') {
    const duration = Date.parse(finished) - Date.parse(started)
    if (Number.isFinite(duration) && duration >= 0) return `${(duration / 1_000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`
  }
  return '—'
}
