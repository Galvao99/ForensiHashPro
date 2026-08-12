import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { DdnaPage } from '../pages/DdnaPage'

function renderPage() {
  return render(<MemoryRouter><DdnaPage /></MemoryRouter>)
}

describe('página institucional DDNA', () => {
  it('apresenta hero, status de desenvolvimento e narrativa central', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /custódia verificável para artefatos digitais/i })).toBeInTheDocument()
    expect(screen.getByText('PRODUTO EM DESENVOLVIMENTO')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /entenda como funciona/i })).toHaveAttribute('href', '#como-funciona')
    expect(screen.getByText(/este é exatamente o mesmo arquivo/i)).toBeInTheDocument()
  })

  it('explica T0, Artifact/Context, Verify e verificação independente', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /marco em que o artefato entra/i })).toBeInTheDocument()
    expect(screen.getByText(/não pretende provar o que aconteceu antes do T0/i)).toBeInTheDocument()
    expect(screen.getAllByText('ARTIFACT').length).toBeGreaterThan(0)
    expect(screen.getAllByText('CONTEXT').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: /e daqui a 5 ou 10 anos/i })).toBeInTheDocument()
    expect(screen.getByText(/confiança não deve depender/i)).toBeInTheDocument()
  })

  it('cobre contratação, selfie, IP e separação DDNA/ForensiHash', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /muito mais que o PDF final/i })).toBeInTheDocument()
    expect(screen.getByText('SELFIE: PRESERVAÇÃO, NÃO BIOMETRIA')).toBeInTheDocument()
    expect(screen.getByText(/geolocalização é uma estimativa/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /DDNA PRESERVA. FORENSIHASH ANALISA/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /o que o DDNA não é/i })).toBeInTheDocument()
  })

  it('renderiza os diagramas técnicos com nomes acessíveis', () => {
    renderPage()
    const diagrams = screen.getAllByRole('img')
    expect(diagrams.length).toBeGreaterThanOrEqual(14)
    expect(screen.getByRole('img', { name: /limite temporal do T0/i })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /snapshot contextual de IP/i })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /ledger de custódia/i })).toBeInTheDocument()
  })

  it('publica CPP, Tema 1061, STJ, ISO, ICP-Brasil e LGPD com ressalvas', () => {
    renderPage()
    expect(screen.getAllByText(/arts. 158-A a 158-F/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Tema 1061/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText('ISO/IEC 27037:2012').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/VALIDAR — validação de assinaturas/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Lei 13.709\/2018/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/não certificam, homologam, recomendam ou tornam o DDNA obrigatório/i)).toBeInTheDocument()
  })

  it('protege todos os links externos', () => {
    renderPage()
    const sources = screen.getAllByRole('link', { name: /ver fonte/i })
    expect(sources.length).toBeGreaterThanOrEqual(13)
    for (const source of sources) {
      expect(source).toHaveAttribute('target', '_blank')
      expect(source).toHaveAttribute('rel', expect.stringContaining('noopener'))
      expect(source).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
      expect(source.getAttribute('href')).toMatch(/^https:\/\//)
    }
  })

  it('não publica alegações institucionais proibidas', () => {
    const { container } = renderPage()
    const content = container.textContent?.toLowerCase() ?? ''
    for (const claim of [
      'ddna garante autenticidade absoluta', 'ddna prova que o conteúdo é verdadeiro',
      'ddna elimina fraude', 'ddna impede adulteração', 'ddna é certificado pela iso',
      'ddna é reconhecido oficialmente por tribunais', 'ddna é obrigatório por lei',
    ]) expect(content).not.toContain(claim)
    expect(content).toContain('exemplo exclusivamente didático')
  })

  it('atualiza SEO da rota e conserva navegação por teclado nativa', async () => {
    renderPage()
    await waitFor(() => expect(document.title).toBe('DDNA — Cadeia de custódia e integridade de arquivos digitais'))
    const hero = screen.getByRole('heading', { name: /custódia verificável/i }).closest('section')!
    expect(within(hero).getAllByRole('link')).toHaveLength(2)
  })
})
