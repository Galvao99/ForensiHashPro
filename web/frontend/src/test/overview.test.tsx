import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { AnalysisSessionProvider, summarizeAnalysis } from '../context/AnalysisSessionContext'
import { DashboardPage } from '../pages/DashboardPage'
import { ResultPage } from '../pages/ResultPage'
import type { AnalysisContract } from '../types/api'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown, ok = true): Response {
  return { ok, json: async () => body } as Response
}

function contract(index: number, state = 'completed'): AnalysisContract {
  return {
    ...analysisFixture,
    analysis_id: `analysis-${index}`,
    state,
    file: { ...analysisFixture.file, name: `document-${index}.pdf` },
    hashes: { ...analysisFixture.hashes, sha256: `${index}23456789abcdef`.repeat(5).slice(0, 64) },
    findings: Array.from({ length: index % 3 }, (_, item) => ({ id: `finding-${item}` })),
    limitations: Array.from({ length: index % 2 }, (_, item) => ({ id: `limitation-${item}` })),
  }
}

function renderOverview(initialResults: AnalysisContract[] = []) {
  return render(<MemoryRouter initialEntries={['/app']}><AnalysisSessionProvider initialResults={initialResults}><Routes><Route path="/app" element={<DashboardPage />} /><Route path="/app/result/:analysisId" element={<ResultPage />} /></Routes></AnalysisSessionProvider></MemoryRouter>)
}

describe('overview da sessão', () => {
  it('mostra estado inicial e contadores zerados sem análises', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ hashes: { available: true } })))
    renderOverview()
    expect(screen.getByText('Nenhuma análise nesta sessão.')).toBeInTheDocument()
    const summary = screen.getByLabelText('Resumo operacional')
    expect(within(summary).getAllByText('0')).toHaveLength(4)
  })

  it('exibe somente as cinco análises mais recentes e contadores corretos', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({})))
    const results = [contract(1), contract(2, 'partial'), contract(3, 'failed'), contract(4), contract(5), contract(6)]
    renderOverview(results)
    expect(screen.getByText('document-1.pdf')).toBeInTheDocument()
    expect(screen.getByText('document-5.pdf')).toBeInTheDocument()
    expect(screen.queryByText('document-6.pdf')).not.toBeInTheDocument()
    const summary = screen.getByLabelText('Resumo operacional')
    expect(within(summary).getByText('6')).toBeInTheDocument()
    expect(within(summary).getByText('4')).toBeInTheDocument()
    expect(within(summary).getAllByText('1')).toHaveLength(2)
  })

  it('abre o resultado completo ao clicar em uma análise da sessão', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({})))
    renderOverview([contract(1)])
    await userEvent.click(screen.getByRole('link', { name: 'document-1.pdf' }))
    expect(screen.getByRole('heading', { name: 'document-1.pdf' })).toBeInTheDocument()
    expect(screen.getAllByText(/123456789abcdef/).length).toBeGreaterThan(0)
  })

  it('abrevia o SHA visualmente sem alterar o valor copiado', () => {
    const source = contract(1)
    const summary = summarizeAnalysis(source)
    expect(summary.sha256).toBe(source.hashes.sha256)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({})))
    renderOverview([source])
    const copy = screen.getByRole('button', { name: 'Copiar valor' })
    expect(copy.parentElement).toHaveTextContent(`${source.hashes.sha256.slice(0, 8)}...${source.hashes.sha256.slice(-4)}`)
    expect(source.hashes.sha256).toHaveLength(64)
  })

  it('mantém resultados visíveis quando capabilities estão indisponíveis e permite tentar novamente', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('offline'))
    vi.stubGlobal('fetch', fetchMock)
    renderOverview([contract(1)])
    expect(screen.getByText('document-1.pdf')).toBeInTheDocument()
    expect(await screen.findByText('Backend indisponível no momento.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(screen.getByText('document-1.pdf')).toBeInTheDocument()
  })

  it('mostra capabilities reais como conteúdo secundário', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ hashes: { available: true }, metadata: { available: false }, ocr: { available: true }, signature: { available: true }, rust_json: { available: false } })))
    renderOverview()
    expect(await screen.findByText('Hash')).toBeInTheDocument()
    expect(screen.getAllByText('Disponível')).toHaveLength(3)
    expect(screen.getAllByText('Indisponível')).toHaveLength(2)
  })

  it('adiciona uma análise real à sessão sem usar armazenamento persistente', async () => {
    vi.stubGlobal('fetch', vi.fn((input: string) => Promise.resolve(response(String(input).includes('/auth/me') ? authFixture : analysisFixture))))
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['synthetic'], 'synthetic.txt'))
    await userEvent.click(screen.getByRole('button', { name: 'Analisar' }))
    expect(await screen.findByRole('heading', { name: 'synthetic.txt' })).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('link', { name: 'Overview' }).find((link) => link.getAttribute('href') === '/app')!)
    expect(screen.getByText('synthetic.txt')).toBeInTheDocument()
    expect(localStorage.getItem('forensihash-theme')).toBe('SYSTEM')
    expect(sessionStorage.length).toBe(0)
  })
})
