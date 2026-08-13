import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ResultView } from '../pages/ResultPage'
import { analysisFixture } from './fixtures'
import type { AnalysisSetResult } from '../types/api'

function fact(id: string, type: string, value: string, provenance?: Record<string, unknown>[]) {
  return { fact_id: id, kind: 'entity', source: 'entity_resolver_v2', data: { type, normalized_value: value, confidence: .92, provenance: provenance ?? [] } }
}

describe('estabilização do pipeline de resultado', () => {
  it('apresenta tipos semânticos reais das entidades e nunca o label genérico entity', () => {
    const result = structuredClone(analysisFixture)
    result.facts = [fact('cpf', 'cpf', '52998224725'), fact('phone', 'phone', '+5521986967225'), fact('ip', 'ip', '201.10.20.30'), fact('date', 'datetime', '2023-08-16'), fact('money', 'money', '1234.56')]
    render(<ResultView result={result} />)
    const entities = screen.getByRole('heading', { name: 'Entidades' }).closest('section')!
    for (const name of ['CPF', 'Telefone', 'Endereço IP', 'Data', 'Valor']) expect(within(entities).getAllByText(name).length).toBeGreaterThan(0)
    expect(within(entities).queryByText(/^entity$/i)).not.toBeInTheDocument()
  })

  it('mostra provenance somente quando recebida', async () => {
    const result = structuredClone(analysisFixture)
    result.facts = [fact('cpf', 'cpf', '52998224725', [{ source_type: 'native_text', evidence_ref: 'ev-1', page: 3, extractor: 'entity_resolver_v2' }]), fact('money', 'money', '10.00')]
    render(<ResultView result={result} />)
    const summaries = screen.getAllByText('CPF')
    await userEvent.click(summaries[0].closest('summary')!)
    expect(screen.getByRole('region', { name: 'Proveniência 1' })).toHaveTextContent('Texto nativo')
    expect(screen.getByRole('region', { name: 'Proveniência 1' })).toHaveTextContent('ev-1')
    expect(screen.getAllByRole('region', { name: /Proveniência/ })).toHaveLength(1)
  })

  it('preserva CreateDate e ModifyDate individuais mesmo com Timeline agregada vazia', () => {
    const result = structuredClone(analysisFixture)
    result.timeline = [
      { record_type: 'event', event_id: 'create', title: 'CreateDate', timestamp: '2023-08-16T14:30:00', raw_timestamp: '2023-08-16T14:30:00', temporal_status: 'timestamped', category: 'metadata', source_type: 'metadata' },
      { record_type: 'event', event_id: 'modify', title: 'ModifyDate', timestamp: '2025-02-14T09:17:00', raw_timestamp: '2025-02-14T09:17:00', temporal_status: 'timestamped', category: 'metadata', source_type: 'metadata' },
    ]
    const analysisSet = { set_id: 'set', state: 'completed', created_at: '', finished_at: '', artifacts: [], limitations: [], correlation_result: { summary: {}, findings: [] }, timeline_result: { events: [], warnings: [], limitations: [], summary: {} } } as AnalysisSetResult
    render(<ResultView result={result} analysisSet={analysisSet} />)
    expect(screen.getByRole('button', { name: /CreateDate/ })).toHaveAttribute('data-position', '0.000000')
    expect(screen.getByRole('button', { name: /ModifyDate/ })).toHaveAttribute('data-position', '100.000000')
  })

  it('posiciona SigningTime proporcionalmente e mantém revisão sem data fora do eixo', () => {
    const result = structuredClone(analysisFixture)
    result.timeline = [
      { event_id: 'create', title: 'CreateDate', timestamp: '2023-01-01T00:00:00Z', temporal_status: 'timestamped', category: 'metadata' },
      { event_id: 'sign', title: 'Signing Time declarado', timestamp: '2024-01-01T00:00:00Z', temporal_status: 'timestamped', category: 'signature' },
      { event_id: 'modify', title: 'ModifyDate', timestamp: '2025-01-01T00:00:00Z', temporal_status: 'timestamped', category: 'metadata' },
      { event_id: 'revision', title: 'Incremental Update #1', timestamp: null, temporal_status: 'structural_only', category: 'pdf_structure' },
    ]
    render(<ResultView result={result} />)
    const signing = Number(screen.getByRole('button', { name: /Signing Time declarado/ }).getAttribute('data-position'))
    expect(signing).toBeGreaterThan(49)
    expect(signing).toBeLessThan(51)
    expect(screen.getByRole('heading', { name: 'Eventos sem data determinável' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Incremental Update #1/ })).not.toHaveAttribute('data-position')
  })

  it('separa tempo do artefato da execução ForensiHash', () => {
    const result = structuredClone(analysisFixture)
    result.timeline = [
      { event_id: 'create', title: 'CreateDate', timestamp: '2023-01-01', temporal_status: 'date_only', category: 'metadata' },
      { event_id: 'started', title: 'Análise iniciada', timestamp: '2026-01-01T10:00:00Z', temporal_status: 'timestamped', category: 'operational' },
    ]
    render(<ResultView result={result} />)
    expect(screen.getByRole('heading', { name: 'Timeline do artefato' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Execução ForensiHash' })).toBeInTheDocument()
  })

  it('mantém tabs em uma linha rolável e indica a tab ativa', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    render(<ResultView result={analysisFixture} />)
    const navigation = screen.getByRole('navigation', { name: 'Seções do resultado' })
    expect(getComputedStyle(navigation).flexWrap).toBe('nowrap')
    expect(getComputedStyle(navigation).overflowX).toBe('auto')
    const timeline = within(navigation).getByRole('link', { name: 'Timeline' })
    await userEvent.click(timeline)
    expect(timeline).toHaveAttribute('aria-current', 'location')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })
})
