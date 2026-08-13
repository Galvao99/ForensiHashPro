import { ReactNode, StrictMode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AnalysisSessionProvider, PROCESSING_POLL_INTERVAL_MS, QUEUED_POLL_INTERVAL_MS, pollIntervalForStatus, useAnalysisSession } from '../context/AnalysisSessionContext'
import type { AnalysisContract, AnalysisSetResult } from '../types/api'
import { analysisFixture } from './fixtures'

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

function result(filename: string, id: string): AnalysisContract {
  return { ...analysisFixture, analysis_id: id, file: { ...analysisFixture.file, name: filename } }
}

function setResult(jobIds: string[]): AnalysisSetResult {
  return {
    set_id: `set-${jobIds.join('-')}`, state: 'completed', created_at: '2026-08-13T12:00:00Z',
    finished_at: '2026-08-13T12:00:01Z', artifacts: [],
    correlation_result: { summary: {}, findings: [] }, limitations: [],
  }
}

function Harness({ files, duplicateConsumer = false }: { files: File[]; duplicateConsumer?: boolean }) {
  const session = useAnalysisSession()
  return <>
    <button type="button" onClick={() => session.enqueueFiles(files, { privateSession: true })}>Enviar</button>
    {session.workspace.analyses.map((item) => <div data-testid="upload" key={item.clientUploadId}>
      {item.filename}:{item.status}:{item.jobId ?? 'sem-job'}
      {(item.status === 'FAILED' || item.status === 'LIMIT_EXCEEDED') &&
        <button type="button" onClick={() => session.retryAnalysis(item.clientUploadId)}>Retry {item.filename}</button>}
    </div>)}
    <output data-testid="set-id">{session.analysisSetResult?.set_id ?? 'sem-set'}</output>
    {duplicateConsumer && <Mirror />}
  </>
}

function Mirror() {
  const { workspace } = useAnalysisSession()
  return <output data-testid="mirror">{workspace.analyses.map((item) => item.jobId).join(',')}</output>
}

function renderProvider(children: ReactNode, strict = false) {
  const tree = <AnalysisSessionProvider>{children}</AnalysisSessionProvider>
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree)
}

function lifecycleFetch(filesExpected: number, statuses: string[] = ['QUEUED', 'PROCESSING', 'SUCCESS']) {
  let created = 0
  const polls = new Map<string, number>()
  const contracts = new Map<string, AnalysisContract>()
  const mock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/analysis-jobs')) {
      const file = (init?.body as FormData).get('file') as File
      const jobId = `job-${++created}`
      contracts.set(jobId, result(file.name, `analysis-${created}`))
      return Promise.resolve(response({ job_id: jobId, analysis_id: jobId, status: 'QUEUED', state: 'queued' }, 202))
    }
    if (url.endsWith('/analysis-sets')) {
      const ids = JSON.parse(String(init?.body)).job_ids as string[]
      expect(ids).toHaveLength(filesExpected)
      return Promise.resolve(response(setResult(ids), 201))
    }
    const jobId = url.split('/analysis-jobs/')[1]?.split('/')[0]
    if (url.endsWith('/result')) return Promise.resolve(response(contracts.get(jobId)))
    const position = polls.get(jobId) ?? 0
    polls.set(jobId, position + 1)
    const status = statuses[Math.min(position, statuses.length - 1)]
    return Promise.resolve(response({ job_id: jobId, analysis_id: jobId, status, state: status.toLowerCase() }))
  })
  return mock
}

function posts(mock: ReturnType<typeof vi.fn>, suffix: string) {
  return mock.mock.calls.filter(([input]) => String(input).endsWith(suffix))
}

