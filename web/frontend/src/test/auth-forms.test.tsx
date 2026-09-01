import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { authFixture } from './fixtures'

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

describe('formulários reais de autenticação', () => {
  it.each(['/login', '/register', '/forgot-password', '/reset-password?token=example'])(
    'usa o logo real e a fundação visual compartilhada em %s',
    async (path) => {
      vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response({}, 401))))
      const { container } = renderAt(path)

      const logo = await screen.findByRole('img', { name: 'ForensiHash' })
      expect(logo).toHaveAttribute('src', '/assets/forensihash_logo_branco.png')
      expect(container.querySelector('.customer-auth-page')).toBeInTheDocument()
      expect(container.querySelector('.customer-auth-surface')).toBeInTheDocument()
      expect(screen.queryByText('FH', { exact: true })).not.toBeInTheDocument()
    },
  )

  it('oferece cadastro e recuperação a partir do login público', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response({}, 401))))
    renderAt('/login')

    expect(await screen.findByRole('link', { name: 'Criar conta' })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: 'Esqueci minha senha' })).toHaveAttribute('href', '/forgot-password')
    expect(screen.getByLabelText('E-mail')).toHaveAttribute('autocomplete', 'email')
    expect(screen.getByLabelText('Senha')).toHaveAttribute('autocomplete', 'current-password')
  })

  it('submete cadastro com o schema exato, confirma a sessão e navega', async () => {
    let meCalls = 0
    const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
      void _init
      const url = String(input)
      if (url.includes('/auth/me')) {
        meCalls += 1
        return Promise.resolve(meCalls === 1 ? response({}, 401) : response(authFixture))
      }
      return Promise.resolve(response(authFixture, 201))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/register')

    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'correct-horse-42')
    await userEvent.type(screen.getByLabelText('Confirmar senha'), 'correct-horse-42')
    await userEvent.click(screen.getByRole('button', { name: 'Criar conta' }))

    await screen.findByRole('heading', { name: 'Visão Geral' })
    const call = fetchMock.mock.calls.find(([input]) => String(input).includes('/auth/register'))
    expect(call).toBeDefined()
    expect(call?.[1]).toMatchObject({ method: 'POST', credentials: 'include' })
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      email: 'person@example.test',
      password: 'correct-horse-42',
      password_confirmation: 'correct-horse-42',
    })
    expect(meCalls).toBe(2)
    expect(window.location.pathname).toBe('/customer')
  })

  it('informa acesso restrito quando cadastro público está desabilitado', async () => {
    vi.stubEnv('VITE_REGISTRATION_ENABLED', 'false')
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response({}, 401))))

    renderAt('/register')

    expect(await screen.findByRole('heading', { name: 'Acesso restrito' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Criar conta' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar para o login' })).toHaveAttribute('href', '/login')
  })

  it('não oferece criação de conta no login restrito', async () => {
    vi.stubEnv('VITE_REGISTRATION_ENABLED', 'false')
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response({}, 401))))

    renderAt('/login')

    expect(await screen.findByText('Acesso restrito. Solicite uma conta ao administrador.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Criar conta' })).not.toBeInTheDocument()
  })

  it('Enter submete login, reconsulta /me e não persiste senha ou sessão no navegador', async () => {
    let meCalls = 0
    const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
      void _init
      const url = String(input)
      if (url.includes('/auth/me')) {
        meCalls += 1
        return Promise.resolve(meCalls === 1 ? response({}, 401) : response(authFixture))
      }
      return Promise.resolve(response(authFixture))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/login')

    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'not-persisted-42{Enter}')

    await screen.findByRole('heading', { name: 'Visão Geral' })
    const call = fetchMock.mock.calls.find(([input]) => String(input).includes('/auth/login'))
    expect(call?.[1]).toMatchObject({ method: 'POST', credentials: 'include' })
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ email: 'person@example.test', password: 'not-persisted-42' })
    expect(meCalls).toBe(2)
    expect(window.location.pathname).toBe('/customer')
    expect(JSON.stringify(localStorage)).not.toContain('not-persisted-42')
    expect(JSON.stringify(sessionStorage)).not.toContain('not-persisted-42')
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).toEqual(['forensihash-theme'])
  })

  it('mostra erro seguro da API e encerra o estado visual de envio', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
      void _init
      const url = String(input)
      if (url.includes('/auth/me')) return Promise.resolve(response({}, 401))
      return Promise.resolve(response({ error: { code: 'invalid_credentials', message: 'E-mail ou senha inválidos.' } }, 401))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/login')

    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'incorrect-000')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos.')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled())
    expect(screen.queryByText(/traceback|exception|stack/i)).not.toBeInTheDocument()
  })

  it('encerra loading e exibe erro quando a confirmação /me retorna 401', async () => {
    let meCalls = 0
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
      const url = String(input)
      if (url.includes('/auth/me')) {
        meCalls += 1
        return Promise.resolve(response({ error: { message: meCalls === 1 ? 'Sem sessão.' : 'A sessão não pôde ser confirmada.' } }, 401))
      }
      return Promise.resolve(response(authFixture))
    }))
    renderAt('/login')

    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'correct-horse-42{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('A sessão não pôde ser confirmada.')
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled()
  })

  it('encerra loading quando a confirmação /me falha por rede', async () => {
    let meCalls = 0
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request) => {
      const url = String(input)
      if (url.includes('/auth/me')) {
        meCalls += 1
        return meCalls === 1
          ? Promise.resolve(response({}, 401))
          : Promise.reject(new TypeError('network unavailable'))
      }
      return Promise.resolve(response(authFixture))
    }))
    renderAt('/login')

    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'correct-horse-42{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar ao backend.')
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled()
  })

  it('ignora a consulta inicial stale sem descartar a confirmação pós-login', async () => {
    let resolveInitial: ((value: Response) => void) | undefined
    const initial = new Promise<Response>((resolve) => { resolveInitial = resolve })
    let meCalls = 0
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input)
      if (url.includes('/auth/me')) {
        meCalls += 1
        return meCalls === 1 ? initial : Promise.resolve(response(authFixture))
      }
      return Promise.resolve(response(authFixture))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/login')
    await waitFor(() => expect(meCalls).toBe(1))

    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'correct-horse-42{Enter}')
    await screen.findByRole('heading', { name: 'Visão Geral' })
    expect(meCalls).toBe(2)

    resolveInitial?.(response({}, 401))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Visão Geral' })).toBeInTheDocument())
    expect(window.location.pathname).toBe('/customer')
  })
})
