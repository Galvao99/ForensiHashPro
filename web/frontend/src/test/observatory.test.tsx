import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { bubbleRadius } from '../observatory/BrazilResearchMap'
import { SourceList } from '../observatory/components'
import { cnjResolution233, researchRevisions, researchSnapshots, stateResearch } from '../observatory/data'
import { metricFor, validateStateResearch } from '../observatory/models'

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

describe('Observatório da Perícia Judicial — pesquisa V1', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 401, json: async () => ({}) } as Response))))

  it('é público, explicita pesquisa em andamento e oferece metodologia clicável', () => {
    renderAt('/observatorio')
    expect(screen.getByRole('heading', { level: 1, name: /o que já sabemos/i })).toBeInTheDocument()
    expect(screen.getAllByText(/pesquisa em andamento/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Pesquisa e Metodologia' })).toHaveAttribute('href', '/observatorio/metodologia')
    expect(screen.getByText(/não constituem censo oficial/i)).toBeInTheDocument()
    expect(screen.getByText(/podem aumentar ou diminuir/i)).toBeInTheDocument()
  })

  it('renderiza mapa geográfico local com paths das 27 UFs', () => {
    const { container } = renderAt('/observatorio')
    const map = screen.getByRole('group', { name: /mapa geográfico interativo do brasil/i })
    expect(within(map).getAllByRole('button')).toHaveLength(27)
    expect(container.querySelectorAll('.map-state path')).toHaveLength(27)
    expect(container.querySelectorAll('.map-state rect')).toHaveLength(0)
    expect(map).toHaveAttribute('viewBox', '0 0 600 600')
  })

  it('usa raiz quadrada no raio para tornar a área proporcional', () => {
    const small = bubbleRadius(100, 10_000)
    const large = bubbleRadius(400, 10_000)
    expect(large / small).toBeCloseTo(2)
    expect((large * large) / (small * small)).toBeCloseTo(4)
  })

  it('não cria bolha nem zero para métrica ausente', async () => {
    const { container } = renderAt('/observatorio')
    await userEvent.click(screen.getByRole('button', { name: 'Cadastro Geral' }))
    const acre = screen.getByRole('button', { name: /Acre, AC.*Sem quantitativo consolidado/i })
    expect(acre.querySelector('circle')).toBeNull()
    await userEvent.click(acre)
    expect(screen.getByRole('complementary')).toHaveTextContent('Sem quantitativo consolidado')
    expect(container.textContent).not.toContain('0 profissionais')
  })

  it('alterna Núcleo Digital e Cadastro Geral preservando a UF selecionada', async () => {
    renderAt('/observatorio')
    const amapa = screen.getByRole('button', { name: /Amapá, AP.*Núcleo Digital.*11/i })
    await userEvent.click(amapa)
    expect(screen.getByRole('complementary')).toHaveTextContent('Amapá')
    await userEvent.click(screen.getByRole('button', { name: 'Cadastro Geral' }))
    expect(screen.getByRole('button', { name: 'Cadastro Geral' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('complementary')).toHaveTextContent('352')
    expect(screen.getByRole('complementary')).toHaveTextContent('Amapá')
    await userEvent.click(screen.getByRole('button', { name: 'Núcleo Digital' }))
    expect(screen.getByRole('complementary')).toHaveTextContent('11')
  })

  it('mostra Outras especialidades como levantamento sem bolhas fictícias', async () => {
    const { container } = renderAt('/observatorio')
    await userEvent.click(screen.getByRole('button', { name: /Outras especialidades/i }))
    expect(screen.getByRole('heading', { name: /Outras especialidades — em levantamento/i })).toBeInTheDocument()
    expect(container.querySelectorAll('.map-bubble')).toHaveLength(0)
    expect(screen.getByRole('complementary')).toHaveTextContent('Em levantamento')
  })

  it('oferece hover, tooltip e seleção persistente sem navegação automática', async () => {
    renderAt('/observatorio')
    const amapa = screen.getByRole('button', { name: /Amapá, AP/i })
    fireEvent.mouseEnter(amapa)
    expect(screen.getByRole('tooltip')).toHaveTextContent('AP · Núcleo Digital')
    expect(screen.getByRole('tooltip')).toHaveTextContent('11')
    await userEvent.click(amapa)
    fireEvent.mouseLeave(amapa)
    expect(screen.getByRole('complementary')).toHaveTextContent('Amapá')
    expect(window.location.pathname).toBe('/observatorio')
  })

  it('seleciona UF por teclado e expõe CTA para a ficha metodológica', async () => {
    renderAt('/observatorio')
    const amapa = screen.getByRole('button', { name: /Amapá, AP/i })
    amapa.focus()
    await userEvent.keyboard('{Enter}')
    expect(within(screen.getByRole('complementary')).getByRole('link', { name: /ver metodologia deste estado/i })).toHaveAttribute('href', '/observatorio/estado/ap')
  })

  it('preserva os quantitativos publicados e seus tipos de contagem', () => {
    const byUf = Object.fromEntries(stateResearch.map(state => [state.uf, state]))
    expect(metricFor(byUf.RJ, 'SOURCE_RECORDS')).toMatchObject({ value: 12165, countType: 'ADMINISTRATIVE_COUNT', unit: 'SOURCE_RECORDS' })
    expect(metricFor(byUf.RJ, 'GENERAL')).toMatchObject({ value: 10804, countType: 'OBSERVED_COUNT', unit: 'UNIQUE_PROFESSIONALS' })
    expect(metricFor(byUf.RJ, 'DIGITAL')?.value).toBe(187)
    expect(metricFor(byUf.SE, 'SOURCE_RECORDS')?.value).toBe(1999)
    expect(metricFor(byUf.SE, 'DIGITAL')?.value).toBe(45)
    expect(metricFor(byUf.PI, 'RESEARCHED_SUBSET')).toMatchObject({ value: 374, countType: 'SUBSET_COUNT' })
    expect(metricFor(byUf.PI, 'DIGITAL')?.value).toBe(51)
    expect(metricFor(byUf.AP, 'GENERAL')?.value).toBe(352)
    expect(metricFor(byUf.AP, 'DIGITAL')?.value).toBe(11)
    expect(metricFor(byUf.PA, 'SOURCE_RECORDS')?.value).toBe(918)
    expect(metricFor(byUf.PA, 'GENERAL')?.value).toBe(577)
    expect(metricFor(byUf.PA, 'DIGITAL')?.value).toBe(10)
    expect(metricFor(byUf.TO, 'SOURCE_RECORDS')?.value).toBe(5272)
    expect(metricFor(byUf.TO, 'DIGITAL')).toMatchObject({ value: 116, countType: 'SUBSET_COUNT', unit: 'CLASSIFIED_RECORDS' })
    expect(metricFor(byUf.RR, 'DIGITAL')?.value).toBe(13)
    expect(metricFor(byUf.PR, 'CREDENTIAL_SPECIALTIES')).toMatchObject({ value: 35373, countType: 'ADMINISTRATIVE_COUNT', unit: 'CREDENTIALS_AND_SPECIALTIES' })
    expect(metricFor(byUf.PR, 'GENERAL')).toBeUndefined()
  })

  it('não apresenta pesquisa parcial como consolidada', () => {
    renderAt('/observatorio/estado/pi')
    expect(screen.getAllByText('Parcial').length).toBeGreaterThan(0)
    expect(screen.queryByText('Consolidado')).not.toBeInTheDocument()
    expect(screen.getAllByText(/não representa a base integral/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/contagem de recorte/i).length).toBeGreaterThan(0)
  })

  it('não apresenta credenciais administrativas como pessoas únicas', () => {
    renderAt('/observatorio/estado/pr')
    expect(screen.getByText('35.373')).toBeInTheDocument()
    expect(screen.getAllByText(/não equivale a pessoas únicas/i).length).toBeGreaterThan(0)
    expect(screen.getByText('Dado administrativo')).toBeInTheDocument()
    expect(screen.queryByText('Cadastro Geral')).not.toBeInTheDocument()
  })

  it('publica fonte oficial clicável com instituição, data e tipo', () => {
    render(<MemoryRouter><SourceList sources={[cnjResolution233]} /></MemoryRouter>)
    expect(screen.getByText(cnjResolution233.title)).toBeInTheDocument()
    expect(screen.getByText(/Conselho Nacional de Justiça · CNJ_ACT · acesso em 05\/09\/2026/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /consultar fonte original/i })).toHaveAttribute('href', cnjResolution233.url)
  })

  it('publica página completa de metodologia, glossário e dificuldades observadas', () => {
    renderAt('/observatorio/metodologia')
    expect(screen.getByRole('heading', { level: 1, name: /como sabemos/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Glossário metodológico' })).toBeInTheDocument()
    expect(screen.getByText('Profissional único identificado')).toBeInTheDocument()
    expect(screen.getByText(/categoria metodológica da pesquisa Arqen/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /como os dados puderam ser consolidados/i })).toBeInTheDocument()
    expect(screen.getByText(/não classifica tribunais como melhores ou piores/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Contexto institucional e normativo' })).toBeInTheDocument()
  })

  it('mantém snapshots estruturados sem inventar revisões', () => {
    expect(researchSnapshots.length).toBeGreaterThan(0)
    expect(researchSnapshots.every(snapshot => snapshot.version === 'v1.1')).toBe(true)
    expect(researchRevisions).toEqual([])
    renderAt('/observatorio/estado/rj')
    expect(screen.getByRole('heading', { name: 'Histórico da pesquisa' })).toBeInTheDocument()
    expect(screen.getByText(/Nenhuma revisão histórica documentada/i)).toBeInTheDocument()
  })

  it('valida fonte e snapshot obrigatórios para todo quantitativo', () => {
    const rj = stateResearch.find(state => state.uf === 'RJ')!
    expect(() => validateStateResearch(rj)).not.toThrow()
    expect(() => validateStateResearch({ ...rj, uf: 'XX' })).toThrow(/Invalid UF/)
    expect(() => validateStateResearch({ ...rj, sources: [] })).toThrow(/Metric source is missing/)
    expect(() => validateStateResearch({ ...rj, snapshots: [] })).toThrow(/Metric snapshot is missing/)
  })

  it('não cria ranking nacional na página', () => {
    const { container } = renderAt('/observatorio')
    expect(container.querySelector('.observatory-rankings')).toBeNull()
    expect(screen.queryByRole('heading', { name: /ranking/i })).not.toBeInTheDocument()
  })

  it.each([320, 375, 390, 430, 768, 1024, 1440, 1920])('mantém mapa e fallback textual em %ipx', width => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
    window.dispatchEvent(new Event('resize'))
    renderAt('/observatorio')
    expect(screen.getByRole('group', { name: /mapa geográfico interativo/i })).toBeInTheDocument()
    expect(screen.getByText(/navegação textual completa/i)).toBeInTheDocument()
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(width)
    cleanup()
  })
})
