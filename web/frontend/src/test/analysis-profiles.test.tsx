import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AnalysisSessionProvider } from '../context/AnalysisSessionContext'
import { AnalysisPage } from '../pages/AnalysisPage'
import { ResultView } from '../pages/ResultPage'
import { AuthProvider } from '../context/AuthContext'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response
}

describe('perfis Free e Pro', () => {
  it('resultado Free omite áreas avançadas vazias e apresenta CTA sem inventar achados', () => {
    const result = structuredClone(analysisFixture)
    result.execution.analysis_profile = 'free'
    result.native_text = null
    result.ocr = null
    result.timeline = null
    result.biometrics = null
    render(<MemoryRouter><ResultView result={result} /></MemoryRouter>)

    expect(screen.getByText('FORENSIHASH FREE')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Continue a investigação com o ForensiHash Pro' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Texto / OCR' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Entidades e endereços IP' })).not.toBeInTheDocument()
    expect(screen.queryByText(/detectamos|encontramos \d+ CPF/i)).not.toBeInTheDocument()
  })

  it('seleção múltipla Free não cria jobs e permite escolher um arquivo', async () => {
    const freeAuth = structuredClone(authFixture)
    freeAuth.user.analysis_profile = 'FREE'
    const fetchMock = vi.fn((input: string | URL | Request) => {
      if (String(input).includes('/auth/me')) return Promise.resolve(response(freeAuth))
      return Promise.reject(new Error(`request inesperado: ${String(input)}`))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter><AuthProvider><AnalysisSessionProvider analysisProfile="FREE"><AnalysisPage /></AnalysisSessionProvider></AuthProvider></MemoryRouter>)
    await screen.findByText('FORENSIHASH FREE')

    await userEvent.upload(screen.getByLabelText('Selecionar pasta'), [
      new File(['a'], 'a.pdf'),
      new File(['b'], 'b.pdf'),
    ])

    expect(screen.getByText('Análise de conjuntos de evidências está disponível no ForensiHash Pro.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Analisar este arquivo' })).toHaveLength(2)
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/analysis-jobs'))).toBe(false)
  })

  it('confirma o escopo e baixa um único ZIP de Snapshot', async () => {
    const fetchMock = vi.fn((...request: [string | URL | Request, RequestInit?]) => {
      void request
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: { get: () => 'attachment; filename="forensihash_ddna_snapshot_analysis-test.zip"' },
        blob: async () => new Blob(['zip'], { type: 'application/zip' }),
      } as unknown as Response)
    })
    vi.stubGlobal('fetch', fetchMock)
    const createObjectURL = vi.fn(() => 'blob:snapshot')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    render(<MemoryRouter><ResultView result={analysisFixture} csrfToken="csrf-test" /></MemoryRouter>)

    await userEvent.click(screen.getByRole('button', { name: 'Gerar DDNA Snapshot' }))
    expect(screen.getByText('relatório técnico em PDF')).toBeInTheDocument()
    expect(screen.getByText('arquivo SHA-256 do PDF')).toBeInTheDocument()
    expect(screen.getByText(/não representa cadeia de custódia original/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Gerar Snapshot' }))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/v1/analyses/analysis-test/ddna-snapshot')
    expect(click).toHaveBeenCalledTimes(1)
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:snapshot')
  })
})
