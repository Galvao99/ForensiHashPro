import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

describe('navegação pública', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))

  it('o logo navega para a página inicial', async () => {
    renderAt('/ddna')
    await userEvent.click(screen.getByRole('link', { name: /forensihash pro — página inicial/i }))
    expect(window.location.pathname).toBe('/')
    expect(screen.getByRole('heading', { name: /análise e rastreabilidade/i })).toBeInTheDocument()
  })

  it('a navbar expõe as áreas institucionais e a análise', () => {
    renderAt('/')
    expect(screen.getByRole('link', { name: 'Produto' })).toHaveAttribute('href', '/forensihash')
    expect(screen.getByRole('link', { name: 'DDNA' })).toHaveAttribute('href', '/ddna')
    expect(screen.getByRole('link', { name: 'Começar análise' })).toHaveAttribute('href', '/app/analysis')
  })

  it('a rota DDNA informa que a tecnologia está em desenvolvimento', () => {
    renderAt('/ddna')
    expect(screen.getAllByText('EM DESENVOLVIMENTO').length).toBeGreaterThan(0)
    expect(screen.getByText(/nenhum registro DDNA/i)).toBeInTheDocument()
  })

  it('login não persiste credenciais', async () => {
    renderAt('/login')
    await userEvent.type(screen.getByLabelText('E-mail'), 'person@example.test')
    await userEvent.type(screen.getByLabelText('Senha'), 'not-persisted')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(screen.getByRole('status')).toHaveTextContent(/nenhuma credencial foi enviada ou armazenada/i)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})
