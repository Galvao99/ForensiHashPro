import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { SourceList } from '../observatory/components'
import { cnjResolution233, stateResearch } from '../observatory/data'
import { comparableRanking, professionalsPer100k, validateStateResearch, type StateResearch } from '../observatory/models'

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

const completed: StateResearch = {
  uf: 'RJ', stateName: 'Rio de Janeiro', status: 'COMPLETED', sourceRecordsCount: 12165,
  uniqueProfessionalsCount: 10804, specialtiesCount: 1957, methodologyVersion: 'v1.0',
  coverage: 'INTEGRAL_DEDUPLICATED',
  population: { value: 17_000_000, referenceYear: 2025, source: cnjResolution233 },
  limitations: [], sources: [cnjResolution233],
}

describe('Observatório da Perícia Judicial', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 401, json: async () => ({}) } as Response))))

  it('é público, renderiza sem autenticação e está na navbar', () => {
    renderAt('/observatorio')
    expect(screen.getByRole('heading', { level: 1, name: /dados, normas e transformações/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Observatório' })[0]).toHaveAttribute('href', '/observatorio')
    expect(screen.getByText('Pesquisa Nacional 2026')).toBeInTheDocument()
    expect(screen.getByText('Pesquisa em andamento')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/observatorio')
  })

  it('não apresenta desconhecido ou NOT_STARTED como zero', () => {
    const { container } = renderAt('/observatorio')
    expect(screen.getAllByText('Não iniciado').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Em levantamento').length).toBeGreaterThan(0)
    expect(container.textContent).not.toContain('0 profissionais')
    expect(container.textContent).not.toContain('27 estados analisados')
  })

  it('carrega detalhe por UF com status, métricas distintas e limitações', () => {
    renderAt('/observatorio/estado/rj')
    expect(screen.getByRole('heading', { level: 1, name: 'Rio de Janeiro' })).toBeInTheDocument()
    expect(screen.getByText('Registros encontrados')).toBeInTheDocument()
    expect(screen.getByText('Profissionais únicos identificados')).toBeInTheDocument()
    expect(screen.getByText(/A presença no cadastro não implica atuação efetiva/i)).toBeInTheDocument()
    expect(screen.getAllByText('Dados em consolidação').length).toBeGreaterThan(0)
  })

  it('expõe título, organização e URL original da fonte', () => {
    render(<MemoryRouter><SourceList sources={[cnjResolution233]} /></MemoryRouter>)
    expect(screen.getByText(cnjResolution233.title)).toBeInTheDocument()
    expect(screen.getByText(/Conselho Nacional de Justiça/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /consultar fonte original/i })).toHaveAttribute('href', cnjResolution233.url)
  })

  it('radar associa conteúdo factual à fonte primária', () => {
    renderAt('/observatorio')
    const radar = screen.getByRole('heading', { name: 'Radar Regulatório' }).closest('section')!
    expect(within(radar).getByText(/Resolução CNJ nº 233 estrutura/)).toBeInTheDocument()
    expect(within(radar).getByRole('link', { name: /consultar fonte original/i })).toHaveAttribute('href', cnjResolution233.url)
    expect(within(radar).getByText(/não constitui aconselhamento jurídico/i)).toBeInTheDocument()
  })

  it('calcula per capita somente com numerador e população conhecidos', () => {
    expect(professionalsPer100k(completed)).toBeCloseTo(63.5529, 4)
    expect(professionalsPer100k({ ...completed, uniqueProfessionalsCount: undefined })).toBeUndefined()
    expect(professionalsPer100k({ ...completed, population: undefined })).toBeUndefined()
  })

  it('ranking exclui estados incompletos mesmo quando possuem números', () => {
    const partial = { ...completed, uf: 'SP', stateName: 'São Paulo', status: 'PARTIAL' as const, uniqueProfessionalsCount: 99999 }
    const ranking = comparableRanking([partial, completed], state => state.uniqueProfessionalsCount)
    expect(ranking.map(item => item.state.uf)).toEqual(['RJ'])
  })

  it('valida UF, contagens e denominador sem converter inválidos em zero', () => {
    expect(() => validateStateResearch(completed)).not.toThrow()
    expect(() => validateStateResearch({ ...completed, uf: 'XX' })).toThrow(/Invalid UF/)
    expect(() => validateStateResearch({ ...completed, uniqueProfessionalsCount: -1 })).toThrow(/uniqueProfessionalsCount/)
  })

  it('publica metodologia e limitação central', () => {
    renderAt('/observatorio/metodologia')
    expect(screen.getByRole('heading', { level: 1, name: /como a pesquisa é estruturada/i })).toBeInTheDocument()
    expect(screen.getByText(/não implica necessariamente atuação efetiva/i)).toBeInTheDocument()
    expect(screen.getByText(/não é uma pontuação automática de verdade/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /voltar ao observatório/i })).toHaveAttribute('href', '/observatorio')
  })

  it('renderiza mapa local com as 27 UFs e foco digital por padrão', () => {
    const { container } = renderAt('/observatorio')
    const map = screen.getByRole('group', { name: /mapa esquemático interativo do brasil/i })
    expect(within(map).getAllByRole('button')).toHaveLength(27)
    expect(container.querySelectorAll('.map-state')).toHaveLength(27)
    expect(screen.getByRole('button', { name: 'Núcleo digital/TI' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/lista abaixo é uma alternativa integral ao mapa/i)).toBeInTheDocument()
  })

  it('importa valores observados sem colapsar registros, pessoas, recortes e credenciais', () => {
    const byUf = Object.fromEntries(stateResearch.map(state => [state.uf, state]))
    expect(byUf.RJ).toMatchObject({ sourceRecordsCount: 12165, uniqueProfessionalsCount: 10804, digitalCoreCount: 187, status: 'COMPLETED' })
    expect(byUf.SE).toMatchObject({ sourceRecordsCount: 1999, digitalCoreCount: 45 })
    expect(byUf.PI).toMatchObject({ researchedSubsetUniqueCount: 374, digitalCoreCount: 51, coverage: 'TERM_BASED_SUBSET' })
    expect(byUf.AP.digitalCoreCount).toBe(11)
    expect(byUf.PA).toMatchObject({ sourceRecordsCount: 918, uniqueProfessionalsCount: 577, digitalCoreCount: 10 })
    expect(byUf.TO).toMatchObject({ sourceRecordsCount: 5272, digitalCoreCount: 116, status: 'PARTIAL' })
    expect(byUf.RR).toMatchObject({ researchedSubsetUniqueCount: 13, digitalCoreCount: 13, status: 'PARTIAL' })
    expect(byUf.PR).toMatchObject({ credentialSpecialtyCount: 35373, coverage: 'CREDENTIALS_ONLY' })
    expect(byUf.PR.uniqueProfessionalsCount).toBeUndefined()
  })

  it('troca para cadastro geral sem converter ausência em zero', async () => {
    renderAt('/observatorio')
    await userEvent.click(screen.getByRole('button', { name: 'Cadastro geral' }))
    expect(screen.getByRole('button', { name: 'Cadastro geral' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByText('10.804').length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: /Acre, AC\. Sem quantitativo consolidado/i }))
    expect(screen.getByRole('complementary')).toHaveTextContent('Sem quantitativo consolidado')
    expect(screen.getByRole('complementary')).not.toHaveTextContent(/^0$/)
  })

  it('seleciona estado por teclado e oferece navegação essencial sem hover', async () => {
    renderAt('/observatorio')
    const amapa = screen.getByRole('button', { name: /Amapá, AP\. 11 profissionais do núcleo digital/i })
    amapa.focus()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('complementary')).toHaveTextContent('Amapá')
    expect(within(screen.getByRole('complementary')).getByRole('link', { name: /ver detalhes/i })).toHaveAttribute('href', '/observatorio/estado/ap')
  })

  it('detalhes preservam qualificadores parciais e retorno explícito', () => {
    renderAt('/observatorio/estado/pi')
    expect(screen.getByText('51')).toBeInTheDocument()
    expect(screen.getByText('374')).toBeInTheDocument()
    expect(screen.getByText(/profissionais únicos no recorte pesquisado/i)).toBeInTheDocument()
    expect(screen.getByText(/não representa o cadastro integral/i)).toBeInTheDocument()
    expect(screen.queryByText(/total de peritos do estado/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /voltar ao observatório/i })).toHaveAttribute('href', '/observatorio')
  })

  it('ranking geral exclui credenciais, linhas e subconjuntos', () => {
    renderAt('/observatorio')
    const ranking = screen.getByRole('heading', { name: /bases integrais comparáveis/i }).closest('section')!
    expect(ranking).toHaveTextContent('RJ')
    expect(ranking).toHaveTextContent('PA')
    expect(ranking).toHaveTextContent('AP')
    expect(ranking).not.toHaveTextContent('PR')
    expect(ranking).not.toHaveTextContent('35.373')
  })

  it('usa layout responsivo sem URLs presas a largura fixa', () => {
    render(<MemoryRouter><SourceList sources={[cnjResolution233]} /></MemoryRouter>)
    const link = screen.getByRole('link', { name: /consultar fonte original/i })
    expect(link.closest('li')).toBeInTheDocument()
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it.each([320, 375, 390, 430, 768, 1024, 1440])('mantém mapa e fallback navegável em %ipx', width => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
    window.dispatchEvent(new Event('resize'))
    renderAt('/observatorio')
    expect(screen.getByRole('group', { name: /mapa esquemático interativo/i })).toHaveAttribute('viewBox', '0 0 600 600')
    expect(screen.getByText(/lista abaixo é uma alternativa integral ao mapa/i)).toBeInTheDocument()
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(width)
    cleanup()
  })
})
