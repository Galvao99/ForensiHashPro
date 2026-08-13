import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { authFixture } from './fixtures'

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

function workspaceFetch() {
  return vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/auth/me')) return Promise.resolve(response(authFixture))
    if (url.endsWith('/capabilities')) return Promise.resolve(response({ hashes: { available: true } }))
    if (url.endsWith('/analysis-jobs') && init?.method === 'POST') return Promise.resolve(response({ job_id: 'overview-job', status: 'QUEUED' }, 202))
    return Promise.resolve(response({ job_id: 'overview-job', status: 'PROCESSING', current_stage: 'ANALYZING' }))
  })
}

describe('overview do workspace atual', () => {
  it('mostra workspace vazio e contadores operacionais zerados', async () => {
    vi.stubGlobal('fetch', workspaceFetch())
    window.history.pushState({}, '', '/app')
    render(<App />)
    expect(await screen.findByText('Workspace vazio.')).toBeInTheDocument()
    const summary = screen.getByLabelText('Resumo do workspace')
    expect(within(summary).getAllByText('0')).toHaveLength(4)
  })

  it('reflete artefatos correntes, inclusive processamento e fila local', async () => {
    const fetchMock = workspaceFetch()
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    const files = [new File(['pdf'], 'contrato.pdf', { type: 'application/pdf' }), new File(['json'], 'logs.json', { type: 'application/json' })]
    Object.defineProperty(files[0], 'webkitRelativePath', { value: 'Caso/contrato.pdf' })
    Object.defineProperty(files[1], 'webkitRelativePath', { value: 'Caso/logs.json' })
    await userEvent.upload(await screen.findByLabelText('Selecionar pasta'), files)
    await userEvent.click(screen.getAllByRole('link', { name: 'Overview' }).find((link) => link.getAttribute('href') === '/app')!)

    expect(await screen.findByText('contrato.pdf')).toBeInTheDocument()
    expect(screen.getByText('logs.json')).toBeInTheDocument()
    expect(screen.getByText('Analisando')).toBeInTheDocument()
    expect(screen.getByText('Aguardando')).toBeInTheDocument()
    expect(screen.getByText('PDF')).toBeInTheDocument()
    expect(screen.getByText('JSON')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith('/analysis-jobs') && init?.method === 'POST')).toHaveLength(1)
  })

  it('mantém os artefatos visíveis se capabilities estiverem indisponíveis', async () => {
    const fetchMock = workspaceFetch()
    fetchMock.mockImplementation((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/me')) return Promise.resolve(response(authFixture))
      if (url.endsWith('/capabilities')) return Promise.reject(new Error('offline'))
      if (url.endsWith('/analysis-jobs') && init?.method === 'POST') return Promise.resolve(response({ job_id: 'overview-job', status: 'QUEUED' }, 202))
      return Promise.resolve(response({ job_id: 'overview-job', status: 'PROCESSING' }))
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['x'], 'evidence.bin'))
    await userEvent.click(screen.getAllByRole('link', { name: 'Overview' }).find((link) => link.getAttribute('href') === '/app')!)
    expect(await screen.findByText('evidence.bin')).toBeInTheDocument()
    expect(await screen.findByText('Backend indisponível no momento.')).toBeInTheDocument()
  })
})
