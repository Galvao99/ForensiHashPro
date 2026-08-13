import { ReactNode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import {
  MAX_ACTIVE_ANALYSES,
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

function completedJobFetch() {
  let index = 0
  const results = new Map<string, AnalysisContract>()
  return vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/auth/me')) return Promise.resolve(response(authFixture))
    if (url.endsWith('/analysis-jobs')) {
      const file = (init?.body as FormData).get('file') as File
      const jobId = `job-${++index}`
      results.set(jobId, contractFor(file, index))
      return Promise.resolve(response({ job_id: jobId, status: 'QUEUED' }))
    }
    const jobId = url.split('/analysis-jobs/')[1].split('/')[0]
    if (url.endsWith('/result')) return Promise.resolve(response(results.get(jobId)))
    return Promise.resolve(response({ job_id: jobId, status: 'SUCCESS', analysis_id: results.get(jobId)?.analysis_id }))
  })
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
    const fetchMock = completedJobFetch()
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
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/api/v1/analysis-jobs'))).toHaveLength(3))
    const analysisCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/api/v1/analysis-jobs'))
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

  it('mostra todos os arquivos da pasta imediatamente, mas mantém somente um job remoto ativo', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/me')) return Promise.resolve(response(authFixture))
      if (url.endsWith('/analysis-jobs')) {
        const file = (init?.body as FormData).get('file') as File
        return Promise.resolve(response({ job_id: `job-${file.name}`, status: 'QUEUED' }))
      }
      return Promise.resolve(response({ job_id: 'job-contrato.pdf', status: 'PROCESSING', current_stage: 'ANALYZING' }))
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.pushState({}, '', '/app/analysis')
    const rendered = render(<App />)
    const files = [
      folderFile('contrato.pdf', 'Caso/contrato.pdf'),
      folderFile('selfie.jpg', 'Caso/selfie.jpg'),
      folderFile('logs.json', 'Caso/logs.json'),
    ]

    await userEvent.upload(await screen.findByLabelText('Selecionar pasta'), files)

    expect(await screen.findByRole('heading', { name: 'Processamento do workspace' })).toBeInTheDocument()
    expect(screen.getByText('3 artefatos · fila local controlada')).toBeInTheDocument()
    expect(screen.getByText('1 analisando')).toBeInTheDocument()
    expect(screen.getByText('2 na fila')).toBeInTheDocument()
    expect(screen.getAllByText('aguardando')).toHaveLength(2)
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/api/v1/analysis-jobs'))).toHaveLength(1)
    rendered.unmount()
  })

  it('mantém um único job remoto ativo e inicia o próximo somente após terminal', async () => {
    const pending: Array<{ file: File; resolve: (value: Response) => void }> = []
    let active = 0
    let maximum = 0
    const results = new Map<string, AnalysisContract>()
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (!url.endsWith('/analysis-jobs')) {
        const jobId = url.split('/analysis-jobs/')[1].split('/')[0]
        if (url.endsWith('/result')) return Promise.resolve(response(results.get(jobId)))
        return Promise.resolve(response({ job_id: jobId, status: 'SUCCESS', analysis_id: results.get(jobId)?.analysis_id }))
      }
      const file = (init?.body as FormData).get('file') as File
      active += 1
      maximum = Math.max(maximum, active)
      return new Promise<Response>((resolve) => pending.push({ file, resolve: (value) => { active -= 1; resolve(value) } }))
    }))
    const files = [new File(['1'], 'one.txt'), new File(['2'], 'two.txt'), new File(['3'], 'three.txt')]
    render(<AnalysisSessionProvider><Harness files={files} /></AnalysisSessionProvider>)

    await userEvent.click(screen.getByRole('button', { name: 'Enfileirar privado' }))
    await waitFor(() => expect(pending).toHaveLength(MAX_ACTIVE_ANALYSES))
    expect(screen.getByText('two.txt:WAITING')).toBeInTheDocument()
    expect(screen.getByText('three.txt:WAITING')).toBeInTheDocument()

    results.set('job-1', contractFor(pending[0].file, 1)); pending[0].resolve(response({ job_id: 'job-1', status: 'QUEUED' }))
    await waitFor(() => expect(pending).toHaveLength(2))
    expect(maximum).toBe(MAX_ACTIVE_ANALYSES)
    results.set('job-2', contractFor(pending[1].file, 2)); pending[1].resolve(response({ job_id: 'job-2', status: 'QUEUED' }))
    await waitFor(() => expect(pending).toHaveLength(3))
    results.set('job-3', contractFor(pending[2].file, 3)); pending[2].resolve(response({ job_id: 'job-3', status: 'QUEUED' }))
    await waitFor(() => expect(screen.getAllByText(/:SUCCESS$/)).toHaveLength(3))
  })

  it('falha individual não interrompe a fila restante', async () => {
    let creation = 0
    const results = new Map<string, AnalysisContract>()
    vi.stubGlobal('fetch', vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/analysis-jobs')) {
        creation += 1
        if (creation === 1) return Promise.resolve(response({ error: { code: 'analysis_failed', message: 'Falha técnica segura.' } }, 422))
        const file = (init?.body as FormData).get('file') as File
        const jobId = `job-${creation}`; results.set(jobId, contractFor(file, creation))
        return Promise.resolve(response({ job_id: jobId, status: 'QUEUED' }))
      }
      const jobId = url.split('/analysis-jobs/')[1].split('/')[0]
      if (url.endsWith('/result')) return Promise.resolve(response(results.get(jobId)))
      return Promise.resolve(response({ job_id: jobId, status: 'SUCCESS', analysis_id: results.get(jobId)?.analysis_id }))
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
    vi.stubGlobal('fetch', completedJobFetch())
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
    vi.stubGlobal('fetch', completedJobFetch())
    render(<AnalysisSessionProvider><Harness files={[file]} /></AnalysisSessionProvider>)
    await userEvent.click(screen.getByRole('button', { name: 'Enfileirar persistido' }))
    await screen.findByText('retained.txt:SUCCESS')

    await userEvent.click(screen.getByRole('button', { name: 'Fechar retained.txt' }))

    expect(screen.getByTestId('workspace-count')).toHaveTextContent('0')
    expect(screen.getByTestId('catalog-count')).toHaveTextContent('1')
    expect(screen.getByTestId('persisted-count')).toHaveTextContent('1')
  })
})
