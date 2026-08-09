import { ReactNode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import {
  ANALYSIS_CONCURRENCY,
  AnalysisSessionProvider,
  safeRelativePath,
  useAnalysisSession,
} from '../context/AnalysisSessionContext'
import type { AnalysisContract } from '../types/api'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

function contractFor(file: File, index: number, state = 'completed'): AnalysisContract {
  return {
    ...analysisFixture,
    analysis_id: `analysis-${index}-${file.name}`,
    state,
    file: { name: file.name, size_bytes: file.size },
    hashes: { sha256: `hash-${file.name}` },
    metadata: { source: file.name },
  }
}

function folderFile(name: string, relativePath: string): File {
  const file = new File([name], name, { type: 'text/plain' })
  Object.defineProperty(file, 'webkitRelativePath', { value: relativePath })
  return file
}

function Harness({ files, children }: { files: File[]; children?: ReactNode }) {
  const { workspace, analyses, persistedAnalyses, enqueueFiles, closeAnalysis } = useAnalysisSession()
  return <div>
    <button type="button" onClick={() => enqueueFiles(files, { privateSession: true })}>Enfileirar privado</button>
    <button type="button" onClick={() => enqueueFiles(files, { privateSession: false, retentionMode: 'RESULT_ONLY' })}>Enfileirar persistido</button>
    <output data-testid="workspace-count">{workspace.analyses.length}</output>
    <output data-testid="catalog-count">{analyses.length}</output>
    <output data-testid="persisted-count">{persistedAnalyses.length}</output>
    {workspace.analyses.map((item) => <div key={item.analysisId}><span>{item.filename}:{item.status}</span><button type="button" onClick={() => closeAnalysis(item.analysisId)}>Fechar {item.filename}</button></div>)}
    {children}
  </div>
}

describe('workspace de análises individuais', () => {
  it('normaliza somente webkitRelativePath e rejeita traversal', () => {
    expect(safeRelativePath(folderFile('a.txt', 'Caso\\docs\\a.txt'))).toBe('Caso/docs/a.txt')
    expect(safeRelativePath(folderFile('a.txt', 'Caso/../a.txt'))).toBeNull()
    expect(safeRelativePath(new File(['a'], 'a.txt'))).toBeUndefined()
  })

  it('seleciona pasta, cria requests independentes e nunca mistura contratos entre abas', async () => {
    let index = 0
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      if (String(input).includes('/auth/me')) return Promise.resolve(response(authFixture))
      const file = (init?.body as FormData).get('file') as File
      index += 1
      return Promise.resolve(response(contractFor(file, index)))
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/app/analysis')
    render(<App />)
    const files = [
      folderFile('contrato.pdf', 'Caso João/documentos/contrato.pdf'),
      folderFile('selfie.jpg', 'Caso João/imagens/selfie.jpg'),
      folderFile('biometria.json', 'Caso João/logs/biometria.json'),
    ]

    await userEvent.upload(await screen.findByLabelText('Selecionar pasta'), files)

    const tablist = await screen.findByRole('tablist', { name: 'Análises abertas' })
    await waitFor(() => expect(within(tablist).getAllByRole('tab')).toHaveLength(3))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/api/v1/analyses'))).toHaveLength(3))
    const analysisCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/api/v1/analyses'))
    for (const [, init] of analysisCalls) {
      const body = init?.body as FormData
      expect(body.get('file')).toBeInstanceOf(File)
      expect([...body.keys()]).not.toContain('relative_path')
      expect([...body.keys()]).not.toContain('workspace')
    }
    expect(screen.getByText('Workspace: Caso João')).toBeInTheDocument()

    await userEvent.click(within(tablist).getByRole('tab', { name: /selfie\.jpg/i }))
    expect(await screen.findByRole('heading', { name: 'selfie.jpg' })).toBeInTheDocument()
    expect(screen.getAllByText('hash-selfie.jpg').length).toBeGreaterThan(0)
    expect(screen.queryByText('hash-contrato.pdf')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Fechar análise de selfie.jpg' }))
    expect(await screen.findByRole('heading', { name: 'biometria.json' })).toBeInTheDocument()
    expect(within(tablist).getAllByRole('tab')).toHaveLength(2)
    expect(within(tablist).getByRole('tab', { name: /biometria\.json/i })).toHaveAttribute('aria-selected', 'true')
  })

  it('limita concorrência a dois e inicia o próximo quando uma análise termina', async () => {
    const pending: Array<{ file: File; resolve: (value: Response) => void }> = []
    let active = 0
    let maximum = 0
    vi.stubGlobal('fetch', vi.fn((_input: string | URL | Request, init?: RequestInit) => {
      const file = (init?.body as FormData).get('file') as File
      active += 1
      maximum = Math.max(maximum, active)
      return new Promise<Response>((resolve) => pending.push({ file, resolve: (value) => { active -= 1; resolve(value) } }))
    }))
    const files = [new File(['1'], 'one.txt'), new File(['2'], 'two.txt'), new File(['3'], 'three.txt')]
    render(<AnalysisSessionProvider><Harness files={files} /></AnalysisSessionProvider>)

    await userEvent.click(screen.getByRole('button', { name: 'Enfileirar privado' }))
    await waitFor(() => expect(pending).toHaveLength(ANALYSIS_CONCURRENCY))
    expect(screen.getByText('three.txt:QUEUED')).toBeInTheDocument()

    pending[0].resolve(response(contractFor(pending[0].file, 1)))
    await waitFor(() => expect(pending).toHaveLength(3))
    expect(maximum).toBe(ANALYSIS_CONCURRENCY)
    pending[1].resolve(response(contractFor(pending[1].file, 2)))
    pending[2].resolve(response(contractFor(pending[2].file, 3)))
    await waitFor(() => expect(screen.getAllByText(/:SUCCESS$/)).toHaveLength(3))
  })

  it('falha individual não interrompe a fila restante', async () => {
    let call = 0
    vi.stubGlobal('fetch', vi.fn((_input: string | URL | Request, init?: RequestInit) => {
      call += 1
      const file = (init?.body as FormData).get('file') as File
      return Promise.resolve(call === 1
        ? response({ error: { code: 'analysis_failed', message: 'Falha técnica segura.' } }, 422)
        : response(contractFor(file, call)))
    }))
    const files = [new File(['1'], 'failed.txt'), new File(['2'], 'ok-1.txt'), new File(['3'], 'ok-2.txt')]
    render(<AnalysisSessionProvider><Harness files={files} /></AnalysisSessionProvider>)

    await userEvent.click(screen.getByRole('button', { name: 'Enfileirar privado' }))

    expect(await screen.findByText('failed.txt:FAILED')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('ok-1.txt:SUCCESS')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('ok-2.txt:SUCCESS')).toBeInTheDocument())
  })

  it('fechar PRIVATE remove da sessão e um novo provider não recupera o resultado', async () => {
    const file = new File(['private'], 'private.txt')
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response(contractFor(file, 1)))))
    const rendered = render(<AnalysisSessionProvider><Harness files={[file]} /></AnalysisSessionProvider>)
    await userEvent.click(screen.getByRole('button', { name: 'Enfileirar privado' }))
    await screen.findByText('private.txt:SUCCESS')
    expect(screen.getByTestId('catalog-count')).toHaveTextContent('1')

    await userEvent.click(screen.getByRole('button', { name: 'Fechar private.txt' }))
    expect(screen.getByTestId('workspace-count')).toHaveTextContent('0')
    expect(screen.getByTestId('catalog-count')).toHaveTextContent('0')

    rendered.unmount()
    render(<AnalysisSessionProvider><Harness files={[]} /></AnalysisSessionProvider>)
    expect(screen.getByTestId('workspace-count')).toHaveTextContent('0')
    expect(screen.getByTestId('catalog-count')).toHaveTextContent('0')
  })

  it('fechar RESULT_ONLY remove apenas a aba e preserva o catálogo histórico', async () => {
    const file = new File(['retained'], 'retained.txt')
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response(contractFor(file, 1)))))
    render(<AnalysisSessionProvider><Harness files={[file]} /></AnalysisSessionProvider>)
    await userEvent.click(screen.getByRole('button', { name: 'Enfileirar persistido' }))
    await screen.findByText('retained.txt:SUCCESS')

    await userEvent.click(screen.getByRole('button', { name: 'Fechar retained.txt' }))

    expect(screen.getByTestId('workspace-count')).toHaveTextContent('0')
    expect(screen.getByTestId('catalog-count')).toHaveTextContent('1')
    expect(screen.getByTestId('persisted-count')).toHaveTextContent('1')
  })
})
