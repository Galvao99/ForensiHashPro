import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, authApi } from '../lib/api'
import { authFixture } from './fixtures'

function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: async () => body } as Response }
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('cliente HTTP da Área do Cliente', () => {
  it('usa o timeout padrão nas requisições de autenticação', async () => {
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(authFixture)))
    await authApi.me()
    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 15_000)
  })

  it('preserva erros HTTP seguros', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ error: { code: 'invalid_credentials', message: 'E-mail ou senha inválidos.' } }, 401)))
    await expect(authApi.login('person@example.test', 'invalid-password')).rejects.toMatchObject({ code: 'invalid_credentials', message: 'E-mail ou senha inválidos.' })
  })

  it('converte expiração em erro público de timeout', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))))))
    const pending = authApi.me()
    const rejection = expect(pending).rejects.toEqual(expect.objectContaining<Partial<ApiError>>({ code: 'request_timeout' }))
    await vi.advanceTimersByTimeAsync(15_000)
    await rejection
  })
})
