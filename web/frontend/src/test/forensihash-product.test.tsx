import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import {
  caseCorrelations, productFeatures, publishedEfficiencyStudies, roadmapItems,
  workflowSteps,
} from '../forensihash/content'
import { ProductPage } from '../pages/ProductPage'

function renderPage() {
  return render(<MemoryRouter><ProductPage /></MemoryRouter>)
}

describe('página institucional ForensiHash V2', () => {
  it('apresenta posicionamento, badges e CTA do hero', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: /da análise isolada de arquivos à correlação técnica do caso/i })).toBeInTheDocument()
    expect(screen.getByText(/plataforma desktop para examinar arquivos digitais/i)).toBeInTheDocument()
    const badges = screen.getByLabelText('Características do ForensiHash')
    for (const label of ['Desktop', 'Análise técnica', 'Correlação de evidências', 'Pesquisa e desenvolvimento']) expect(within(badges).getByText(label)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver como funciona' })).toHaveAttribute('href', '#como-funciona')
  })

  it('explica o problema e o papel profissional sem universalizar o fluxo', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /análise técnica e correlação, em um fluxo rastreável/i })).toBeInTheDocument()
    expect(screen.getByText(/pode exigir ferramentas diferentes/i)).toBeInTheDocument()
    expect(screen.getByText(/sem substituir interpretação, conferência ou redação pericial/i)).toBeInTheDocument()
  })

  it('renderiza o workflow auditado na ordem correta', () => {
    renderPage()
    const flow = screen.getByRole('list', { name: 'Fluxo técnico do ForensiHash' })
    expect(within(flow).getAllByRole('listitem')).toHaveLength(workflowSteps.length)
    expect(within(flow).getAllByRole('heading').map(item => item.textContent)).toEqual(workflowSteps.map(item => item.name))
    expect(screen.getByText(/resultado técnico é mais útil quando o perito consegue retornar à sua origem/i)).toBeInTheDocument()
  })

  it('publica somente features auditadas com status, escopo, limitação e evidência', () => {
    renderPage()
    expect(productFeatures.length).toBeGreaterThan(8)
    for (const feature of productFeatures) {
      expect(['AVAILABLE', 'IN_DEVELOPMENT']).toContain(feature.status)
      expect(feature.scope).not.toHaveLength(0)
      expect(feature.limitation).toBeTruthy()
      expect(feature.evidence.length).toBeGreaterThan(0)
      expect(screen.getByRole('heading', { name: feature.name })).toBeInTheDocument()
    }
    const capabilitySection = screen.getByRole('heading', { name: /o que o ForensiHash analisa hoje/i }).closest('section')!
    expect(within(capabilitySection).getAllByText('Disponível')).toHaveLength(productFeatures.filter(item => item.status === 'AVAILABLE').length)
    expect(within(capabilitySection).getAllByText('Em desenvolvimento')).toHaveLength(productFeatures.filter(item => item.status === 'IN_DEVELOPMENT').length)
  })

  it('descreve correlações canônicas com comparação, observação e não inferência', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /relações somente quando há suporte técnico/i })).toBeInTheDocument()
    for (const correlation of caseCorrelations) {
      const heading = screen.getByRole('heading', { name: correlation.name })
      const card = heading.closest('article')!
      expect(card).toHaveTextContent(correlation.compares)
      expect(card).toHaveTextContent(correlation.observes)
      expect(card).toHaveTextContent(correlation.doesNotMean)
      expect(correlation.evidence.length).toBeGreaterThan(0)
    }
    expect(screen.getByLabelText('Princípios de neutralidade técnica')).toHaveTextContent('correlação ≠ causalidade')
    expect(screen.getByLabelText('Princípios de neutralidade técnica')).toHaveTextContent('mesmo IP ≠ mesma pessoa')
  })

  it('explica Timeline e provenance sem reconstrução factual automática', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /organizar o tempo sem reescrever a história/i })).toBeInTheDocument()
    expect(screen.getByText(/precisão, timezone, papel temporal e limitações permanecem visíveis/i)).toBeInTheDocument()
    expect(screen.getByText(/arquivo, página, faixa textual, objeto ou stream/i)).toBeInTheDocument()
    expect(screen.getByText(/não “reconstrói a verdade dos fatos”/i)).toBeInTheDocument()
  })

  it('usa somente screenshots reais declarados, lazy e com alt descritivo', () => {
    renderPage()
    const images = screen.getAllByRole('img')
    expect(images).toHaveLength(2)
    expect(images[0]).toHaveAttribute('src', '/assets/forensihash-correlation-explorer.png')
    expect(images[0]).toHaveAttribute('loading', 'lazy')
    expect(images[0].getAttribute('alt')).toMatch(/Explorador de correlações/)
    expect(images[1]).toHaveAttribute('src', '/assets/forensihash-timeline.png')
    expect(images[1].getAttribute('alt')).toMatch(/Timeline do ForensiHash/)
    expect(screen.getByText(/capturas reais da interface desktop com dados sintéticos de teste/i)).toBeInTheDocument()
  })

  it('apresenta eficiência como expectativa e mantém benchmark vazio', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /menos operação repetitiva. mais tempo para revisar/i })).toBeInTheDocument()
    expect(screen.getByText(/ainda não existe benchmark público/i)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /comparação planejada do estudo de eficiência/i })).toHaveTextContent('Fluxo tradicional')
    expect(screen.getByText(/redução de tempo =/i)).toHaveTextContent('(T_manual − T_FH) / T_manual × 100')
    expect(publishedEfficiencyStudies).toEqual([])
    expect(screen.getByText(/Nenhum benchmark foi publicado nesta versão/i)).toBeInTheDocument()
  })

  it('separa roadmap disponível, em desenvolvimento e planejado', () => {
    renderPage()
    for (const status of ['AVAILABLE', 'IN_DEVELOPMENT', 'PLANNED'] as const) {
      const items = roadmapItems.filter(item => item.status === status)
      expect(items.length).toBeGreaterThan(0)
      expect(items.every(item => item.evidence.length > 0)).toBe(true)
    }
    expect(screen.getByRole('heading', { name: 'Disponível' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Em desenvolvimento' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Planejado' })).toBeInTheDocument()
    expect(screen.getByText(/itens planejados não são apresentados como capacidade atual/i)).toBeInTheDocument()
  })

  it('mantém limitações e fronteira local-first visíveis', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /o que precisa permanecer explícito/i })).toBeInTheDocument()
    expect(screen.getByText(/dados ausentes permanecem ausentes/i)).toBeInTheDocument()
    expect(screen.getByText(/assinatura e intervalo de certificado não equivalem a validação criptográfica completa/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /desktop local-first/i })).toBeInTheDocument()
    expect(screen.getByText(/não são enviados automaticamente ao site/i)).toBeInTheDocument()
    expect(screen.getByText(/consulta externa de contexto de IP é opcional/i)).toBeInTheDocument()
  })

  it('não publica claims proibidos nem ganhos de performance sem benchmark', () => {
    const { container } = renderPage()
    const text = container.textContent?.toLowerCase() ?? ''
    for (const claim of ['detecta fraude', 'detector de fraude', 'garante autenticidade', 'comprova autoria', '100% preciso', '3x mais rápido', '30% mais rápido', '80% mais eficiente']) expect(text).not.toContain(claim)
    expect(text).not.toMatch(/economiza \d+ horas?/)
    expect(text).toContain('não decide fraude, autenticidade, autoria ou validade jurídica')
    expect(text).toContain('correlação não equivale a causalidade')
  })

  it.each([390, 768, 1024, 1440, 1920])('mantém estrutura responsiva em %ipx', width => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
    window.dispatchEvent(new Event('resize'))
    renderPage()
    expect(screen.getByRole('list', { name: 'Fluxo técnico do ForensiHash' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Planejado' })).toBeInTheDocument()
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(width)
    cleanup()
  })

  it('mantém links locais e CTA existentes', () => {
    renderPage()
    expect(screen.getAllByRole('link', { name: /Explorar funcionalidades/ })[0]).toHaveAttribute('href', '#funcionalidades')
    expect(screen.getByRole('link', { name: /Área do Cliente/ })).toHaveAttribute('href', '/customer')
  })
})