describe('lifecycle idempotente de AnalysisJob e Analysis Set', () => {
  it('usa polling adaptativo e encerra agendamento em estados terminais', () => {
    expect(pollIntervalForStatus('QUEUED')).toBe(QUEUED_POLL_INTERVAL_MS)
    expect(pollIntervalForStatus('PROCESSING')).toBe(PROCESSING_POLL_INTERVAL_MS)
    expect(pollIntervalForStatus('SUCCESS')).toBeNull()
    expect(pollIntervalForStatus('FAILED')).toBeNull()
  })
  it('um arquivo mantém uma entrada e um POST através de StrictMode, rerender e queued → processing → success', async () => {
    const fetchMock = lifecycleFetch(1)
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['pdf'], 'contrato.pdf')
    const rendered = renderProvider(<Harness files={[file]} duplicateConsumer />, true)

    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByText(/contrato\.pdf:QUEUED:job-1/)).toBeInTheDocument()
    rendered.rerender(<StrictMode><AnalysisSessionProvider><Harness files={[file]} duplicateConsumer /></AnalysisSessionProvider></StrictMode>)
    await waitFor(() => expect(screen.getByText(/contrato\.pdf:SUCCESS:job-1/)).toBeInTheDocument(), { timeout: 8_000 })

    expect(screen.getAllByTestId('upload')).toHaveLength(1)
    expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(1)
    await waitFor(() => expect(posts(fetchMock, '/analysis-sets')).toHaveLength(1))
  }, 10_000)

  it('três UploadItems, inclusive dois com conteúdo igual, criam exatamente três jobs e um set', async () => {
    const fetchMock = lifecycleFetch(3, ['SUCCESS'])
    vi.stubGlobal('fetch', fetchMock)
    const files = [
      new File(['igual'], 'contrato.pdf'),
      new File(['igual'], 'selfie.jpg'),
      new File(['logs'], 'logs.json'),
    ]
    renderProvider(<Harness files={files} />)

    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    await waitFor(() => expect(screen.getAllByText(/:SUCCESS:job-/)).toHaveLength(3))
    await waitFor(() => expect(screen.getByTestId('set-id')).not.toHaveTextContent('sem-set'))

    expect(screen.getAllByTestId('upload')).toHaveLength(3)
    expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(3)
    expect(posts(fetchMock, '/analysis-sets')).toHaveLength(1)
  })

  it('429 é terminal local e somente retry manual autoriza outro POST', async () => {
    let attempts = 0
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input)
      if (url.endsWith('/analysis-jobs')) {
        attempts += 1
        if (attempts === 1) return Promise.resolve(response({ error: { code: 'analysis_capacity_reached', message: 'Capacidade temporária atingida.' } }, 429))
        return Promise.resolve(response({ job_id: 'retry-job', status: 'QUEUED' }, 202))
      }
      return new Promise<Response>(() => undefined)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderProvider(<Harness files={[new File(['x'], 'capacity.pdf')]} />)

    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByText(/capacity\.pdf:FAILED:sem-job/)).toBeInTheDocument()
    expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(1)
    await new Promise((resolve) => window.setTimeout(resolve, 0))
    expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(1)

    await userEvent.click(screen.getByRole('button', { name: 'Retry capacity.pdf' }))
    await waitFor(() => expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(2))
  })

  it('409 na criação do set registra uma única tentativa mesmo após novas renderizações', async () => {
    const fetchMock = lifecycleFetch(1, ['SUCCESS'])
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = String(input)
      if (url.endsWith('/analysis-sets')) return Promise.resolve(response({ error: { code: 'analysis_set_not_ready', message: 'Ainda não pronto.' } }, 409))
      if (url.endsWith('/analysis-jobs')) return Promise.resolve(response({ job_id: 'job-409', status: 'QUEUED' }, 202))
      if (url.endsWith('/result')) return Promise.resolve(response(result('set.pdf', 'analysis-409')))
      return Promise.resolve(response({ job_id: 'job-409', status: 'SUCCESS' }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const rendered = renderProvider(<Harness files={[new File(['x'], 'set.pdf')]} />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    await waitFor(() => expect(screen.getByText(/set\.pdf:SUCCESS:job-409/)).toBeInTheDocument())
    await waitFor(() => expect(posts(fetchMock, '/analysis-sets')).toHaveLength(1))
    rendered.rerender(<AnalysisSessionProvider><Harness files={[]} duplicateConsumer /></AnalysisSessionProvider>)
    await new Promise((resolve) => window.setTimeout(resolve, 0))
    expect(posts(fetchMock, '/analysis-sets')).toHaveLength(1)
  })

  it('estado arbitrário em storage não restaura File nem reenvia job existente', async () => {
    localStorage.setItem('forensihash-workspace', JSON.stringify({ job_id: 'existing-job' }))
    sessionStorage.setItem('forensihash-workspace', JSON.stringify({ job_id: 'existing-job' }))
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderProvider(<Harness files={[]} />)
    await new Promise((resolve) => window.setTimeout(resolve, 0))
    expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(0)
  })

  it('unmount encerra o polling do único job compartilhado por múltiplos consumidores', async () => {
    const fetchMock = lifecycleFetch(1, ['PROCESSING'])
    vi.stubGlobal('fetch', fetchMock)
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort')
    const rendered = renderProvider(<Harness files={[new File(['x'], 'long.pdf')]} duplicateConsumer />)
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }))
    await waitFor(() => expect(screen.getByText(/long\.pdf:PROCESSING:job-1/)).toBeInTheDocument())
    expect(posts(fetchMock, '/analysis-jobs')).toHaveLength(1)
    rendered.unmount()
    expect(abortSpy).toHaveBeenCalledTimes(1)
  })
})
