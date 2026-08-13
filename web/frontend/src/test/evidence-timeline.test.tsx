import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { EvidenceTimeline, positionTimelineEvents, timestampMilliseconds } from '../components/EvidenceTimeline'

const event = (id: string, timestamp: string | null, extra: Record<string, unknown> = {}) => ({ event_id: id, title: id, timestamp, raw_timestamp: timestamp, temporal_status: timestamp ? 'timestamped' : 'structural_only', ...extra })

describe('timeline horizontal proporcional', () => {
  it('posiciona início, ponto proporcional e fim na escala temporal real', () => {
    const values = [event('início', '2021-01-01T00:00:00Z'), event('próximo', '2021-01-02T00:00:00Z'), event('meio', '2023-01-01T00:00:00Z'), event('fim', '2025-01-01T00:00:00Z')]
    const positions = positionTimelineEvents(values)
    expect(positions[0].position).toBe(0)
    expect(positions.at(-1)?.position).toBe(100)
    expect(positions[1].position).toBeLessThan(0.1)
    expect(positions[2].position).toBeCloseTo(50, 0)
    expect(positions[3].position - positions[2].position).toBeGreaterThan(positions[1].position - positions[0].position)
  })

  it('mantém timestamps iguais na mesma posição e usa lanes distintas', () => {
    const values = positionTimelineEvents([event('a', '2025-01-01T00:00:00Z'), event('b', '2025-01-01T00:00:00Z')])
    expect(values[0].position).toBe(50)
    expect(values[1].position).toBe(50)
    expect(values[0].lane).not.toBe(values[1].lane)
  })

  it('centraliza um único evento sem divisão por zero', () => {
    expect(positionTimelineEvents([event('único', '2025-01-01T00:00:00Z')])[0].position).toBe(50)
  })

  it('não atribui timestamp a evento estrutural ou timestamp inválido', () => {
    expect(timestampMilliseconds(event('estrutural', null))).toBeNull()
    expect(timestampMilliseconds(event('inválido', 'não-é-data'))).toBeNull()
  })

  it('mantém escala global quando eventos visíveis são filtrados', () => {
    const all = [event('a', '2020-01-01T00:00:00Z'), event('b', '2022-01-01T00:00:00Z'), event('c', '2024-01-01T00:00:00Z')]
    const filtered = positionTimelineEvents([all[1]], all)
    expect(filtered[0].position).toBeCloseTo(50, 0)
  })

  it('abre detalhes acessíveis e mostra apenas provenance existente', async () => {
    const values = [event('ModifyDate', '2025-02-14T09:17:03-03:00', { filename: 'contrato.pdf', source_type: 'metadata', field_path: 'xmp:ModifyDate', evidence_ref: 'ev-1' })]
    render(<EvidenceTimeline visibleEvents={values} scaleEvents={values} />)
    await userEvent.click(screen.getByRole('button', { name: /ModifyDate/ }))
    const panel = screen.getByRole('complementary', { name: /Detalhes do evento ModifyDate/ })
    expect(within(panel).getAllByText('contrato.pdf').length).toBeGreaterThan(0)
    expect(within(panel).getAllByText('metadata').length).toBeGreaterThan(0)
    expect(within(panel).getAllByText('xmp:ModifyDate').length).toBeGreaterThan(0)
    expect(within(panel).queryByText('Engine')).not.toBeInTheDocument()
  })

  it('mantém eventos sem timestamp fora da linha cronológica e clicáveis', async () => {
    const structural = event('Revisão incremental #2', null, { source_type: 'pdf_structure' })
    render(<EvidenceTimeline visibleEvents={[structural]} scaleEvents={[structural]} />)
    expect(document.querySelector('.timeline-axis')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Revisão incremental #2/ }))
    expect(screen.getByText('Data não determinável pelo contrato.')).toBeInTheDocument()
  })
})
