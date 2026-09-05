import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { SourceList } from '../observatory/components'
import { cnjResolution233 } from '../observatory/data'
import { comparableRanking, professionalsPer100k, validateStateResearch, type StateResearch } from '../observatory/models'

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

const completed: StateResearch = {
  uf: 'RJ', stateName: 'Rio de Janeiro', status: 'COMPLETED', sourceRecordsCount: 12165,
  uniqueProfessionalsCount: 10804, specialtiesCount: 1957, methodologyVersion: 'v1.0',
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
    expect(screen.getAllByText('Não iniciado')).toHaveLength(27)
    expect(screen.getAllByText('Em levantamento').length).toBeGreaterThan(0)
    expect(container.textContent).not.toContain('0 profissionais')
    expect(container.textContent).not.toContain('27 estados analisados')
  })

  it('carrega detalhe por UF com status, métricas distintas e limitações', () => {
    renderAt('/observatorio/estado/rj')
    expect(screen.getByRole('heading', { level: 1, name: 'Rio de Janeiro' })).toBeInTheDocument()
    expect(screen.getByText('Registros encontrados')).toBeInTheDocument()
    expect(screen.getByText('Profissionais únicos identificados')).toBeInTheDocument()
    expect(screen.getByText('Dados estaduais ainda não coletados ou consolidados.')).toBeInTheDocument()
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
  })

  it('usa layout responsivo sem URLs presas a largura fixa', () => {
    render(<MemoryRouter><SourceList sources={[cnjResolution233]} /></MemoryRouter>)
    const link = screen.getByRole('link', { name: /consultar fonte original/i })
    expect(link.closest('li')).toBeInTheDocument()
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })
})
