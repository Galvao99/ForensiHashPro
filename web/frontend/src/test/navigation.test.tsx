import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { authFixture } from './fixtures'

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

describe('navegação pública', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))

  it('o logo navega para a página inicial', async () => {
    renderAt('/ddna')
    await userEvent.click(screen.getAllByRole('link', { name: /arqen.*página inicial/i })[0])
    expect(window.location.pathname).toBe('/')
    expect(screen.getByRole('heading', { name: /proveniência.*integridade.*rastreabilidade/i })).toBeInTheDocument()
  })

  it('a navbar expõe as áreas institucionais e a análise', () => {
    renderAt('/')
    expect(screen.getAllByRole('link', { name: 'ForensiHash' })[0]).toHaveAttribute('href', '/forensihash')
    expect(screen.getAllByRole('link', { name: 'DDNA' })[0]).toHaveAttribute('href', '/ddna')
    expect(screen.getByRole('link', { name: 'Acessar plataforma' })).toHaveAttribute('href', '/app/analysis')
    expect(screen.queryByRole('link', { name: 'Tecnologia' })).not.toBeInTheDocument()
    expect(document.querySelector('a[href="/technology"]')).not.toBeInTheDocument()
  })

  it('a rota DDNA informa que a tecnologia está em desenvolvimento', () => {
    renderAt('/ddna')
    expect(screen.getByText('PRODUTO EM DESENVOLVIMENTO')).toBeInTheDocument()
    expect(screen.getByText(/não um serviço de custódia disponível/i)).toBeInTheDocument()
  })

  it('login funciona sem persistir credenciais', async () => {
    let meCalls = 0
    vi.stubGlobal('fetch', vi.fn((input: string) => {
      const isMe = String(input).includes('/auth/me')
      meCalls += Number(isMe)
      const unauthorized = isMe && meCalls === 1
      return Promise.resolve({ ok: !unauthorized, status: unauthorized ? 401 : 200, json: async () => authFixture } as Response)
    }))
    renderAt('/login')
    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'not-persisted')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByText('Pessoa Teste')
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).toEqual(['forensihash-theme'])
    expect(JSON.stringify(localStorage)).not.toContain('person@example.test')
    expect(JSON.stringify(localStorage)).not.toContain('not-persisted')
    expect(sessionStorage.length).toBe(0)
  })
})
