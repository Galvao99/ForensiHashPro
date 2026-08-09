import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 400, json: async () => body } as Response
}

function authenticatedFetch(handler: (url: string, init?: RequestInit) => Promise<Response> | Response) { return vi.fn((input: string | URL | Request, init?: RequestInit) => { const url = String(input); return url.includes('/auth/me') ? Promise.resolve(response(authFixture)) : Promise.resolve(handler(url, init)) }) }

function completedAnalysisFetch() {
  return authenticatedFetch((url) => {
    if (url.endsWith('/analysis-jobs')) return response({ job_id: 'job-1', status: 'QUEUED' })
    if (url.endsWith('/result')) return response(analysisFixture)
    return response({ job_id: 'job-1', status: 'SUCCESS', analysis_id: analysisFixture.analysis_id, current_stage: 'FINISHED', started_at: '2026-01-01T00:00:00Z' })
  })
}

describe('integração HTTP', () => {
  it('renderiza capabilities informadas pelo backend', async () => {
    vi.stubGlobal('fetch', authenticatedFetch(() => response({ hashes: { available: true }, metadata: { available: false }, ocr: { available: true } })))
    window.history.pushState({}, '', '/app')
    render(<App />)
    expect(await screen.findByText('Hash')).toBeInTheDocument()
    expect(screen.getAllByText('Disponível').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Indisponível').length).toBeGreaterThan(0)
    expect(fetch).toHaveBeenCalledWith('/api/v1/capabilities', expect.objectContaining({ credentials: 'include' }))
  })

  it('envia upload real como multipart e renderiza o hash retornado', async () => {
    const fetchMock = completedAnalysisFetch()
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    const file = new File(['synthetic'], 'synthetic.txt', { type: 'text/plain' })
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), file)
    expect((await screen.findAllByText('abc123')).length).toBeGreaterThan(0)
    expect(document.querySelector('.activity-spinner')).not.toBeInTheDocument()
    const analysisCall = fetchMock.mock.calls.find(([url]) => url === '/api/v1/analysis-jobs')!
    const [, init] = analysisCall
    expect(analysisCall[0]).toBe('/api/v1/analysis-jobs')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
  })

  it('apresenta erro seguro retornado pela API', async () => {
    vi.stubGlobal('fetch', authenticatedFetch(() => response({ error: { code: 'file_too_large', message: 'O arquivo excede o limite permitido.' } }, false)))
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['x'], 'large.bin'))
    expect(await screen.findByRole('alert')).toHaveTextContent('O arquivo excede o limite permitido.')
    expect(screen.queryByText(/traceback|exception|\/tmp/i)).not.toBeInTheDocument()
  })

  it('mostra processamento indeterminado sem percentual inventado', async () => {
    vi.stubGlobal('fetch', authenticatedFetch((url) => url.endsWith('/analysis-jobs')
      ? response({ job_id: 'pending-job', status: 'QUEUED' })
      : response({ job_id: 'pending-job', status: 'PROCESSING', current_stage: 'ANALYZING', started_at: new Date().toISOString() })))
    window.history.pushState({}, '', '/app/analysis')
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort')
    const rendered = render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['x'], 'pending.bin'))
    await waitFor(() => expect(screen.getAllByText('Analisando').length).toBeGreaterThan(0))
    expect(screen.getByText('ANÁLISE EM ANDAMENTO')).toBeInTheDocument()
    expect(document.querySelector('.activity-spinner')).toBeInTheDocument()
    expect(screen.getByText('00:00')).toBeInTheDocument()
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument()
    rendered.unmount()
    expect(abortSpy).toHaveBeenCalled()
  })

  it('encerra o indicador e exibe erro seguro quando o job falha', async () => {
    vi.stubGlobal('fetch', authenticatedFetch((url) => url.endsWith('/analysis-jobs')
      ? response({ job_id: 'failed-job', status: 'QUEUED' })
      : response({ job_id: 'failed-job', status: 'FAILED', error_code: 'processing_failed', safe_error_message: 'A análise não pôde ser concluída.' })))
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['x'], 'failed.bin'))
    expect(await screen.findByRole('alert')).toHaveTextContent('A análise não pôde ser concluída.')
    expect(document.querySelector('.activity-spinner')).not.toBeInTheDocument()
  })
})
