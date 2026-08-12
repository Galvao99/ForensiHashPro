import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'

function renderHome() {
  window.history.pushState({}, '', '/')
  return render(<App />)
}

describe('homepage institucional ARQEN', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) })))

  it('apresenta ARQEN como marca-mãe e os dois produtos', () => {
    renderHome()
    expect(screen.getAllByAltText('ARQEN')[0]).toHaveAttribute('src', '/assets/arqen_logo_branca.png')
    expect(screen.getByRole('heading', { level: 1, name: /proveniência.*integridade.*rastreabilidade/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /conhecer DDNA/i })).toHaveAttribute('href', '/ddna')
    expect(screen.getByRole('link', { name: /conhecer ForensiHash/i })).toHaveAttribute('href', '/forensihash')
  })

  it('mantém CTAs e navegação em rotas existentes', () => {
    renderHome()
    expect(screen.getByRole('link', { name: /conheça nossas soluções/i })).toHaveAttribute('href', '#solutions')
    expect(screen.getByRole('link', { name: /explorar tecnologia/i })).toHaveAttribute('href', '/technology')
    const navigation = screen.getByRole('navigation', { name: /navegação principal/i })
    const localRoutes = within(navigation).getAllByRole('link').map(link => link.getAttribute('href'))
    expect(localRoutes).toEqual(['/#solutions', '/technology', '/ddna', '/forensihash', '/references', '/app/analysis'])
  })

  it('oferece menu mobile acessível', async () => {
    renderHome()
    const menu = screen.getByRole('button', { name: 'Abrir menu' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(menu)
    expect(screen.getByRole('button', { name: 'Fechar menu' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('expõe interações por teclado e explicações com ressalvas', async () => {
    renderHome()
    const hashNode = screen.getByRole('button', { name: 'HASH' })
    hashNode.focus()
    await waitFor(() => expect(hashNode).toHaveAttribute('aria-pressed', 'true'))
    await userEvent.click(screen.getByRole('tab', { name: 'Contexto' }))
    expect(screen.getByRole('tabpanel', { name: 'Contexto' })).toHaveTextContent(/não identifica, isoladamente, uma pessoa/i)
  })

  it('descreve setores como aplicações e não como clientes', () => {
    const { container } = renderHome()
    expect(screen.getByRole('heading', { name: /setores com desafios/i })).toBeInTheDocument()
    expect(container.textContent).toContain('Esta lista não representa clientes')
    expect(container.textContent).not.toContain('Trusted by')
    expect(container.textContent).not.toContain('Usado por')
  })

  it('não publica alegações absolutas proibidas', () => {
    const { container } = renderHome()
    const text = container.textContent?.toLowerCase() ?? ''
    for (const claim of ['elimina fraude', '100% seguro', 'impossível adulterar', 'certificado pela iso', 'validado pelo stj']) expect(text).not.toContain(claim)
  })
})
