import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { authFixture } from './fixtures'

function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: async () => body } as Response }
function renderAt(path: string, authenticated = false) {
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url.includes('/auth/logout')) return Promise.resolve(response(undefined, 204))
    return Promise.resolve(authenticated ? response(authFixture) : response({}, 401))
  }))
  window.history.pushState({}, '', path)
  return render(<App />)
}

describe('transição para Área do Cliente', () => {
  it('protege /customer e redireciona visitante ao login', async () => {
    renderAt('/customer')
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('mostra somente conta real e placeholders honestos', async () => {
    renderAt('/customer', true)
    expect(await screen.findByRole('heading', { name: 'Visão Geral' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'ForensiHash' })).toHaveAttribute('src', '/assets/forensihash_logo_branco.png')
    expect(screen.queryByText('FH', { exact: true })).not.toBeInTheDocument()
    expect(screen.getAllByText('person@example.test')).toHaveLength(2)
    expect(screen.getByText('Ainda não verificado')).toBeInTheDocument()
    expect(screen.queryByText(/Nova análise|Analisar evidências|Histórico de análises|ForensiHash Free/i)).not.toBeInTheDocument()
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'DDNA' })).not.toBeInTheDocument()
    expect(screen.queryByText(/plano ativo|licença válida|fatura|dispositivos ativos/i)).not.toBeInTheDocument()
  })

  it.each(['/app', '/app/analysis', '/app/history', '/app/ddna', '/analysis'])('redireciona a rota forense obsoleta %s para /customer', async (path) => {
    renderAt(path, true)
    await screen.findByRole('heading', { name: 'Visão Geral' })
    expect(window.location.pathname).toBe('/customer')
  })

  it('mantém logout com invalidação no backend', async () => {
    const view = renderAt('/customer', true)
    await screen.findByRole('heading', { name: 'Visão Geral' })
    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    const fetchMock = vi.mocked(fetch)
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).includes('/auth/logout') && init?.method === 'POST')).toBe(true)
    view.unmount()
  })

  it('não chama APIs forenses ao carregar a Área do Cliente', async () => {
    renderAt('/customer', true)
    await screen.findByRole('heading', { name: 'Visão Geral' })
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.every(([input]) => !/analysis|ddna|capabilities/.test(String(input)))).toBe(true))
  })
})
