import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, authApi, createAnalysisJob, submitAnalysis } from '../lib/api'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('timeouts do cliente HTTP', () => {
  it('limita apenas o upload/criação do job a 60 segundos', async () => {
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ job_id: 'job-1', status: 'QUEUED' })))

    await createAnalysisJob(new File(['fixture'], 'fixture.txt'))

    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 60_000)
  })

  it('usa 120 segundos somente para a análise síncrona', async () => {
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(analysisFixture)))

    await submitAnalysis(new File(['fixture'], 'fixture.txt'))

    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 120_000)
  })

  it('mantém o timeout padrão curto nas requisições de autenticação', async () => {
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(authFixture)))

    await authApi.me()

    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 15_000)
    expect(setTimeoutSpy).not.toHaveBeenCalledWith(expect.any(Function), 120_000)
  })

  it('preserva erros HTTP reais sem convertê-los em timeout', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      error: { code: 'analysis_rejected', message: 'Arquivo rejeitado com segurança.' },
    }, 422)))

    await expect(submitAnalysis(new File(['fixture'], 'fixture.txt'))).rejects.toMatchObject({
      name: 'Error',
      code: 'analysis_rejected',
      message: 'Arquivo rejeitado com segurança.',
    })
  })

  it('mantém a mensagem específica quando o limite da análise é atingido', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })))

    const request = submitAnalysis(new File(['fixture'], 'fixture.txt'))
    const rejection = expect(request).rejects.toEqual(expect.objectContaining<Partial<ApiError>>({
      code: 'request_timeout',
      message: 'O backend não respondeu dentro do tempo esperado.',
    }))

    await vi.advanceTimersByTimeAsync(120_000)
    await rejection
  })
})
