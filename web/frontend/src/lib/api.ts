import type { AnalysisContract, ApiErrorEnvelope, Capabilities } from '../types/api'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code = 'request_failed',
    public readonly requestId?: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${configuredBase}${path}`, init)
  if (!response.ok) {
    let payload: ApiErrorEnvelope = {}
    try {
      payload = (await response.json()) as ApiErrorEnvelope
    } catch {
      // A resposta pública permanece genérica quando o servidor não envia JSON.
    }
    throw new ApiError(
      payload.error?.message ?? 'Não foi possível concluir a solicitação.',
      payload.error?.code,
      payload.error?.request_id,
    )
  }
  return (await response.json()) as T
}

export function getCapabilities(): Promise<Capabilities> {
  return request<Capabilities>('/api/v1/capabilities')
}

export function submitAnalysis(file: File): Promise<AnalysisContract> {
  const body = new FormData()
  body.append('file', file)
  return request<AnalysisContract>('/api/v1/analyses', { method: 'POST', body })
}
