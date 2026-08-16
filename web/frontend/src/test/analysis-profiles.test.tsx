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
})
