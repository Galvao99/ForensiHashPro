import type { ApiErrorEnvelope, AuthResponse } from '../types/api'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''
const parsedTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS)
const requestTimeoutMs = Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : 15_000

export class ApiError extends Error {
  constructor(message: string, public readonly code = 'request_failed', public readonly requestId?: string) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs)
  try {
    const response = await fetch(`${configuredBase}${path}`, { credentials: 'include', ...init, signal: controller.signal })
    if (!response.ok) {
      let payload: ApiErrorEnvelope = {}
      try { payload = await response.json() as ApiErrorEnvelope } catch { /* Keep public failures generic. */ }
      throw new ApiError(payload.error?.message ?? 'Não foi possível concluir a solicitação.', payload.error?.code, payload.error?.request_id)
    }
    if (response.status === 204) return undefined as T
    return await response.json() as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('O backend não respondeu dentro do tempo esperado.', 'request_timeout')
    if (error instanceof TypeError) throw new ApiError('Não foi possível conectar ao backend.', 'network_error')
    throw error
  } finally { window.clearTimeout(timeout) }
}

export const authApi = {
  me: () => request<AuthResponse>('/api/v1/auth/me'),
  login: (email: string, password: string) => request<AuthResponse>('/api/v1/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }),
  register: (payload: object) => request<AuthResponse>('/api/v1/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  logout: (csrf: string) => request<void>('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } }),
  forgotPassword: (email: string) => request<{ message: string }>('/api/v1/auth/forgot-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) }),
  resetPassword: (token: string, password: string, password_confirmation: string) => request<{ message: string }>('/api/v1/auth/reset-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, password, password_confirmation }) }),
}
