import type { AnalysisContract, AnalysisJobCreated, AnalysisJobState, AnalysisSetResult, ApiErrorEnvelope, AuthResponse, Capabilities, PrivacyPreferences, WebUser } from '../types/api'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''
const timeoutFromEnvironment = (value: string | undefined, fallback: number) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}
const requestTimeoutMs = timeoutFromEnvironment(import.meta.env.VITE_API_TIMEOUT_MS, 15_000)
const analysisTimeoutMs = timeoutFromEnvironment(import.meta.env.VITE_ANALYSIS_TIMEOUT_MS, 120_000)
const jobUploadTimeoutMs = timeoutFromEnvironment(import.meta.env.VITE_JOB_UPLOAD_TIMEOUT_MS, 60_000)

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code = 'request_failed',
    public readonly requestId?: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = requestTimeoutMs): Promise<T> {
  const controller = new AbortController()
  const externalSignal = init?.signal
  const abortFromExternal = () => controller.abort()
  if (externalSignal?.aborted) controller.abort()
  else externalSignal?.addEventListener('abort', abortFromExternal, { once: true })
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${configuredBase}${path}`, { credentials: 'include', ...init, signal: controller.signal })
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
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('O backend não respondeu dentro do tempo esperado.', 'request_timeout')
    }
    if (error instanceof TypeError) {
      throw new ApiError('Não foi possível conectar ao backend.', 'network_error')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
    externalSignal?.removeEventListener('abort', abortFromExternal)
  }
}

export function getCapabilities(): Promise<Capabilities> {
  return request<Capabilities>('/api/v1/capabilities')
}

export function submitAnalysis(file: File, options?: { retentionMode?: string; privateSession?: boolean; csrfToken?: string }): Promise<AnalysisContract> {
  const body = new FormData()
  body.append('file', file)
  if (options?.retentionMode) body.append('retention_mode', options.retentionMode)
  body.append('private_session', String(Boolean(options?.privateSession)))
  return request<AnalysisContract>('/api/v1/analyses', { method: 'POST', body, headers: options?.csrfToken ? { 'X-CSRF-Token': options.csrfToken } : undefined }, analysisTimeoutMs)
}

export function createAnalysisJob(file: File, options?: { retentionMode?: string; privateSession?: boolean; csrfToken?: string }): Promise<AnalysisJobCreated> {
  const body = new FormData()
  body.append('file', file)
  if (options?.retentionMode) body.append('retention_mode', options.retentionMode)
  body.append('private_session', String(Boolean(options?.privateSession)))
  return request('/api/v1/analysis-jobs', { method: 'POST', body, headers: options?.csrfToken ? { 'X-CSRF-Token': options.csrfToken } : undefined }, jobUploadTimeoutMs)
}

export function getAnalysisJob(jobId: string, signal?: AbortSignal): Promise<AnalysisJobState> {
  return request(`/api/v1/analysis-jobs/${encodeURIComponent(jobId)}`, { signal })
}

export function getAnalysisJobResult(jobId: string, signal?: AbortSignal): Promise<AnalysisContract> {
  return request(`/api/v1/analysis-jobs/${encodeURIComponent(jobId)}/result`, { signal })
}

export function createAnalysisSet(jobIds: string[], csrfToken?: string): Promise<AnalysisSetResult> {
  return request('/api/v1/analysis-sets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}) },
    body: JSON.stringify({ job_ids: jobIds }),
  })
}

export function getAnalysisSet(setId: string): Promise<AnalysisSetResult> {
  return request(`/api/v1/analysis-sets/${encodeURIComponent(setId)}`)
}

export const authApi = {
  me: () => request<AuthResponse>('/api/v1/auth/me'),
  login: (email: string, password: string) => request<AuthResponse>('/api/v1/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }),
  register: (payload: object) => request<AuthResponse>('/api/v1/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  logout: (csrf: string) => request<void>('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } }),
  updatePrivacy: (payload: object, csrf: string) => request<PrivacyPreferences>('/api/v1/auth/privacy', { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }),
  users: () => request<WebUser[]>('/api/v1/admin/users'),
  updateUser: (id: string, payload: object, csrf: string) => request<WebUser>(`/api/v1/admin/users/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }),
}

export function getHistory(): Promise<Array<{ id: string; result: AnalysisContract }>> { return request('/api/v1/analyses/history') }
