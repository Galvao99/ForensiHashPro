import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 400, json: async () => body } as Response
}

function authenticatedFetch(handler: (url: string, init?: RequestInit) => Promise<Response> | Response) { return vi.fn((input: string | URL | Request, init?: RequestInit) => { const url = String(input); return url.includes('/auth/me') ? Promise.resolve(response(authFixture)) : Promise.resolve(handler(url, init)) }) }

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
    const fetchMock = authenticatedFetch(() => response(analysisFixture))
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    const file = new File(['synthetic'], 'synthetic.txt', { type: 'text/plain' })
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), file)
    await userEvent.click(screen.getByRole('button', { name: 'Analisar' }))
    expect((await screen.findAllByText('abc123')).length).toBeGreaterThan(0)
    const analysisCall = fetchMock.mock.calls.find(([url]) => url === '/api/v1/analyses')!
    const [, init] = analysisCall
    expect(analysisCall[0]).toBe('/api/v1/analyses')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
  })

  it('apresenta erro seguro retornado pela API', async () => {
    vi.stubGlobal('fetch', authenticatedFetch(() => response({ error: { code: 'file_too_large', message: 'O arquivo excede o limite permitido.' } }, false)))
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['x'], 'large.bin'))
    await userEvent.click(screen.getByRole('button', { name: 'Analisar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('O arquivo excede o limite permitido.')
    expect(screen.queryByText(/traceback|exception|\/tmp/i)).not.toBeInTheDocument()
  })

  it('mostra processamento indeterminado sem percentual inventado', async () => {
    vi.stubGlobal('fetch', authenticatedFetch(() => new Promise(() => undefined)))
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['x'], 'pending.bin'))
    await userEvent.click(screen.getByRole('button', { name: 'Analisar' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('PROCESSING'))
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument()
  })
})
