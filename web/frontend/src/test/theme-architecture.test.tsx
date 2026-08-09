import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { authFixture } from './fixtures'

const LIGHT_LOGO = 'forensihash_logo_completo.png'
const DARK_LOGO = 'forensihash_logo_dark_cropped.png'

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

function visitorFetch() {
  return vi.fn().mockResolvedValue(response({}, 401))
}

function authenticatedFetch() {
  return vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url.includes('/auth/me')) return Promise.resolve(response(authFixture))
    if (url.includes('/auth/logout')) return Promise.resolve(response(undefined, 204))
    return Promise.resolve(response({}))
  })
}

function systemTheme(initialDark: boolean) {
  let dark = initialDark
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  const media = {
    get matches() { return dark },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener)),
    removeEventListener: vi.fn((_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener)),
    dispatchEvent: vi.fn(),
  } as unknown as MediaQueryList
  vi.stubGlobal('matchMedia', vi.fn(() => media))
  return {
    setDark(value: boolean) {
      dark = value
      listeners.forEach((listener) => listener({ matches: value } as MediaQueryListEvent))
    },
  }
}

describe('fronteira pública e autenticada do tema', () => {
  it('mantém Home e logo públicos claros com preferência e OS escuros', async () => {
    localStorage.setItem('forensihash-theme', 'DARK')
    systemTheme(true)
    vi.stubGlobal('fetch', visitorFetch())
    window.history.pushState({}, '', '/')
    render(<App />)
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'))
    expect(screen.getByAltText('ForensiHash')).toHaveAttribute('src', expect.stringContaining(LIGHT_LOGO))
  })

  it.each(['/login', '/register'])('mantém %s exclusivamente light', async (route) => {
    localStorage.setItem('forensihash-theme', 'DARK')
    systemTheme(true)
    vi.stubGlobal('fetch', visitorFetch())
    window.history.pushState({}, '', route)
    render(<App />)
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'))
    expect(document.querySelector('.auth-panel')).toBeInTheDocument()
  })

  it('permite LIGHT e DARK autenticados e alterna o logo sem mudar dimensões', async () => {
    localStorage.setItem('forensihash-theme', 'DARK')
    systemTheme(false)
    vi.stubGlobal('fetch', authenticatedFetch())
    window.history.pushState({}, '', '/app')
    render(<App />)
    const selector = await screen.findByLabelText('Tema')
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
    expect(document.querySelector('.app-sidebar')).toBeInTheDocument()
    screen.getAllByAltText('ForensiHash').forEach((logo) => {
      expect(logo.getAttribute('src')).toContain(DARK_LOGO)
      expect(logo).toHaveClass('brand__logo')
    })
    await userEvent.selectOptions(selector, 'LIGHT')
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'))
    screen.getAllByAltText('ForensiHash').forEach((logo) => {
      expect(logo.getAttribute('src')).toContain(LIGHT_LOGO)
      expect(logo).toHaveClass('brand__logo')
    })
  })

  it('resolve SYSTEM apenas autenticado e acompanha mudança do sistema', async () => {
    localStorage.setItem('forensihash-theme', 'SYSTEM')
    const system = systemTheme(false)
    vi.stubGlobal('fetch', authenticatedFetch())
    window.history.pushState({}, '', '/app')
    render(<App />)
    await screen.findByLabelText('Tema')
    expect(document.documentElement.dataset.theme).toBe('light')
    system.setDark(true)
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
    screen.getAllByAltText('ForensiHash').forEach((logo) => expect(logo.getAttribute('src')).toContain(DARK_LOGO))
  })

  it('logout força light sem apagar a preferência visual', async () => {
    localStorage.setItem('forensihash-theme', 'DARK')
    systemTheme(false)
    vi.stubGlobal('fetch', authenticatedFetch())
    window.history.pushState({}, '', '/app')
    render(<App />)
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('forensihash-theme')).toBe('DARK')
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).toEqual(['forensihash-theme'])
  })
})
