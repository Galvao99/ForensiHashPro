import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ProductPage } from '../pages/ProductPage'

function renderPage() {
  return render(<MemoryRouter><ProductPage /></MemoryRouter>)
}

describe('página institucional ForensiHash', () => {
  it('apresenta hero, capacidades e públicos', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: /análise técnica de artefatos digitais/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /para quem o ForensiHash foi pensado/i })).toBeInTheDocument()
    expect(screen.getByText('PERITOS')).toBeInTheDocument()
    expect(screen.getByText('ADVOGADOS')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /o que ele analisa/i })).toBeInTheDocument()
  })

  it('explica fluxo, warnings, timeline e correlação', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /como funciona uma análise/i })).toBeInTheDocument()
    expect(screen.getByText(/resultado técnico/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /da observação ao detalhe verificável/i })).toBeInTheDocument()
    expect(screen.getByText(/ModifyDate anterior a CreationDate/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /tempo declarado e estrutura observável/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /relações entre arquivos/i })).toBeInTheDocument()
  })

  it('cobre contratação, limites, DDNA e CTA final', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Contratação eletrônica' })).toBeInTheDocument()
    expect(screen.getByText(/material que foi efetivamente disponibilizado/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /o que o ForensiHash não decide/i })).toBeInTheDocument()
    expect(screen.getByText(/a interpretação permanece dependente/i)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /DDNA preserva o estado/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Área do Cliente' })).toHaveAttribute('href', '/customer')
  })

  it('não publica conclusões automáticas proibidas', () => {
    const { container } = renderPage()
    const text = container.textContent?.toLowerCase() ?? ''
    for (const claim of ['detecta fraude', 'prova autoria', 'confirma autenticidade', 'elimina fraude', 'garante autenticidade']) expect(text).not.toContain(claim)
    expect(text).toContain('não determina fraude')
  })
})
