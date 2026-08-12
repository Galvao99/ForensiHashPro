import { render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import indexHtml from '../../index.html?raw'

const routeTitles: Array<[string, string]> = [
  ['/', 'ARQEN | Infraestrutura para Evidências Digitais'],
  ['/ddna', 'DDNA | Custódia e Proveniência Digital — ARQEN'],
  ['/forensihash', 'ForensiHash | Análise de Artefatos Digitais — ARQEN'],
  ['/references', 'Referências Técnicas e Jurídicas | ARQEN'],
  ['/login', 'Acessar plataforma | ARQEN'],
  ['/register', 'Criar conta | ARQEN'],
]

describe('branding do documento público', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }))
    document.head.insertAdjacentHTML('beforeend', '<meta name="description"><meta property="og:title"><meta property="og:description"><meta property="og:site_name">')
  })

  it('configura somente o favicon oficial na raiz pública', () => {
    expect(indexHtml).toContain('<link rel="icon" type="image/png" href="/logo_icon.png" />')
    expect(indexHtml.match(/rel="(?:shortcut )?icon"/g)).toHaveLength(1)
    expect(indexHtml.toLowerCase()).not.toContain('vite.svg')
    expect(indexHtml).not.toContain('/assets/logo_icon.png')
  })

  it('define ARQEN como site_name e inclui theme-color', () => {
    expect(indexHtml).toContain('<meta property="og:site_name" content="ARQEN" />')
    expect(indexHtml).toContain('<meta name="theme-color" content="#050505" />')
  })

  it.each(routeTitles)('define o título específico de %s', async (route, title) => {
    window.history.pushState({}, '', route)
    const view = render(<App />)
    await waitFor(() => expect(document.title).toBe(title))
    view.unmount()
  })

  it('sincroniza Open Graph com a rota atual', async () => {
    window.history.pushState({}, '', '/references')
    render(<App />)
    await waitFor(() => expect(document.querySelector('meta[property="og:title"]')).toHaveAttribute('content', 'Referências Técnicas e Jurídicas | ARQEN'))
    expect(document.querySelector('meta[property="og:site_name"]')).toHaveAttribute('content', 'ARQEN')
  })
})
