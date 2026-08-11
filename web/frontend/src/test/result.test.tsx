import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ResultView } from '../pages/ResultPage'
import { analysisFixture } from './fixtures'
import type { AnalysisSetResult } from '../types/api'

describe('resultado técnico', () => {
  it('formata hashes e copia o valor integral sem recalculá-lo', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    render(<ResultView result={analysisFixture} />)
    const hashes = document.querySelector<HTMLElement>('#hashes')!
    expect(within(hashes).getByRole('columnheader', { name: 'Algoritmo' })).toBeInTheDocument()
    expect(within(hashes).getByText('abc123')).toBeInTheDocument()
    expect(within(hashes).getByText('def456')).toBeInTheDocument()
    const shaRow = within(hashes).getByText('SHA256').closest('tr')!
    await userEvent.click(within(shaRow).getByRole('button', { name: 'Copiar valor' }))
    expect(writeText).toHaveBeenCalledWith('abc123')
  })

  it('preserva diferenças entre processing statuses', () => {
    render(<ResultView result={analysisFixture} />)
    expect(screen.getAllByText('Concluído').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Sem resultados').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Não executado').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Indisponível').length).toBeGreaterThan(0)
  })

  it('distingue null de coleção vazia', () => {
    render(<ResultView result={analysisFixture} />)
    expect(screen.getByText(/não executado ou indisponível; consulte as etapas/i)).toBeInTheDocument()
    expect(screen.getByText(/nenhuma assinatura digital incorporada foi identificada/i)).toBeInTheDocument()
    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })

  it('apresenta metadados e execução sem JSON cru nas seções principais', () => {
    render(<ResultView result={analysisFixture} />)
    const metadata = screen.getByRole('heading', { name: 'Metadados' }).closest('section')!
    expect(within(metadata).getByText('Documento')).toBeInTheDocument()
    expect(within(metadata).getAllByText('Synthetic')).not.toHaveLength(0)
    expect(metadata.querySelector('.json-view')).not.toBeInTheDocument()
    const execution = screen.getByRole('heading', { name: 'Execução' }).closest('section')!
    expect(within(execution).getByRole('columnheader', { name: 'Etapa' })).toBeInTheDocument()
    expect(within(execution).getByRole('columnheader', { name: 'Status' })).toBeInTheDocument()
  })

  it('mantém um único JSON técnico completo como seção secundária', async () => {
    render(<ResultView result={analysisFixture} />)
    expect(document.querySelectorAll('.json-view')).toHaveLength(1)
    await userEvent.click(screen.getByText('Expandir JSON'))
    const raw = document.querySelector('.json-view')!
    expect(raw).toHaveTextContent('"schema_version": "1.0.0"')
  })

  it('mantém o contrato imutável e as tabs superiores acessíveis', () => {
    const original = structuredClone(analysisFixture)
    render(<ResultView result={analysisFixture} />)
    const navigation = screen.getByRole('navigation', { name: 'Seções do resultado' })
    expect(navigation).toHaveClass('result-nav')
    expect(within(navigation).getAllByRole('link')).toHaveLength(12)
    expect(analysisFixture).toEqual(original)
  })

  it('mostra correlação resumida e detalhes explicáveis', async () => {
    const analysisSet: AnalysisSetResult = {
      set_id: 'set-1', state: 'completed', created_at: '2026-08-11T00:00:00Z', finished_at: '2026-08-11T00:00:01Z',
      artifacts: [], limitations: [], correlation_result: { summary: { warning: 1 }, findings: [{
        finding_id: 'finding-1', category: 'entity_mismatch', severity: 'warning',
        summary: 'Telefone divergente', description: 'Valores diferentes no mesmo papel semântico.',
        rule_id: 'entity_mismatch', source_engine: 'correlation_engine_v2', confidence: 0.9,
        evidence: [{ filename: 'a.pdf', page: 2 }, { filename: 'b.pdf', page: 4 }],
        entities: [], limitations: [], metadata: { semantic_role: 'customer' },
      }] },
    }
    render(<ResultView result={analysisFixture} analysisSet={analysisSet} />)
    expect(screen.getByRole('heading', { name: 'Telefone divergente' })).toBeInTheDocument()
    await userEvent.click(screen.getByText('Ver detalhes'))
    expect(screen.getAllByText('entity_mismatch').length).toBeGreaterThan(0)
    expect(screen.getByText('a.pdf')).toBeInTheDocument()
  })

  it('mostra eventos temporais e estruturais, detalhes e filtros', async () => {
    const result = structuredClone(analysisFixture)
    result.timeline = [
      { record_type: 'event', event_id: 'time-1', title: 'CreationDate', description: 'Data registrada.', timestamp: '2023-01-26T15:50:12-03:00', raw_timestamp: '2023:01:26 15:50:12-03:00', timezone_status: 'explicit', precision: 'second', category: 'metadata', temporal_status: 'timestamped', filename: 'contrato.pdf', source_type: 'metadata' },
      { record_type: 'event', event_id: 'struct-1', title: 'Incremental Update #1', description: 'Revisão estrutural.', timestamp: null, category: 'pdf_structure', temporal_status: 'structural_only', structural_sequence: 2, offset: 218073, filename: 'contrato.pdf', source_type: 'pdf_structure' },
      { record_type: 'warning', warning_id: 'warning-1', title: 'Ordem temporal inconsistente', description: 'ModifyDate é anterior a CreationDate.' },
    ]
    render(<ResultView result={result} />)
    const timeline = screen.getByRole('heading', { name: 'Timeline' }).closest('section')!
    expect(within(timeline).getAllByText('CreationDate').length).toBeGreaterThan(0)
    expect(within(timeline).getAllByText('Incremental Update #1').length).toBeGreaterThan(0)
    expect(within(timeline).getByText('Data não determinada')).toBeInTheDocument()
    expect(within(timeline).getAllByText(/Ordem temporal inconsistente/).length).toBeGreaterThan(0)
    await userEvent.selectOptions(within(timeline).getByLabelText('Filtrar por tipo'), 'structural')
    const eventList = timeline.querySelector<HTMLElement>('.timeline-list')!
    expect(within(eventList).queryByText('CreationDate')).not.toBeInTheDocument()
    expect(within(eventList).getAllByText('Incremental Update #1').length).toBeGreaterThan(0)
    await userEvent.click(within(timeline).getAllByText('Ver detalhes')[0])
    expect(within(timeline).getAllByText('warning-1').length).toBeGreaterThan(0)
  })

  it('renderiza a Timeline em viewport mobile sem linha horizontal obrigatória', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    const result = structuredClone(analysisFixture)
    result.timeline = [{ record_type: 'event', event_id: 'm1', title: 'Evento', timestamp: null, temporal_status: 'structural_only', category: 'pdf_structure' }]
    render(<ResultView result={result} />)
    expect(document.querySelector('.timeline-list')).toBeInTheDocument()
    expect(document.querySelector('.timeline-view')).toBeInTheDocument()
  })

  it('apresenta inspeção de archive com warning factual e árvore expansível', async () => {
    const result = structuredClone(analysisFixture)
    result.technical_structure.archive = {
      parser_id: 'archive_zip_v1', detected_type: 'ZIP', state: 'partial',
      metadata: { archive_type: 'ZIP', total_entries: 2, directory_entries: 0 },
      warnings: [{ code: 'executable_content_detected', message: 'Conteúdo executável detectado no arquivo compactado.' }],
      embedded_artifacts: [
        { embedded_artifact_ref: 'entry-1', filename: 'contrato.pdf', detected_type: 'PDF', sha256: 'abc' },
        { embedded_artifact_ref: 'entry-2', filename: 'setup.exe', detected_type: 'PE', inspection_flags: ['executable_content_detected'] },
      ],
    }
    render(<ResultView result={result} />)
    const section = screen.getByRole('heading', { name: 'Archive Inspection' }).closest('section')!
    expect(within(section).getByText('Conteúdo executável detectado no arquivo compactado.')).toBeInTheDocument()
    expect(within(section).queryByText(/malware/i)).not.toBeInTheDocument()
    await userEvent.click(within(section).getByText('Explorar conteúdo'))
    await userEvent.click(within(section).getByRole('button', { name: /entries/i }))
    await userEvent.click(within(section).getAllByRole('button', { name: /entrie/i })[2])
    expect(within(section).getAllByText(/setup.exe/i).length).toBeGreaterThan(0)
  })

  it('não oferece abertura ou execução automática de entries', async () => {
    const result = structuredClone(analysisFixture)
    result.technical_structure.archive = {
      metadata: { archive_type: 'ZIP', total_entries: 1 }, warnings: [],
      embedded_artifacts: [{ embedded_artifact_ref: 'entry', filename: 'install.js', inspection_flags: ['script_content_detected'] }],
    }
    render(<ResultView result={result} />)
    const section = screen.getByRole('heading', { name: 'Archive Inspection' }).closest('section')!
    expect(within(section).queryByRole('link', { name: /abrir|executar/i })).not.toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: /executar/i })).not.toBeInTheDocument()
  })

  it('mantém a árvore de archive em layout responsivo', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    const result = structuredClone(analysisFixture)
    result.technical_structure.archive = { metadata: { archive_type: 'ZIP', total_entries: 0 }, warnings: [], embedded_artifacts: [] }
    render(<ResultView result={result} />)
    expect(document.querySelector('.archive-inspection')).toBeInTheDocument()
    expect(document.querySelector('.archive-summary')).toBeInTheDocument()
  })
})
