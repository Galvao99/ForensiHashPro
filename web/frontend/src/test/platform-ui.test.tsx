import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { analysisFixture, authFixture } from './fixtures'
import { ResultView } from '../pages/ResultPage'

function response(body: unknown, ok = true): Response { return { ok, status: ok ? 200 : 401, json: async () => body } as Response }
function authenticated(role: 'USER' | 'ADMIN' = 'USER') { const auth = { ...authFixture, user: { ...authFixture.user, role } }; return vi.fn((input: string) => Promise.resolve(response(String(input).includes('/auth/me') ? auth : {}))) }

describe('plataforma autenticada', () => {
  it('protege a área app e redireciona visitante ao login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, false)))
    window.history.pushState({}, '', '/app/account')
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('exibe sidebar do usuário e permite recolhimento', async () => {
    vi.stubGlobal('fetch', authenticated())
    window.history.pushState({}, '', '/app')
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Recolher sidebar' })
    await userEvent.click(button)
    expect(document.querySelector('.app-shell')).toHaveClass('sidebar-collapsed')
    expect(screen.queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
  })

  it('mostra gestão de usuários apenas para ADMIN', async () => {
    vi.stubGlobal('fetch', authenticated('ADMIN'))
    window.history.pushState({}, '', '/app')
    render(<App />)
    expect(await screen.findByRole('link', { name: 'Usuários' })).toBeInTheDocument()
  })

  it('persiste somente preferência LIGHT, DARK ou SYSTEM', async () => {
    vi.stubGlobal('fetch', authenticated())
    window.history.pushState({}, '', '/app')
    render(<App />)
    const select = await screen.findByLabelText('Tema')
    await userEvent.selectOptions(select, 'DARK')
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
    expect(localStorage.getItem('forensihash-theme')).toBe('DARK')
    expect(localStorage.length).toBe(1)
  })

  it('oferece sessão privada e resultado formatado com RAW JSON secundário', async () => {
    vi.stubGlobal('fetch', authenticated())
    window.history.pushState({}, '', '/app/analysis')
    const view = render(<App />)
    expect(await screen.findByRole('checkbox', { name: /sessão privada/i })).toBeChecked()
    view.unmount()
    render(<ResultView result={analysisFixture} />)
    expect(screen.getByRole('heading', { name: 'Identificação e hashes' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /dados técnicos completos/i })).toBeInTheDocument()
    expect(screen.getByText(/expandir JSON/i)).toBeInTheDocument()
    expect(screen.getAllByText('Indisponível').length).toBeGreaterThan(0)
  })
})
