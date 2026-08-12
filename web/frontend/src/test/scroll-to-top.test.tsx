import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'

describe('posição de navegação pública', () => {
  const scrollTo = vi.fn()
  const scrollIntoView = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn())
    vi.stubGlobal('scrollTo', scrollTo)
    Element.prototype.scrollIntoView = scrollIntoView
  })

  it('move uma nova rota sem hash para o topo', async () => {
    window.history.pushState({}, '', '/')
    render(<App />)
    scrollTo.mockClear()
    await userEvent.click(screen.getAllByRole('link', { name: 'ForensiHash' })[0])
    expect(window.location.pathname).toBe('/forensihash')
    expect(scrollTo).toHaveBeenCalledWith(0, 0)
  })

  it('preserva navegação intencional para uma âncora existente', () => {
    window.history.pushState({}, '', '/ddna#t0')
    render(<App />)
    expect(scrollIntoView).toHaveBeenCalled()
    expect(scrollTo).not.toHaveBeenCalled()
  })
})
