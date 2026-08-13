import { StrictMode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import type { AnalysisContract } from '../types/api'
import { analysisFixture, authFixture } from './fixtures'

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

function calls(mock: ReturnType<typeof vi.fn>, method: string, suffix: string) {
  return mock.mock.calls.filter(([input, init]) => String(input).endsWith(suffix) && (init?.method ?? 'GET') === method)
}

describe('browser staging regression — app completo', () => {
  it('mantém um POST e um poller no App real através de StrictMode, rotas, resultado e refresh', async () => {
    vi.stubEnv('VITE_ANALYSIS_DIAGNOSTICS', 'true')
    let statusRequest = 0
    const contract: AnalysisContract = {
      ...analysisFixture,
      analysis_id: 'analysis-browser-1',
      file: { ...analysisFixture.file, name: 'contrato.pdf' },
    }
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return Promise.resolve(response(authFixture))
      if (url.endsWith('/capabilities')) return Promise.resolve(response({ hashes: { available: true } }))
      if (url.endsWith('/analysis-jobs') && init?.method === 'POST') {
        return Promise.resolve(response({ job_id: 'browser-job-1', analysis_id: 'browser-job-1', status: 'QUEUED', state: 'queued' }, 202))
      }
      if (url.endsWith('/analysis-jobs/browser-job-1/result')) return Promise.resolve(response(contract))
      if (url.endsWith('/analysis-jobs/browser-job-1')) {
        statusRequest += 1
        return Promise.resolve(response({
          job_id: 'browser-job-1', analysis_id: 'browser-job-1',
          status: statusRequest === 1 ? 'PROCESSING' : 'SUCCESS',
          state: statusRequest === 1 ? 'running' : 'completed',
          current_stage: statusRequest === 1 ? 'ANALYZING' : 'FINISHED',
        }))
      }
      if (url.endsWith('/analysis-sets')) return Promise.resolve(response({
        set_id: 'browser-set-1', state: 'completed', created_at: '2026-08-13T12:00:00Z',
        finished_at: '2026-08-13T12:00:01Z', artifacts: [],
        correlation_result: { summary: {}, findings: [] }, limitations: [],
      }, 201))
      throw new Error(`Request inesperado: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const diagnosticSpy = vi.spyOn(console, 'info').mockImplementation(() => undefined)
    window.history.pushState({}, '', '/app/analysis')

    const rendered = render(<StrictMode><App /></StrictMode>)
    await userEvent.upload(await screen.findByLabelText('Selecionar arquivo'), new File(['%PDF'], 'contrato.pdf', { type: 'application/pdf' }))

    expect(await screen.findByRole('heading', { name: 'contrato.pdf' })).toBeInTheDocument()
    await waitFor(() => expect(calls(fetchMock, 'GET', '/analysis-jobs/browser-job-1')).toHaveLength(2), { timeout: 5_000 })
    expect(calls(fetchMock, 'POST', '/analysis-jobs')).toHaveLength(1)
    expect(calls(fetchMock, 'POST', '/analysis-sets')).toHaveLength(1)

    await userEvent.click(screen.getAllByRole('link', { name: 'Overview' }).find((link) => link.getAttribute('href') === '/app')!)
    expect(await screen.findByText('Últimas análises')).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('link', { name: 'Nova análise' })[0])
    expect(await screen.findByLabelText('Selecionar arquivo')).toBeInTheDocument()
    expect(calls(fetchMock, 'POST', '/analysis-jobs')).toHaveLength(1)

    const lifecycleEvents = diagnosticSpy.mock.calls
      .filter(([label]) => label === '[analysis-lifecycle]')
      .map(([, details]) => details as { event: string; providerInstanceId: string; clientUploadId?: string; jobId?: string })
    const createdUploads = lifecycleEvents.filter(({ event }) => event === 'upload.created')
    const createdJobs = lifecycleEvents.filter(({ event }) => event === 'job.created')
    const createdPollers = lifecycleEvents.filter(({ event }) => event === 'poller.created')
    expect(new Set(createdUploads.map(({ clientUploadId }) => clientUploadId)).size).toBe(1)
    expect(new Set(createdJobs.map(({ jobId }) => jobId))).toEqual(new Set(['browser-job-1']))
    expect(createdPollers).toHaveLength(1)
    expect(new Set(createdJobs.map(({ providerInstanceId }) => providerInstanceId).filter(Boolean)).size).toBe(1)

    rendered.unmount()
    render(<StrictMode><App /></StrictMode>)
    await screen.findByLabelText('Selecionar arquivo')
    expect(calls(fetchMock, 'POST', '/analysis-jobs')).toHaveLength(1)
  }, 10_000)
})
