import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ResultView } from '../pages/ResultPage'
import { analysisFixture } from './fixtures'
import type { AnalysisSetResult } from '../types/api'

describe('resultado técnico', () => {
  it('apresenta cabeçalho e resumo forense apenas com identificação disponível', () => {
    const result = structuredClone(analysisFixture)
    result.file = { name: 'contrato.pdf', size_bytes: 862208, mime_type: 'application/pdf' }
    result.declared_type = '.pdf'
    result.detected_type = 'PDF'
    result.technical_structure = { pdf: { pdf_version: '1.7', page_count: 14, object_count: 183, stream_count: 42, incremental_revision_count: 2 } }
    render(<ResultView result={result} />)
    expect(screen.getByRole('heading', { name: 'contrato.pdf' })).toBeInTheDocument()
    expect(screen.getByText('ANÁLISE CONCLUÍDA')).toBeInTheDocument()
    const summary = document.querySelector<HTMLElement>('#summary')!
    expect(within(screen.getByRole('heading', { name: 'contrato.pdf' }).closest('header')!).getByText(/14 páginas/)).toBeInTheDocument()
    expect(within(summary).getByText('183')).toBeInTheDocument()
    expect(within(summary).getByText('2')).toBeInTheDocument()
    expect(within(summary).getByText('application/pdf')).toBeInTheDocument()
  })

  it('trata ausência de assinatura como informação neutra', () => {
    render(<ResultView result={analysisFixture} />)
    const summary = document.querySelector<HTMLElement>('#summary')!
    expect(within(summary).getByText(/nenhuma assinatura criptográfica incorporada foi encontrada/i)).toBeInTheDocument()
    expect(within(summary).getAllByLabelText('Informação neutra').length).toBeGreaterThan(0)
  })

  it('resume assinatura existente sem inferir validade', () => {
    const result = structuredClone(analysisFixture)
    result.signatures = [{ signer: 'Autoridade de Teste', integrity: 'valid' }]
    render(<ResultView result={result} />)
    expect(screen.getByText(/1 assinatura\(s\) incorporada\(s\) reportada\(s\)/i)).toBeInTheDocument()
    expect(screen.queryByText(/autoria comprovada|documento autêntico/i)).not.toBeInTheDocument()
  })

  it('expande finding com regra, evidências e provenance existente', async () => {
    const result = structuredClone(analysisFixture)
    result.findings = [{ finding_id: 'f-1', title: 'Datas divergentes', statement: 'Valores temporais distintos foram observados.', severity: 'warning', rule_id: 'metadata_date_rule', evidence_refs: ['fact-metadata-1'], confidence: 0.8 }]
    render(<ResultView result={result} />)
    const finding = screen.getByText('Datas divergentes').closest('details')!
    expect(finding).not.toHaveAttribute('open')
    await userEvent.click(within(finding).getByText('Datas divergentes'))
    expect(within(finding).getByText('metadata_date_rule')).toBeInTheDocument()
    await userEvent.click(within(finding).getByRole('button', { name: /evidence refs/i }))
    expect(within(finding).getByText('fact-metadata-1')).toBeInTheDocument()
  })

  it('omite valores opcionais ausentes sem inventar páginas, versão ou autoria', () => {
    render(<ResultView result={analysisFixture} />)
    const header = screen.getByRole('heading', { name: 'synthetic.txt' }).closest('header')!
    expect(within(header).queryByText(/páginas|PDF 1\.|autor/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/fraude detectada|documento falso|arquivo adulterado|autoria comprovada/i)).not.toBeInTheDocument()
  })

  it('apresenta entidades somente quando reportadas pelo contrato', () => {
    const result = structuredClone(analysisFixture)
    result.ip_addresses = [{ ip: '192.0.2.10', source: 'native_text' }]
    result.facts = [{ fact_id: 'entity-1', kind: 'entity', source: 'entity_resolver_v2', data: { type: 'email', normalized_value: 'perito@example.test', provenance: [{ source_type: 'native_text', evidence_ref: 'evidence-test' }] } }]
    render(<ResultView result={result} />)
    const summary = document.querySelector<HTMLElement>('#summary')!
    expect(within(summary).getByText('192.xxx.xxx.10')).toBeInTheDocument()
    expect(within(summary).getAllByText('E-mail').length).toBeGreaterThan(0)
    expect(within(summary).queryByText(/^entity$/i)).not.toBeInTheDocument()
  })

  it('formata hashes e copia o valor integral sem recalculá-lo', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    render(<ResultView result={analysisFixture} />)
    const hashes = document.querySelector<HTMLElement>('#identification')!
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
    expect(within(timeline).getByText('Eventos sem data determinável')).toBeInTheDocument()
    expect(within(timeline).getAllByText(/Ordem temporal inconsistente/).length).toBeGreaterThan(0)
    await userEvent.selectOptions(within(timeline).getByLabelText('Filtrar por tipo'), 'structural')
    expect(within(timeline).queryByRole('button', { name: /CreationDate/ })).not.toBeInTheDocument()
    expect(within(timeline).getByRole('button', { name: /Incremental Update #1/ })).toBeInTheDocument()
    await userEvent.click(within(timeline).getAllByText('Ver detalhes')[0])
    expect(within(timeline).getAllByText('warning-1').length).toBeGreaterThan(0)
  })

  it('mantém eventos sem data fora do eixo cronológico em viewport mobile', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    const result = structuredClone(analysisFixture)
    result.timeline = [{ record_type: 'event', event_id: 'm1', title: 'Evento', timestamp: null, temporal_status: 'structural_only', category: 'pdf_structure' }]
    render(<ResultView result={result} />)
    expect(document.querySelector('.timeline-axis')).not.toBeInTheDocument()
    expect(document.querySelector('.undated-events')).toBeInTheDocument()
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
